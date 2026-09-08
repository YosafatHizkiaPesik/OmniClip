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

Aturan lain:
- Hanya boleh memakai candidate_id yang ada di daftar.
- Menggeser batas hanya lewat start_sentence/end_sentence (indeks kalimat).
  start_sentence boleh mundur sedikit untuk menangkap konteks pembuka;
  end_sentence boleh maju jauh untuk menangkap penutup gagasan.
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
                    required=["candidate_id", "score", "reason", "hook_text", "suggested_title"],
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
        max_output_tokens=8192,
        system_instruction=SYSTEM_ID,
    )

    last_error: Optional[Exception] = None
    for model_name in models:
        for attempt in range(2):
            try:
                resp = client.models.generate_content(
                    model=model_name, contents=prompt, config=config
                )
                data = json.loads(resp.text)
                refined = _apply_selections(data, pool, sentences, max_clips,
                                            max_seconds=max_seconds)
                if refined:
                    log.info("Gemini %s memilih %d klip", model_name, len(refined))
                    return refined, model_name
                raise ValueError("Gemini tidak mengembalikan satupun kandidat yang dikenal")
            except Exception as e:
                last_error = e
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

    raise RuntimeError(f"Semua model Gemini gagal: {last_error}")


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

    for sel in (data.get("selections") or [])[: max_clips * 2]:
        try:
            cid = int(sel.get("candidate_id"))
        except (TypeError, ValueError):
            continue
        if cid < 0 or cid >= len(pool) or cid in seen:
            continue
        seen.add(cid)

        base = pool[cid]
        i, j = base.sentence_span

        si, sj = sel.get("start_sentence"), sel.get("end_sentence")
        if isinstance(si, int) and isinstance(sj, int) and 0 <= si < sj <= len(sentences):
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
