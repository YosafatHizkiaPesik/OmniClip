# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Satu orang: pemilik aplikasi ini, seorang kreator berbahasa Indonesia yang
memotong podcast dan wawancara panjang YouTube menjadi klip vertikal pendek,
lalu mengunggahnya sendiri ke Shorts/Reels/TikTok. Ia menjalankan aplikasinya di
mesinnya sendiri, bukan sebagai layanan untuk orang lain.

Situasinya: satu sesi kerja berarti menonton sebagian video satu sampai dua jam,
memeriksa belasan klip yang ditawarkan mesin, membetulkan yang salah, memotong
sendiri momen yang terlewat, lalu merender beberapa klip sekaligus. Perbaikan
subtitle dan penanda penutur dilakukan baris per baris, puluhan kali per sesi.

*(Disimpulkan dari PRD "Personal Intelligent Clipper" dan dari pemakaian nyata
selama pengembangan; belum dikonfirmasi lewat wawancara terpisah.)*

## Product Purpose

Mengubah video panjang menjadi beberapa klip vertikal siap unggah tanpa membuka
editor video lain. Berhasil bila sebuah podcast satu jam menghasilkan klip-klip
yang benar-benar layak diunggah, dengan subtitle yang benar dan bingkai yang
mengikuti pembicara, dalam satu kali duduk.

## Positioning

Mesin pemilih momennya **tidak pernah mengarang**. Batas klip selalu jatuh di
batas kalimat nyata, setiap baris subtitle adalah kata yang benar-benar
diucapkan, dan skor berasal dari perhitungan yang komponennya bisa dilihat.
Ketika AI tidak tersedia, sistem mengatakannya dan tetap bekerja dengan mesin
heuristik lokal — bukan menyembunyikan kegagalan di balik data karangan.

Semuanya berjalan lokal: video, transkrip, model suara, dan hasil render tidak
pernah meninggalkan mesin pengguna kecuali transkrip yang dikirim ke Gemini saat
penajaman peringkat dinyalakan.

## Operating Context

Dijalankan di mesin pribadi Linux: backend FastAPI di `127.0.0.1:8000`, frontend
Vite di `localhost:5173`. **Karena backend terikat ke localhost, aplikasi ini
saat ini tidak bisa dibuka dari perangkat lain di jaringan yang sama.** Membuka
akses dari HP memerlukan perubahan bind dan CORS — keputusan yang belum diambil.

Anggaran mesin: 8 inti, tanpa GPU, RAM bebas sekitar 2,9 GB. Batas itu
menentukan arsitekturnya: antrean job dengan lane `cpu` berkonkurensi satu,
sehingga transkripsi Whisper dan encoding x264 tidak pernah hidup bersamaan.

Alurnya: cari video → tonton → Clip → pekerjaan berjalan di latar → buka Clip
Studio → sunting → render → berkas tersimpan lokal → diunggah manual oleh
pengguna.

## Capabilities and Constraints

Rute yang ada: `/` (cari), `/watch/:videoId`, `/studio`, `/studio/:videoId`
(editor), `/clips`, `/downloads`, `/settings`.

Kemampuan nyata hari ini:
- Pencarian dan unduhan YouTube lewat yt-dlp, sampai 1080p.
- Transkrip: caption otomatis YouTube (jalur cepat) atau faster-whisper lokal.
- Pemilihan momen: mesin heuristik enam komponen, ditajamkan Gemini bila ada
  API key. Jumlah klip tumbuh mengikuti durasi (±1 klip tiap 4 menit).
- Pemisahan penutur dari warna suara (CAM++ ONNX), jumlahnya bisa disetel
  pengguna bila tebakan otomatis meleset.
- Bingkai mengikuti wajah (YuNet), bilah kabur, potong tengah, atau orisinal.
- Subtitle karaoke per kata dibakar lewat ASS: 13 font display terbundel, warna
  per penutur, animasi, penempatan bebas, lebar kotak teks.
- Editor timeline: gelombang suara, geser batas, gabung potongan dari menit
  lain, klip buatan tangan lewat penanda masuk/keluar, pintasan papan tik.
- Render ffmpeg dengan normalisasi loudness; nama berkas memuat judul video.

Batasan yang mengikat desain:
- Video sumbernya panjang (satu sampai dua jam) dan klipnya banyak (bisa 19–40
  dari satu video). Daftar panjang adalah keadaan normal, bukan kasus tepi.
- Pekerjaan berat berjalan di latar dengan progres nyata dari server; UI tidak
  boleh mengarang teks progres dari angka.
- Gemini opsional dan bisa gagal (kuota, 503). Keadaan "memakai mesin lokal"
  harus terbaca, bukan disembunyikan.
- Pemisahan penutur adalah PERKIRAAN dan bisa meleset; hasilnya selalu bisa
  disunting per baris.

Belum diputuskan: apakah aplikasi akan dibuka dari HP lewat jaringan lokal, atau
"fit untuk HP" hanya berarti tata letak yang rapi di jendela sempit.

## Brand Commitments

Nama produk: **OmniClip AI**. Bahasa antarmuka: Indonesia, seluruhnya.

Tidak ada logo, palet, atau tipografi yang dijadikan pengikat oleh pengguna;
tampilan yang ada sekarang diperlakukan sebagai bukti, bukan otoritas — pengguna
meminta rancang ulang total.

## Evidence on Hand

- `PRD OmniClip.pdf` di root proyek: dokumen produk asli. Sebagian sudah usang
  terhadap kode (menyebut Flutter dan Google Drive multi-akun; keduanya tidak
  dipakai, lapisan Drive dihapus karena hanya simulasi).
- Klip hasil render sungguhan di `OmniClip_Storage/edited_clips/`.
- Video sumber sungguhan di `OmniClip_Storage/local_downloads/`, termasuk
  podcast 69 menit dengan analisis 19 klip tersimpan.
- Tidak ada pengguna lain, tidak ada data penggunaan, tidak ada tolok ukur.
  Ketiadaan itu tidak boleh diisi karangan.

## Product Principles

1. **Jangan pernah mengarang.** Subtitle, batas klip, dan skor selalu berasal
   dari sumber nyata. Bila datanya tidak ada, katakan — jangan isi.
2. **Perkiraan harus terbaca sebagai perkiraan.** Penutur, skor, dan bingkai
   otomatis semuanya tebakan; semuanya bisa dibetulkan tangan.
3. **Kerja berat berjalan di latar.** Pengguna boleh mengantre beberapa video
   dan pergi; progresnya datang dari server.
4. **Lokal lebih dulu.** Berjalan penuh tanpa API key; layanan luar menajamkan,
   bukan menyalakan.
5. **Menyunting adalah pekerjaan utamanya.** Layar tempat memperbaiki subtitle,
   penutur, dan batas klip adalah tempat waktu paling banyak dihabiskan.

## Accessibility & Inclusion

Seluruh teks antarmuka berbahasa Indonesia. Belum ada standar aksesibilitas
yang ditetapkan pengguna.
