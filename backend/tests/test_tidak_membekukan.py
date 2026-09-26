"""
Tidak ada pekerjaan lambat yang dipanggil langsung di dalam fungsi async.

Satu pemanggilan sinkron yang lambat di dalam `async def` membekukan SELURUH
server, bukan hanya permintaan itu: event loop hanya satu, dan selama ia
tertahan tidak ada permintaan lain yang dijawab. Terukur 26 September 2026:
`/api/video-info` memanggil `get_video_info` langsung, dan `/api/settings` —
yang biasanya menjawab dalam 0,00 detik — menjadi 4,83 detik karena harus
menunggu di belakangnya. Membuka satu video membuat semua tab lain ikut diam,
dan beberapa video berbarengan menumpuk sampai peramban kehabisan sambungan.
Itulah "terkadang macet dan gagal, harus refresh dulu, bahkan dengan wifi yang
kencang" yang dilaporkan pemiliknya.

Sesudah diperbaiki: 0,07 detik untuk permintaan yang sama, di saat yang sama.

Uji ini membaca kode, bukan menjalankannya. Daftar di bawah adalah fungsi yang
TERUKUR lambat atau menghubungi jaringan; menambahkannya ke sana menjaganya.
"""

import ast
import unittest
from pathlib import Path

ROUTERS = Path(__file__).resolve().parents[1] / "app" / "routers"

# Fungsi yang terukur lambat, dengan alasannya.
LAMBAT = {
    "get_video_info": "±5 detik, menghubungi YouTube",
    "search_youtube_videos": "1-4 detik, menghubungi YouTube",
    "get_best": "171 milidetik, mengurai transkrip utuh",
    "cek": "sampai 20 detik, menghubungi GitHub",
    "urlopen": "jaringan, batas waktunya 20-25 detik",
    "deteksi_facecam_waktu": "detik-detik, membaca video",
    "plan_reframe": "detik-detik, membaca video",
}


def _dibungkus(baris: str) -> bool:
    return "to_thread" in baris or "run_in_executor" in baris


class TidakMembekukanServer(unittest.TestCase):
    def test_tidak_ada_pemanggilan_lambat_langsung(self):
        temuan = []
        for f in sorted(ROUTERS.glob("*.py")):
            teks = f.read_text(encoding="utf-8")
            baris = teks.splitlines()
            pohon = ast.parse(teks)
            for fn in ast.walk(pohon):
                if not isinstance(fn, ast.AsyncFunctionDef):
                    continue
                # Fungsi bersarang biasa dijalankan lewat to_thread oleh
                # pemanggilnya; isinya bukan bagian dari event loop.
                bersarang = {id(n) for d in ast.walk(fn)
                             if isinstance(d, (ast.FunctionDef, ast.Lambda)) and d is not fn
                             for n in ast.walk(d)}
                for n in ast.walk(fn):
                    if id(n) in bersarang or not isinstance(n, ast.Call):
                        continue
                    nama = getattr(n.func, "id", None) or getattr(n.func, "attr", None)
                    if nama in LAMBAT and not _dibungkus(baris[n.lineno - 1]):
                        temuan.append(f"{f.name}:{n.lineno} {fn.name} memanggil "
                                      f"{nama} langsung ({LAMBAT[nama]})")
        self.assertEqual(temuan, [], "\n" + "\n".join(temuan))

    def test_setiap_pemakai_asyncio_bisa_mengimpornya(self):
        """
        `py_compile` tidak menangkap nama yang belum diimpor. Memindahkan
        pemanggilan ke `asyncio.to_thread` di fungsi yang tidak mengimpor
        `asyncio` baru meledak saat dijalankan — tertangkap empat kali saat
        perbaikan ini dikerjakan, salah satunya tombol Simpan.
        """
        salah = []
        for f in sorted(ROUTERS.glob("*.py")):
            pohon = ast.parse(f.read_text(encoding="utf-8"))
            modul = any(isinstance(n, ast.Import) and any(a.name == "asyncio" for a in n.names)
                        for n in pohon.body)
            for fn in ast.walk(pohon):
                if not isinstance(fn, ast.AsyncFunctionDef):
                    continue
                pakai = any(isinstance(n, ast.Attribute) and getattr(n.value, "id", "") == "asyncio"
                            for n in ast.walk(fn))
                lokal = any(isinstance(n, ast.Import) and any(a.name == "asyncio" for a in n.names)
                            for n in ast.walk(fn))
                if pakai and not (modul or lokal):
                    salah.append(f"{f.name}:{fn.lineno} {fn.name}")
        self.assertEqual(salah, [])

    def test_info_video_disimpan(self):
        """Dulu SAMA lambatnya pada panggilan kedua: 5,0 detik, tiap kali."""
        sumber = (ROUTERS / "videos.py").read_text(encoding="utf-8")
        badan = sumber.split("async def video_info")[1].split("\n@router")[0]
        self.assertIn("cache_repo.ambil", badan)
        self.assertIn("cache_repo.simpan", badan)
        # Tapi ada-tidaknya berkas lokal TIDAK ikut disimpan: video yang
        # barusan selesai diunduh harus langsung terlihat terunduh.
        self.assertIn("find_local_video, video_id", badan)


class ResolusiBawaan(unittest.TestCase):
    """
    Bawaan unduhan 1080p, dari satu sumber.

    Dulu "Terbaik" (sampai 2160p): terukur 42 video, 37,9 GB, terbesar 3,99 GB,
    dan pengguna mengeluh "video yang didownload terlalu besar hingga proses
    lama". Angka bawaannya dulu ditulis di tiga tempat berbeda.
    """

    def test_satu_sumber(self):
        from app.services.ytdlp import RESOLUSI_BAWAAN
        self.assertEqual(RESOLUSI_BAWAAN, "1080p")
        for f in ("clips.py", "videos.py"):
            sumber = (ROUTERS / f).read_text(encoding="utf-8")
            self.assertNotIn('str = "Terbaik"', sumber, f)

    def test_permintaan_tanpa_resolusi_memakai_bawaan(self):
        from app.routers.clips import AutoClipRequest
        from app.routers.videos import DownloadRequest
        self.assertEqual(AutoClipRequest(video_id="x").quality, "1080p")
        self.assertEqual(DownloadRequest(url="x").resolution, "1080p")


if __name__ == "__main__":
    unittest.main()


class KotakCariSepertiYouTube(unittest.TestCase):
    """
    Riwayat pencarian tampil sebagai dropdown yang menempel di bawah kotak cari,
    bukan deretan chip di bawah seluruh formulir. Diminta pemiliknya: "buat
    search bar itu mirip milik youtube atau google karena lebih bagus seperti
    itu dan clean".
    """

    HOME = Path(__file__).resolve().parents[2] / "frontend" / "src" / "routes" / "Home.jsx"

    def test_dropdown_dengan_papan_ketik(self):
        jsx = self.HOME.read_text(encoding="utf-8")
        self.assertIn('role="combobox"', jsx)
        self.assertIn('role="listbox"', jsx)
        for tombol in ("ArrowDown", "ArrowUp", "Escape"):
            self.assertIn(tombol, jsx)

    def test_klik_saran_tidak_hilang(self):
        """
        Menekan saran lebih dulu melepas fokus dari kotaknya. Dulu jeda 180
        milidetik dipakai supaya tekanannya sempat sampai, dan klik yang sedikit
        lebih lambat hilang begitu saja. `onMouseDown` + `preventDefault`
        menjalankan pilihannya sebelum fokus lepas.
        """
        jsx = self.HOME.read_text(encoding="utf-8")
        self.assertIn("onMouseDown={(e) => { e.preventDefault(); pilihSaran(r.query); }}", jsx)
        self.assertNotIn("setTimeout(() => setCariAktif(false), 180)", jsx)

    def test_pencarian_otomatis_tidak_masuk_riwayat(self):
        """
        Panel video terkait mencari dengan "nama kanal + empat kata judul".
        Tanpa `catat=0`, tiap video yang dibuka menambah baris riwayat yang tidak
        pernah diketik siapa pun — terlihat di dropdown sebagai "Windah Basudara
        AKU HARUS LINDUNGI PRESIDENT" dan sejenisnya.
        """
        watch = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "routes"
                 / "Watch.jsx").read_text(encoding="utf-8")
        self.assertIn("&limit=15&catat=0", watch)
        sumber = (ROUTERS / "videos.py").read_text(encoding="utf-8")
        self.assertIn("if limit <= 20 and catat:", sumber)


class GaleriGayaJudul(unittest.TestCase):
    """
    Tiap gaya judul memperlihatkan dirinya. Dulu hanya nama dan satu kalimat,
    jadi satu-satunya cara tahu rupa "Stiker dilempar" adalah memilihnya lalu
    memutar pratinjau klip. Diminta pemiliknya: "buatkan juga preview
    tampilannya seperti apa agar jelas saat kita memilih".
    """

    PANEL = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "features"
             / "studio" / "TitlePanel.jsx")

    def test_contoh_memakai_gaya_dan_gerak_yang_sama(self):
        jsx = self.PANEL.read_text(encoding="utf-8")
        self.assertIn("function ContohGaya", jsx)
        badan = jsx.split("function ContohGaya")[1].split("\nexport default")[0]
        # CSS dan gerak diambil dari entri yang SAMA dengan pratinjau klip.
        self.assertIn("v.css(", badan)
        self.assertIn("v.anim", badan)
        # Gerak diputar ulang saat disentuh: `key` yang berubah membuat
        # elemennya lahir ulang.
        self.assertIn("key={putar}", badan)
        self.assertIn("onMouseEnter", badan)

    def test_judul_klip_sendiri_yang_dipakai(self):
        jsx = self.PANEL.read_text(encoding="utf-8")
        self.assertIn("teks={cardText ||", jsx)
