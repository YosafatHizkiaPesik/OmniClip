"""
Menulis identitas aplikasi Google ke dalam bundel, dijalankan alur build.

Dipisah jadi berkas sendiri, bukan `python -c` satu baris di dalam YAML, karena
satu baris itu harus melewati tiga lapis pengutipan sekaligus (YAML, bash, lalu
Python) dan setiap lapis punya aturan sendiri soal tanda kutip dan garis miring.
Yang salah di sana tidak ketahuan sampai build berjalan di GitHub.

Berkas keluarannya ada di daftar abaikan git. Lihat `config.py` untuk alasan
mengapa variabel lingkungan saja tidak cukup pada aplikasi yang dibungkus.
"""

import os
import sys
from pathlib import Path

TUJUAN = Path(__file__).resolve().parents[1] / "backend" / "app" / "identitas_google.py"


def main() -> int:
    client_id = os.environ.get("GOOGLE_ID", "").strip()
    rahasia = os.environ.get("GOOGLE_RAHASIA", "").strip()
    if not (client_id and rahasia):
        print("Identitas Google tidak dipasang: rahasianya kosong.")
        return 0
    TUJUAN.write_text(
        '"""Ditulis alur build dari rahasia GitHub. Jangan disunting, jangan di-commit."""\n'
        f"CLIENT_ID = {client_id!r}\n"
        f"CLIENT_SECRET = {rahasia!r}\n",
        encoding="utf-8",
    )
    # Nilainya TIDAK dicetak. Yang dicetak cuma cukup untuk memastikan
    # rahasianya memang terbaca, bukan untuk membacanya kembali dari log.
    print(f"Identitas ditulis ke {TUJUAN.name} "
          f"(client id berakhiran {client_id[-6:]}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
