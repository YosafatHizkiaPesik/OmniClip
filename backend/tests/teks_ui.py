"""
Membaca teks UI untuk tes penjaga (JOB-3 J3-8).

Sejak antarmuka dua bahasa, kalimat di layar tidak lagi ditulis langsung di
berkas .jsx, melainkan di kamus `frontend/src/locales/id.js` dan dipanggil
lewat `t('kunci')`. Tes yang memastikan sebuah kalimat ada di layar membaca
berkas komponennya DITAMBAH kamus Indonesia, supaya tetap menangkap kalimat
yang hilang tanpa terikat pada di mana kalimat itu ditulis.
"""

from pathlib import Path

AKAR = Path(__file__).resolve().parents[2]
KAMUS_ID = AKAR / "frontend" / "src" / "locales" / "id.js"


def teks_ui(berkas: Path) -> str:
    return berkas.read_text(encoding="utf-8") + "\n" + KAMUS_ID.read_text(encoding="utf-8")
