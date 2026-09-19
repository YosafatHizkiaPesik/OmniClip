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
from .peringkat_model import catat_gagal, tanpa_kuota
from .transcript import Sentence

log = logging.getLogger("omniclip.gemini")

SYSTEM_ID = """Anda editor konten video berbahasa Indonesia yang berpengalaman memilih
potongan untuk Shorts/Reels/TikTok.

Anda diberi transkrip lengkap sebuah video beserta daftar KANDIDAT potongan yang
sudah dihitung sistem. Tugas Anda memilih potongan terbaik dan menentukan batas
yang benar untuk masing-masing.

YANG PALING PENTING: setiap potongan harus bisa dimengerti oleh PENONTON BARU.

Bayangkan orang yang sedang menggulir TikTok dan belum pernah melihat video ini.
Ia tidak tahu apa yang dibicarakan sebelum potongan dimulai. Maka:

1. AWAL. Kalimat pertama tidak boleh bergantung pada sesuatu yang diucapkan
   sebelumnya. Tanda-tanda awal yang menggantung: dibuka dengan "setelah itu",
   "terus", "makanya", "nah itu", "jadi", kata ganti ("dia", "itu", "gitu")
   yang merujuk ke hal sebelumnya, jawaban atas pertanyaan yang belum diajukan,
   atau lanjutan dari sebuah cerita/aturan/istilah yang dijelaskan lebih awal.
   Bila begitu, MUNDURKAN start_sentence ke tempat topik, cerita, atau
   pertanyaan itu dimulai — sejauh apa pun perlu.

2. AKHIR. Potongan harus sampai ke puncaknya: jawaban dari pertanyaannya,
   punchline/tawa dari leluconnya, kesimpulan dari ceritanya. Jangan berhenti
   di tengah daftar, di tengah penjelasan, atau tepat sebelum inti keluar.
   Bila perlu, MAJUKAN end_sentence.

3. PANJANG adalah hasil, bukan target. Kebanyakan gagasan utuh dalam obrolan
   atau podcast butuh 40-100 detik. Di bawah 25 detik hanya pantas bila satu
   lelucon atau pernyataan memang lengkap sendirian. Kandidat sistem SERING
   TERLALU PENDEK karena dihitung dari pola bicara, bukan dari isi — jangan
   meniru panjangnya.

4. PADAT. Setelah awal dan akhirnya benar, potongan terbaik adalah yang
   PALING SINGKAT yang masih lolos uji penonton baru. Mulai di kalimat yang
   memperkenalkan topiknya, bukan di basa-basi sebelumnya; berhenti begitu
   puncaknya keluar, bukan di obrolan sesudahnya. Satu pembahasan panjang
   yang berisi dua momen kuat lebih baik dijadikan dua potongan.

Sebelum menentukan nomor kalimat, isi kolom "konteks": apa yang harus diketahui
penonton agar potongan ini masuk akal, dan di kalimat nomor berapa hal itu
diucapkan. Lalu tentukan start_sentence dari situ.

Anda TIDAK terikat pada daftar kandidat. Kandidat hanya petunjuk tempat yang
mungkin menarik. Bila ada bagian lain yang lebih kuat, ambil: isi candidate_id
dengan -1 lalu tentukan start_sentence dan end_sentence sendiri. Bila beberapa
kandidat sebenarnya satu pembahasan yang sama, jadikan satu potongan.

Tolak bagian yang intinya tidak bisa dibuat utuh. Tapi video panjang hampir
selalu punya banyak momen yang layak — telusuri SELURUH transkrip, dari awal
sampai akhir, dan penuhi jumlah yang diminta bila momennya memang ada.

Aturan lain:
- Rentang ditentukan lewat start_sentence (kalimat pertama yang masuk) dan
  end_sentence (kalimat TERAKHIR yang masuk), yaitu NOMOR KALIMAT di
  transkrip — sama seperti "kalimat 114-119" pada daftar kandidat. Jangan
  pernah menulis angka detik.
- Dua potongan tidak boleh berisi bagian yang sama.
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
                    required=["konteks", "candidate_id", "start_sentence", "end_sentence",
                              "score", "reason", "hook_text", "suggested_title"],
                    # Urutan ini disengaja: model menulis dari atas ke bawah,
                    # jadi "konteks" — apa yang perlu diketahui penonton dan di
                    # kalimat mana itu diucapkan — ditulis SEBELUM nomor
                    # kalimat awal. Tanpa itu, awal klip ditentukan lebih dulu
                    # dan alasannya menyusul.
                    property_ordering=["konteks", "candidate_id", "start_sentence",
                                       "end_sentence", "score", "reason", "hook_text",
                                       "suggested_title", "hashtags"],
                    properties={
                        "konteks": types.Schema(type=types.Type.STRING),
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


# Batas satu permintaan (milidetik) dan seluruh rangkaian percobaan (detik).
# Jawaban normal untuk transkrip sejam datang dalam 60-100 detik.
PER_PANGGILAN_MS = 150_000
BATAS_TOTAL_DETIK = 360


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
    kabar=None,
    batal=None,
) -> tuple[list[Candidate], Optional[str]]:
    """
    Meminta Gemini memilih dan merapikan kandidat.

    Mengembalikan (kandidat_hasil, nama_model). Melempar exception bila semua
    model gagal — pemanggil menangkapnya dan memakai hasil heuristik.

    `kabar(pesan)` dipanggil di setiap percobaan supaya yang menunggu tahu
    model mana yang sedang ditanya dan kenapa pindah; `batal()` dipanggil di
    antara percobaan dan boleh melempar untuk menghentikannya.
    """
    from google import genai
    from google.genai import types

    pool = candidates[:shortlist]
    # Batas waktu per permintaan. Dulu tidak ada sama sekali: Gemini menjawab
    # "503 sedang sibuk" untuk dua model, lalu satu permintaan berikutnya tidak
    # pernah dijawab — dan "Cari ulang" menunggu satu setengah jam tanpa akhir.
    client = genai.Client(api_key=api_key,
                          http_options=types.HttpOptions(timeout=PER_PANGGILAN_MS))
    tenggat = time.monotonic() + BATAS_TOTAL_DETIK
    if model_override:
        # Model pilihan pengguna dicoba lebih dulu; sisanya tetap jadi cadangan
        # bila model itu kebetulan sedang penuh atau sudah dipensiunkan.
        models = [model_override] + [m for m in models if m != model_override]

    prompt = (
        f"Judul video: {video_title}\n\n"
        f"=== TRANSKRIP ({len(sentences)} kalimat) ===\n"
        f"{_format_transcript(sentences, max_chars)}\n\n"
        f"=== KANDIDAT POTONGAN ===\n{_format_candidates(pool, sentences)}\n\n"
        f"Pilih {max_clips} potongan terbaik (boleh kurang hanya bila videonya "
        f"memang tidak punya cukup momen yang layak) dan urutkan dari yang paling kuat.\n"
        f"Batas durasi satu potongan: {max_seconds:.0f} detik. Pastikan setiap "
        f"potongan lolos uji penonton baru: awalnya bisa dimengerti tanpa "
        f"konteks sebelumnya, dan akhirnya sampai ke puncak gagasannya."
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
    for urutan, model_name in enumerate(models):
        if tanpa_kuota(model_name) and urutan + 1 < len(models):
            continue
        for attempt in range(2):
            if batal is not None:
                batal()
            sisa = tenggat - time.monotonic()
            if sisa <= 5:
                failures.append(f"batas waktu {BATAS_TOTAL_DETIK} dtk habis")
                break
            if kabar is not None:
                kabar(f"Menunggu jawaban {model_name}"
                      + (f" (percobaan {attempt + 1})" if attempt else "") + "…")
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
                berikut = models[urutan + 1] if urutan + 1 < len(models) else None
                if catat_gagal(model_name, e):
                    # Kuota nol atau model sudah ditutup: mengulang tidak
                    # akan pernah berhasil. Pindah model tanpa menunggu.
                    if kabar is not None and berikut:
                        kabar(f"{model_name} tidak tersedia untuk kunci ini — mencoba {berikut}…")
                    break
                sibuk = any(x in msg for x in ("503", "UNAVAILABLE", "overloaded",
                                               "high demand", "timed out", "Timeout",
                                               "timeout", "504", "DEADLINE"))
                if sibuk:
                    # Model yang sedang penuh jarang pulih dalam beberapa detik;
                    # mengulanginya hanya menambah waktu tunggu. Pindah model.
                    if kabar is not None:
                        kabar(f"{model_name} sedang sibuk"
                              + (f" — mencoba {berikut}…" if berikut else "."))
                    break
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

        # end_sentence INKLUSIF — nomor kalimat terakhir yang masuk, sama
        # dengan cara daftar kandidat menuliskan rentangnya ("kalimat 114-119").
        # Dulu kode membacanya sebagai "sesudah yang terakhir" tanpa pernah
        # memberi tahu model, sehingga model yang menjawab seperti tampilan
        # kandidat kehilangan kalimat penutupnya — sering justru punchline-nya.
        si, sj_akhir = sel.get("start_sentence"), sel.get("end_sentence")
        rentang_sah = (isinstance(si, int) and isinstance(sj_akhir, int)
                       and 0 <= si <= sj_akhir < len(sentences))
        sj = sj_akhir + 1 if rentang_sah else None

        free = cid == -1
        if free:
            if not rentang_sah:
                continue
            # Rentang bebas tetap tidak bisa berhalusinasi: indeksnya divalidasi
            # terhadap daftar kalimat nyata, dan waktunya diambil dari kalimat
            # itu — bukan dari angka yang ditulis model.
            base = Candidate(
                start=sentences[si]["s"], end=sentences[sj - 1]["e"], score=0.5,
                breakdown={"gemini_free": 1.0}, sentence_span=(si, sj),
                reason_keys=[], text=" ".join(x["text"] for x in sentences[si:sj]),
            )
        else:
            base = pool[cid]
        i, j = base.sentence_span

        # Batas dari model diterima apa adanya selama sah dan panjangnya masuk
        # akal. Dulu awal hanya boleh mundur delapan kalimat: pada obrolan yang
        # kalimatnya pendek-pendek itu cuma belasan detik, sehingga model yang
        # sudah benar ingin mundur ke awal topik dibatalkan diam-diam — dan
        # klipnya tetap dibuka dengan "setelah itu…" yang tidak dimengerti
        # siapa pun yang belum menonton videonya.
        if rentang_sah and not free:
            if 8.0 <= sentences[sj - 1]["e"] - sentences[si]["s"] <= max_seconds:
                i, j = si, sj

        start = sentences[i]["s"]
        end = sentences[j - 1]["e"]
        if end - start < 8.0 or end - start > max_seconds:
            continue
        if (i, j) in seen_free:
            continue
        seen_free.add((i, j))
        # Setelah batasnya dilebarkan, dua pilihan bisa berakhir di pembahasan
        # yang sama. Yang lebih dulu disebut model (yang lebih kuat) menang.
        if any(min(end, b.end) - max(start, b.start) > 0.5 * min(end - start, b.end - b.start)
               for b in out):
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


SYSTEM_BATAS = """Anda penyunting akhir potongan video pendek berbahasa Indonesia.

Untuk setiap potongan Anda diberi transkrip di sekitarnya, bernomor per
kalimat, dan rentang potongan yang sekarang. Transkripnya hasil pengenalan
suara otomatis: tanda baca sering hilang dan satu "kalimat" bisa berhenti di
tengah ucapan.

Periksa dua hal saja:

1. AWAL — bisakah penonton yang belum pernah melihat video ini memahami
   kalimat pertama? Bila kalimat pertama menjawab pertanyaan yang tidak ikut,
   melanjutkan cerita yang awalnya tidak ikut, atau memakai "itu/dia/gitu/
   terus/makanya" yang merujuk ke belakang, mundurkan start_sentence ke tempat
   topiknya dimulai. Bila awalnya berisi basa-basi yang tidak perlu, majukan.

2. AKHIR — apakah potongan berhenti setelah puncaknya (jawaban, punchline,
   kesimpulan)? Bila berhenti di tengah ucapan (misalnya berakhir dengan
   "kalau", "yang", "tapi", "terus") atau sebelum intinya keluar, majukan
   end_sentence. Bila setelah puncaknya masih ada obrolan yang tidak perlu,
   mundurkan.

Jangan memanjangkan tanpa alasan. Bila batasnya sudah benar, kembalikan
angka yang sama. Kedua nomor adalah kalimat yang MASUK (inklusif) dan harus
berada di dalam transkrip yang diberikan untuk potongan itu."""


def _schema_batas():
    from google.genai import types
    return types.Schema(
        type=types.Type.OBJECT, required=["potongan"],
        properties={"potongan": types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(
                type=types.Type.OBJECT,
                required=["nomor", "catatan", "start_sentence", "end_sentence"],
                property_ordering=["nomor", "catatan", "start_sentence", "end_sentence"],
                properties={
                    "nomor": types.Schema(type=types.Type.INTEGER),
                    "catatan": types.Schema(type=types.Type.STRING),
                    "start_sentence": types.Schema(type=types.Type.INTEGER),
                    "end_sentence": types.Schema(type=types.Type.INTEGER),
                }),
        )},
    )


def rapikan_batas(
    *,
    sentences: list[Sentence],
    candidates: list[Candidate],
    api_key: str,
    models: list[str],
    max_seconds: float = 240.0,
    sebelum: int = 25,
    sesudah: int = 15,
    kabar=None,
    batal=None,
) -> int:
    """
    Pemeriksaan kedua: awal dan akhir setiap klip, dilihat dari dekat.

    Pemilihan klip membaca transkrip utuh — pada video empat puluh menit itu
    ribuan kalimat sekaligus — dan di skala itu model cukup andal menemukan
    MOMEN, tapi ceroboh di BATAS-nya: terukur, sekitar sepertiga klip masih
    dibuka dengan kalimat yang merujuk ke belakang atau berhenti di "…kalau".
    Di sini model hanya melihat beberapa puluh kalimat di sekitar tiap klip,
    dengan satu tugas.

    Mengubah `candidates` di tempat dan mengembalikan jumlah klip yang
    batasnya berubah. Galat apa pun dilempar; pemanggil tetap memakai batas
    hasil pemilihan.
    """
    from google import genai
    from google.genai import types

    if not candidates:
        return 0
    n = len(sentences)
    jendela: list[tuple[int, int]] = []
    bagian: list[str] = []
    for k, c in enumerate(candidates):
        i, j = c.sentence_span
        lo, hi = max(0, i - sebelum), min(n, j + sesudah)
        jendela.append((lo, hi))
        baris = []
        for idx in range(lo, hi):
            mm, ss = divmod(int(sentences[idx]["s"]), 60)
            baris.append(f"[{idx}] {mm}:{ss:02d} {sentences[idx]['text'][:220]}")
        bagian.append(
            f"=== POTONGAN {k} — sekarang kalimat {i}-{j - 1} "
            f"({c.end - c.start:.0f} detik) ===\n" + "\n".join(baris))
    prompt = ("\n\n".join(bagian)
              + f"\n\nPeriksa awal dan akhir setiap potongan (nomor 0-{len(candidates) - 1}). "
                f"Batas panjang satu potongan {max_seconds:.0f} detik.")

    config = types.GenerateContentConfig(
        response_mime_type="application/json", response_schema=_schema_batas(),
        temperature=0.2, max_output_tokens=min(32768, 4096 + 400 * len(candidates)),
        system_instruction=SYSTEM_BATAS,
    )
    client = genai.Client(api_key=api_key,
                          http_options=types.HttpOptions(timeout=120_000))
    tenggat = time.monotonic() + 200
    data = None
    gagal: list[str] = []
    for model_name in models:
        if tanpa_kuota(model_name) and model_name != models[-1]:
            continue
        if time.monotonic() > tenggat:
            gagal.append("batas waktu habis")
            break
        if batal is not None:
            batal()
        if kabar is not None:
            kabar(f"Memeriksa awal dan akhir tiap klip ({model_name})…")
        try:
            resp = client.models.generate_content(model=model_name, contents=prompt,
                                                  config=config)
            data = json.loads(resp.text or "")
            break
        except Exception as e:
            catat_gagal(model_name, e)
            gagal.append(f"{model_name}: {str(e)[:120]}")
            log.warning("Pemeriksaan batas gagal di %s: %s", model_name, str(e)[:200])
    if data is None:
        raise RuntimeError("Pemeriksaan batas gagal — " + " | ".join(gagal))

    lama = [(c.start, c.end, c.sentence_span, c.text) for c in candidates]
    berubah = 0
    for row in data.get("potongan") or []:
        try:
            k = int(row["nomor"])
            si, se = int(row["start_sentence"]), int(row["end_sentence"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (0 <= k < len(candidates)):
            continue
        lo, hi = jendela[k]
        if not (lo <= si <= se < hi):
            continue
        start, end = sentences[si]["s"], sentences[se]["e"]
        if not (8.0 <= end - start <= max_seconds):
            continue
        c = candidates[k]
        if (si, se + 1) == tuple(c.sentence_span):
            continue
        c.start, c.end, c.sentence_span = start, end, (si, se + 1)
        c.text = " ".join(x["text"] for x in sentences[si:se + 1])
        berubah += 1

    # Batas yang bergeser bisa menabrak klip lain. Klip yang lebih kuat (lebih
    # dulu di daftar) menang; yang kalah kembali ke batas sebelumnya.
    for k, c in enumerate(candidates):
        tabrak = any(
            min(c.end, b.end) - max(c.start, b.start) > 0.5 * min(c.end - c.start, b.end - b.start)
            for b in candidates[:k])
        if tabrak and (c.start, c.end) != lama[k][:2]:
            c.start, c.end, c.sentence_span, c.text = lama[k]
            berubah -= 1
    return berubah


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
        if tanpa_kuota(model) and model != models[-1]:
            continue
        try:
            resp = client.models.generate_content(
                model=model, contents=prompt, config=config)
            data = json.loads(resp.text)
        except Exception as e:      # model penuh, dipensiunkan, atau JSON rusak
            last = e
            catat_gagal(model, e)
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
