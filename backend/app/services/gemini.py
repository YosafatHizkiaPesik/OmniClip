"""
Penajaman hasil klip dengan Google Gemini.

Tiga perbedaan mendasar dari versi lama:

1. Gemini TIDAK PERNAH mengeluarkan angka detik. Ia hanya memilih dari kandidat
   yang sudah dihasilkan mesin heuristik, dan menggeser batas lewat INDEKS
   KALIMAT. LLM tidak andal berhitung atas daftar timestamp panjang — itu akar
   penyebab klip di luar rentang video pada sistem lama.

2. Transkrip dikirim utuh, bukan dipotong 180 baris pertama. Pemotongan itulah
   sebabnya "klip" dari paruh akhir video pasti karangan.

3. Output memakai response_schema, bukan regex pengupas pagar ```json.

Kegagalan Gemini tidak pernah menjatuhkan pipeline: hasil heuristik tetap valid.
"""

import json
import logging
import time
from typing import Optional

from .clipmodel import normalize_hashtags
from .heuristics import Candidate, make_hook_text
from .transcript import Sentence

log = logging.getLogger("omniclip.gemini")

SYSTEM_ID = """Anda editor konten video berbahasa Indonesia yang berpengalaman memilih
potongan untuk Shorts/Reels/TikTok.

Anda diberi transkrip lengkap sebuah video beserta daftar KANDIDAT potongan yang
sudah dihitung sistem. Tugas Anda memilih dan merapikan kandidat itu — BUKAN
membuat potongan baru.

YANG PALING PENTING: setiap potongan harus berisi SATU GAGASAN UTUH.

Kandidat yang diberikan sistem dihitung dari panjang dan energi bicara, bukan
dari isi. Akibatnya kandidat sering berhenti tepat setelah pertanyaan diajukan
atau tepat sebelum inti jawabannya keluar. Tugas Anda memperbaiki itu: baca
transkrip di sekitar kandidat, lalu PERLUAS end_sentence sampai gagasannya
selesai — pertanyaan beserta jawabannya, cerita beserta penutupnya, klaim
beserta alasannya.

Tolak kandidat yang intinya tidak selesai dan tidak bisa diselesaikan dalam
batas durasi. Lebih baik mengembalikan 4 potongan utuh daripada 8 potongan
yang menggantung.

Anda TIDAK terikat pada daftar kandidat. Bila membaca transkrip menunjukkan ada
bagian menarik yang tidak terdaftar, ambil saja: isi candidate_id dengan -1 lalu
tentukan start_sentence dan end_sentence sendiri. Kandidat sistem hanya titik
awal — Andalah yang membaca isinya.

Aturan lain:
- Rentang ditentukan lewat start_sentence/end_sentence, yaitu NOMOR KALIMAT
  yang ada di transkrip di atas. Jangan pernah menulis angka detik.
- Untuk kandidat dari daftar: start_sentence boleh mundur sedikit untuk
  menangkap konteks pembuka; end_sentence boleh maju jauh untuk menangkap
  penutup gagasan.
- hook_text harus SETIA pada isi klip. Dilarang menjanjikan sesuatu yang tidak
  ada di dalam potongan tersebut.
- reason maksimal 20 kata, bahasa Indonesia, sebutkan gagasan apa yang dibahas.
- score adalah 0-100 dan harus mencerminkan penilaian jujur; potongan biasa
  memang pantas mendapat nilai sedang."""


def _build_schema():
    from google.genai import types

    return types.Schema(
        type=types.Type.OBJECT,
        required=["selections"],
        properties={
            "selections": types.Schema(
                type=types.Type.ARRAY,
                items=types.Schema(
                    type=types.Type.OBJECT,
                    required=["candidate_id", "start_sentence", "end_sentence",
                              "score", "reason", "hook_text", "suggested_title"],
                    properties={
                        "candidate_id": types.Schema(type=types.Type.INTEGER),
                        "start_sentence": types.Schema(type=types.Type.INTEGER),
                        "end_sentence": types.Schema(type=types.Type.INTEGER),
                        "score": types.Schema(type=types.Type.NUMBER),
                        "reason": types.Schema(type=types.Type.STRING),
                        "hook_text": types.Schema(type=types.Type.STRING),
                        "suggested_title": types.Schema(type=types.Type.STRING),
                        "hashtags": types.Schema(
                            type=types.Type.ARRAY,
                            items=types.Schema(type=types.Type.STRING),
                        ),
                    },
                ),
            )
        },
    )


def _format_transcript(sentences: list[Sentence], max_chars: int) -> str:
    """Transkrip padat: satu baris per kalimat, diberi indeks dan waktu."""
    lines = []
    total = 0
    for idx, s in enumerate(sentences):
        mm, ss = divmod(int(s["s"]), 60)
        line = f"[{idx}] {mm}:{ss:02d} {s['text']}"
        total += len(line) + 1
        if total > max_chars:
            lines.append(f"... (transkrip dipotong pada kalimat {idx} karena terlalu panjang)")
            break
        lines.append(line)
    return "\n".join(lines)


def _format_candidates(candidates: list[Candidate], sentences: list[Sentence]) -> str:
    out = []
    for cid, c in enumerate(candidates):
        i, j = c.sentence_span
        m0, s0 = divmod(int(c.start), 60)
        m1, s1 = divmod(int(c.end), 60)
        out.append(
            f"candidate_id={cid} | kalimat {i}-{j - 1} | {m0}:{s0:02d}-{m1}:{s1:02d} "
            f"({c.duration:.0f} detik) | skor_sistem={c.score:.2f}\n"
            f"  isi: {c.text[:400]}"
        )
    return "\n\n".join(out)


def refine_candidates(
    *,
    sentences: list[Sentence],
    candidates: list[Candidate],
    video_title: str,
    api_key: str,
    models: list[str],
    max_clips: int = 8,
    max_chars: int = 350000,
    shortlist: int = 25,
    max_seconds: float = 80.0,
    model_override: Optional[str] = None,
) -> tuple[list[Candidate], Optional[str]]:
    """
    Meminta Gemini memilih dan merapikan kandidat.

    Mengembalikan (kandidat_hasil, nama_model). Melempar exception bila semua
    model gagal — pemanggil menangkapnya dan memakai hasil heuristik.
    """
    from google import genai
    from google.genai import types

    pool = candidates[:shortlist]
    client = genai.Client(api_key=api_key)
    if model_override:
        # Model pilihan pengguna dicoba lebih dulu; sisanya tetap jadi cadangan
        # bila model itu kebetulan sedang penuh atau sudah dipensiunkan.
        models = [model_override] + [m for m in models if m != model_override]

    prompt = (
        f"Judul video: {video_title}\n\n"
        f"=== TRANSKRIP ({len(sentences)} kalimat) ===\n"
        f"{_format_transcript(sentences, max_chars)}\n\n"
        f"=== KANDIDAT POTONGAN ===\n{_format_candidates(pool, sentences)}\n\n"
        f"Pilih maksimal {max_clips} potongan terbaik dan urutkan dari yang paling kuat.\n"
        f"Batas durasi satu potongan: {max_seconds:.0f} detik. Perluas end_sentence "
        f"sampai gagasannya utuh selama masih di dalam batas itu."
    )

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=_build_schema(),
        temperature=0.4,
        # Anggaran keluaran mengikuti jumlah klip yang diminta. Nilai tetap 8192
        # cukup untuk delapan klip, tapi dengan sembilan belas — masing-masing
        # membawa alasan, judul, dan tagar — JSON-nya terpotong di tengah dan
        # json.loads gagal. Model membalas 200 OK, jadi kegagalannya terlihat
        # seperti "model menolak" padahal ia kehabisan ruang menulis. Model seri
        # 3 juga memakai anggaran yang sama untuk penalaran internalnya.
        max_output_tokens=min(32768, 6144 + max_clips * 800),
        system_instruction=SYSTEM_ID,
    )

    last_error: Optional[Exception] = None
    failures: list[str] = []
    for model_name in models:
        for attempt in range(2):
            try:
                resp = client.models.generate_content(
                    model=model_name, contents=prompt, config=config
                )
                text = resp.text or ""
                try:
                    data = json.loads(text)
                except json.JSONDecodeError as e:
                    # Alasan berhenti dan panjang teks membedakan "model salah
                    # format" dari "model kehabisan token" — dua kegagalan yang
                    # tanpa ini terlihat sama persis di log.
                    reason = getattr(
                        (resp.candidates or [None])[0], "finish_reason", None)
                    raise ValueError(
                        f"JSON tidak lengkap ({len(text)} karakter, "
                        f"finish_reason={reason}): {e}") from e
                refined = _apply_selections(data, pool, sentences, max_clips,
                                            max_seconds=max_seconds)
                if refined:
                    log.info("Gemini %s memilih %d klip", model_name, len(refined))
                    return refined, model_name
                raise ValueError("Gemini tidak mengembalikan satupun kandidat yang dikenal")
            except Exception as e:
                last_error = e
                failures.append(f"{model_name}: {str(e)[:160]}")
                log.warning("Gemini %s gagal (percobaan %d): %s",
                            model_name, attempt + 1, str(e)[:200])
                msg = str(e)
                if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                    if attempt == 0:
                        time.sleep(3)
                        continue
                    break            # kuota habis -> model berikutnya
                if "404" in msg or "NOT_FOUND" in msg:
                    break            # model tidak ada -> model berikutnya
                if attempt == 0:
                    config.temperature = 0.1
                    continue
                break

    # Seluruh riwayat kegagalan dilaporkan, bukan hanya yang terakhir. Model
    # terakhir dalam rantai biasanya yang paling tidak menarik penyebabnya —
    # kegagalan model PERTAMA-lah yang menjelaskan apa yang sebenarnya salah.
    raise RuntimeError("Semua model Gemini gagal — " + " | ".join(failures)
                       or f"Semua model Gemini gagal: {last_error}")


def _apply_selections(data: dict, pool: list[Candidate],
                      sentences: list[Sentence], max_clips: int,
                      *, max_seconds: float = 80.0) -> list[Candidate]:
    """
    Menerapkan pilihan model ke kandidat nyata.

    Entri dengan candidate_id tak dikenal dibuang, dan geseran batas hanya
    diterima bila indeks kalimatnya masuk akal. Dengan begitu model secara
    struktural tidak bisa menghasilkan klip di luar rentang video.
    """
    out: list[Candidate] = []
    seen: set[int] = set()
    seen_free: set[tuple] = set()

    for sel in (data.get("selections") or [])[: max_clips * 2]:
        try:
            cid = int(sel.get("candidate_id"))
        except (TypeError, ValueError):
            continue
        if cid >= len(pool) or cid < -1:
            continue
        if cid >= 0:
            if cid in seen:
                continue
            seen.add(cid)

        free = cid == -1
        if free:
            si_raw, sj_raw = sel.get("start_sentence"), sel.get("end_sentence")
            if not (isinstance(si_raw, int) and isinstance(sj_raw, int)):
                continue
            if not (0 <= si_raw < sj_raw <= len(sentences)):
                continue
            span_start = sentences[si_raw]["s"]
            span_end = sentences[sj_raw - 1]["e"]
            if not (8.0 <= span_end - span_start <= max_seconds):
                continue
            # Rentang bebas tetap tidak bisa berhalusinasi: indeksnya divalidasi
            # terhadap daftar kalimat nyata, dan waktunya diambil dari kalimat
            # itu — bukan dari angka yang ditulis model.
            base = Candidate(
                start=span_start, end=span_end, score=0.5,
                breakdown={"gemini_free": 1.0}, sentence_span=(si_raw, sj_raw),
                reason_keys=[], text=" ".join(s["text"] for s in sentences[si_raw:sj_raw]),
            )
            pool_key = ("free", si_raw, sj_raw)
            if pool_key in seen_free:
                continue
            seen_free.add(pool_key)
        else:
            base = pool[cid]
        i, j = base.sentence_span

        si, sj = sel.get("start_sentence"), sel.get("end_sentence")
        if (not free and isinstance(si, int) and isinstance(sj, int)
                and 0 <= si < sj <= len(sentences)):
            # Awal boleh bergeser sedikit saja — menggeser awal jauh berarti
            # klip lain yang dipilih, bukan kandidat ini. Akhir boleh maju jauh,
            # karena justru di situlah penutup gagasan biasanya berada; yang
            # membatasinya adalah durasi, bukan jumlah kalimat.
            if abs(si - i) <= 8 and sj > si and (sj - j) <= 60 and (j - sj) <= 8:
                cand_start = sentences[si]["s"]
                cand_end = sentences[sj - 1]["e"]
                if cand_end - cand_start <= max_seconds:
                    i, j = si, sj

        start = sentences[i]["s"]
        end = sentences[j - 1]["e"]
        if end - start < 8.0 or end - start > max_seconds:
            continue

        score = sel.get("score")
        try:
            score_norm = max(0.0, min(1.0, float(score) / 100.0))
        except (TypeError, ValueError):
            score_norm = base.score

        reason = (sel.get("reason") or "").strip()
        hook = (sel.get("hook_text") or "").strip() or make_hook_text(sentences, i, j)

        cand = Candidate(
            start=start, end=end, score=score_norm,
            breakdown={**base.breakdown, "gemini": round(score_norm, 4)},
            sentence_span=(i, j),
            reason_keys=list(base.reason_keys),
            hook_text=hook.upper()[:70],
            text=" ".join(s["text"] for s in sentences[i:j]),
        )
        # Alasan tulisan model disimpan terpisah dari reason_keys yang terukur,
        # supaya UI bisa membedakan mana yang dihitung dan mana yang ditulis AI.
        cand.gemini_reason = reason[:200]           # type: ignore[attr-defined]
        cand.suggested_title = (sel.get("suggested_title") or "").strip()[:120]  # type: ignore[attr-defined]
        cand.hashtags = [h for h in (sel.get("hashtags") or []) if isinstance(h, str)][:8]  # type: ignore[attr-defined]
        out.append(cand)
        if len(out) >= max_clips:
            break

    return out


def rewrite_titles(
    *,
    clips: list[dict],
    video_title: str,
    api_key: str,
    models: list[str],
    model_override: Optional[str] = None,
) -> tuple[dict[int, dict], Optional[str]]:
    """
    Menulis ulang judul dan tagar untuk klip yang sudah ada.

    Terpisah dari `refine_candidates` karena pertanyaannya berbeda. Yang di sana
    adalah "potongan mana yang layak"; yang di sini "bagaimana potongan ini
    dijual". Klip yang tidak terpilih Gemini pada analisis awal keluar dengan
    judul heuristik — sebuah kalimat dari klipnya sendiri: akurat, dan sama
    sekali tidak memancing. Ini yang membetulkannya, tanpa menganalisis ulang
    apa pun.

    Mengembalikan ({indeks_klip: {title, hashtags}}, nama_model).
    """
    from google import genai
    from google.genai import types

    schema = types.Schema(
        type=types.Type.OBJECT,
        required=["clips"],
        properties={
            "clips": types.Schema(
                type=types.Type.ARRAY,
                items=types.Schema(
                    type=types.Type.OBJECT,
                    required=["index", "title", "hashtags"],
                    properties={
                        "index": types.Schema(type=types.Type.INTEGER),
                        "title": types.Schema(type=types.Type.STRING),
                        "hashtags": types.Schema(
                            type=types.Type.ARRAY,
                            items=types.Schema(type=types.Type.STRING)),
                    },
                ),
            )
        },
    )

    bagian = []
    for c in clips:
        teks = " ".join((l.get("text") or "") for l in (c.get("subtitles") or []))
        bagian.append(f"[{c['index']}] {teks[:1500]}")

    prompt = (
        f"Judul video sumber: {video_title}\n\n"
        "Untuk TIAP potongan di bawah, tulis satu judul pendek berbahasa Indonesia "
        "untuk video vertikal, dan 5-8 tagar.\n\n"
        "Aturan judul:\n"
        "- Maksimal 60 karakter, tanpa tanda kutip, tanpa nama kanal.\n"
        "- Harus memancing rasa penasaran TAPI tidak boleh menjanjikan apa pun "
        "yang tidak ada di potongannya. Judul yang berlebihan membuat penonton "
        "keluar di detik kelima, dan itu menurunkan videonya.\n"
        "- Sebut hal paling khas dari potongan itu: angka, nama, klaim, atau "
        "pertentangan yang benar-benar diucapkan.\n"
        "- Hindari pembuka basa-basi seperti 'Ternyata', 'Inilah', 'Wajib tahu'.\n\n"
        "Aturan tagar:\n"
        "- Huruf kecil, tanpa spasi, diawali #.\n"
        "- Sebutkan bidang bahasannya (#finansial, #komedi, #pasangan, dan "
        "sejenisnya), bukan kata kerja percakapan.\n"
        "- Hanya tagar yang benar-benar nyambung dengan isi potongan.\n\n"
        "=== POTONGAN ===\n" + "\n\n".join(bagian)
    )

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
        temperature=0.75,      # judul butuh keberanian, bukan ketepatan
        max_output_tokens=max(2048, 260 * len(clips)),
        system_instruction=SYSTEM_ID,
    )

    # Batas waktu WAJIB ada di sini.
    #
    # Tanpa itu satu panggilan yang tidak pernah dijawab menggantung selamanya:
    # job-nya berhenti di 20% tanpa pesan galat, lajur `net` ikut tertahan, dan
    # satu-satunya cara keluar adalah menghidupkan ulang server. Terlihat sendiri
    # saat menulis fungsi ini — job pertama menggantung lebih dari lima menit.
    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=90_000),   # milidetik
    )
    if model_override:
        models = [model_override] + [m for m in models if m != model_override]

    last: Optional[Exception] = None
    for model in models:
        try:
            resp = client.models.generate_content(
                model=model, contents=prompt, config=config)
            data = json.loads(resp.text)
        except Exception as e:      # model penuh, dipensiunkan, atau JSON rusak
            last = e
            log.warning("Menulis ulang judul gagal di %s: %s", model, e)
            continue

        out: dict[int, dict] = {}
        for row in (data.get("clips") or []):
            try:
                idx = int(row["index"])
            except (KeyError, TypeError, ValueError):
                continue
            judul = str(row.get("title") or "").strip().strip('"')[:100]
            tags = normalize_hashtags(row.get("hashtags") or [])
            if judul:
                out[idx] = {"title": judul, "hashtags": tags}
        if out:
            return out, model

    if last:
        raise last
    raise RuntimeError("Gemini tidak mengembalikan judul apa pun.")
