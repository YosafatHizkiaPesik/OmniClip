"""
Pekerjaan latar Montase di antrean `jobs.py`.

  montase_siapkan    lajur net  mengunduh Node (bila perlu) dan Chrome Headless Shell
  montase_uji_render lajur cpu  merender dokumen uji Tahap 0 dan mengukur waktunya

Render memegang `giliran_cpu` seperti render klip: Chrome headless memakai
semua inti yang diberikan, dan berebut dengan Whisper atau render lain hanya
membuat keduanya lebih lambat.
"""

from __future__ import annotations

from ..config import PORT
from . import mesin, unduh, uji


def run_siapkan(ctx):
    if not unduh.jalur_node_terunduh() and not mesin.jalur_node():
        unduh.pasang_node(lambda f: ctx.progress(0.4 * f, stage="node",
                                                 message="Mengunduh Node"))
    ctx.check_cancelled()
    ctx.progress(0.4, stage="browser", message="Menyiapkan Chrome Headless Shell")

    def kabar(baris):
        if "unduh" in baris:
            ctx.progress(0.4 + 0.6 * float(baris["unduh"]), stage="browser",
                         message="Mengunduh Chrome Headless Shell")

    hasil = mesin.siapkan_browser(kabar)
    return {"status": mesin.status(), "browser": hasil}


def run_uji_render(ctx):
    ctx.giliran_cpu(lambda: ctx.progress(0.0, stage="antre",
                                         message="Menunggu giliran render"))

    def kabar(baris):
        if "kemajuan" in baris:
            ctx.progress(float(baris["kemajuan"]), stage="render",
                         message=f"Bingkai {baris.get('bingkai', 0)} dari {baris.get('total', '?')}")
        elif baris.get("tahap"):
            ctx.progress(0.0, stage="render", message="Menyiapkan render")

    return uji.render(f"http://127.0.0.1:{PORT}", kabar=kabar, batal=lambda: ctx.cancelled)
