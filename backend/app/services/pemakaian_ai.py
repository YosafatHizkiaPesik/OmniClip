"""
Mencatat setiap panggilan ke model AI: berapa dipakai, oleh siapa, dan hasilnya.

Ada karena satu pertanyaan yang sebelumnya tidak bisa dijawab: "jatah saya
masih sisa berapa?" Jawaban sebelumnya selalu sama, yaitu menunggu sampai
gagal lalu menebak sebabnya. Terukur 24 September 2026, jatah gratis Gemini
hanya 20 permintaan per model per project per hari, jadi pertanyaan itu bukan
rasa ingin tahu melainkan syarat untuk bisa merencanakan hari.

Yang dicatat sengaja sedikit dan tidak ada satu pun yang rahasia: nama model,
untuk pekerjaan apa, berapa token, berhasil atau tidak. Kunci API tidak pernah
ikut, bahkan sidiknya. Isi permintaan juga tidak — transkrip milik pemiliknya,
dan mencatatnya berarti menyalin seluruh video ke basis data untuk kedua
kalinya.

Kegagalan mencatat TIDAK pernah menjatuhkan pekerjaan yang sedang berjalan.
Catatan pemakaian yang membuat render gagal adalah pertukaran yang bodoh.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

log = logging.getLogger("omniclip.pemakaian")

# Jatah gratis Gemini bila Google belum pernah menyebutkan angkanya sendiri.
#
# Google TIDAK PERNAH mengirim sisa kuota: diperiksa 24 September 2026, jawaban
# suksesnya tidak memuat satu pun header kuota. Yang ia sebutkan hanya BATASNYA,
# dan itu pun hanya di dalam galat 429 saat jatahnya sudah habis. Jadi:
#
#   - selama belum pernah habis, angka di bawah dipakai sebagai patokan awal;
#   - begitu sekali habis, batas SUNGGUHAN dari Google menggantikannya, dan
#     hitungan hari itu dipatok ke batas tersebut — pada saat itu sisanya bukan
#     lagi perkiraan melainkan nol yang diketahui pasti.
JATAH_HARIAN_PER_MODEL = 20
_NAMA_BATAS = "ai.batas_harian_model"

# Berapa lama catatan disimpan. Cukup untuk melihat kecenderungan sebulan,
# tidak cukup lama untuk menjadi tumpukan yang tak pernah dibaca.
SIMPAN_HARI = 30


def _conn():
    from ..db import get_conn
    return get_conn()


def siapkan() -> None:
    """Membuat tabelnya bila belum ada. Dipanggil saat migrasi berjalan."""
    _conn().executescript("""
        CREATE TABLE IF NOT EXISTS pemakaian_ai (
          id          INTEGER PRIMARY KEY AUTOINCREMENT,
          created_at  REAL    NOT NULL,
          penyedia    TEXT    NOT NULL DEFAULT 'gemini',
          model       TEXT    NOT NULL,
          pekerjaan   TEXT    NOT NULL,
          video_id    TEXT,
          masuk       INTEGER NOT NULL DEFAULT 0,
          keluar      INTEGER NOT NULL DEFAULT 0,
          berpikir    INTEGER NOT NULL DEFAULT 0,
          berhasil    INTEGER NOT NULL DEFAULT 1,
          sebab       TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_pemakaian_waktu ON pemakaian_ai (created_at);
    """)


def catat(*, model: str, pekerjaan: str, penyedia: str = "gemini",
          video_id: Optional[str] = None, pakai: Optional[dict] = None,
          berhasil: bool = True, sebab: str = "") -> None:
    """Satu panggilan model. Tidak pernah melempar."""
    try:
        p = pakai or {}
        _conn().execute(
            """INSERT INTO pemakaian_ai
               (created_at, penyedia, model, pekerjaan, video_id,
                masuk, keluar, berpikir, berhasil, sebab)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (time.time(), penyedia, model or "?", pekerjaan, video_id,
             int(p.get("masuk") or 0), int(p.get("keluar") or 0),
             int(p.get("berpikir") or 0), 1 if berhasil else 0, sebab[:200]),
        )
    except Exception as e:                  # mencatat bukan alasan gagal
        log.debug("Pemakaian AI tidak tercatat: %s", str(e)[:120])


def batas_model(model: str) -> int:
    """Batas harian model ini: yang disebutkan Google, atau patokan awal."""
    try:
        import json
        from ..repos import settings as settings_repo
        data = json.loads(settings_repo.get(_NAMA_BATAS) or "{}")
        return int(data.get(model) or JATAH_HARIAN_PER_MODEL)
    except Exception:
        return JATAH_HARIAN_PER_MODEL


def tandai_habis(model: str, batas: Optional[int] = None) -> None:
    """
    Dipanggil saat Google menolak dengan "jatah harian habis".

    Dua hal terjadi di sini, dan keduanya mengubah angka perkiraan jadi angka
    yang diketahui: batas sungguhannya disimpan, dan hitungan hari ini dipatok
    ke batas itu. Panggilan yang dilakukan aplikasi LAIN dengan kunci yang sama
    tidak pernah terlihat dari sini, dan inilah satu-satunya saat selisihnya
    bisa diperbaiki.
    """
    try:
        import json

        from ..repos import settings as settings_repo

        if batas and batas > 0:
            data = json.loads(settings_repo.get(_NAMA_BATAS) or "{}")
            if data.get(model) != batas:
                data[model] = int(batas)
                settings_repo.set_value(_NAMA_BATAS, json.dumps(data))
                log.info("Batas harian %s menurut Google: %d", model, batas)

        siapkan()
        c = _conn()
        awal = _batas_hari_ini()
        sudah = c.execute(
            "SELECT COUNT(*) FROM pemakaian_ai WHERE model = ? AND created_at >= ?",
            (model, awal)).fetchone()[0]
        kurang = max(0, batas_model(model) - int(sudah or 0))
        if kurang:
            # Baris penyeimbang: panggilan yang benar-benar terjadi tapi tidak
            # lewat sini. Ditandai supaya tidak terbaca sebagai pekerjaan nyata.
            now = time.time()
            c.executemany(
                """INSERT INTO pemakaian_ai
                   (created_at, penyedia, model, pekerjaan, video_id,
                    masuk, keluar, berpikir, berhasil, sebab)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                [(now, "gemini", model, "di luar OmniClip", None, 0, 0, 0, 1,
                  "penyeimbang: Google menyatakan jatah harian habis")
                 for _ in range(kurang)])
            log.info("Hitungan %s disetel ke batasnya (%d), selisih %d",
                     model, batas_model(model), kurang)
    except Exception as e:
        log.debug("Penyeimbang jatah gagal: %s", str(e)[:120])


def terpakai_hari_ini(model: str) -> int:
    """Berapa panggilan model ini sudah dipakai sejak jatahnya berputar."""
    try:
        row = _conn().execute(
            "SELECT COUNT(*) AS n FROM pemakaian_ai WHERE model = ? AND created_at >= ?",
            (model, _batas_hari_ini()),
        ).fetchone()
        return int(row["n"] if row else 0)
    except Exception:
        return 0


def sisa_model(model: str) -> int:
    """Perkiraan sisa jatah harian model ini. Tidak pernah negatif."""
    return max(0, batas_model(model) - terpakai_hari_ini(model))


def _batas_hari_ini() -> float:
    """Awal hari kuota Google: tengah malam waktu Pasifik."""
    from .peringkat_model import detik_ke_putaran
    return time.time() + detik_ke_putaran() - 86400


def ringkas(hari: int = 7) -> dict:
    """
    Angka yang dibaca orang, bukan baris mentah.

    `hari_ini` dihitung dari tengah malam waktu PASIFIK, bukan tengah malam di
    sini: yang menentukan sisa jatah adalah jam milik Google, dan menampilkan
    hitungan berdasarkan jam lokal akan berbohong tiap sore.
    """
    try:
        siapkan()
        c = _conn()
        awal_hari = _batas_hari_ini()
        sejak = time.time() - hari * 86400

        per_model = [dict(r) for r in c.execute(
            """SELECT model, penyedia, COUNT(*) AS panggilan,
                      SUM(berhasil) AS sukses,
                      SUM(masuk) AS masuk, SUM(keluar) AS keluar
                 FROM pemakaian_ai WHERE created_at >= ?
                GROUP BY model ORDER BY panggilan DESC""", (awal_hari,))]
        per_pekerjaan = [dict(r) for r in c.execute(
            """SELECT pekerjaan, COUNT(*) AS panggilan,
                      SUM(masuk + keluar + berpikir) AS token
                 FROM pemakaian_ai WHERE created_at >= ?
                GROUP BY pekerjaan ORDER BY panggilan DESC""", (sejak,))]
        video = [dict(r) for r in c.execute(
            """SELECT video_id, COUNT(*) AS panggilan,
                      SUM(masuk + keluar + berpikir) AS token
                 FROM pemakaian_ai
                WHERE created_at >= ? AND video_id IS NOT NULL
                GROUP BY video_id""", (sejak,))]

        # Sisa jatah HANYA untuk Gemini: OpenRouter menghitungnya sendiri dengan
        # aturan yang berbeda, dan menebaknya di sini akan menyesatkan.
        sisa = []
        for m in per_model:
            if m["penyedia"] != "gemini":
                continue
            terpakai = int(m["panggilan"] or 0)
            batas = batas_model(m["model"])
            sisa.append({"model": m["model"], "terpakai": terpakai,
                         "jatah": batas, "sisa": max(0, batas - terpakai),
                         # Sudah pernah ditolak Google hari ini? Kalau ya,
                         # angkanya bukan perkiraan lagi.
                         "pasti": terpakai >= batas})

        n_video = len(video) or 1
        return {
            "hari_ini": {
                "panggilan": sum(int(m["panggilan"] or 0) for m in per_model),
                "token": sum(int((m["masuk"] or 0) + (m["keluar"] or 0))
                             for m in per_model),
                "per_model": per_model,
                "sisa": sisa,
            },
            "rentang_hari": hari,
            "per_pekerjaan": per_pekerjaan,
            "rata_per_video": {
                "panggilan": round(sum(int(v["panggilan"] or 0) for v in video) / n_video, 1),
                "token": round(sum(int(v["token"] or 0) for v in video) / n_video),
                "video": len(video),
            },
            "jatah_per_model": JATAH_HARIAN_PER_MODEL,
        }
    except Exception as e:
        log.warning("Ringkasan pemakaian gagal: %s", str(e)[:160])
        return {"hari_ini": {"panggilan": 0, "token": 0, "per_model": [], "sisa": []},
                "per_pekerjaan": [], "rata_per_video": {"panggilan": 0, "token": 0,
                                                        "video": 0},
                "jatah_per_model": JATAH_HARIAN_PER_MODEL, "rentang_hari": hari}


def bersihkan() -> int:
    try:
        siapkan()
        cur = _conn().execute("DELETE FROM pemakaian_ai WHERE created_at < ?",
                              (time.time() - SIMPAN_HARI * 86400,))
        return cur.rowcount
    except Exception:
        return 0
