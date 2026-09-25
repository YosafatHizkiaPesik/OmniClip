# Rencana OmniClip

Daftar hidup: apa yang **belum dikerjakan**, apa yang **masih lemah**, dan apa
yang **belum pernah diuji**. Diperbarui 25 September 2026 pada versi 1.0.8.

Berkas ini menggantikan `SISA-PEKERJAAN.md`, yang sekarang jadi arsip. Aturannya
satu: **poin yang selesai dicoret dari sini**, bukan ditinggalkan dengan catatan
"sudah". Yang sudah selesai tercatat di riwayat git.

---

## A. Keputusan yang menunggu pemiliknya

**A1. Keputusan pemiliknya, dan angkanya mendukungnya.** Folder unduhan sudah
di SSD; klip jadi dan basis data tetap di cakram putar, dan itu memang tidak
apa-apa. Terukur 24 September 2026: klip jadi rata-rata 21 MB, dan cakram itu
menulis 57 MB/detik, jadi menyimpan satu klip menghabiskan sekitar 0,4 detik
dari render yang memakan menit. Yang mahal adalah MEMBACA sumbernya berulang
kali, dan itu sudah pindah. Sisa yang layak dipertimbangkan hanya basis data,
karena ia ditulis sedikit-sedikit tapi sangat sering.

**A3. Mendaftarkan aplikasi Google.** Hanya Google sekarang, TikTok dan Meta
tidak lagi butuh pendaftaran apa pun sejak unggahannya jadi setengah otomatis.
Langkahnya ada di dalam aplikasi (Akun → Tambah akun) dan di
[PANDUAN-AKUN.md](PANDUAN-AKUN.md). Sampai ini dikerjakan, unggah ke YouTube
dan Drive tidak bisa dipakai, dan tidak bisa diuji (lihat E1).

**A4. Rilis 1.0.8.** Nomor versinya sudah dinaikkan di `backend/app/version.py`
pada 25 September 2026 atas permintaan pemiliknya. Yang TERSISA dan hanya bisa
dilakukan pemiliknya: commit, push, lalu beri tag `v1.0.8` supaya CI membangun
`.exe` dan paket Linux. Alur build menolak tag yang tidak cocok dengan berkas
versi, jadi tagnya harus persis `v1.0.8`.

Isi rilis ini, dari 1.0.7: tema subtitle yang akhirnya benar-benar dirender,
jarak antar kata yang bisa diatur, sisipan yang bisa disusun (petak bebas,
fade, pengulangan, urutan tumpuk), bingkai wajah yang bisa diperbesar dan
digeser, bingkai yang tidak lagi tertinggal saat penutur berganti, getaran
bingkai yang berkurang, pencatat pemakaian AI, cadangan OpenRouter, pemindahan
folder yang benar, unggahan yang kegagalannya terlihat, dan tagar yang tidak
lagi mengarang nama orang.

**A5. Sertifikat penanda tangan Windows.** Langkah penandatanganannya sudah
ada di CI dan tinggal menunggu rahasianya; tanpa sertifikat, Windows Defender
tetap menahan pemasangannya dengan "More info -> Run anyway". Pilihannya ada di
[PANDUAN-TANDA-TANGAN.md](PANDUAN-TANDA-TANGAN.md), dan semuanya keputusan
pemiliknya: gratis lewat SignPath (khusus sumber terbuka), atau berbayar.

**A6. Isi identitas aplikasi Google bawaan.** Kodenya sudah siap
(`OMNICLIP_GOOGLE_CLIENT_ID` dan `OMNICLIP_GOOGLE_CLIENT_SECRET`, dengan PKCE),
dan selama kosong perilakunya persis seperti sebelumnya. Yang tersisa keputusan
pemiliknya: mengisinya saat membangun rilis, lalu mengajukan verifikasi OAuth
supaya batas 100 test user hilang.

---

## B. Diminta, belum dibangun

**B2. Sisipan yang benar-benar bisa disusun.** Diminta 25 September 2026,
**sebagian besar SELESAI** hari yang sama. Yang tersisa ada di akhir poin ini.

Tujuannya, dengan kata pemiliknya: menaruh media lain yang bisa diatur sesuka
hati. Podcast bola menampilkan cuplikan gol yang diimpor, dan bingkai cuplikan
itu diatur tangan. Efek suara atau musik supaya klip tidak terasa sepi. Intinya
menambah variasi pada isi klip, bukan sekadar menempelkan berkas.

*Yang sudah ada sekarang* (`MediaPanel.jsx`, `render.siapkan_sisipan`):
gambar, video, dan audio bisa ditambahkan dari pustaka; tiap lapisan punya
detik mulai, lama, "dari detik" untuk video, volume, dan sakelar redam untuk
audio. Semuanya diketik sebagai angka di dalam daftar.

*Yang dikerjakan 25 September 2026:*

- **Bingkai sisipan diatur tangan.** Petak bebas dalam PERSEN kanvas (`rect`),
  diseret dan diubah ukurannya langsung di pratinjau lewat `beginRectDrag` yang
  sama dengan bingkai video utama, atau diketik sebagai empat angka. Lima
  preset lama tetap ada tapi sekarang MENULIS rect, jadi hanya ada satu bentuk
  yang disimpan; klip yang tersimpan sebelum ini tetap memakai presetnya.
  Ditambah pilihan isi petak (penuhi lalu potong, atau muat utuh) dan
  ketembusan.
- **Lembut masuk dan keluar** untuk gambar, cuplikan, dan suara sekaligus. Pada
  visual ia bekerja di SALURAN ALFA, jadi yang memudar sisipannya, bukan gambar
  di bawahnya.
- **Putar berulang** untuk berkas yang lebih pendek daripada petaknya, lewat
  `-stream_loop` yang berdiri sebelum `-i`. Panjang yang diminta tidak lagi
  dipotong sepanjang berkasnya saat sakelar ini menyala.
- **Urutan tumpuk** dengan tombol naik dan turun, memindahkan lapisannya di
  dalam daftar. Urutan daftar itu sendiri yang dipakai render, jadi tidak ada
  angka z tersendiri yang bisa berbeda dari yang terlihat.
- Diuji dengan render sungguhan: petak 8%/14%/60%/22% mendarat tepat di
  situ, ketembusan 85% memperlihatkan video di bawahnya, dan fade 0,6 detik
  terlihat separuh tembus pada detik 1,3. 343 uji lolos.

*Lajur linimasa* ternyata sudah ada sejak sebelumnya di `ClipTimeline.jsx`:
diseret untuk memindah, ujungnya ditarik untuk memotong, dan menarik ujung kiri
ikut memajukan detik di dalam berkasnya. *Redam otomatis* juga sudah ada
(`sidechaincompress`).

*Yang MASIH belum ada:*

- **Memilih bagian mana dari sumbernya yang dipakai.** "Penuhi lalu potong"
  selalu memotong dari tengah. Cuplikan gol yang subjeknya di tepi kiri tidak
  bisa digeser di dalam petaknya sendiri.
- **Gerakan di dalam sisipan**: menggeser atau memperbesar perlahan (Ken Burns)
  belum ada, jadi gambar diam tetap benar-benar diam.

*Ditambahkan 25 September 2026 bersama sisipan:* bingkai wajah bisa diperbesar
sampai 2x dan digeser tegak (`frame_zoom`, `frame_geser_y`), supaya wajah bisa
dipindahkan ke bawah saat sisipan menutupi bagian atas. Angkanya menyatakan ke
mana WAJAHNYA pindah, bukan ke mana jendelanya pindah. Pustaka efek suara
bawaan dikosongkan atas keputusan pemiliknya; mesin pembangkitnya ditinggal
utuh di `aset.EFEK`.
- **Pratinjau fade pada suara**: pemutar sisipan di Studio memakai volume
  tetap; lembut masuk dan keluarnya baru terdengar di hasil render.

*Selesai bila*: satu klip podcast bola berisi cuplikan gol yang dibingkai
tangan, satu efek suara di puncaknya, dan musik latar yang meredam sendiri saat
orang bicara, seluruhnya disusun lewat linimasa tanpa mengetik satu angka pun,
lalu dirender dan hasilnya sama dengan pratinjaunya.

**B1. SELESAI.** Tombol "Pilihkan tema untuk klip ini" di panel Gaya, dan
tema untuk SEMUA klip sudah dipilihkan lebih awal di latar belakang sesudah
auto-klip, jadi tombolnya menjawab seketika. AI membaca isi klip, memilih satu
dari 26 tema, menyebut alasannya, dan menyalakan warna per penutur hanya bila
klipnya memang berisi lebih dari satu orang. Yang sengaja TIDAK dikerjakan:
menerapkannya sendiri. Tema adalah keputusan rasa, dan mengganti gaya yang
sudah disetel tangan bukan hal yang pantas terjadi diam-diam.

---

## C. Saran perbaikan yang belum dikerjakan

**C7. Menghapusnya tetap keputusan orang.** Ruang cakram sekarang MENGUSULKAN
video sumber yang layak dibuang (sudah ada klipnya, diunduh lebih dari 14 hari
lalu, lebih besar dari 300 MB) beserta alasannya, dan menandainya sekaligus.
Yang sengaja TIDAK ada: penghapus yang berjalan sendiri. Mengklip ulang video
yang sudah dihapus berarti mengunduhnya lagi, dan mesin tidak tahu mana yang
masih akan dipakai.

**C0. Huruf kapital untuk aksara yang tidak mengenalnya** sekarang dimatikan
sendiri (Jepang, Korea, Mandarin, Arab), di render maupun di pratinjau. Yang
belum: tema yang wujudnya memang bergantung pada huruf kapital tetap ditawarkan
untuk aksara itu, dan di sana ia jadi tema biasa tanpa pemberitahuan.

**C6. SELESAI.** Studio memutar sumbernya langsung bila peramban sanggup
(h264 sampai 1080p), dan untuk sumber 4K atau VP9 yang memang butuh salinan,
salinannya dibuat 1600 piksel, bukan 1280 seperti salinan analisis. Dua
pekerjaan, dua ukuran.

**C5. Enam sambungan untuk seluruh tab.** Pratinjau klip sekarang baru dimuat
saat kartunya terlihat DAN tabnya sedang ditampilkan, paling banyak tiga
sekaligus, dan tiap permintaan menyerah setelah 30 detik dengan galat yang
menyebutkan sebabnya. Yang belum ada: batas yang sama untuk gambar sampul di
halaman Cari video, yang jumlahnya juga puluhan.

**C4. Gemini yang sibuk, bukan Gemini yang tidak ada.** Rantai model sekarang
mengantre ulang model yang menjawab 503 dan mencobanya lagi setelah 20 detik,
dan kartu proyek menyebutkan sebabnya saat klip dipilih mesin lokal. Yang belum
ada: tombol "coba Gemini lagi" langsung dari kartu, tanpa membuka editor.

**C1. Pratinjau yang benar-benar menampilkan hasil rapat.** Sesudah "Rapatkan
jeda", pemutar Studio memutar segmen barunya, tapi peralihan antar potongan di
pratinjau tidak semulus hasil rendernya.

**C3. Statistik sesudah unggah.** Berapa tayangan tiap klip, ditarik dari API
masing-masing, supaya terlihat jenis klip mana yang berhasil.

---

## D. Kelemahan yang masih ada

**D1. Ikut wajah salah sorot ±27% waktu** pada bidikan berisi beberapa orang
(turun dari 46%). Bidikan lebar dengan wajah kecil sengaja belum ditangani:
gerak mulut di sana tidak bisa dipercaya.

**D2. Kartun berwajah jelas** masih dianggap "ada orang", jadi jumlah penuturnya
ditebak dari suara dan efek suara bisa terhitung sebagai orang.

**D4. SELESAI.** Teks yang sudah terbakar di gambar sumber (anime fansub,
potongan berita) dideteksi dari keramaian tepi di seperempat bawah gambar, dan
subtitle OmniClip dinaikkan sampai di atasnya. Diuji pada lima klip: dua anime
bersubtitle terdeteksi (81% dan 89% tinggi gambar), tiga video bersih tidak
ditandai.

**D5. Pola reaksi otomatis untuk kartun belum ada.**

**D8. 503 tidak bisa dihindari, hanya dikelilingi.** "Sedang sibuk" datang
dari kapasitas Google untuk jalur gratis, dan berlaku untuk semua project
gratis sekaligus, jadi kunci kedua tidak menolong di sana (ia menolong pada
batas per menit dan per hari). Yang menolong: menunggu lalu mencoba lagi
sendiri (sudah) dan OpenRouter (sudah). Menyalakan penagihan Google juga
menolong, tapi itu sudah ditolak pemiliknya: OmniClip harus tetap jalan gratis.
Yang belum ada: penjelasan di aplikasi tentang bedanya 503 dan kuota habis,
supaya pemiliknya tidak membeli kunci kedua untuk masalah yang salah.

**D9. Jatah gratis Gemini cukup untuk pemakaian sehari-hari, dan OmniClip
tetap gratis.** Keputusan pemiliknya 25 September 2026: tidak menyalakan
penagihan Google, karena tiap pengguna nanti memakai kuncinya sendiri.

Angkanya mendukung itu, dan sekarang terukur dari catatan pemakaian sendiri.
Jatah Google 20 permintaan per hari per model per project
(`GenerateRequestsPerDayPerProjectPerModel-FreeTier`), dan satu kunci biasanya
melihat tujuh model penuh, jadi sekitar 140 permintaan sehari. Biaya per video:

    memilih klip     1 sampai 3 panggilan   (yang paling berat, ~30rb token)
    tema subtitle    1 panggilan            (satu untuk semua klip sekaligus)
    caption          1 panggilan per klip   (hanya saat tombolnya ditekan)
    bingkai AI       1 panggilan per klip   (hanya bila sakelarnya menyala)

Dengan sakelar bingkai otomatis MATI, satu video memakan 2 sampai 4 panggilan,
jadi jatah sehari cukup untuk puluhan video. Yang menghabiskannya cuma satu
hal: sakelar bingkai otomatis, yang mengantre satu panggilan per klip untuk
enam klip pertama tiap video. Terukur 25 September 2026: dari 80 panggilan
sungguhan dalam sehari, 66 di antaranya sutradara bingkai dan hanya 4 pemilihan
klip.

Penjagaannya sudah ada: sutradara bingkai berhenti memakai sebuah model saat
sisanya tinggal `CADANGAN_KLIP` panggilan, supaya pemilihan klip video
berikutnya tetap kebagian.

**D7. Gemini bisa tidak bisa dipakai seharian.** Terukur 23 September 2026:
enam dari enam model flash menjawab 503 sepanjang hari. Rantai sekarang
mengantre ulang model yang sibuk, mengingat model yang terakhir benar-benar
menjawab, dan jatuh ke OpenRouter sebelum ke mesin lokal. Tapi tanpa kunci
OpenRouter, hari seperti itu tetap berakhir di mesin lokal, dan klipnya terasa
datar.

---

## E. Belum pernah diuji (risiko nyata)

**E1. Unggah sungguhan ke YouTube dan Drive.** Berkas OAuth sudah terpasang
dan jalur izinnya sudah dilewati sampai ke Google, tapi belum ada satu berkas
pun yang benar-benar terkirim. Tiga cacat yang menghalanginya sudah diperbaiki
24 September 2026 dan semuanya baru ketahuan karena dicoba sungguhan: izin
YouTube dan Drive diminta bersamaan (ditolak Google), oauthlib menolak alamat
balik http loopback, dan `include_granted_scopes` diam-diam menggabungkan izin
lama ke permintaan baru. Yang tersisa: menekan tombolnya sampai tersambung,
lalu mengirim satu klip.

**E2a. Bundel Windows tanpa konsol.** Ikon, keterangan versi, penyembunyian
jendela proses anak, dan tombol Keluar semuanya dikerjakan dan diuji di Linux;
yang tidak bisa diuji dari sini justru bagian yang khusus Windows. Rilis
berikutnya harus dicoba langsung di Windows.

**E2. Semua fitur baru di Windows:** unduhan Deno dan server PO Token, encoder
GPU, profil, impor lewat jalur, dan unduhan font Noto.

**E3. Render GPU pada aplikasi desktop Linux.** Ffmpeg statis yang dibundel
dibangun tanpa encoder GPU, jadi di sana render masih x264 walau kartunya
mampu.

**E4. Pemulihan cadangan sampai tuntas.** Membuat cadangan sudah diuji
(74 MB, lolos `PRAGMA integrity_check`, 105 analisis utuh). Menukarnya saat
aplikasi dimulai belum pernah dijalankan sungguhan.

---

## Pengujian

```bash
cd backend && ./venv/bin/python -m unittest discover -s tests -t .
```

100 uji, tanpa memasang apa pun, selesai dalam sepersekian detik. Yang diuji
adalah bagian yang rusaknya paling tidak terlihat: penyusun teks dan subtitle,
tema dan sorotan kata, caption dan tagar, perapatan jeda, geometri bingkai,
penilaian isi klip,
skema dan jawaban model AI, pemilihan model Whisper, serta pemeriksaan jalur
berkas yang datang dari peramban.

Uji pertama yang ditulis langsung menemukan satu cacat: `"Cek 天井 mix"`
kehilangan kedua spasinya karena aturan lama menghapus spasi bila salah satu
sisinya CJK. Sekarang syaratnya kedua sisi.
