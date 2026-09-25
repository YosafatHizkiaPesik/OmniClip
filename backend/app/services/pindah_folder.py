"""
Memindahkan isi folder unduhan atau klip ke tempat yang dipilih pemiliknya.

Ada sebagai pekerjaan berlatar, bukan sebagai satu permintaan HTTP, karena
yang dipindahkan puluhan gigabita: sebuah permintaan yang menggantung sepuluh
menit tanpa satu angka pun adalah persis keluhan yang memunculkan berkas ini
("tidak ada progress loading atau apapun"). Yang dipindahkan sekarang punya
persentase, nama berkas yang sedang jalan, dan tombol batal.

Tiga hal yang membuatnya aman diulang:

- Berkas yang sudah ada di tujuan dengan ukuran sama dilewati, jadi pemindahan
  yang terputus bisa dilanjutkan tanpa menyalin ulang apa pun.
- Penyalinan lintas cakram menulis ke berkas sementara `.omnipindah` dan baru
  diberi nama aslinya setelah utuh, sehingga berkas separuh tidak pernah
  terlihat seperti video yang benar.
- Sumbernya dihapus hanya setelah salinannya selesai dan ukurannya cocok.

Folder aktif diganti begitu pemindahannya selesai (`config.setel_folder`),
supaya berkas yang baru pindah tidak menghilang sampai aplikasi dijalankan
ulang.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from ..errors import JobCancelled

log = logging.getLogger("omniclip.pindah")

POTONGAN = 8 * 1024 * 1024      # besar satu tulisan saat menyalin lintas cakram
AKHIRAN_SEMENTARA = ".omnipindah"


def _daftar(asal: Path) -> list[Path]:
    """Semua berkas di dalam `asal`, termasuk yang di subfolder profil."""
    if not asal.is_dir():
        return []
    return sorted(p for p in asal.rglob("*")
                  if p.is_file() and not p.name.endswith(AKHIRAN_SEMENTARA))


def ukuran_total(asal: Path) -> tuple[int, int]:
    """(jumlah berkas, jumlah bita) yang akan dipindahkan."""
    berkas = _daftar(asal)
    total = 0
    for f in berkas:
        try:
            total += f.stat().st_size
        except OSError:
            pass
    return len(berkas), total


def _salin(sumber: Path, tujuan: Path, lapor, batal) -> None:
    """Menyalin satu berkas sepotong demi sepotong, supaya progresnya hidup."""
    sementara = tujuan.with_name(tujuan.name + AKHIRAN_SEMENTARA)
    tujuan.parent.mkdir(parents=True, exist_ok=True)
    with open(sumber, "rb") as masuk, open(sementara, "wb") as keluar:
        while True:
            if batal is not None:
                batal()
            potongan = masuk.read(POTONGAN)
            if not potongan:
                break
            keluar.write(potongan)
            lapor(len(potongan))
    shutil.copystat(sumber, sementara, follow_symlinks=True)
    if sementara.stat().st_size != sumber.stat().st_size:
        sementara.unlink(missing_ok=True)
        raise OSError(f"Salinan {tujuan.name} tidak lengkap.")
    sementara.replace(tujuan)


def pindahkan(asal: Path, tujuan: Path, *, lapor=None, batal=None) -> dict:
    """
    Memindahkan seluruh isi `asal` ke `tujuan`.

    `lapor(bita_selesai, total_bita, nama_berkas)` dipanggil selama berjalan;
    `batal()` boleh melempar untuk menghentikannya di tengah berkas.
    """
    asal, tujuan = Path(asal).resolve(), Path(tujuan).resolve()
    tujuan.mkdir(parents=True, exist_ok=True)
    berkas = _daftar(asal)
    total = sum(f.stat().st_size for f in berkas if f.is_file())
    selesai = pindah = lewat = 0
    gagal: list[str] = []

    for f in berkas:
        if batal is not None:
            batal()
        rel = f.relative_to(asal)
        ke = tujuan / rel
        try:
            besar = f.stat().st_size
        except OSError:
            continue

        # Sudah ada di sana dengan ukuran sama: sisa dari pemindahan yang
        # terputus. Sumbernya dibuang, bukan disalin ulang.
        if ke.is_file() and ke.stat().st_size == besar:
            f.unlink(missing_ok=True)
            lewat += 1
            selesai += besar
            if lapor:
                lapor(selesai, total, rel.name)
            continue

        maju = [selesai]

        def _tambah(n: int) -> None:
            maju[0] += n
            if lapor:
                lapor(maju[0], total, rel.name)

        try:
            if lapor:
                lapor(selesai, total, rel.name)
            try:
                # Satu cakram: berpindah nama, tidak ada bita yang disalin.
                ke.parent.mkdir(parents=True, exist_ok=True)
                os.replace(f, ke)
                _tambah(besar)
            except OSError:
                _salin(f, ke, _tambah, batal)
                f.unlink(missing_ok=True)
            pindah += 1
            selesai = maju[0]
        except JobCancelled:
            raise
        except OSError as e:
            log.warning("Gagal memindahkan %s: %s", rel, e)
            gagal.append(rel.name)
            selesai += besar

    # Folder kosong yang tertinggal ikut dibersihkan, tapi folder asalnya
    # sendiri tetap ada: ia mungkin folder bawaan yang dibuat saat startup.
    for d in sorted((p for p in asal.rglob("*") if p.is_dir()),
                    key=lambda p: len(p.parts), reverse=True):
        try:
            d.rmdir()
        except OSError:
            pass

    return {"dipindah": pindah, "dilewati": lewat, "gagal": gagal, "bita": total}


def run_pindah_folder(ctx) -> dict:
    """
    payload: {jenis: "unduhan"|"klip", tujuan: "<jalur>"}

    Memindahkan berkasnya, menulis penunjuk foldernya, lalu mengarahkan
    aplikasi yang sedang berjalan ke folder baru.
    """
    from .. import config as cfg

    jenis = ctx.payload["jenis"]
    if jenis not in ("unduhan", "klip"):
        raise RuntimeError(f"Jenis folder tidak dikenal: {jenis}")
    tujuan = Path(ctx.payload["tujuan"]).expanduser().resolve()
    asal = (cfg.DOWNLOAD_DIR if jenis == "unduhan" else cfg.CLIPS_DIR).resolve()
    nama = "Video sumber terunduh" if jenis == "unduhan" else "Klip jadi"

    if tujuan == asal:
        ctx.progress(1.0, stage="done", message=f"{nama} sudah ada di folder itu.")
        return {"dipindah": 0, "folder": str(tujuan)}
    if tujuan.is_relative_to(asal):
        raise RuntimeError("Folder tujuan ada di dalam folder asalnya.")

    jumlah, bita = ukuran_total(asal)
    ctx.progress(0.0, stage="prepare",
                 message=f"{jumlah} berkas, {bita / 1073741824:.1f} GB akan dipindahkan…")

    def lapor(selesai: int, total: int, berkas: str) -> None:
        ctx.progress(min(0.98, selesai / total) if total else 0.98, stage="encode",
                     message=f"Memindahkan {berkas} ({selesai / 1073741824:.1f} "
                             f"dari {total / 1073741824:.1f} GB)")

    hasil = pindahkan(asal, tujuan, lapor=lapor, batal=ctx.check_cancelled)

    # Penunjuk ditulis SESUDAH berkasnya pindah. Kalau pemindahannya terputus,
    # folder aktifnya tidak berubah dan tidak ada berkas yang tercecer di
    # tempat yang tidak dicari siapa pun.
    data = cfg._user_data_dir()
    data.mkdir(parents=True, exist_ok=True)
    penunjuk = data / f"lokasi-{jenis}.txt"
    bawaan = (cfg.STORAGE_DIR /
              ("local_downloads" if jenis == "unduhan" else "edited_clips")).resolve()
    # Kembali ke folder bawaan berarti penunjuknya DIHAPUS, bukan diisi jalur
    # bawaannya: penunjuk yang menyebut tempat bawaan akan salah begitu seluruh
    # penyimpanan dipindahkan, dan salahnya tidak akan terlihat sampai saat itu.
    if tujuan == bawaan:
        penunjuk.unlink(missing_ok=True)
    else:
        penunjuk.write_text(str(tujuan), encoding="utf-8")
    cfg.setel_folder(jenis, tujuan)
    log.info("%s dipindahkan ke %s (%d berkas)", nama, tujuan, hasil["dipindah"])

    pesan = f"{nama} sekarang di {tujuan}. {hasil['dipindah']} berkas dipindahkan"
    if hasil["dilewati"]:
        pesan += f", {hasil['dilewati']} sudah ada di sana"
    if hasil["gagal"]:
        pesan += f". {len(hasil['gagal'])} berkas gagal dipindahkan"
    ctx.progress(1.0, stage="done", message=pesan + ".")
    return {**hasil, "folder": str(tujuan), "jenis": jenis}
