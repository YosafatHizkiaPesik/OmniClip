"""
Memastikan gerbang Cloudflare Access menolak yang harus ditolak.

    venv/bin/python uji_cf_access.py

Tidak memanggil Cloudflare sama sekali: sepasang kunci RSA dibuat di tempat,
dipakai sebagai "kunci publik Cloudflare", lalu token-token ditempa di atasnya —
termasuk token yang ditandatangani kunci penyerang dan token sah milik aplikasi
Access ORANG LAIN.

Yang terakhir itu alasan berkas ini ada. Cloudflare menulis klaim `aud` sebagai
DAFTAR, sementara google.auth membandingkannya sebagai nilai tunggal; memakai
parameter `audience=` pustaka itu membuat setiap token sah ikut tertolak, dan
"perbaikan" yang paling menggoda adalah menghapus pemeriksaan aud sama sekali.
Kalau itu terjadi, token dari aplikasi Access siapa pun di internet akan
diterima di sini. Uji ini yang menangkapnya.
"""

import asyncio
import datetime
import os
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

os.environ["OMNICLIP_CF_ACCESS_TEAM"] = "timsaya"
os.environ["OMNICLIP_CF_ACCESS_AUD"] = "aud-aplikasi-omniclip-1234567890abcdef"

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from google.auth import crypt, jwt as gjwt

def buat_kunci(nama):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subj = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, nama)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(subj).issuer_name(subj)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=30))
            .sign(key, hashes.SHA256()))
    pem_key = key.private_bytes(serialization.Encoding.PEM,
                                serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()).decode()
    pem_cert = cert.public_bytes(serialization.Encoding.PEM).decode()
    return pem_key, pem_cert

ASLI_KEY, ASLI_CERT = buat_kunci("cloudflare-asli")
PALSU_KEY, _        = buat_kunci("penyerang")

from app.services import cf_access
cf_access._fetch_certs = lambda: {"kid-asli": ASLI_CERT}

ISS = "https://timsaya.cloudflareaccess.com"
AUD = os.environ["OMNICLIP_CF_ACCESS_AUD"]

def token(key=ASLI_KEY, *, aud=AUD, iss=ISS, email="yosafathizkiapesik@gmail.com",
          exp_delta=3600, kid="kid-asli"):
    now = int(time.time())
    signer = crypt.RSASigner.from_string(key, kid)
    return gjwt.encode(signer, {"aud": [aud], "iss": iss, "email": email,
                                "iat": now - 10, "exp": now + exp_delta,
                                "sub": "abc"}).decode()

class Req:
    def __init__(self, tok, peer="127.0.0.1"):
        self.headers = {cf_access.HEADER: tok} if tok else {}
        self.cookies = {}
        self.client = type("C", (), {"host": peer})()

async def main():
    kasus = [
        ("token sah dari terowongan",        Req(token()),                                    True),
        ("aud aplikasi Access ORANG LAIN",   Req(token(aud="aud-punya-orang-lain-xxxxxxxx")), False),
        ("iss tim lain",                     Req(token(iss="https://timlain.cloudflareaccess.com")), False),
        ("ditandatangani kunci penyerang",   Req(token(PALSU_KEY)),                           False),
        ("token sudah kedaluwarsa",          Req(token(exp_delta=-60)),                       False),
        ("kid tidak dikenal",                Req(token(kid="kid-karangan")),                  False),
        ("tanpa token",                      Req(None),                                       False),
        ("token sah TAPI dari LAN",          Req(token(), peer="192.168.1.50"),               False),
        ("teks sembarang sebagai token",     Req("bukan-jwt-sama-sekali"),                    False),
    ]
    gagal = 0
    for nama, req, harus_lolos in kasus:
        email, alasan = await cf_access.verify(req)
        lolos = bool(email)
        ok = lolos == harus_lolos
        gagal += not ok
        print(f"  {'OK  ' if ok else 'SALAH'} {nama:34} -> {'diterima' if lolos else 'ditolak'}"
              f"{'' if lolos else f'  ({alasan[:58]})'}")

    # Daftar email di sisi kita sendiri.
    os.environ["OMNICLIP_CF_ACCESS_EMAILS"] = "oranglain@contoh.com"
    email, alasan = await cf_access.verify(Req(token()))
    ok = not email
    gagal += not ok
    print(f"  {'OK  ' if ok else 'SALAH'} {'di luar daftar email kita':34} -> "
          f"{'diterima' if email else 'ditolak'}  ({alasan[:58]})")

    os.environ["OMNICLIP_CF_ACCESS_EMAILS"] = "yosafathizkiapesik@gmail.com"
    email, _ = await cf_access.verify(Req(token()))
    ok = bool(email)
    gagal += not ok
    print(f"  {'OK  ' if ok else 'SALAH'} {'ada di daftar email kita':34} -> "
          f"{'diterima sebagai ' + email if email else 'ditolak'}")

    print(f"\n  {'SEMUA LULUS' if not gagal else f'{gagal} GAGAL'}")
    return gagal

raise SystemExit(asyncio.run(main()))
