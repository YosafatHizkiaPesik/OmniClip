"""
Pemulihan kata sandi, dari terminal komputer ini.

Tidak ada "lupa kata sandi" lewat email di OmniClip — tidak ada email, tidak ada
server surat, dan menambahkannya berarti menambah satu layanan luar yang harus
dipercaya untuk memegang kunci rumah. Gantinya adalah ini: siapa pun yang sudah
duduk di depan komputer ini sudah bisa membaca seluruh isinya, jadi memberi
mereka jalan memasang kata sandi baru tidak menambah kuasa apa pun.

    venv/bin/python reset_password.py                 # pasang kata sandi baru
    venv/bin/python reset_password.py --lepas         # kembali ke mode lokal

Backend boleh sedang berjalan; kata sandi dibaca dari basis data setiap kali
dipakai. Tapi ingat: mengganti kata sandi mencabut SEMUA sesi, termasuk HP yang
sedang terbuka.
"""

import getpass
import sys

from app.db import run_migrations
from app.services import auth

MIN_LENGTH = 8


def main() -> int:
    run_migrations()

    if "--lepas" in sys.argv:
        auth.clear_password()
        print("Kata sandi dilepas. OmniClip kembali ke mode lokal.")
        print("JANGAN jalankan terowongan dalam keadaan ini.")
        return 0

    if auth.has_password():
        print("Kata sandi saat ini akan DIGANTI, dan semua sesi dicabut.")
    else:
        print("Belum ada kata sandi. Memasang yang pertama.")

    try:
        first = getpass.getpass(f"Kata sandi baru (min. {MIN_LENGTH} karakter): ")
        second = getpass.getpass("Ulangi: ")
    except (KeyboardInterrupt, EOFError):
        print("\nDibatalkan.")
        return 1

    if len(first) < MIN_LENGTH:
        print(f"Terlalu pendek: {len(first)} karakter, minimal {MIN_LENGTH}.")
        return 1
    if first != second:
        print("Kedua isian tidak sama.")
        return 1

    auth.set_password(first)
    print("Kata sandi dipasang. Semua perangkat lain harus masuk ulang.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
