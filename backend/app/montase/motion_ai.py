"""
AI pembuat animasi Montase (JOB-4 M4.3, M4.6, M4.7, M4.10).

Satu format permintaan dan balasan untuk DUA jalur:
  - API: koneksi AI di Pengaturan, urutan K-12 (Claude -> Gemini ->
    OpenRouter -> lokal, sesuai urutan yang dipilih pemilik), dengan setelan
    "AI untuk Montase" untuk mengutamakan satu koneksi;
  - salin-tempel: pengguna menempel permintaan yang sama ke Project Claude.ai
    (atau chat AI lain) lalu menempel balasannya kembali.
Pemeriksa (periksa.py), panel properti, dan pustaka tidak tahu jalur mana
yang dipakai.

Prompt sistem: kontrak (kontrak_komponen.md) + panduan singkat Remotion +
contoh dari pustaka bawaan + konteks proyek (kanvas, durasi, font, zona
aman). Bagian yang panjang dan tetap ditaruh di depan supaya bisa di-cache
penyedia yang mendukungnya.

Revisi (M4.6) = permintaan baru yang membawa kode versi sebelumnya; hasilnya
versi baru, bukan penimpaan. Lembar fakta video (M4.7) = kata yang diucapkan,
momen tawa/kejut, warna dominan di rentang terpilih, dikirim sebagai teks.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Callable, Optional

from ..config import BUNDLE_DIR, FROZEN, PROJECT_DIR
from . import teks

log = logging.getLogger("omniclip.montase.motion_ai")

VERSI_KONTRAK = 1
PERCOBAAN = 3          # satu percobaan + paling banyak dua perbaikan (M4.3)
TEMPEL_DETIK = 2.0     # animasi ditaruh di bukti terdekat, paling jauh ±2 detik

CONTOH = ("HitungMundur.jsx", "LabelNama.jsx", "LingkaranPanah.jsx", "AngkaNaik.jsx")

PANDUAN_REMOTION = """\
Panduan singkat Remotion 4 (yang dipakai di sini):
- `useCurrentFrame()` = bingkai sekarang (0 di awal item). `useVideoConfig()` =
  {fps, width, height, durationInFrames}.
- `interpolate(frame, [a, b], [x, y], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing})`.
- `spring({frame, fps, config: {damping, stiffness, mass}, delay})` menghasilkan 0..1 (bisa
  melewati 1 sedikit); untuk masuk yang memantul.
- `Easing.in/out/inOut(Easing.cubic)`, `Easing.bezier(...)`, `Easing.back(1.7)`.
- `random("benih")` angka 0..1 yang SAMA setiap render; pakai benih berbeda per elemen.
- `<AbsoluteFill>` lapisan selebar kanvas; `<Sequence from={n} durationInFrames={m}>` untuk
  menunda bagian dalam; `<Series>` untuk urutan.
- `@remotion/shapes`: `<Circle radius>`, `<Rect>`, `<Star>`, `<Triangle>`, `<Pie>` (SVG).
- `@remotion/paths`: `evolvePath(progress, d)` -> {strokeDasharray, strokeDashoffset} untuk
  garis yang menggambar dirinya; `getLength(d)`.
- `@remotion/noise`: `noise2D("benih", x, y)` -1..1 untuk goyangan halus yang deterministik.
- SVG inline (`<svg viewBox>`) untuk bentuk; CSS `transform`, `opacity`, `filter` diatur
  dari nilai bingkai.
"""


class GagalAi(Exception):
    pass


# --- bahan prompt ---------------------------------------------------------------

def _folder_contoh() -> Path:
    if FROZEN:
        return BUNDLE_DIR / "montase_contoh"
    return PROJECT_DIR / "frontend" / "src" / "features" / "montase" / "komposisi" / "motion"


def _zona(kanvas: dict) -> str:
    # Sama dengan frontend/src/features/montase/pratinjau/zonaAman.js.
    if kanvas.get("tinggi", 1920) > kanvas.get("lebar", 1080):
        return "kiri 6%, kanan 16%, atas 10%, bawah 22% (video tegak)"
    return "5% di setiap tepi"


def kontrak(kanvas: Optional[dict] = None) -> str:
    """Teks kontrak (kontrak_komponen.md) dengan font dan zona aman terisi."""
    k = kanvas or {"lebar": 1080, "tinggi": 1920}
    sumber = (Path(__file__).with_name("kontrak_komponen.md")).read_text(encoding="utf-8")
    font = ", ".join(f["keluarga"] for f in teks.font_bawaan() if teks.jalur_font(f["keluarga"]))
    return (sumber.replace("{VERSI_KONTRAK}", str(VERSI_KONTRAK)).replace("{FONT}", font)
            .replace("{ZONA}", _zona(k)))


def contoh() -> str:
    bagian = []
    for nama in CONTOH:
        p = _folder_contoh() / nama
        try:
            bagian.append(f"### {nama}\n\n```jsx\n{p.read_text(encoding='utf-8').strip()}\n```")
        except OSError:
            continue
    return "\n\n".join(bagian)


def sistem(kanvas: Optional[dict] = None) -> str:
    return (kontrak(kanvas) + "\n\n" + PANDUAN_REMOTION
            + "\n\n## Contoh dari pustaka bawaan (sudah lolos pemeriksaan)\n\n" + contoh())


def pesan(permintaan: str, *, kanvas: dict, durasi: Optional[int] = None,
          fakta: Optional[str] = None, kode_lama: Optional[str] = None,
          galat: Optional[list[str]] = None) -> str:
    """Pesan pengguna: permintaan + konteks proyek (+ kode lama untuk revisi, + galat)."""
    fps = kanvas.get("fps", 30)
    baris = [f"Versi kontrak: {VERSI_KONTRAK}",
             f"Kanvas: {kanvas.get('lebar', 1080)}x{kanvas.get('tinggi', 1920)} pada {fps} fps."]
    if durasi:
        baris.append(f"Durasi item: {durasi} bingkai ({durasi / fps:.1f} detik).")
    if fakta:
        baris.append("Lembar fakta rentang video (pakai untuk menyesuaikan isi dan waktu):\n" + fakta)
    if kode_lama:
        baris.append("Kode versi sekarang (ubah sesuai permintaan, pertahankan yang tidak diminta "
                     "berubah):\n```tsx\n" + kode_lama.strip() + "\n```")
        baris.append("Permintaan revisi: " + permintaan.strip())
    else:
        baris.append("Permintaan: " + permintaan.strip())
    if galat:
        baris.append("Versi sebelumnya DITOLAK pemeriksa OmniClip. Perbaiki semua masalah ini "
                     "lalu kirim kode lengkapnya lagi:\n- " + "\n- ".join(galat))
    baris.append("Jawab dengan dua blok (```tsx dan ```json) sesuai kontrak.")
    return "\n\n".join(baris)


# --- membaca balasan ------------------------------------------------------------

_BLOK = re.compile(r"```([a-zA-Z]*)\s*\n(.*?)```", re.S)


def uraikan(balasan: str) -> dict:
    """
    Balasan AI (atau tempelan dari Claude.ai) -> {kode, nama, alasan, durasi,
    taruh_di}. Toleran: blok kode tanpa label bahasa, JSON di luar blok, dan
    teks pembuka/penutup diabaikan.
    """
    if not balasan or not balasan.strip():
        raise GagalAi("Balasannya kosong.")
    blok = _BLOK.findall(balasan)
    kode = next((b for bhs, b in blok if bhs.lower() in ("tsx", "jsx", "ts", "js", "typescript",
                                                         "javascript")), None)
    if kode is None:
        kode = next((b for bhs, b in blok if "export default" in b), None)
    if kode is None and "export default" in balasan:
        kode = balasan
    if not kode:
        raise GagalAi("Tidak ada blok kode komponen (```tsx) di balasan.")
    meta = {}
    teks_json = next((b for bhs, b in blok if bhs.lower() == "json"), None)
    if teks_json is None:
        m = re.search(r"\{[^{}]*\"nama\"[^{}]*\}", balasan)
        teks_json = m.group(0) if m else None
    if teks_json:
        try:
            meta = json.loads(teks_json)
        except ValueError:
            meta = {}
    return {
        "kode": kode.strip() + "\n",
        "nama": str(meta.get("nama") or "Animasi AI")[:80],
        "alasan": str(meta.get("alasan") or "")[:500],
        "durasi": int(meta["durasi"]) if str(meta.get("durasi", "")).isdigit() else None,
        "taruh_di": float(meta["taruh_di"]) if isinstance(meta.get("taruh_di"), (int, float)) else None,
    }


# --- lembar fakta video (M4.7) ---------------------------------------------------

def _warna_dominan(jalur: Path, detik: float) -> Optional[str]:
    r = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0.0, detik):.2f}", "-i", str(jalur),
                        "-frames:v", "1", "-vf", "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True, timeout=30)
    if r.returncode != 0 or len(r.stdout) < 3:
        return None
    return "#%02X%02X%02X" % tuple(r.stdout[:3])


def lembar_fakta(pid: int, dokumen: dict, mulai: int, durasi: int) -> dict:
    """
    Fakta rentang [mulai, mulai+durasi) bingkai: kata yang diucapkan (lajur
    subtitle, atau kata.json bahan yang sudah disalin), momen tawa/kejut/sorak
    (momen.py, bila bisa dihitung), dan warna dominan. Mengembalikan
    {"teks": ringkasan untuk AI, "bukti": [{t, jenis}] dalam detik dari awal rentang}.
    """
    from . import bahan as bahan_svc
    from . import subtitle

    fps = dokumen["kanvas"]["fps"]
    akhir = mulai + durasi
    baris, bukti = [], []
    kata = []
    for l in dokumen["lajur"]:
        if not l.get("subtitle"):
            continue
        for i in l["item"]:
            for k in i.get("kata") or []:
                t = i["mulai"] + k["t"]
                if mulai <= t < akhir:
                    kata.append((t, k["w"]))
    if not kata:
        for item, _l in subtitle._bersuara(dokumen):
            f = bahan_svc.folder(item["bahan"]) / "kata.json"
            if not f.is_file():
                continue
            try:
                daftar = json.loads(f.read_text(encoding="utf-8")).get("kata", [])
            except ValueError:
                continue
            for w in subtitle.ke_linimasa(daftar, item, fps):
                if mulai <= w["t"] < akhir:
                    kata.append((w["t"], w["w"]))
    if kata:
        kata.sort()
        baris.append("Kata yang diucapkan (detik dari awal rentang): " + " ".join(
            f"[{(t - mulai) / fps:.1f}] {w}" for t, w in kata[:200]))
        for t, w in kata:
            if w.endswith(("!", "?")):
                bukti.append({"t": (t - mulai) / fps, "jenis": "seru"})

    for l in dokumen["lajur"]:
        if l["jenis"] != "video" or l.get("sembunyi"):
            continue
        for item in l["item"]:
            if item["jenis"] != "video" or item["mulai"] >= akhir or item["mulai"] + item["durasi"] <= mulai:
                continue
            jalur = bahan_svc.jalur_asli(pid, item.get("bahan") or "")
            if jalur is None:
                continue
            k = float(item.get("kecepatan") or 1)
            a = max(mulai, item["mulai"])
            b = min(akhir, item["mulai"] + item["durasi"])
            s0 = ((item.get("potong_awal") or 0) + (a - item["mulai"]) * k) / fps
            s1 = ((item.get("potong_awal") or 0) + (b - item["mulai"]) * k) / fps
            warna = _warna_dominan(jalur, (s0 + s1) / 2)
            if warna:
                baris.append(f"Warna dominan bingkai: {warna}")
            try:
                from ..services import momen
                hasil = momen.cari_momen(jalur, [{"start": s0, "end": s1}], dengar=True)
            except Exception as e:      # noqa: BLE001 - model suara tidak ada, berkas aneh
                log.info("Momen tidak terhitung: %s", str(e)[:160])
                hasil = []
            for m in hasil:
                t = (a - mulai) / fps + m["t"] / k
                bukti.append({"t": round(t, 2), "jenis": "+".join(m["jenis"])})
            break
    if bukti:
        baris.append("Momen terdengar (detik dari awal rentang): " + ", ".join(
            f"{b['t']:.1f} {b['jenis']}" for b in bukti[:30]))
    baris.append(f"Rentang: {durasi / fps:.1f} detik.")
    return {"teks": "\n".join(baris), "bukti": bukti}


def tempel_ke_bukti(taruh_di: Optional[float], bukti: list[dict]) -> Optional[float]:
    """Waktu usulan AI ditempelkan ke bukti terdekat, paling jauh ±2 detik."""
    if taruh_di is None:
        return None
    dekat = min(bukti, key=lambda b: abs(b["t"] - taruh_di), default=None)
    if dekat is not None and abs(dekat["t"] - taruh_di) <= TEMPEL_DETIK:
        return dekat["t"]
    return taruh_di


# --- jalur API ----------------------------------------------------------------

SKEMA_JAWABAN = {
    "type": "OBJECT",
    "properties": {
        "kode": {"type": "STRING", "description": "seluruh kode komponen TSX"},
        "nama": {"type": "STRING"},
        "alasan": {"type": "STRING"},
        "durasi": {"type": "INTEGER"},
        "taruh_di": {"type": "NUMBER"},
    },
    "required": ["kode", "nama", "alasan", "durasi"],
}


def hanya_lokal() -> bool:
    from ..services import koneksi_ai
    rantai = koneksi_ai.rantai()
    return bool(rantai) and all(k["penyedia"] in ("lokal", "kustom") for k in rantai)


def tanya(sistem_teks: str, pesan_teks: str, *, utamakan: Optional[str] = None,
          kabar: Optional[Callable[[str], None]] = None, batal=None) -> tuple[dict, str, dict]:
    from ..services import penyedia_ai
    if not penyedia_ai.ada_ai():
        raise GagalAi("Belum ada koneksi AI. Tambahkan di Pengaturan > AI, atau pakai mode "
                      "salin-tempel dengan Claude.ai.")
    with penyedia_ai.pekerjaan("montase_animasi"):
        data, model, pakai = penyedia_ai.tanya(
            [{"teks": pesan_teks}], schema=SKEMA_JAWABAN, sistem=sistem_teks, api_key="", models=[],
            suhu=0.4, maks_keluaran=16000, kabar=kabar, batal=batal, utamakan=utamakan)
    hasil = {
        "kode": str(data.get("kode") or ""),
        "nama": str(data.get("nama") or "Animasi AI")[:80],
        "alasan": str(data.get("alasan") or "")[:500],
        "durasi": int(data["durasi"]) if isinstance(data.get("durasi"), (int, float)) else None,
        "taruh_di": float(data["taruh_di"]) if isinstance(data.get("taruh_di"), (int, float)) else None,
    }
    # Sebagian model tetap membungkus kode dengan pagar walau diminta JSON.
    if "```" in hasil["kode"]:
        try:
            hasil["kode"] = uraikan(hasil["kode"])["kode"]
        except GagalAi:
            pass
    return hasil, model, pakai


def nilai_bingkai(permintaan: str, gambar: list[bytes], *, utamakan: Optional[str] = None) -> Optional[dict]:
    """Langkah 5 pemeriksaan: AI yang bisa melihat menilai bingkai contoh. None bila tidak ada."""
    from ..services import koneksi_ai, penyedia_ai
    if not gambar or not koneksi_ai.rantai(butuh_gambar=True):
        return None
    skema = {"type": "OBJECT", "properties": {"sesuai": {"type": "BOOLEAN"}, "catatan": {"type": "STRING"}},
             "required": ["sesuai", "catatan"]}
    bahan = [{"teks": f"Permintaan animasi: {permintaan}\nIni lima bingkai contohnya (10-90% durasi). "
                      "Apakah isinya sesuai permintaan? Catatan singkat, satu kalimat."}]
    bahan += [{"gambar": g, "mime": "image/jpeg"} for g in gambar[:5]]
    try:
        with penyedia_ai.pekerjaan("montase_animasi_nilai"):
            data, _m, _p = penyedia_ai.tanya(bahan, schema=skema, sistem="Kamu penilai animasi video.",
                                             api_key="", models=[], suhu=0.1, maks_keluaran=400,
                                             utamakan=utamakan)
        return {"sesuai": bool(data.get("sesuai")), "catatan": str(data.get("catatan") or "")[:300]}
    except Exception as e:      # noqa: BLE001 - penilaian hanya peringatan
        log.info("Penilaian bingkai dilewati: %s", str(e)[:160])
        return None


# --- paket Project Claude (M4.10) -------------------------------------------------

INSTRUKSI_PROJECT = """\
Kamu adalah penulis animasi untuk OmniClip Montase. Setiap pesan berisi permintaan
animasi dan konteks proyek dari OmniClip. Balas SELALU dengan tepat dua blok: satu
blok ```tsx berisi seluruh kode komponen, dan satu blok ```json berisi
{"nama", "alasan", "durasi"} (bisa ditambah "taruh_di"). Ikuti berkas "Kontrak
OmniClip Montase" di Project knowledge dengan ketat. Kalau pesan berisi daftar
masalah dari pemeriksa OmniClip, perbaiki semuanya dan kirim kode lengkapnya lagi.
"""


def paket_claude() -> str:
    """Satu berkas .md untuk Project Claude.ai: instruksi + kontrak + contoh."""
    return (f"# Paket Project Claude untuk OmniClip Montase (versi {VERSI_KONTRAK})\n\n"
            "## 1. Tempel bagian ini ke *Project instructions*\n\n"
            f"```text\n{INSTRUKSI_PROJECT}```\n\n"
            "## 2. Unggah berkas ini ke *Project knowledge*\n\n"
            "Isi di bawah ini adalah kontraknya. Kalau OmniClip memberi tahu versi paket "
            "berubah, unduh ulang dan ganti berkas ini.\n\n---\n\n"
            + sistem() + "\n")
