"""
Profil: satu orang atau satu kanal di dalam OmniClip.

Tiap profil boleh menyambungkan SATU akun Google sendiri — Drive-nya sendiri
(15 GB gratis per akun) dan kanal YouTube-nya sendiri — dan membawa folder
klip, riwayat pencarian, minat untuk beranda, serta setelan unggah otomatis
sendiri. Pemiliknya ingin satu akun fokus ke satu jenis konten.

Yang sengaja DIPAKAI BERSAMA: video sumber yang sudah diunduh dan hasil
analisisnya. Video yang sama tidak perlu diunduh dan dianalisis dua kali hanya
karena dua profil ingin mengklipnya; yang terpisah adalah daftar Partitur-nya.

Profil aktif dibawa tiap permintaan lewat header `X-Omniclip-Profil`, bukan
disimpan sekali di server: dua tab (atau laptop dan HP) boleh bekerja di
profil yang berbeda tanpa saling menimpa. Job yang dibuat selama permintaan
mencatat profilnya di payload (lihat JobQueue.enqueue), jadi render dan
unggahan yang berjalan di latar tetap tahu milik siapa mereka.
"""

from __future__ import annotations

import contextvars
import logging
import re
import shutil
from pathlib import Path
from typing import Optional

from ..config import CLIPS_DIR, STORAGE_DIR

log = logging.getLogger("omniclip.profil")

HEADER = "x-omniclip-profil"
UTAMA = 1

_kini: contextvars.ContextVar[int] = contextvars.ContextVar("profil", default=UTAMA)

# Setelan unggah bawaan profil baru: tidak ada yang keluar dari komputer
# sampai pemiliknya sendiri menyalakannya.
UNGGAH_BAWAAN = {
    "otomatis": False,          # unggah sendiri setelah render selesai
    "youtube": True,
    "drive": False,
    # Jarak jam antar unggahan otomatis; 0 = semuanya langsung naik.
    "jadwal_jam": 0,
    "privasi": "private",       # private | unlisted | public
    "deskripsi": "{judul}\n\n{hashtag}",
    "hashtag": ["#shorts"],
}


# Nama yang dipakai saat sebuah akun baru dibuat, SEBELUM ia masuk ke Google.
# Begitu akunnya tersambung, namanya diganti alamat surelnya sendiri —
# meminta orang mengarang nama untuk akun yang sudah punya nama adalah
# pekerjaan yang tidak perlu ada.
NAMA_SEMENTARA = "Akun baru"


def namai_dari_akun(pid: int, email: str) -> Optional[str]:
    """
    Memberi nama akun dari alamat surelnya, bila namanya masih sementara.

    Nama yang sudah diketik pemiliknya sendiri tidak pernah ditimpa.
    """
    from ..repos import profil as repo
    p = repo.ambil(pid)
    if not p or not email:
        return None
    if (p.get("nama") or "").strip() not in ("", NAMA_SEMENTARA):
        return None
    nama = email.split("@")[0].replace(".", " ").strip()[:40] or email[:40]
    repo.ubah(pid, nama=nama)
    return nama


def _folder_otomatis(jalur: str) -> bool:
    """
    Apakah folder ini dipilihkan sistem, bukan ditunjuk pemiliknya.

    Yang dipilihkan sistem berbentuk "Nama (7)" DI DALAM folder klip. Yang
    ditunjuk sendiri lewat "Pindahkan ke…" bisa di mana saja, dan tidak pernah
    boleh diubah diam-diam.
    """
    if not jalur:
        return True
    d = Path(jalur)
    try:
        if d.parent.resolve() != CLIPS_DIR.resolve():
            return False
    except OSError:
        return False
    return bool(re.search(r"\(\d+\)$", d.name))


def folder_untuk_akun(pid: int, email: str) -> Optional[str]:
    """
    Menamai folder klip menurut AKUN GOOGLE-nya, dan memakai ulang yang sudah ada.

    Sebelumnya folder dipatok saat profil dibuat, dengan nama "Akun baru (6)" —
    saat itu akun Googlenya memang belum diketahui. Akibatnya terasa persis
    seperti yang dilaporkan: login yang gagal berkali-kali meninggalkan profil
    yang dihapus lagi, tiap percobaan berikutnya membuat folder baru, dan yang
    akhirnya berhasil mendarat di "Akun baru (6)" — sebuah nama yang tidak
    memberi tahu siapa pun akun mana isinya.

    Sekarang namanya datang dari surelnya, TANPA nomor profil. Itu yang membuat
    keluar lalu masuk lagi dengan akun yang sama kembali ke folder yang sama,
    berikut seluruh klip yang sudah ada di dalamnya.

    Folder yang ditunjuk pemiliknya sendiri tidak disentuh.
    """
    from ..repos import profil as repo

    p = repo.ambil(pid)
    if not p or not email or "@" not in email:
        return None
    if not _folder_otomatis(p.get("folder_klip") or ""):
        return None

    nama = _slug(email.split("@")[0].replace(".", " "))
    tujuan = CLIPS_DIR / nama
    lama = Path(p["folder_klip"]) if p.get("folder_klip") else None
    if lama and lama.resolve() == tujuan.resolve():
        return None

    try:
        if lama and lama.is_dir() and not tujuan.exists():
            # Klip yang sudah telanjur masuk folder bernomor ikut pindah.
            lama.rename(tujuan)
        else:
            tujuan.mkdir(parents=True, exist_ok=True)
            if lama and lama.is_dir():
                for f in lama.iterdir():
                    if not (tujuan / f.name).exists():
                        f.rename(tujuan / f.name)
                try:
                    lama.rmdir()
                except OSError:
                    pass
    except OSError as e:
        log.warning("Folder akun tidak bisa disiapkan: %s", str(e)[:160])
        return None

    repo.ubah(pid, folder_klip=str(tujuan))
    log.info("Folder klip akun %s mengikuti surelnya: %s", pid, tujuan.name)
    return str(tujuan)


def kini() -> int:
    return _kini.get()


def setel(pid: int):
    return _kini.set(pid)


def pulihkan(token) -> None:
    _kini.reset(token)


def dari_header(nilai: Optional[str]) -> int:
    """Nomor profil dari header, atau profil Utama bila kosong/tidak dikenal."""
    try:
        pid = int((nilai or "").strip())
    except ValueError:
        return UTAMA
    from ..repos import profil as repo
    return pid if pid > 0 and repo.ambil(pid) else UTAMA


def _slug(nama: str) -> str:
    s = re.sub(r"[^\w\- ]+", "", nama, flags=re.UNICODE).strip()
    return re.sub(r"\s+", " ", s)[:40] or "Profil"


def folder_klip(pid: int) -> Path:
    """Folder hasil render profil ini. Profil Utama memakai folder klip lama."""
    from ..repos import profil as repo
    p = repo.ambil(pid)
    if p and p.get("folder_klip"):
        d = Path(p["folder_klip"])
    elif pid == UTAMA or not p:
        d = CLIPS_DIR
    else:
        d = CLIPS_DIR / f"{_slug(p['nama'])} ({pid})"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ikutkan_nama_folder(pid: int, nama_baru: str) -> Optional[str]:
    """
    Menamai ulang folder klip supaya mengikuti nama akunnya.

    Folder yang isinya milik "Horor" tapi bernama "Akun baru (3)" adalah folder
    yang tidak bisa dikenali dari luar aplikasi, dan di luar aplikasi itulah
    orang mencarinya: di pengelola berkas, saat mau mengunggah dari HP.

    Yang TIDAK ikut berubah, dan keduanya disengaja:

    - folder yang ditunjuk sendiri lewat "Pindahkan ke…". Itu pilihan yang
      sudah dinyatakan, dan mengubahnya karena akunnya diganti nama berarti
      membatalkan pilihan orang tanpa diminta.
    - profil Utama, yang klipnya tinggal di akar `edited_clips`. Memindahkannya
      berarti memindahkan seluruh klip lama ke subfolder baru hanya karena
      namanya diganti.

    Mengembalikan jalur barunya bila benar-benar berpindah, atau None.
    """
    from ..repos import profil as repo

    p = repo.ambil(pid)
    if not p or pid == UTAMA or p.get("folder_klip"):
        return None
    lama = CLIPS_DIR / f"{_slug(p['nama'])} ({pid})"
    baru = CLIPS_DIR / f"{_slug(nama_baru)} ({pid})"
    if baru == lama:
        return None
    try:
        if baru.exists():
            # Nama itu sudah dipakai sesuatu. Berhenti, jangan menimpa.
            log.warning("Folder %s sudah ada; nama folder tidak diubah", baru.name)
            return None
        if lama.is_dir():
            lama.rename(baru)
        else:
            baru.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        # Nama folder bukan alasan menggagalkan penggantian nama akun.
        log.warning("Folder klip tidak bisa diganti nama: %s", str(e)[:160])
        return None
    log.info("Folder klip akun %s: %s -> %s", pid, lama.name, baru.name)
    return str(baru)


def folder_akun(pid: int) -> Path:
    """Tempat token Google profil ini (izin 0600, di luar folder klip)."""
    d = STORAGE_DIR / "akun" / str(pid)
    d.mkdir(parents=True, exist_ok=True)
    # Token lama (sebelum ada profil) menjadi milik profil Utama.
    if pid == UTAMA:
        lama = STORAGE_DIR / "google_token.json"
        baru = d / "google_token.json"
        if lama.is_file() and not baru.exists():
            shutil.move(str(lama), str(baru))
    return d


def unggah(pid: int) -> dict:
    from ..repos import profil as repo
    p = repo.ambil(pid) or {}
    return {**UNGGAH_BAWAAN, **(p.get("unggah") or {})}


def kategori_klip(pid: int) -> str:
    """Kategori media untuk URL klip profil ini (/api/media/<kategori>/<berkas>)."""
    return f"klip_{pid}"
