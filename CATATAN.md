# Catatan OmniClip

Satu berkas, menggantikan sebelas berkas MD yang tersebar. Isinya tiga hal:
apa yang **belum selesai**, **langkah mengurus izin unggah**, dan **acuan teknis**
yang masih dipakai.

Ditulis 29 September 2026, versi 1.2.1. Diperbarui 2 Oktober 2026, versi 1.3.1.

> **Dua berkas catatan, dan itu memang membingungkan.** `JOB-1.md` ditulis
> belakangan dengan isi yang sebagian sama persis dengan di sini. Keduanya
> mengaku "satu berkas yang menggantikan sisanya", dan tidak ada yang benar
> selama keduanya berdiri. Keduanya sudah diperbarui 2 Oktober 2026; yang
> belum diputuskan pemiliknya adalah mana yang dipertahankan.

---

# BAGIAN 1 — Yang belum selesai

## 1.1 Bingkai otomatis klip game

Ini yang paling sering dikeluhkan dan yang paling banyak dikerjakan.

**Sudah bisa:** mengenali klip game, menemukan facecam walau letaknya di tepi
tengah, mengikuti facecam yang berpindah antar POV, memecah klip jadi bagian
"permainan saja", "permainan + wajah", dan "wajah penuh", serta memotong
linimasa di tiap pergantian supaya bisa disetel tangan.

**Angka terakhir**, 2 Oktober 2026, diukur pada empat klip LaperGang (1.528
sampel berwajah) dengan menjalankan detektor wajah di tiap sampel lalu
membandingkannya dengan panel yang berlaku saat itu: **93,1% tepat, 106
meleset.** Sempat 94,1% sebelum deteksi tepi panel diperbaiki; satu poin itu
dibayar dengan sadar untuk kotak panel yang jauh lebih tepat ukurannya (lebar
nilai tengah 192 piksel -> 290).

**Yang sudah dikerjakan sejak catatan ini ditulis:**

- Menggeser titik pergantian supaya MENDAHULUI, bukan mengikuti. Batas
  sekarang maju ~190 ms: setengah jarak sampel (menaruh batas tepat di
  sampelnya selalu terlambat) plus satu sampel lagi, karena telat dan terlalu
  cepat tidak sama beratnya di mata penonton.
- Penajaman tepi panel, yang ternyata MATI sejak jendela pemindaian
  dipersempit: ia menuntut empat bingkai gradien sementara jendela 0,5 detik
  hanya memberi dua. Gradien sekarang dihitung per blok dua detik, terpisah
  dari jendela letak yang tetap setengah detik.

**Yang masih meleset:** sebagian bidikan masih mendapat kotak panel yang lebih
kecil daripada panel sebenarnya, saat satu sisinya kebetulan sewarna dengan
gambar di sebelahnya. Empat percobaan terakhir menukar satu kesalahan dengan
kesalahan lain; yang tersisa di situ bukan penyetelan angka melainkan
pendekatan yang berbeda.

## 1.2 Ukuran bidang wajah pada klip game

**Aturannya dibalik 1 Oktober 2026.** Dulu potongan diukur dari KEPALA; itu
menghasilkan potongan yang lebih kecil daripada panelnya di kedua sisi
sekaligus — terukur 240x136 dari panel 386x303. Sekarang ukurannya ditentukan
PANEL: kotak terbesar berasio bidang yang muat di dalam kotak facecam,
diletakkan pada kepalanya, disusutkan 2% tiap sisi sebagai marjin aman.

Aturan pemiliknya satu arah, dan itu yang menentukan rancangannya: **tidak
boleh LEBIH dari kotak facecam, kurang sedikit tidak apa-apa.** Terukur pada
236 potongan tersimpan: seluruhnya di dalam kotaknya, dan satu sisinya pas
dengan sisi panel.

**Batasnya sekarang bahannya, bukan geometrinya.** Bidang wajah selebar 1080
piksel sementara kotak facecam di sumber 1080p hanya 192-806 piksel: rata-rata
3,5 kali perbesaran, 5,6 kali pada yang terkecil. Satu-satunya jalan menaikkan
ketajamannya ada di hulu — sumber 1440p atau 4K.

## 1.3 Sisipan

- **Memilih bagian sumber yang dipakai.** "Penuhi lalu potong" selalu memotong
  dari tengah. Cuplikan gol yang subjeknya di tepi kiri tidak bisa digeser di
  dalam petaknya sendiri.
- **Gerakan di dalam sisipan** (Ken Burns): gambar diam tetap benar-benar diam.
- **Pratinjau fade suara.** Pemutar sisipan di Studio memakai volume tetap;
  lembut masuk dan keluarnya baru terdengar di hasil render.

## 1.4 Belum pernah diuji sungguhan

- ~~Unggah ke YouTube dan Drive.~~ **Sudah teruji.** Pemiliknya sudah
  mengunggah beberapa video lewat fitur ini. Keluhan yang tersisa bukan soal
  alurnya melainkan MUTU video di YouTube, dan sebabnya ditemukan 2 Oktober
  2026: render selalu mengeluarkan **30 fps** dari sumber 60 fps (`render.py`,
  `fps=30`). Resolusi dan bitrate justru baik: 1080x1920, 13,7 Mbps. Mengubahnya
  kira-kira menggandakan kerja filter, jadi itu keputusan pemiliknya.
- **Windows.** Bundelnya terbangun tiap rilis, tapi tidak ada yang pernah
  menjalankannya di Windows sungguhan. Termasuk unduhan Deno, server PO Token,
  dan encoder GPU.
- **Render GPU pada Linux.** Pada mesin pemiliknya VAAPI terpilih dan dipakai
  (`h264_vaapi (low power)`, terlihat di log tiap kali aplikasi mulai). Yang
  belum diuji: ffmpeg STATIS yang dibundel ke rilis, dan NVENC.
- **Pemulihan cadangan sampai tuntas.** Membuat cadangan sudah diuji;
  memulihkannya belum.

## 1.5 Lainnya

- ~~Beranda menyarankan video yang tidak layak diklip.~~ **Selesai 6 Oktober
  2026** (`services/beranda.py`). Dilaporkan sambil menunjukkan layarnya: vlog
  23 detik 3 tayangan, dan kuliah teknik wawancara 216 tayangan enam tahun
  lalu. Sebabnya beranda memakai urutan RELEVANSI pencarian apa adanya, tanpa
  satu pun saringan. Sekarang: kueri beranda diurutkan menurut TAYANGAN
  (separuhnya dibatasi sebulan terakhir), ditambah lapis "sedang ramai" dari
  `videos.list?chart=mostPopular&regionCode=ID` kategori Gaming, Hiburan, dan
  Komedi, dan saringan mutu bersama (3 menit sampai 4 jam, bukan siaran
  langsung, bukan video musik, tayangan minimal yang mengalah bertahap supaya
  beranda tidak pernah kosong). Lapis ramai memakai kunci YouTube Data API yang
  sama dengan Analitik, disimpan tiga jam.

- **Pola reaksi otomatis untuk kartun** belum ada.
- ~~Statistik sesudah unggah.~~ **Selesai 2 Oktober 2026**, dan sejak
  6 Oktober 2026 punya halamannya sendiri: **Analitik**
  (`components/AnalitikTab.jsx` + `services/analitik.py`). Angka kecil di kartu
  Klip jadi tetap ada, tapi yang menjawab "klip mana yang jalan dan apa yang
  harus diubah" halaman itu: total dan median tayangan, tabel per klip, dan
  daftar periksa `fyp.py` yang digabung dari semua klip terunggah. Di bawah
  delapan klip terbaca ia TIDAK membandingkan apa pun dan mengatakan alasannya;
  di atas itu baru median klip yang kena sebuah temuan dibandingkan dengan yang
  tidak. Kuncinya dipasang di Akun > Tayangan klip — kunci API, bukan izin akun, karena token
  unggah menjawab 403 untuk `videos.list` dan menambah izin baca akan menuntut
  tiap akun menyambung ulang. Harganya: hanya video PUBLIK yang terbaca, dan
  yang tidak terbaca hilang dari daftar, bukan jadi nol.
- **Sutradara AI** memakai kuota Gemini; jatah gratisnya bisa habis seharian
  penuh, dan saat itu terjadi jalur heuristik lokal yang dipakai.
- ~~Sakelar sensor kata kasar.~~ **Selesai**, ada di Pengaturan > Subtitle
  (`components/SakelarSensor.jsx`).

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
