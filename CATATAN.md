# Catatan OmniClip

Satu berkas, menggantikan sebelas berkas MD yang tersebar. Isinya tiga hal:
apa yang **belum selesai**, **langkah mengurus izin unggah**, dan **acuan teknis**
yang masih dipakai.

Ditulis 29 September 2026, versi 1.2.1.

---

# BAGIAN 1 — Yang belum selesai

## 1.1 Bingkai otomatis klip game

Ini yang paling sering dikeluhkan dan yang paling banyak dikerjakan.

**Sudah bisa:** mengenali klip game, menemukan facecam walau letaknya di tepi
tengah, mengikuti facecam yang berpindah antar POV, memecah klip jadi bagian
"permainan saja", "permainan + wajah", dan "wajah penuh", serta memotong
linimasa di tiap pergantian supaya bisa disetel tangan.

**Yang masih meleset**, diukur pada klip LaperGang 85 detik dengan menjalankan
detektor wajah di tiap sampel lalu membandingkannya dengan kotak yang dipakai:

| | |
|---|---|
| Tepat | 605 sampel (88,7%) |
| Meleset | 60 sampel (8,8%) |
| Tanpa wajah tepi | 17 sampel (2,5%) |

Melesetnya berkumpul di lima rentang, semuanya **di sekitar pergantian POV**:
klip detik 24,0-24,6 / 32,5-33,4 / 36,8-38,8 / 70,0-70,6 / 80,5-81,9.

**Yang belum dikerjakan:** menggeser titik pergantian kotak supaya MENDAHULUI
peralihan POV sedikit, bukan mengikutinya. Itu yang akan memangkas 8,8% itu.

## 1.2 Ukuran bidang wajah pada klip game

Wajah mengisi 20-24% luas potongan, naik dari 16-18% sesudah potongannya
diukur dari wajah dan bukan dari seluruh panel.

**Batasnya sekarang geometri:** potongan wajib berbentuk sama dengan bidangnya.
Bidang wajah setinggi 40% pada kanvas 9:16 itu melebar (rasio 1,4), sementara
kepala orang tegak. Untuk memuat kepala, potongannya terpaksa melebar dan ikut
membawa ruangan di kiri-kanannya.

**Jalan keluarnya** menaikkan batas tinggi bidang wajah dari 40% ke sekitar
55%, di `render.GAMING_WAJAH_MAKS`. Belum dikerjakan karena itu memakan jatah
bidang permainan di semua klip game, dan itu keputusan rasa pemiliknya.

## 1.3 Sisipan

- **Memilih bagian sumber yang dipakai.** "Penuhi lalu potong" selalu memotong
  dari tengah. Cuplikan gol yang subjeknya di tepi kiri tidak bisa digeser di
  dalam petaknya sendiri.
- **Gerakan di dalam sisipan** (Ken Burns): gambar diam tetap benar-benar diam.
- **Pratinjau fade suara.** Pemutar sisipan di Studio memakai volume tetap;
  lembut masuk dan keluarnya baru terdengar di hasil render.

## 1.4 Belum pernah diuji sungguhan

- **Unggah ke YouTube dan Drive.** Berkas OAuth sudah terpasang dan alurnya
  berjalan, tapi belum pernah ada video yang benar-benar naik.
- **Windows.** Bundelnya terbangun tiap rilis, tapi tidak ada yang pernah
  menjalankannya di Windows sungguhan. Termasuk unduhan Deno, server PO Token,
  dan encoder GPU.
- **Render GPU pada Linux.** Ffmpeg statis yang dibundel belum diuji dengan
  VAAPI/NVENC di mesin yang punya kartu grafis.
- **Pemulihan cadangan sampai tuntas.** Membuat cadangan sudah diuji;
  memulihkannya belum.

## 1.5 Lainnya

- **Pola reaksi otomatis untuk kartun** belum ada.
- **Statistik sesudah unggah** (berapa tayangan tiap klip) belum ada.
- **Sutradara AI** memakai kuota Gemini; jatah gratisnya bisa habis seharian
  penuh, dan saat itu terjadi jalur heuristik lokal yang dipakai.
- **Sakelar sensor kata kasar** belum ada di Pengaturan. Bagian dalamnya sudah
  menerima pilihan (`build_ass(sensor=...)`), tinggal tombolnya.

---

# BAGIAN 2 — Langkah mengurus izin unggah otomatis

Bagian ini yang perlu diurus pemiliknya sendiri. Tidak ada kode yang bisa
menggantikannya.

## 2.0 Fakta yang paling menentukan, baca ini dulu

> **Video yang diunggah lewat API dari proyek Google yang BELUM lolos audit
> akan dikunci sebagai privat.** Bukan "bawaannya privat", tapi dikunci, dan
> menurut aturan Google tidak bisa dijadikan publik sampai auditnya lolos.
> Berlaku untuk semua proyek yang dibuat sejak 28 Juli 2020.

Akibatnya: audit YouTube bukan sekadar cara menaikkan kuota. Ia **satu-satunya
cara** membuat unggahan YouTube berguna sama sekali. Selama belum lolos, tiap
klip yang naik akan terkunci privat dan harus dipublikasikan tangan.

Yang **tidak** terkena aturan ini: Google Drive, TikTok, Facebook, dan
Instagram.

## 2.1 Yang dibutuhkan bersama oleh ketiga platform

Urus ini lebih dulu, karena ketiganya memintanya:

1. **Domain sendiri**, misalnya `omniclip.id`.
2. **Tiga halaman** di domain itu: beranda produk, **kebijakan privasi**, dan
   syarat penggunaan. Halaman statis gratis sudah cukup (GitHub Pages).
3. **Video demo** yang memperlihatkan alur izinnya. Dituntut Google dan Meta.
4. **Badan usaha yang bisa diverifikasi** (NIB atau akta). Hanya Meta yang
   memintanya.

## 2.2 Google dan YouTube

1. Buktikan kepemilikan domain di **Google Search Console**, dengan akun yang
   sama dengan pemilik project Cloud.
2. **Cloud Console → APIs & Services → OAuth consent screen**: isi nama
   aplikasi, logo 120x120 piksel, email dukungan, email pengembang, domain
   terverifikasi, dan tautan ketiga halaman tadi.
3. Ubah status dari **Testing** ke **In production**.
4. Tekan **Prepare for verification**, lalu kirim.
5. Rekam **video demo**: halaman izin Google dengan client ID terlihat di
   alamatnya, lalu bagaimana OmniClip memakainya untuk mengunggah.
6. Ajukan **audit kuota YouTube** di formulir terpisah. Ini yang membuka kunci
   privat di poin 2.0.

**Perkiraan waktu:** 2 sampai 8 minggu, biasanya dengan beberapa kali tanya
jawab lewat email.

**Biaya:** gratis. Izin OmniClip (`youtube.upload` dan `drive.file`) tidak
termasuk *restricted*, jadi **tidak perlu** audit keamanan pihak ketiga (CASA)
yang biayanya ribuan dolar per tahun.

**Efek sampingan penting:** selama status masih Testing, izin Google
**kedaluwarsa tiap 7 hari**, jadi pengguna harus masuk ulang seminggu sekali.
Ini saja sudah alasan cukup untuk memverifikasi.

## 2.3 TikTok

1. Daftar di **developers.tiktok.com**, buat aplikasi.
2. Ajukan produk **Content Posting API** dengan izin `video.publish`.
3. Verifikasi domain tempat klipnya diambil.
4. Ikuti **audit** TikTok.

**Tanpa audit:** unggahan hanya masuk sebagai **draf** ke aplikasi TikTok
pengguna, dan tombol terbit ditekan tangan di HP. Itu tetap jauh lebih cepat
daripada memindahkan berkas sendiri, jadi tahap ini tetap berguna.

**Perkiraan waktu:** 1 sampai 4 minggu.

## 2.4 Facebook dan Instagram

Keduanya lewat satu pintu, Meta.

1. Buat aplikasi di **developers.facebook.com**, jenis **Business**.
2. Lakukan **Business Verification**. Ini yang paling lama.
3. Instagram harus jenis **Bisnis atau Kreator** dan **tertaut ke Halaman
   Facebook**. Instagram pribadi tidak bisa dipakai sama sekali.
4. Ajukan **App Review** untuk izin:
   - `instagram_content_publish` (Reels)
   - `pages_manage_posts` dan `pages_read_engagement` (Facebook)
5. Sertakan video demo alur unggahnya.

**Batasan teknis yang perlu disiapkan:** Instagram hanya menerima video lewat
**URL publik**, bukan unggahan berkas langsung. Jadi OmniClip harus menaruh
klipnya di tempat yang bisa diakses Instagram lebih dulu. Sambungan Google
Drive yang sudah ada bisa dipakai untuk itu.

**Perkiraan waktu:** 2 sampai 6 minggu.

## 2.5 Ringkasan

| Platform | Yang didaftarkan | Yang ditunggu | Perkiraan |
|---|---|---|---|
| Google/YouTube | OAuth client jenis Desktop app | verifikasi OAuth + audit kuota | 2-8 minggu |
| TikTok | App, scope `video.publish` | app review + audit | 1-4 minggu |
| Meta (FB+IG) | App Business + verifikasi bisnis | App Review dua izin | 2-6 minggu |

**Kode unggahnya belum ditulis untuk TikTok, Facebook, dan Instagram**, dan itu
keputusan sadar: ketiganya tidak bisa diuji sama sekali sebelum aplikasinya
terdaftar dan disetujui. Menulis kode yang tidak pernah bisa dijalankan hanya
menghasilkan tebakan yang terlihat seperti fitur. Begitu kuncinya ada,
bangunannya kecil: `target` di `routers/uploads.py` tinggal ditambah, dan
`run_upload` di `services/pipeline.py` tinggal mengarahkannya.

---

# BAGIAN 3 — Acuan teknis

## 3.1 Menaikkan versi dan merilis

1. Ubah nomor di `backend/app/version.py`, **hanya di situ**.
2. Beri tag git yang **sama persis**, misalnya `v1.2.2`.
3. Dorong tagnya. Alur build GitHub menolak tag yang tidak cocok dengan berkas
   itu.

**Aturan nomor:** angka tengah naik bila ada yang **baru bisa dilakukan**
pengguna; angka terakhir naik bila hanya **memperbaiki** yang sudah ada.

## 3.2 Windows Defender dan tanda tangan digital

Bundel Windows belum ditandatangani, jadi Defender menampilkan layar biru
"Windows protected your PC". Pengguna menekan **More info → Run anyway**.

Sertifikat penandatangan kode berbayar, sekitar 200-400 dolar per tahun. Alur
build sudah siap memakainya: simpan sertifikat sebagai rahasia GitHub
`WINDOWS_PFX_BASE64` dan `WINDOWS_PFX_PASSWORD`, dan langkah penandatanganan
berjalan sendiri. Tanpa rahasia itu, build tetap jalan dan hasilnya tetap
terbit, hanya tanpa tanda tangan.

## 3.3 Berkas rahasia yang tidak boleh ikut ter-commit

- `backend/.env` (kunci Gemini)
- `OmniClip_Storage/google_client_secret.json`, `google_token.json`
- `OmniClip-Data/akun/` (token OAuth tiap profil)

Sebelum commit, periksa: `git diff --cached | grep -iE "AIza[0-9A-Za-z_-]{20,}"`
harus kosong.

## 3.4 Letak data

| Isi | Tempat |
|---|---|
| Video mentah | folder unduhan pilihan pengguna |
| Basis data, klip jadi, model | `OmniClip-Data/` di sebelah folder aplikasi |
| Setelan lokasi | folder data sistem, bukan di dalam folder yang ditunjuknya |

Folder aplikasi ditukar seluruhnya tiap pembaruan, jadi tidak ada data yang
boleh tinggal di dalamnya.

## 3.5 Sensor kata kasar

Daftar katanya ada di `backend/app/services/sensor.py`, dan salinannya untuk
pratinjau di `frontend/src/lib/sensor.js` **diturunkan dari situ**. Uji
`test_sensor_kata.py` membandingkan keduanya dan gagal bila salah satu berubah
sendiri. Menambah atau membuang kata: ubah di sisi Python, lalu segarkan
salinan JS-nya.

Umpatan ringan sengaja dibiarkan atas keputusan pemiliknya: `babi`, `cok`,
`cuk`, `anjir`, `bodoh`, `bego`, `setan`, `gila`.
