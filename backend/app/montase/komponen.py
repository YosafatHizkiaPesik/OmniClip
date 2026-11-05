"""
Komponen animasi buatan AI: versi, pemeriksaan, dan pustaka (JOB-4 M4.3-M4.10).

Alur satu versi:
  kode (dari AI lewat API, atau tempelan balasan Claude.ai)
    -> dicatat sebagai versi baru berstatus `draf`
    -> periksa.py (kompilasi, statis, 5 bingkai, gerak)
    -> status `lolos` atau `gagal` + catatan (masalah, peringatan, penilaian AI)
Jalur API mencoba lagi paling banyak dua kali dengan galatnya dikirim balik ke
AI. Jalur salin-tempel mengembalikan pesan perbaikan untuk ditempel ke chat.

Hanya versi `lolos` yang bisa disimpan ke pustaka (M4.8) dan disajikan ke
pratinjau/render (rute bertoken /t/<token>/komponen/<id>/<versi>/kode.js).
"""

from __future__ import annotations

import logging
from typing import Optional

from ..repos import montase as repo
from ..services import profil
from . import motion_ai, periksa

log = logging.getLogger("omniclip.montase.komponen")


def _kanvas(dokumen: Optional[dict]) -> dict:
    k = (dokumen or {}).get("kanvas") or {}
    return {"lebar": k.get("lebar", 1080), "tinggi": k.get("tinggi", 1920), "fps": k.get("fps", 30)}


def setelan_koneksi() -> str:
    from ..repos import settings as settings_repo
    return settings_repo.get("montase.ai_koneksi", "") or ""


def catat_dan_periksa(pid: int, *, kode: str, nama: str, permintaan: str, asal: str,
                      kanvas: dict, durasi: Optional[int], komponen_id: Optional[str] = None,
                      alasan: str = "", jalur: str = "api", model: str = "",
                      taruh_di: Optional[float] = None) -> dict:
    """Satu versi baru: dicatat, diperiksa, dan statusnya diperbarui."""
    baris = repo.catat_komponen(pid, {
        "id": komponen_id, "nama": nama, "asal": asal, "sumber_tsx": kode,
        "durasi_bawaan": durasi, "permintaan": permintaan, "status": "draf",
    })
    folder = periksa.folder_gambar(baris["id"], baris["versi"])
    hasil = periksa.periksa(kode, kanvas=kanvas, durasi=durasi or 2 * kanvas.get("fps", 30),
                            pid=pid, simpan_ke=folder)
    catatan = {"masalah": hasil.get("masalah", []), "peringatan": hasil.get("peringatan", []),
               "tahap": hasil.get("tahap"), "alasan": alasan, "jalur": jalur, "model": model,
               "gambar": len(hasil.get("gambar", [])), "taruh_di": taruh_di}
    repo.perbarui_komponen(pid, baris["id"], baris["versi"],
                           status="lolos" if hasil.get("lolos") else "gagal",
                           hasil_js=hasil.get("js"), catatan=catatan)
    return repo.ambil_komponen(pid, baris["id"], baris["versi"])


def pesan_perbaikan(versi: dict) -> str:
    """Untuk salin-tempel: galat pemeriksa sebagai pesan ke chat yang sama."""
    c = versi.get("catatan") or {}
    return ("Pemeriksa OmniClip menolak kode tadi. Perbaiki semua masalah ini lalu kirim "
            "kedua blok (```tsx dan ```json) lagi:\n- " + "\n- ".join(c.get("masalah") or ["(tanpa rincian)"]))


def buat_lewat_ai(pid: int, permintaan: str, *, dokumen: Optional[dict], durasi: Optional[int],
                  fakta: Optional[dict] = None, komponen_id: Optional[str] = None,
                  kabar=None, batal=None) -> dict:
    """
    Jalur API (M4.3): AI menulis, pemeriksa menilai, galat dikirim balik
    paling banyak dua kali. Revisi (M4.6) bila `komponen_id` diberikan: kode
    versi terakhir ikut dikirim dan hasilnya versi berikutnya.
    """
    kanvas = _kanvas(dokumen)
    kode_lama = None
    if komponen_id:
        lama = repo.ambil_komponen(pid, komponen_id, dengan_kode=False)
        kode_lama = (lama or {}).get("sumber_tsx")
    sistem = motion_ai.sistem(kanvas)
    utamakan = setelan_koneksi() or None
    galat: Optional[list[str]] = None
    versi = None
    for i in range(motion_ai.PERCOBAAN):
        if kabar:
            kabar(0.1 + 0.25 * i, "Meminta AI menulis animasi" if i == 0 else f"Perbaikan ke-{i}")
        teks_pesan = motion_ai.pesan(permintaan, kanvas=kanvas, durasi=durasi,
                                     fakta=(fakta or {}).get("teks"), kode_lama=kode_lama, galat=galat)
        jawab, model, _pakai = motion_ai.tanya(sistem, teks_pesan, utamakan=utamakan, batal=batal)
        if not jawab["kode"].strip():
            galat = ["Balasan tidak berisi kode komponen."]
            continue
        if kabar:
            kabar(0.4 + 0.2 * i, "Memeriksa animasi")
        taruh = motion_ai.tempel_ke_bukti(jawab.get("taruh_di"), (fakta or {}).get("bukti", []))
        versi = catat_dan_periksa(pid, kode=jawab["kode"], nama=jawab["nama"], permintaan=permintaan,
                                  asal="ai", kanvas=kanvas, durasi=jawab.get("durasi") or durasi,
                                  komponen_id=komponen_id or (versi or {}).get("id"),
                                  alasan=jawab["alasan"], jalur="api", model=model, taruh_di=taruh)
        if versi["status"] == "lolos":
            break
        galat = (versi.get("catatan") or {}).get("masalah")
        kode_lama = jawab["kode"]
    if versi is None:
        raise motion_ai.GagalAi("AI tidak mengirim kode yang bisa diperiksa.")
    if versi["status"] == "lolos":
        gambar = periksa.gambar_base64(_jalur_gambar(versi))
        nilai = motion_ai.nilai_bingkai(permintaan, gambar, utamakan=utamakan)
        if nilai is not None:
            c = dict(versi.get("catatan") or {})
            c["penilaian"] = nilai
            if not nilai["sesuai"]:
                c.setdefault("peringatan", []).append("Penilai AI: " + nilai["catatan"])
            repo.perbarui_komponen(pid, versi["id"], versi["versi"], catatan=c)
            versi = repo.ambil_komponen(pid, versi["id"], versi["versi"])
    if motion_ai.hanya_lokal():
        c = dict(versi.get("catatan") or {})
        c.setdefault("peringatan", []).append(
            "Hanya AI lokal yang tersedia: model kecil jarang menulis kode animasi yang baik.")
        repo.perbarui_komponen(pid, versi["id"], versi["versi"], catatan=c)
        versi = repo.ambil_komponen(pid, versi["id"], versi["versi"])
    return versi


def dari_tempelan(pid: int, balasan: str, *, permintaan: str, dokumen: Optional[dict],
                  durasi: Optional[int], komponen_id: Optional[str] = None,
                  fakta: Optional[dict] = None) -> dict:
    """Jalur salin-tempel (M4.10): balasan Claude.ai diperiksa dengan pemeriksa yang sama."""
    jawab = motion_ai.uraikan(balasan)
    taruh = motion_ai.tempel_ke_bukti(jawab.get("taruh_di"), (fakta or {}).get("bukti", []))
    versi = catat_dan_periksa(pid, kode=jawab["kode"], nama=jawab["nama"], permintaan=permintaan,
                              asal="ai", kanvas=_kanvas(dokumen), durasi=jawab.get("durasi") or durasi,
                              komponen_id=komponen_id, alasan=jawab["alasan"], jalur="salin_tempel",
                              taruh_di=taruh)
    if versi["status"] != "lolos":
        versi["pesan_perbaikan"] = pesan_perbaikan(versi)
    return versi


def _jalur_gambar(versi: dict) -> list[str]:
    folder = periksa.folder_gambar(versi["id"], versi["versi"])
    return [str(p) for p in sorted(folder.glob("bingkai_*.jpg"))]


def jumlah_gambar(versi: dict) -> int:
    return len(_jalur_gambar(versi))


# --- pekerjaan antrean ---------------------------------------------------------

def _dokumen(pid: int, proyek_id: Optional[str]) -> Optional[dict]:
    if not proyek_id:
        return None
    p = repo.ambil_proyek(pid, proyek_id)
    return p["dokumen"] if p else None


def run_motion(ctx):
    """Pekerjaan `montase_motion` (lajur net): buat/revisi lewat AI, atau periksa tempelan."""
    from ..errors import InvalidInput
    p = ctx.payload
    pid = int(p.get("profil_id") or profil.kini())
    dokumen = _dokumen(pid, p.get("proyek_id"))
    fakta = None
    if dokumen and p.get("rentang"):
        r = p["rentang"]
        ctx.progress(0.03, stage="fakta", message="Membaca isi video di rentang itu")
        try:
            fakta = motion_ai.lembar_fakta(pid, dokumen, int(r["mulai"]), int(r["durasi"]))
        except Exception as e:      # noqa: BLE001 - lembar fakta pelengkap, bukan syarat
            log.warning("Lembar fakta gagal: %s", str(e)[:200])
    try:
        if p.get("mode") == "tempel":
            ctx.progress(0.2, stage="periksa", message="Memeriksa animasi")
            versi = dari_tempelan(pid, p["balasan"], permintaan=p.get("permintaan", ""),
                                  dokumen=dokumen, durasi=p.get("durasi"),
                                  komponen_id=p.get("komponen_id"), fakta=fakta)
        else:
            versi = buat_lewat_ai(pid, p["permintaan"], dokumen=dokumen, durasi=p.get("durasi"),
                                  fakta=fakta, komponen_id=p.get("komponen_id"),
                                  kabar=lambda f, m: ctx.progress(f, stage="ai", message=m),
                                  batal=lambda: ctx.cancelled)
    except motion_ai.GagalAi as e:
        raise InvalidInput(str(e)) from e
    versi["gambar"] = jumlah_gambar(versi)
    return versi


def mulai(payload: dict) -> str:
    from ..services.jobs import queue
    pid = profil.kini()
    job_id, _ = queue.enqueue("montase_motion", {**payload, "profil_id": pid}, lane="net")
    return job_id
