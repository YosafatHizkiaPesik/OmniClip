# Job 1 — Mengurus izin unggah, dan daftar pekerjaan yang belum selesai

Ditulis 29 September 2026, versi 1.3.0.

Isinya dua hal:
1. **Langkah demi langkah mengurus izin** supaya unggah otomatis bisa jalan.
2. **Daftar pekerjaan** yang belum dikerjakan.

---

# BAGIAN 1 — Langkah mengurus izin unggah

## Fakta yang menentukan, baca ini dulu

> **Video yang diunggah lewat API dari proyek Google yang BELUM lolos audit
> akan dikunci sebagai privat.** Bukan "bawaannya privat", tapi dikunci, dan
> menurut aturan Google tidak bisa dijadikan publik sampai auditnya lolos.
> Berlaku untuk semua proyek yang dibuat sejak 28 Juli 2020.

Jadi audit YouTube bukan sekadar cara menaikkan kuota. Ia **satu-satunya cara**
membuat unggahan YouTube berguna. Selama belum lolos, tiap klip yang naik
terkunci privat dan harus dipublikasikan tangan.

Yang **tidak** terkena aturan ini: Google Drive, TikTok, Facebook, Instagram.

---

## Tahap 0 — Yang harus ada lebih dulu (1-2 hari)

Ketiga platform memintanya. Kerjakan sekali, dipakai semua.

### 0.1 Beli domain

Misalnya `omniclip.id` atau `omniclip.app`. Di Niagahoster atau Domainesia
sekitar Rp 150-300 ribu per tahun.

### 0.2 Buat tiga halaman

Gratis dengan GitHub Pages:

1. Buat repo baru bernama `omniclip-web`
2. Isi dengan `index.html`, `privacy.html`, `terms.html`
3. Settings → Pages → aktifkan
4. Settings → Pages → Custom domain → isi domain Anda
5. Di pengelola domain, arahkan CNAME ke `username.github.io`

Isi minimal:

| Halaman | Isi |
|---|---|
| `index.html` | Nama produk, satu paragraf penjelasan, tangkapan layar |
| `privacy.html` | Data apa yang diambil, untuk apa, disimpan di mana |
| `terms.html` | Aturan pemakaian |

### 0.3 Rekam video demo

Satu rekaman layar 1-3 menit:

1. Membuka OmniClip
2. Menekan "Masuk dengan Google"
3. **Halaman izin Google dengan alamatnya terlihat jelas** — client ID harus
   terbaca di bilah alamat
4. Memilih izin
5. Kembali ke OmniClip
6. Mengunggah satu klip

Unggah ke YouTube sebagai **Unlisted**.

Bagian alamat yang terlihat itu **wajib**. Google dan Meta menolak video yang
tidak memperlihatkannya.

### 0.4 Siapkan dokumen usaha

NIB atau akta pendirian. Hanya Meta yang meminta.

---

## Tahap 1 — Google dan YouTube (2-8 minggu)

Kerjakan lebih dulu: antreannya paling panjang, dan tanpa audit unggahan
YouTube tidak berguna.

### 1.1 Verifikasi domain

[Google Search Console](https://search.google.com/search-console) → Add
property → Domain → masukkan domain → tambahkan record TXT di pengelola domain
→ Verify.

Wajib memakai akun Google yang **sama** dengan pemilik project Cloud.

### 1.2 Isi OAuth consent screen

Cloud Console → APIs & Services → OAuth consent screen:

| Kolom | Isi |
|---|---|
| App name | OmniClip |
| User support email | email Anda |
| App logo | PNG 120x120 |
| Application home page | `https://domain-anda/` |
| Privacy policy link | `https://domain-anda/privacy.html` |
| Terms of service link | `https://domain-anda/terms.html` |
| Authorized domains | domain Anda |
| Developer contact | email Anda |

### 1.3 Periksa daftar izin

Harus tepat tiga: `youtube.upload`, `drive.file`, `userinfo.email`.

Jangan tambah yang lain. Tiap izin tambahan memperpanjang review.

### 1.4 Publikasikan

Tombol **Publish app**, ubah status dari Testing ke In production.

### 1.5 Ajukan verifikasi

Tombol **Prepare for verification** → isi formulir → lampirkan tautan video
demo → tulis alasan tiap izin.

Contoh alasan untuk `youtube.upload`:

> Aplikasi desktop yang membuat klip pendek dari video panjang. Izin ini
> dipakai untuk mengunggah klip hasil suntingan ke kanal YouTube milik
> pengguna sendiri, atas permintaan eksplisit pengguna.

### 1.6 Ajukan audit kuota YouTube

**Formulir terpisah.** Cari "YouTube API Services - Audit and Quota Extension
Form". Inilah yang membuka kunci privat.

### Yang terjadi selama menunggu

- Izin Google **kedaluwarsa tiap 7 hari**, jadi harus masuk ulang seminggu
  sekali.
- Video yang diunggah terkunci privat.

### Biaya

Gratis. Izin OmniClip tidak termasuk *restricted*, jadi **tidak perlu** audit
keamanan pihak ketiga (CASA) yang biayanya ribuan dolar per tahun.

---

## Tahap 2 — Meta, Facebook dan Instagram (2-6 minggu)

### 2.1 Siapkan akun

- Instagram diubah ke jenis **Bisnis atau Kreator**
- **Tautkan ke sebuah Halaman Facebook**

Instagram pribadi tidak bisa dipakai sama sekali.

### 2.2 Buat aplikasi

[developers.facebook.com](https://developers.facebook.com) → My Apps → Create
App → jenis **Business**.

### 2.3 Verifikasi bisnis

Business Settings → Security Center → Start Verification → unggah dokumen
usaha.

**Ini yang paling lama**, beberapa hari sampai dua minggu.

### 2.4 Tambahkan produk

Instagram Graph API dan Facebook Login.

### 2.5 Ajukan App Review

Empat izin:

- `instagram_content_publish`
- `pages_manage_posts`
- `pages_read_engagement`
- `pages_show_list`

Sertakan video demo dan penjelasan tiap izin.

### Batasan teknis yang perlu disiapkan

Instagram hanya menerima video lewat **URL publik**, bukan unggahan berkas
langsung. Jadi OmniClip harus menaruh klipnya di tempat yang bisa diakses
Instagram lebih dulu. Sambungan Google Drive yang sudah ada bisa dipakai.

---

## Tahap 3 — TikTok (1-4 minggu)

1. Daftar di [developers.tiktok.com](https://developers.tiktok.com), buat
   aplikasi
2. Tambahkan produk **Content Posting API**, ajukan scope `video.publish`
3. Verifikasi domain di menu URL Properties
4. Ajukan audit

**Tanpa audit sudah bisa dipakai:** klip masuk sebagai **draf** ke aplikasi
TikTok Anda, tinggal tekan terbit di HP. Jadi TikTok bisa dikerjakan terakhir.

---

## Ringkasan

| Platform | Yang didaftarkan | Yang ditunggu | Perkiraan |
|---|---|---|---|
| Google/YouTube | OAuth client jenis Desktop app | verifikasi OAuth + audit kuota | 2-8 minggu |
| TikTok | App, scope `video.publish` | app review + audit | 1-4 minggu |
| Meta (FB+IG) | App Business + verifikasi bisnis | App Review empat izin | 2-6 minggu |

**Urutan yang disarankan:** Tahap 0 → Google → Meta → TikTok.

---

# BAGIAN 2 — Pekerjaan yang belum dikerjakan

## A. Bingkai otomatis klip game

**A1. Akurasi bingkai game: 91,6%.**
Diperbarui 30 September 2026 sesudah pemiliknya mengirim tujuh tangkapan layar.

| Tahap | Akurasi | Meleset |
|---|---|---|
| awal sesi | 64,5% | — |
| beralih "ikuti wajah" saat wajah dominan | 75,1% | 363 |
| **jendela pemindaian 2,0 -> 0,5 detik** | **88,7%** | 164 |
| **panel besar dilaporkan + jadi sorot wajah** | **91,6%** | 123 |

Dua perubahan terakhir yang menentukan, dan keduanya menyerang hal yang sama:
PANEL YANG SALAH DIPAKAI PADA WAKTU YANG SALAH.

**Jendela 2,0 -> 0,5 detik.** Sebuah panel berlaku mulai dari awal jendela
tempat ia ditemukan, jadi panjang jendela adalah batas atas seberapa basi panel
itu bisa jadi. Saat basi ia tidak meleset sedikit — terbukti dengan menggambar
kotaknya di atas bingkai asli, ia menunjuk sudut ruangan gelap dan balok
Minecraft. Ongkosnya TIDAK bertambah (11,9 -> 10,7 detik) karena deteksi wajah
berjalan per bingkai.

**Panel besar tidak lagi dibuang.** `FACECAM_LUAS_MAKS = 0.16` dulu membuang
panel yang lebih besar dari 16% bingkai dengan alasan "ini bidikan kamera
biasa, bukan gameplay". Akibatnya bukan penolakan yang rapi melainkan panel
BASI: jendela tanpa facecam mewarisi letak jendela sebelumnya. Dan yang dibuang
justru sinyal terkuat untuk keputusan yang diminta pemiliknya — "jika facecam
nya membesar maka sorot saja mukanya". Sekarang dilaporkan, lalu
`_tandai_panel_besar` mengubahnya jadi bidikan wajah pada ambang 9,5% luas
bingkai (diukur: panel besar 10,3-15,0%, panel biasa <= 8,9%).

**A1-lama. Akurasi bingkai game: 75,1%.**
Diperbarui 30 September 2026, diukur ulang dengan alat ukur yang MENGHITUNG
pergantian mode: pada potongan "ikuti wajah" bingkainya memang mengikuti wajah,
jadi menghukumnya dengan potongan bidang wajah adalah salah ukur.

| Tahap | Akurasi |
|---|---|
| awal | 64,5% |
| jelajah gerak wajah + kurungan panel | 70,6% |
| **+ beralih "ikuti wajah" saat wajah dominan** | **75,1%** |
| + penempelan ulang waktu | 60,0%, DIBUANG |

Klip yang dikeluhkan pemiliknya sendiri naik dari 55,5% ke 83,7%.

**Yang berhasil:** potongan wajah yang wajahnya lebih lebar dari 10% bingkai
mendapat batas minimum sendiri 1,5 detik, bukan 4 detik. Batas empat detik ada
untuk menahan kedipan dan itu benar selama kedua pilihannya sama-sama wajar —
tapi saat wajah memenuhi layar, bingkai game bukan pilihan yang kurang bagus
melainkan salah. Ambang 10% diukur, bukan ditebak: lebar wajah tengah potongan
"game" 3,6-8,3%, potongan "wajah" 10,3-14,1%.

**Yang gagal dan dicatat di `reframe.py`:** menempelkan tiap sampel ke panel
yang paling cocok. Alasannya kuat (20,6% melesetnya karena salah WAKTU, bukan
salah deteksi; hanya 8,8% yang benar-benar tidak punya panel cocok) tapi
implementasinya menurunkan akurasi ke 60,0%.

**A1-lama. Akurasi bingkai game: 70,6%.**
Terukur 30 September 2026 dengan alat ukur baru: 1.456 sampel berwajah dari
empat klip LaperGang, memeriksa apakah wajah yang terdeteksi benar-benar
termuat di potongan bidang wajah yang aktif saat itu.

| Cara | Akurasi |
|---|---|
| petak dari satu kepala | 64,5% |
| petak dari jelajah gerak wajah | 73,3% |
| jelajah gerak + kurungan keras di panel | **70,6%** (dipakai) |

Kurungan keras memakan 2,7 poin dan tetap dipakai, karena poin yang hilang itu
adalah bidikan yang "tepat" dengan cara memakan layar permainan — persis yang
dilarang pemiliknya.

Tiga hal yang sudah diperbaiki hari itu:
- **Ukuran kepala.** `awan_kotak` adalah gabungan seluruh posisi wajah selama
  dua detik; kalau orangnya bergerak ia melar sampai 51,6% tinggi layar, dan
  potongannya ikut melar sampai 105% lebar panel. Sekarang ada `wajah_kotak`
  (satu kepala berukuran tengah) yang dipakai untuk menilai, dan `_ruang_wajah`
  mengurung hasilnya di dalam panel.
- **Tepi atas panel tidak pernah dicari.** Syaratnya memakai kotak tebakan yang
  sudah dilebarkan 1,85-2,2 kali, jadi ia menyentuh pinggir bingkai jauh lebih
  sering daripada panelnya. Sekarang yang memutuskan awan wajahnya sendiri.
- **Jendela berisi dua facecam.** Jendela 2 detik yang di tengahnya POV berganti
  melaporkan gabungan dua letak. Sekarang dipecah dua bila awan wajahnya jauh
  lebih besar daripada satu kepala. Terukur: 8 bidikan jadi 11, panel yang
  tadinya 51,3% tinggi turun ke 35,8%.

*Yang belum:* 70,6% masih jauh dari cukup. Melesetnya masih berkumpul di sekitar
pergantian POV.

**A1b. 8,8% bingkai meleset (pengukuran lama, kriteria lebih longgar).**
Terukur pada klip LaperGang 85 detik dengan menjalankan detektor wajah di tiap
sampel lalu membandingkannya dengan kotak yang dipakai: 605 sampel tepat
(88,7%), 60 meleset (8,8%), 17 tanpa wajah tepi (2,5%).

Melesetnya berkumpul di lima rentang, semuanya di sekitar pergantian POV: klip
detik 24,0-24,6 / 32,5-33,4 / 36,8-38,8 / 70,0-70,6 / 80,5-81,9.

*Yang perlu dikerjakan:* menggeser titik pergantian kotak supaya MENDAHULUI
peralihan POV sedikit, bukan mengikutinya.

**A2. Ukuran bidang wajah. SELESAI 30 September 2026.**
Wajah kini mengisi rerata 38,9% luas potongan (median 40,8%, terukur pada 390
bidikan gameplay tersimpan), naik dari 16-24%.

Yang diubah: bidang wajah tidak lagi selebar kanvas. Lebarnya dipersempit
sampai bentuknya sama dengan RUANG KEPALA pemain, lalu ditaruh di tengah dengan
latar kabur di kiri-kanannya. Tinggi bidangnya tidak disentuh, jadi bidang
permainan tidak kehilangan satu piksel pun — itu syarat yang diminta pemiliknya:
"buat agar bidang wajah pas dengan facecam dan tidak memakan bidang permainan".

Bentuknya diambil dari kepala, bukan dari panel facecam. Panel memuat kepala
beserta kursi, meja, dan dinding; menyamakan bentuk bidang dengan bentuk panel
hanya menaikkan wajah ke 24%, sedangkan mengikuti kepala menaikkannya ke 39%.

Batas bawah lebarnya `render.WAJAH_LEBAR_MIN` = 55%. 269 dari 444 bidikan
menyentuh batas itu, jadi menurunkannya masih bisa menaikkan angkanya lagi —
tapi bidang yang lebih sempit dari itu jadi pita kurus di tengah layar.

## B. Sisipan

| | |
|---|---|
| **B1** | Memilih bagian sumber yang dipakai. "Penuhi lalu potong" selalu memotong dari tengah, jadi cuplikan yang subjeknya di tepi tidak bisa digeser. |
| **B2** | Gerakan di dalam sisipan (Ken Burns). Gambar diam tetap benar-benar diam. |
| **B0** | **SELESAI 30 September 2026:** sisipan TULISAN (`jenis: "teks"`), terpisah dari judul klip. Isi, 13 font terbundel, ukuran, warna, garis luar, kotak latar, letak bebas, lama tampil, lembut masuk/keluar, dan transparansi. Dibuat untuk syarat kampanye seperti "@motionklip". Transparansi untuk gambar dan video ternyata sudah ada sejak sebelumnya. |
| **B3** | Pratinjau fade suara. Pemutar sisipan di Studio memakai volume tetap; lembut masuk dan keluarnya baru terdengar di hasil render. |

## C. Belum pernah diuji sungguhan

| | |
|---|---|
| **C1** | **Unggah ke YouTube dan Drive.** Alurnya berjalan, tapi belum pernah ada video yang benar-benar naik. |
| **C2** | **Windows.** Bundelnya terbangun tiap rilis, tapi belum pernah dijalankan di Windows sungguhan. Termasuk unduhan Deno, server PO Token, dan encoder GPU. |
| **C3** | **Render GPU pada Linux.** Ffmpeg statis yang dibundel belum diuji dengan VAAPI atau NVENC. |
| **C4** | **Pemulihan cadangan.** Membuatnya sudah diuji, memulihkannya belum. |

## D. Belum dibangun

| | |
|---|---|
| **D1** | **Kode unggah TikTok, Facebook, Instagram.** Menunggu izin, karena ketiganya tidak bisa diuji sebelum aplikasinya disetujui. Begitu kuncinya ada: `target` di `routers/uploads.py` ditambah, `run_upload` di `services/pipeline.py` diarahkan. |
| **D2a** | Musik latar bawaan. Efek suara sudah ada 17 buah yang dibangkitkan sendiri (`services/efek_suara.py`), tapi MUSIK tidak bisa dibangkitkan begitu saja dan yang beredar hampir semuanya berhak cipta. Jalan yang tersisa: mengunduh sekali dari pustaka CC0 saat pengguna memintanya, bukan membundelnya. |
| **D2** | Suara baca judul: pilihannya masih sedikit. Hanya dua suara Indonesia dari Microsoft (Ardi dan Gadis) plus satu Piper lokal; sisanya cuma ubahan laju dan nada. Tidak ada layanan gratis lain yang punya banyak suara INDONESIA — lihat catatan di bawah. |
| **D3** | Statistik sesudah unggah: berapa tayangan tiap klip. |
| **D4** | Pola reaksi otomatis untuk kartun. |
| **D5** | Tanda tangan digital Windows. Alur build sudah siap memakainya (rahasia `WINDOWS_PFX_BASE64` dan `WINDOWS_PFX_PASSWORD`), tinggal sertifikatnya, 200-400 dolar per tahun. |

---

# Catatan pratinjau tersendat

Ditulis 30 September 2026 sesudah pemiliknya bertanya: "setiap kali melihat
video di studio maju mundur tersendat sendat apa itu istilahnya dan mengapa
bisa terjadi".

Istilahnya **frame drop**. Terukur di mesinnya, klip gaming 1920x1080 **60 fps**:

| Pemutar | fps didekode | Bingkai jatuh per 12 dtk |
|---|---|---|
| latar kabur | 31,5 | 202 |
| pemutar utama | 60,2 | 0 |
| bidang wajah | 59,0 | 419 |
| bidang permainan | 59,1 | 422 |

Empat pemutar untuk BERKAS YANG SAMA: 210 bingkai 1080p per detik diminta dari
prosesor 15 watt, dan 1.043 dari 2.517 bingkai jatuh — **41%**. Itu juga yang
membuat bidang permainan tampak PUTIH: dekoder yang kehabisan napas sampai
tidak mengeluarkan bingkai sama sekali.

Diperbaiki dengan menggambar susunan ke **kanvas** dari satu dekoder
(`ClipPreview.pakaiKanvas`): pemutar utama satu-satunya yang mendekode, kanvas
menyalin bingkainya ke tiap bidang dengan `drawImage`. Latar kabur ikut
digambar kanvas, jadi elemen videonya tidak dibuat sama sekali.

Sesudahnya: **2 pemutar, 120 fps, 2,6% jatuh**. Dua yang tersisa memang berbeda
isi — panel "Video sumber" di kiri dan pratinjau hasil di kanan.

Efek sampingnya: tidak ada lagi cermin yang bisa tertinggal, jadi seluruh mesin
pengejaran kecepatan putar dan pelompatan yang selama ini jadi sumber "maju
mundur" tidak terpakai lagi di jalur ini.

*Yang belum:* `AMBANG_PUTAR = 1920` di `services/proksi.py` memutuskan salinan
ringan hanya untuk sumber yang LEBIH LEBAR dari 1920. Aturan itu ditulis demi
kualitas gambar dan masih benar untuk satu dekoder, tapi ia tidak melihat laju
bingkai: sumber 1080p60 tetap diputar apa adanya. Dengan jalur kanvas hal itu
tidak lagi mendesak.

---

# Catatan tombol hitung ulang bingkai

Ditulis 1 Oktober 2026. Pemiliknya melaporkan bahwa perbaikan bingkai "tidak
ada yang berubah", dan ia benar — tapi sebabnya BERLAPIS TIGA, dan tiap lapis
menyembunyikan lapis berikutnya. Ditulis lengkap karena pola ini akan terulang.

1. **Tombolnya tidak pernah digambar.** Prop `onUlangSemua` ditambahkan ke
   `FramePanel`, tapi tombolnya ada di dalam sub-komponen `PemanasanBingkai`
   yang hanya menerima `videoId`. Kodenya benar di dua tempat terpisah, dan
   salah hanya pada sambungannya. Tidak akan ketahuan tanpa menguji di
   peramban.

2. **Permintaannya ditolak.** `_jadwalkan_jejak_sekarang` punya penjaga
   `_sudah_dipanaskan`: daftar klip yang sama dan sudah pernah selesai tidak
   diantrekan lagi. Benar untuk pemanasan otomatis, salah untuk tombol — di
   sana daftar klipnya memang sama, yang berubah ATURAN pembingkaiannya.
   `paksa` sekarang melewatinya.

3. **Pekerjaannya tidak menghitung apa pun.** Ini yang paling menipu:
   pekerjaannya diantrekan, dijalankan, dan selesai dengan status "done" dan
   pesan "12 klip siap dipakai" — dalam 0,06 detik, karena semua letak facecam
   dibaca dari simpanan. Simpanan itu tidak pernah bisa dibuang per video,
   karena nomor videonya hanya ada DI DALAM sidik hash, bukan di kuncinya.
   Kuncinya sekarang `facecam:{video_id}:{sidik}`, dan `?ulang=true` membuang
   simpanan video itu lebih dulu.

Sesudah ketiganya: tekan tombol, dan "Bingkai klip 3 dari 12" muncul dalam 3
detik.

**Pelajaran yang berlaku umum:** pekerjaan yang selesai dengan status "done"
dan pesan yang meyakinkan belum tentu mengerjakan apa pun. Yang membuktikannya
lamanya, bukan statusnya.

---

# Catatan papan suara

Ditulis 30 September 2026. Efek suara bawaan DIHAPUS SELURUHNYA, diganti
pengimpor papan suara.

Dua percobaan membuat efek sendiri, dua penolakan pemiliknya. Pertama
(25 September) satu baris rumus `lavfi` per efek: "jelek-jelek". Kedua
(30 September) disusun dengan numpy — transien, badan, ekor, sapuan nada dan
tapis bergerak: "sama sekali tidak ada suara yang saya suka dan akan saya
pakai". Ia lalu menunjuk halaman pencarian Indonesia di myinstants.com.

Kesimpulannya bukan sintesisnya kurang bagus, melainkan yang dicari memang
bukan suara sintetis: yang dipakai pembuat klip Indonesia adalah potongan
soundboard — tawa, teriakan, kutipan acara.

**Kenapa pengimpor, bukan bundel.** Isi papan suara itu rekaman milik orang
lain yang diunggah orang lain lagi. Membundelnya berarti mendistribusikan ulang
karya orang di dalam aplikasi yang DIJUAL, dan masalahnya berpindah ke pemilik
aplikasi. Sebagai pengimpor, penggunalah yang memilih dan mengunduhnya di
mesinnya sendiri — sama seperti berkas apa pun yang ia impor.

**Yang perlu diketahui teknisnya.** Cloudflare menolak permintaan dari server:
403 untuk curl maupun yt-dlp polos, dan `--extractor-args generic:impersonate`
saja tidak cukup (metadatanya lewat, berkasnya tidak). Yang bekerja:
`curl_cffi` untuk membaca halamannya, dan `yt-dlp` dengan
`impersonate=ImpersonateTarget("chrome")` untuk berkasnya. `curl_cffi` sudah
masuk requirements.txt.

Terverifikasi: halaman pencarian Indonesia memberi 36 suara berikut namanya
yang benar, dan berkasnya masuk pustaka dengan durasi terbaca.

---

# Catatan pratinjau tersendat, hitam, dan tidak sinkron

Diperbarui 30 September 2026. Sesudah jalur kanvas (lihat catatan di bawah),
pemiliknya masih melaporkan tiga gejala: "tampilan video hitam, video looping
bahkan preview dan raw tidak singkron".

Ketiganya satu penyebab, dan bukan di pratinjau melainkan di panel **Video
sumber** (`FrameStage.jsx`). Ia masih memakai cara lama: melompat
(`currentTime = ...`) tiap kali selisihnya lewat 0,2 detik. Lompatan memaksa
dekoder mencari bingkai kunci, yang membuatnya tertinggal lagi, lalu
dilompatkan lagi — lingkaran yang tidak pernah tertutup pada mesin 15 watt.
Hitam adalah lompatan yang mendarat sebelum bingkai kunci berikutnya terdekode.

Lingkaran yang sama sudah dipatahkan di ClipPreview berbulan sebelumnya;
FrameStage terlewat.

Perbaikannya mengejar dengan KECEPATAN PUTAR, dan kecepatannya SEBANDING dengan
selisihnya (dibatasi ±12%). Langkah tetap 4% masih meninggalkan selisih 0,29
detik karena butuh tujuh detik untuk menutupnya.

| | sebelum | langkah tetap 4% | sebanding |
|---|---|---|---|
| waktu mundur | berulang | 0x | 0x |
| selisih dua panel | — | 0,061-0,294 dtk | **0,013-0,031 dtk** |

0,031 detik itu sekitar dua bingkai pada 60 fps.

---

# Catatan suara baca judul

Ditulis 30 September 2026 sesudah memeriksa daftar suara yang benar-benar ada.

`edge-tts` (Suara Microsoft) yang sudah terpasang menyediakan **322 suara**,
gratis, tanpa kunci, dan tanpa batas kuota yang pernah kita temui. Itu sudah
layanan gratis terbaik yang ada. Masalahnya bukan kuota melainkan pilihan:
dari 322 itu, yang berbahasa **Indonesia hanya dua** — `id-ID-ArdiNeural` dan
`id-ID-GadisNeural`.

Yang bisa menambah pilihan tanpa biaya:

| Cara | Tambahan | Catatan |
|---|---|---|
| 12 suara `Multilingual` di edge-tts | 12 karakter | Sudah diuji membaca kalimat Indonesia dan keluar bunyinya, tapi logatnya belum saya dengarkan. Contohnya ada di `~/contoh-suara-omniclip/`. |
| Menambah suara Piper Indonesia | sedikit | Hanya `id_ID-news_tts` yang tersedia di repositori Piper. |
| Ubahan laju dan nada | tak terbatas | Cara yang dipakai sekarang untuk membuat enam pilihan dari dua suara. |

Yang **tidak** menjawab: ElevenLabs gratis hanya 10 ribu huruf sebulan; Kokoro,
MeloTTS, dan XTTS-v2 tidak mendukung bahasa Indonesia; gTTS gratis tapi cuma
satu suara dan lebih datar daripada yang sudah ada.

---

# Catatan penomoran versi

Nomor versi naik **satu per satu di angka terakhir**: 1.3.0 → 1.3.1 → 1.3.2 →
... → 1.3.9, dan baru setelah itu 1.4.0.

Besar kecilnya isi rilis tidak menentukan. Ubah nomornya hanya di
`backend/app/version.py`, lalu beri tag git yang sama persis.
