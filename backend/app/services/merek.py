"""
Identitas kanal: intro dan outro bermerek per akun (JOB-2 F2-5).

Klip dari mesin yang sama terlihat sama di ribuan kanal. Yang membuat penonton
mengenali "ini klip dari kanal X" adalah bagian yang SELALU sama di kanal itu
dan tidak ada di kanal lain: penutup dengan nama kanalnya, cuplikan pembuka
yang sama, gaya yang konsisten. Itu juga yang disebut kebijakan YouTube
sebagai "unik untuk kanal tersebut".

Tiga bagian, semuanya pilihan, disimpan di setelan akun (kelompok `merek`):

  outro_teks  kartu teks di atas bingkai terakhir yang dibekukan, misalnya
              "Ikuti @kanal untuk klip lainnya". Tidak butuh berkas apa pun.
  intro       id aset video atau gambar dari pustaka Sisipan. DIBATASI
              `INTRO_MAKS` detik: di video pendek, detik pertama menentukan
              apakah orang bertahan, dan intro panjang adalah cara tercepat
              kehilangan mereka. Bawaannya kosong.
  outro       id aset video atau gambar, disambung paling akhir.

Bagian merek TIDAK dihitung sebagai nilai tambah (F3-1): ia sama di setiap
klip, jadi justru bukan transformasi atas klip itu.
"""

from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("omniclip.merek")

INTRO_MAKS = 3.0
OUTRO_MAKS = 8.0
GAMBAR_DETIK = 2.0


def setelan(pid: int) -> dict:
    from ..repos import profil as profil_repo
    try:
        return dict(profil_repo.setelan(pid, "merek") or {})
    except Exception:                            # noqa: BLE001
        return {}


def _aset(aset_id: str, maks: float) -> Optional[dict]:
    from . import aset as aset_svc

    aset_id = (aset_id or "").strip()
    if not aset_id:
        return None
    path = aset_svc.jalur(aset_id)
    info = aset_svc.info(aset_id) if path else None
    if path is None or not info or info.get("jenis") not in ("video", "gambar"):
        log.warning("Aset merek %r tidak ditemukan atau bukan video/gambar", aset_id)
        return None
    if info["jenis"] == "gambar":
        d = min(maks, GAMBAR_DETIK)
    else:
        d = min(maks, float(info.get("durasi") or 0.0))
    if d <= 0.2:
        return None
    return {"path": path, "jenis": info["jenis"], "d": round(d, 3),
            "punya_suara": bool(info.get("punya_suara"))}


def siapkan(merek: Optional[dict]) -> dict:
    """{intro, outro, outro_teks} yang benar-benar bisa dipakai."""
    m = merek or {}
    if m.get("aktif") is False:
        return {"intro": None, "outro": None, "outro_teks": ""}
    teks = " ".join(str(m.get("outro_teks") or "").split())[:160]
    return {"intro": _aset(str(m.get("intro") or ""), INTRO_MAKS),
            "outro": _aset(str(m.get("outro") or ""), OUTRO_MAKS),
            "outro_teks": teks}


def komentar_outro(siap: dict) -> list[dict]:
    """Outro teks sebagai komentar penutup bertanda merek (lihat komentar.py)."""
    if not siap.get("outro_teks"):
        return []
    return [{"posisi": "penutup", "teks": siap["outro_teks"], "tampil_teks": True,
             "mode": "bekukan", "merek": True}]


def _potongan(n: int, a: dict, idx: int, out_w: int, out_h: int, fps: int,
              bagian: list[str]) -> tuple[list[str], str, str]:
    """Input dan graf satu intro/outro; mengembalikan (input, label v, label a)."""
    d = a["d"]
    if a["jenis"] == "gambar":
        inp = ["-loop", "1", "-t", f"{d:.3f}", "-i", str(a["path"])]
    else:
        inp = ["-t", f"{d:.3f}", "-i", str(a["path"])]
    bagian.append(
        f"[{idx}:v]scale={out_w}:{out_h}:force_original_aspect_ratio=decrease,"
        f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,"
        f"fps={fps},format=yuv420p,trim=duration={d:.3f},setpts=PTS-STARTPTS[mrv{n}]")
    if a["jenis"] == "video" and a["punya_suara"]:
        bagian.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,"
                      f"apad,atrim=duration={d:.3f},asetpts=PTS-STARTPTS[mra{n}]")
    else:
        bagian.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={d:.3f}[mra{n}]")
    return inp, f"[mrv{n}]", f"[mra{n}]"


def graf_render(siap: dict, vin: str, ain: str, *, input_awal: int, out_w: int,
                out_h: int, fps: int) -> tuple[list[str], str, str, str, float]:
    """(input, graf, label video, label audio, detik tambahan) intro + outro berkas."""
    intro, outro = siap.get("intro"), siap.get("outro")
    if not intro and not outro:
        return [], "", vin, ain, 0.0
    inputs: list[str] = []
    bagian: list[str] = [f"{vin}format=yuv420p,setsar=1[mrU]",
                         f"{ain}aresample=48000,aformat=channel_layouts=stereo[mrUa]"]
    urut: list[str] = []
    idx = input_awal
    tambah = 0.0
    if intro:
        inp, v, a = _potongan(0, intro, idx, out_w, out_h, fps, bagian)
        inputs += inp
        idx += 1
        urut.append(v + a)
        tambah += intro["d"]
    urut.append("[mrU][mrUa]")
    if outro:
        inp, v, a = _potongan(1, outro, idx, out_w, out_h, fps, bagian)
        inputs += inp
        urut.append(v + a)
        tambah += outro["d"]
    bagian.append("".join(urut) + f"concat=n={len(urut)}:v=1:a=1[mrV][mrA]")
    return inputs, ";".join(bagian), "[mrV]", "[mrA]", round(tambah, 3)
