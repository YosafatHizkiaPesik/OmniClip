# Rencana OmniClip

Daftar hidup: apa yang **belum dikerjakan**, apa yang **masih lemah**, dan apa
yang **belum pernah diuji**. Ditulis 23 September 2026 pada versi 1.0.7.

Berkas ini menggantikan `SISA-PEKERJAAN.md`, yang sekarang jadi arsip: isinya
ditulis 12 September dan sebagian besar sudah dikerjakan sejak itu, tapi
daftarnya tidak pernah ikut berubah — sehingga membacanya justru menyesatkan.
Aturannya sederhana: **poin yang selesai dicoret dari sini, bukan ditinggalkan
dengan catatan "sudah"**, dan yang sudah selesai dicatat di riwayat git, bukan
di sini.

Urutan yang disepakati pemiliknya: **B3 dan B4 lebih dulu**, lalu seluruh
bagian C.

---

## A. Keputusan yang menunggu pemiliknya

**A1. Data masih di cakram NTFS yang lambat.** Terukur: 67 MB/detik di cakram
kerja sekarang, 523 MB/detik di SSD. Itu faktor lingkungan terbesar pada
kecepatan render — lebih besar daripada semua perbaikan kode yang sudah
dilakukan. Memindahkan `OmniClip-Data` ke SSD tidak butuh kode apa pun, hanya
keputusan dan ruang.

**A2. Berkas sisa 17 GB.** Satu `.f623.mp4` tanpa suara tertinggal di unduhan.
Ia masih bisa dipakai ulang yt-dlp, jadi tidak dibuang sendiri, tapi ia juga
tidak akan pernah terpakai lagi bila videonya sudah selesai diklip.

---

## B. Diminta, belum dibangun

**B1. Sutradara AI untuk gaya subtitle.** Font, warna, bentuk, dan posisi yang
berbeda menurut isi dan penuturnya. Sutradara sekarang hanya mengatur bingkai.

**B2. Sutradara otomatis sesudah auto-klip.** Sekarang harus ditekan per klip di
Studio. Perlu: sakelar di Pengaturan, penjadwalan prioritas rendah sesudah
`run_auto_clip`, tahap tambahan di bilah proses Partitur, dan **cache hasil per
(video, segmen, model, versi prompt)** supaya tombol yang ditekan ulang tidak
membakar kuota dua kali.

**B3. OpenRouter sebagai cadangan Gemini.** Saat Gemini kena limit harian,
seluruh jalur sutradara mati. OpenRouter punya model gratis yang menerima video
dan suara. Perlu diverifikasi lebih dulu pada panggilan uji: format pengiriman
video untuk model `:free` dan batas ukuran inline-nya; bila video tidak
diterima, pakai jalur gambar kunci + suara.

**B4. Unggah ke Facebook, Instagram, dan TikTok.** Baru YouTube dan Drive yang
ada. Ketiganya lewat Graph API (Facebook/Instagram) dan Content Posting API
(TikTok), masing-masing dengan pendaftaran aplikasi dan peninjauan sendiri.

---

## C. Saran perbaikan, urut menurut dampaknya

### Kualitas klip

**C1. Buang jeda dan "eee" otomatis (jump cut).** Klip 60 detik yang dipadatkan
jadi 45 detik terasa jauh lebih rapat, dan ini yang paling membedakan klip
amatir dari klip editor. Bahannya sudah ada: jejak energi suara dan waktu per
kata.

**C2. Panduan area aman di pratinjau.** Garis samar penanda tempat TikTok,
Reels, dan Shorts menaruh tombol dan captionnya, supaya subtitle tidak tertutup
UI aplikasi.

**C3. Perapian suara.** Denoise ringan dan penyeimbang volume antar-penutur.

**C4. Ekspor subtitle terpisah (.srt/.ass).** Untuk YouTube, subtitle terunggah
lebih baik daripada yang dibakar ke gambar: bisa dimatikan penonton, dan
diterjemahkan otomatis oleh YouTube.

### Alur kerja

**C5. Klip banyak video sekaligus.** Centang beberapa hasil pencarian, antre
semuanya.

**C6. Penjadwal unggah.** Klip diantre dengan jam tayang, bukan naik sekaligus.
Lebih aman untuk kanal baru, dan cocok dengan batas kuota harian YouTube.

**C7. Riwayat unggah per profil**, terlihat di Klip jadi lengkap dengan tautan
videonya, supaya jelas klip mana yang sudah naik ke mana.

**C8. Pemantau ruang penyimpanan.** Unduhan sudah 42 GB. Perlu ringkasan
pemakaian dan pembersihan sekali tekan untuk video sumber yang klipnya sudah
jadi.

**C9. Cadangkan dan pulihkan.** Satu tombol untuk basis data dan setelan,
supaya pindah komputer tidak menghapus semua pekerjaan.

### Fondasi

**C10. Pengujian otomatis.** Hari ini proyek ini tidak punya satu pun berkas
uji. Semuanya diuji manual. Yang paling sering rusak dan paling layak diuji:
penyusun subtitle, geometri bingkai, dan pemilihan encoder.

**C11. Font Jepang, Korea, dan Arab dibundel**, dengan pemilihan font otomatis
menurut bahasa subtitle. Tanpa ini, huruf Jepang muncul sebagai kotak kosong di
komputer yang tidak punya fontnya.

**C12. Model Whisper dipilih otomatis menurut bahasa.** Bahasa non-Latin memakai
model yang lebih besar, dengan peringatan jujur bahwa prosesnya lebih lama.

**C13. Halaman Kesehatan sistem.** Satu layar berisi status yt-dlp, PO Token,
encoder GPU, cookies, akun Google, dan ruang cakram. Sekarang semuanya hanya
terlihat di log.

---

## D. Kelemahan yang masih ada

**D1. Ikut wajah salah sorot ±27% waktu** pada bidikan berisi beberapa orang
(turun dari 46%). Bidikan lebar dengan wajah kecil sengaja belum ditangani:
gerak mulut di sana tidak bisa dipercaya.

**D2. Kartun berwajah jelas** masih dianggap "ada orang", jadi jumlah penuturnya
ditebak dari suara dan efek suara bisa terhitung sebagai orang.

**D3. Pindah ke "Susun sendiri" secara manual masih berkedip hitam sesaat.**
Yang sudah mulus hanya potongan susunan sutradara dan bingkai game.

**D4. Whisper "base" buruk untuk bahasa Jepang**, dan terjemahannya ikut salah.
Model besar bisa dipilih di Pengaturan, tapi tidak ada peringatan otomatis
(lihat C12).

**D5. Subtitle bisa bertabrakan dengan subtitle yang sudah tertanam** di video
fansub. Terjemahan sudah dipindah ke atas, tapi posisinya masih tetap, bukan
dihitung dari isi gambar.

**D6. Pola reaksi otomatis untuk kartun belum ada.**

---

## E. Belum pernah diuji (risiko nyata)

**E1. Unggah sungguhan ke YouTube dan Drive.** Belum ada berkas OAuth dari
Google Cloud di komputer pengembangan, jadi jalur unggah belum pernah menyentuh
server Google.

**E2. Semua fitur baru di Windows:** unduhan Deno dan server PO Token, encoder
GPU, profil, dan impor lewat jalur.

**E3. Render GPU pada aplikasi desktop Linux.** Ffmpeg statis yang dibundel
dibangun tanpa encoder GPU sama sekali, jadi di sana render masih x264 walau
kartunya mampu.
