# Sisa Pekerjaan OmniClip

> **Arsip.** Daftar yang berlaku sekarang ada di [RENCANA.md](RENCANA.md).
>
> Berkas ini ditulis 12 September 2026 dan terus ditambahi catatan pengerjaan
> sampai 23 September, tapi daftar "belum selesai" di bagian atasnya tidak
> pernah ikut dikoreksi, sebagian besar sudah dikerjakan. Disimpan karena
> angka-angka pengukurannya masih berguna, bukan karena daftarnya masih benar.

Catatan hal-hal yang **belum selesai**, ditulis 12 September 2026 setelah commit
`b4f991f`. Tiap poin memuat apa yang sudah terukur, bukan hanya apa yang terasa,
supaya saat dikerjakan nanti tidak perlu menebak ulang dari awal.

Urutan yang disepakati: **subtitle dulu**, lalu **membuat sistem bisa diakses
online**. Bingkai sengaja ditinggalkan dulu dalam keadaan sekarang.

---

## 1. Bingkai otomatis, ditunda, sekitar 80% benar

Sudah bekerja: bingkai mengikuti orang yang sedang bicara. Kuncinya bukan
algoritma pencocokannya melainkan cara mulut diukur, dulu petaknya diskalakan
jarak antar mata, yang menyusut sampai 0,30 lebar wajah ketika orang duduk
saling menghadap, sehingga yang terukur dinding di belakangnya. Sekarang
diskalakan lebar kotak wajah, dan yang diukur **bukaan** mulut ditambah
**ragam** bukaannya, bukan beda piksel antar bingkai.

| cara mengukur | pemisahan (simpangan baku) |
|---|---|
| beda piksel, petak lama | 0,023, setara nol |
| beda piksel, petak benar | 0,181 |
| bukaan mulut | 0,512 |
| bukaan + ragamnya | **1,074** |

Penempatan bingkai, diukur pada 10.599 sampel dari empat video: 99,5% wajah di
dalam kotak, 96,3% di tengah, 2,8% terjebak di antara dua wajah.

### Yang masih kurang

**a. Wajah hilang saat efek abu-abu + tangan menutupi wajah.**
Diperiksa pada `XtAoIx6-EWw` detik 469. Kejenuhan warna separuh kanan layar
jatuh dari ~120 ke 46,8 (efek hitam-putih), dan jumlah wajah terdeteksi turun
dari 2 ke 1. Tapi penyebabnya **bukan semata warnanya**: pada bingkai itu
orangnya juga sedang menutupi wajah dengan tangan sambil menunduk. Empat
penawar murah sudah dicoba dan semuanya gagal, sampel diperbesar ke 960 px,
seluruh bingkai dijadikan abu-abu, kontras lokal dinaikkan (CLAHE), dan
gabungan CLAHE + sampel besar. Tidak satu pun menemukan wajahnya.

Perlu diputuskan nanti: ini soal **deteksi wajah** (butuh detektor yang tahan
oklusi) atau soal **pilihan editorial**. Momen itu adalah reaksi, bukan ucapan,
membingkainya butuh kemampuan yang berbeda dari mengikuti penutur, yaitu
mengenali momen penting. Keduanya sah, tapi bukan satu pekerjaan yang sama.

**b. Kesepakatan pemetaan wajah↔suara masih menengah.**
Diukur sebagai konsistensi antar klip dalam satu video: 78%, dengan 75% klip
berhasil dipetakan. Sisanya jatuh ke aturan "ikuti bidikan penyunting", yang
aman tapi tidak pernah berpindah pada bidikan dua orang yang diam.

**c. Belum dicoba sama sekali:** model deteksi penutur aktif sungguhan
(TalkNet/SyncNet dalam bentuk ONNX). Itu arah yang paling menjanjikan kalau
suatu saat 80% dirasa belum cukup.

---

## 2. Subtitle, hasil render berbeda dari pratinjau

**Ini pekerjaan berikutnya.**

Sudah dibetulkan sebelumnya (commit `37aa145`): **ukuran huruf** dan
**pembungkus baris**. Penyebabnya, `size` adalah Fontsize pada berkas ASS, dan
libass tidak memperlakukannya seperti `font-size` CSS, terukur, tinggi kapital
lurus terhadap Fontsize dengan kemiringan 0,521, sedangkan pratinjau memakai
0,756, jadi teks di editor 1,45× lebih besar daripada di video.

### Yang masih berbeda

- **Warna font.** Warna dasar per penutur dan warna sorotan kata tidak sama
  antara pratinjau dan hasil render. Belum dilacak. Tempat pertama yang harus
  diperiksa: apakah `caption_style` yang dikirim ke `/render-clip` benar-benar
  memuat `speaker_colors` dan `highlight`, dan apakah `CaptionStyleModel` di
  `backend/app/routers/clips.py` tidak membuang keduanya.
- **Animasi tidak ada di hasil render.** Di pratinjau kata aktif memantul
  (`karaoke_pop`); di video tidak terlihat. Perlu dicek apakah `animation`
  ikut terkirim, dan apakah tag `\t(...)` pada ASS benar-benar tertulis.

### Cara mengujinya (sudah terbukti berguna)

Tangkap layar `.clip-preview-box` lewat Playwright pada detik tertentu,
ambil bingkai hasil render pada detik yang sama dengan `ffmpeg -ss`, lalu
bandingkan berdampingan. Tanpa itu, perbedaan ukuran 1,45× sempat tidak
terlihat selama berminggu-minggu.

---

## 3. Auto-subtitle per orang, yang paling sulit

Tujuannya: sistem sendiri yang menentukan **ada berapa orang**, lalu
memasangkan **suara** dengan **wajah**, lalu memberi warna subtitle per orang,
tanpa pembetulan manual.

Tiga bagian, dan masing-masing punya masalahnya sendiri:

### a. Berapa orang di video

Sudah ada, memakai sidik wajah SFace dengan pagar "jumlah wajah terbanyak yang
pernah terlihat bersamaan" saat sidiknya lemah.

| video | sebenarnya | hasil sistem |
|---|---|---|
| podcast empat orang | 4 | 4 |
| podcast dua dokter | 2 | 3 |
| rekaman lapangan | 2 | 2 |
| Andry/Atta | 2 | 2 |

### b. Nomor orang masih bisa tertumpuk

Diamati pengguna pada video lima orang dengan susunan **2 kiri, 1 tengah,
2 kanan**: yang kiri dapat nomor 1 dan 2, tengah 3, tapi **yang kanan dapat 1
dan 4**, nomor 1 terpakai dua kali untuk orang berbeda.

Penyebab yang sudah diketahui dari video lain: kemiripan sidik wajah antar
orang **yang sama** bisa jatuh ke 0,133-0,175 saat wajahnya kecil atau
menyamping, sementara antar orang **berbeda** bisa naik ke 0,262-0,279. Kedua
sebaran itu bertumpang tindih, jadi tidak ada satu ambang yang memisahkannya.

Arah yang masuk akal: gunakan **posisi duduk** sebagai pengunci pada video
berkamera diam, dua orang yang terlihat bersamaan di tempat berbeda pasti
orang berbeda, apa pun kata sidik wajahnya. Itu kendala keras yang belum
dipakai untuk mencegah tabrakan nomor.

### c. Memasangkan suara dengan wajah

Sejak 12 September ada jalur baru: **suara ditambatkan ke wajah**. Ketika layar
hanya memuat satu wajah, penyuntingnya sendiri sudah mengatakan siapa yang
bicara; ketika beberapa wajah terlihat, bukaan mulut yang menjawab. Potongan
suara pada saat-saat itu jadi contoh berlabel, dan dari situ disusun satu model
suara per orang untuk melabeli seluruh rekaman. Labelnya **adalah** nomor orang,
jadi warna subtitle dan nomor wajah berhenti jadi dua penomoran yang berbeda.

Metodenya menguji dirinya sendiri sebelum dipakai: model dibangun dari separuh
jangkar, lalu ditanyai separuh yang belum pernah dilihatnya. Lulus di atas 70%,
dipakai; di bawahnya, sistem kembali ke pengelompokan suara biasa.

| rekaman | jangkar | uji silang | hasil |
|---|---|---|---|
| podcast dua orang berpotong close-up | 126 kalimat | **84%** | dipakai, nomor penutur = nomor wajah |
| rekaman meja statis lima orang | 199 kalimat | 60% | ditolak, kembali ke cara lama |

**Yang masih kurang:** rekaman berkamera diam yang tidak pernah memotong ke satu
orang. Di sana jangkar "satu wajah di layar" hampir tidak ada (terukur 1,4 detik
untuk enam klip), jadi yang tersisa hanya bukaan mulut, dan bukaan mulut saja
menghasilkan jangkar yang tercemar reaksi penyimak. Arah yang belum dicoba:
model deteksi penutur aktif sungguhan (TalkNet/SyncNet ONNX) untuk menggantikan
bukaan mulut sebagai sumber jangkar kedua.

---

## 4. Dipakai di mana saja, sebagai aplikasi desktop

**Arahnya berubah 12 September 2026.** Rencana hosting ditinggalkan: tidak ada
anggaran untuk domain, VPS, maupun mini PC selama clipping belum menghasilkan,
dan laptop tidak boleh dijadikan server. Bentuknya sekarang **satu aplikasi yang
dijalankan tiap orang di komputernya sendiri**, dengan penyimpanan
sendiri-sendiri. Lihat `PANDUAN-APLIKASI-DESKTOP.md`.

`.apk` tidak dikerjakan, dan alasannya terukur: keempat dependensi inti punya
**nol** wheel Android (ctranslate2, onnxruntime, opencv, av), sementara Windows
punya semuanya. Tiap satu harus dikompilasi silang dari sumber untuk
`aarch64-linux-android`, dan `ffmpeg-kit`, satu-satunya jalur ffmpeg praktis di
Android, sudah diarsipkan pengembangnya.

### Sudah selesai dan diuji

- **Bundel PyInstaller** (`backend/omniclip.spec`), satu-folder, ± 770 MB
  terpasang. Peluncur `omniclip_app.py` memilih port kosong sendiri dan membuka
  peramban.
- **Penyimpanan pindah ke folder pengguna** saat terbungkus
  (`%LOCALAPPDATA%\OmniClip`), supaya memperbarui aplikasi tidak menghapus klip.
  `OMNICLIP_STORAGE` menimpa keduanya.
- **ffmpeg statis dibundel**, ditaruh di depan `PATH`, satu baris, bukan
  sebelas suntingan di tempat pemanggilan, dan yt-dlp ikut menemukannya.
- **SFace mengunduh dirinya sendiri.** Dulu hanya bisa didapat lewat perintah
  curl di requirements.txt: cukup saat satu-satunya pengguna adalah penulis
  kodenya, dan berarti pengenal wajah tidak akan pernah menyala di komputer
  siapa pun begitu aplikasinya dibagikan.
- **`--periksa`**: bundel memeriksa dirinya sendiri, 16 pustaka, berkas
  bundelan, ffmpeg beserta 7 filter dan 2 encoder yang dipakai, detektor wajah,
  migrasi basis data, dan satu subtitle yang benar-benar dibakar. CI
  menggagalkan build kalau ada yang kurang.
- **GitHub Actions** membangun `.exe` Windows dan `.tar.gz` Linux pada tiap tag.
  Gratis tanpa batas karena repo publik, dan itu satu-satunya cara: PyInstaller
  tidak bisa membangun untuk sistem lain.

### Cacat Windows yang ditemukan dan diperbaiki

`fontsdir` masuk ke filtergraph ffmpeg **tanpa disiapkan**. Parser filtergraph
memperlakukan `:` sebagai pemisah opsi, dan di Windows nilainya berbentuk
`C:\Program Files\...`. Dibuktikan dengan folder ber-titik-dua di Linux:

```
Could not create a libass track when reading file 'uji/OmniClip/fonts'
```

Bukan font yang keliru, **setiap render bersubtitle gagal**, hanya di Windows.
Tiga tempat menyusun path untuk filtergraph dengan tiga salinan kode yang tidak
sama, dan salinan `fontsdir` tidak pernah mendapat perlakuan itu sama sekali.
Sekarang ketiganya memakai `services/paths.ffpath()`.

### Bukti bundel Linux, menyeluruh

Dijalankan terhadap pustaka video asli: render 12 detik selesai dalam 15 detik,
1080x1920 h264 30fps, AAC 48kHz stereo. Bingkai diperiksa dengan mata, reframe
mengikuti orang yang bicara, subtitle terbakar dengan font bundelan, sorotan
kata kuning, tanda air di tempatnya. SFace terunduh sendiri di tengah analisis.

### Yang belum

1. **Belum ada build Windows yang pernah dijalankan.** Semua bukti di atas dari
   Linux. `--periksa` di CI Windows adalah pengganti yang jujur, tapi bukan
   pengganti orang yang benar-benar membukanya.
2. **Tidak bertanda tangan digital.** Windows Defender akan menahan aplikasinya
   dengan "More info -> Run anyway". Sertifikat penandatangan kode berbayar.
3. **Cookies YouTube masih lewat variabel lingkungan**, belum bisa dipasang dari
   antarmuka.
4. **Tidak ada pembersihan otomatis.** Terukur: 3,8 GB per bulan, dan 82%-nya
   video sumber yang sebenarnya bisa dibuang setelah klipnya jadi.
5. ~~Pembaruan masih manual~~, **selesai.** Aplikasi mengecek GitHub
   Releases, dan bisa mengunduh serta memasang sendiri lewat proses penolong
   yang menukar folder setelah aplikasi tertutup. Diuji dengan membangun bundel
   0.9.0 dan membiarkannya memperbarui diri ke 1.0.0: unduh 319 MB, tukar,
   buka kembali, ~60 detik. Rilis pertama: **v1.0.1**.

### Yang tetap berguna dari rencana hosting

Gerbang kata sandi dan pemeriksaan identitas Cloudflare Access tetap ada dan
tetap dipakai: gerbang itulah yang membuat "buka dari HP lewat Wi-Fi rumah"
aman, tanpa domain dan tanpa biaya. `PANDUAN-AKSES-JARAK-JAUH.md` tetap berlaku
kalau suatu saat ada anggaran untuk domain.

## Catatan cara kerja yang terbukti mahal kalau dilanggar

- **Lihat datanya, jangan cuma hitung.** Perbaikan bingkai terbesar sesi ini
  datang setelah petak mulutnya ditampilkan sebagai gambar. Sebelum itu, berjam-
  jam dihabiskan menyetel statistik di atas petak yang isinya dinding bambu.
- **Ukur sebelum dan sesudah, pada video yang tidak dipakai menyetel.**
  Beberapa "perbaikan" ternyata hanya cocok pada satu video.
- **Kontrol negatif itu perlu.** Rekaman stand-up satu orang adalah yang
  membuktikan bahwa pemisahan penutur tidak mengarang orang kedua.

---

# Catatan: gulir tak hingga, dan kenapa ia "masih rusak" tiga kali

Dilaporkan rusak tiga kali berturut-turut, dan dua kali pertama saya menjawab
dengan bukti bahwa kodenya benar. Buktinya memang benar, dan tidak menjawab
apa pun, karena saya mengukur hal yang salah.

Kesalahan ukur saya: potret daftar diambil SETELAH semuanya tenang. Yang
dialami pengguna justru terjadi di antaranya. Setiap pemuatan, termasuk yang
dipicu gulir, mengganti seluruh daftar dengan dua belas kotak kerangka
(`{loading ? <kerangka/> : <daftar/>}`). Terekam langkah demi langkah:

    langkah | scrollY | tinggi halaman | kartu
       1    |    1100 |           2608 | 20
       2    |     685 |           1453 | 12      <- runtuh

Tinggi halaman runtuh, peramban memaksa posisi gulir turun, lalu data datang
dan seluruh kartu ter-render ulang. Di layar itu terbaca persis seperti
"dilempar ke atas dan videonya diganti". Syaratnya sekarang
`loading && !feed.length`: kerangka hanya muncul saat memang belum ada apa-apa.

Pelajaran yang layak disimpan: uji yang menunggu sampai tenang tidak bisa
menemukan cacat yang hanya ada saat belum tenang. Untuk keluhan yang menyangkut
posisi gulir, rekam JEJAKNYA, bukan keadaan akhirnya.

# Antrean pembaruan berikutnya

Ditulis 16 September 2026. Empat hal yang diminta dan sengaja **ditunda**,
bukan karena sulit, melainkan karena gulir tak hingga dan pembaruan pustaka
didahulukan. Urutan di bawah adalah urutan yang masuk akal untuk dikerjakan.

## A. Pemilih folder, SELESAI 16 September 2026

Dikerjakan dengan jalan nomor 1 di bawah: penjelajah folder di backend
(`GET /api/settings/jelajah`) plus dialog `FolderPicker.jsx`. Ada pintasan ke
Home/Desktop/Unduhan/Video/Dokumen dan ke tiap cakram terpasang, tombol "Folder
baru", dan penolakan folder yang tidak bisa ditulisi. Catatan aslinya
ditinggalkan di bawah karena alasannya masih menjelaskan kenapa ia dibangun
begitu.

## A-lama. Pemilih folder, bukan mengetik jalur

Sekarang tombol "Pindahkan ke…" membuka `window.prompt` dan meminta jalur
diketik penuh (`/media/ynot/744E3DDC4E3D97B6/Projek Coding/...`). Itu hampir
mustahil dilakukan benar tanpa menyalin dari tempat lain, dan satu salah ketik
berarti folder yang tidak ada.

Yang menghalangi, dan perlu diputuskan lebih dulu: **halaman web tidak pernah
diberi jalur berkas sungguhan oleh peramban.** `<input type="file" webkitdirectory>`
memberi nama berkas di dalam folder, bukan jalur folder itu di cakram.
`showDirectoryPicker()` memberi pegangan yang hanya berlaku di dalam peramban,
tidak bisa dipakai ffmpeg. Jadi ada dua jalan:

1. **Penjelajah folder buatan sendiri di backend.** Endpoint yang mendaftar isi
   sebuah direktori, dan dialog di frontend untuk menyusurinya. Bekerja di mana
   saja termasuk saat OmniClip dibuka dari HP. Kira-kira satu berkas komponen
   plus satu endpoint, dan perlu penjagaan ketat supaya ia tidak jadi cara
   membaca seluruh cakram dari jauh.
2. **Dialog folder milik sistem operasi**, dipanggil dari backend (`tkinter`,
   `zenity`, atau PowerShell). Terasa paling benar di komputer sendiri, tapi
   TIDAK bekerja saat OmniClip dibuka dari perangkat lain, dialognya muncul di
   komputer yang menjalankan backend.

Saran: nomor 1, dengan daftar tempat umum (Home, Desktop, Videos, cakram yang
terpasang) sebagai titik awal supaya jarang perlu menyusur jauh.

## B. Durasi klip per proyek, SELESAI 16 September 2026

Pemilihnya (`features/studio/PanjangKlip.jsx`) sekarang ada di dua tempat klip
DIMULAI: panel "Klip video baru" di Partitur, dan di bawah tombol "Potong jadi
klip" di halaman tonton. Nilai di Pengaturan tinggal jadi bawaan untuk video
baru.

Sengaja TIDAK ditaruh di dalam editor klip: nilai ini dipakai saat kandidat
dicari, jadi ia menentukan klip mana yang ADA, bukan bagaimana klip yang sudah
ada ditampilkan. Menaruhnya di editor akan menjanjikan sesuatu yang tidak bisa
ditepati tanpa menganalisis ulang seluruh video.

## B-lama. Durasi klip diatur per proyek, bukan di pengaturan utama

Sekarang `omniclip_clip_length` tinggal di `localStorage` dan berlaku untuk
semua. Yang diinginkan: tiap proyek membawa durasinya sendiri.

Tabel `projects` sudah punya `state_json`, jadi tempatnya sudah tersedia, yang
perlu dikerjakan adalah memindahkan pilihannya ke panel proyek, memakai nilai
pengaturan utama hanya sebagai **bawaan untuk proyek baru**, dan meneruskannya
lewat `AutoClipRequest` alih-alih membacanya dari localStorage saat job dibuat.

## C. Filter pencarian: dilengkapi

Sudah beres di pembaruan ini: "terpopuler" diurutkan ulang di sisi kita memakai
jumlah tayangan yang memang ikut di hasil pencarian datar, jadi urutannya benar
menurun. Yang belum:

- **Durasi** (pendek / sedang / panjang), YouTube punya parameternya, dan
  untuk auto-clip inilah filter yang paling berguna: video 40 menit dan video
  3 menit menuntut perlakuan yang sama sekali berbeda.
- **Tanggal unggah** sebagai penyaring (minggu ini, bulan ini, tahun ini),
  bukan hanya sebagai pengurut.
- **"Rating"** masih diserahkan sepenuhnya ke YouTube. Tidak seperti tayangan,
  angkanya tidak ikut di hasil pencarian datar, jadi mengurutkannya di sini
  menuntut satu permintaan per video, persis pola yang memicu verifikasi bot.
  Perlu diputuskan: hapus pilihannya, atau ambil datanya hanya untuk kartu yang
  terlihat.

## D-1. Klip gameplay, SELESAI SEBAGIAN 16 September 2026

Mode bingkai baru `gaming`: wajah pemain di bidang atas, permainannya UTUH di
bidang tengah, sisanya latar kabur tempat subtitle duduk. Letak facecam dicari
sendiri dari videonya (`reframe.deteksi_facecam`), tidak ada yang perlu
digambar pengguna.

Yang menandai facecam bukan "wajah terbesar" melainkan wajah yang semuanya
terkurung di petak kecil yang tidak berpindah. Model pertama saya, semua wajah
berbagi satu titik tengah, SALAH, dan bahan uji yang membuktikannya: sebaran
tegaknya 0,005 tapi mendatarnya 0,061, bukan karena panel bergerak melainkan
karena ada DUA orang di dalam panel yang sama.

Diuji: facecam buatan di x=72,9% terdeteksi di x=72,0%; dua podcast sebagai
kontrol keduanya ditolak; render menghasilkan 1080x1920 dengan wajah diperbesar
penuh di atas dan permainan utuh tanpa diregangkan.

BELUM diuji pada rekaman gameplay sungguhan, unduhan bahan ujinya gagal dua
kali. Yang masih perlu dilihat: facecam berbentuk lingkaran (banyak dipakai
streamer), facecam yang berpindah sisi di tengah video, dan video tanpa facecam
sama sekali yang seharusnya jatuh ke mode `smart`.

## D-3. Linimasa bingkai, SELESAI 16 September 2026

Satu klip, beberapa cara membingkai, masing-masing berlaku di potongan waktunya
sendiri (`frame_keys`). Tiap kunci menghasilkan kanvas penuh lewat cabangnya
sendiri, lalu ditumpuk dengan `enable=between(t,…)`.

Alternatif yang DITOLAK: satu crop yang ukurannya digerakkan `sendcmd`. Jauh
lebih murah, tapi mengubah lebar crop di tengah aliran mengubah ukuran bingkai
yang masuk ke `scale` dan memaksa ffmpeg menyusun ulang filter graph-nya di
tengah jalan. Menggerakkan posisi saja aman, itulah yang dipakai "ikuti
wajah"; mengganti ukuran tidak. Ongkos cara yang dipakai: tiap cabang tetap
dihitung walau tidak terlihat, jadi render melambat kira-kira sebanding jumlah
kuncinya.

Diuji: satu klip 12 detik dengan tiga kunci (gaming -> kotak tetap -> potong
tengah) menghasilkan tiga potongan yang benar-benar berbeda, dan subtitle
karaoke tetap berjalan melintasi ketiganya.

Yang BELUM: kotak untuk mode "box" masih diisi lewat empat kolom angka (x/y/w/h
persen), belum bisa diseret di atas pratinjau. Seretan sudah ada untuk mode
"Susun sendiri", jadi bahannya tersedia, yang perlu dikerjakan adalah
menyambungkan kotak kunci terpilih ke editor persegi yang sama.

## D-2. Apakah pemilihan klip menyesuaikan jenis kontennya

Pertanyaan yang belum dijawab dan belum diuji: gameplay, kartun anak, dan
podcast diperlakukan sama atau tidak.

Yang sudah pasti dari kode: **bingkai** sudah menyesuaikan, `plan_reframe()`
mengukur `face_coverage`, dan di bawah 0,20 ia otomatis pindah ke mode bilah
kabur. Rekaman layar dan gameplay jatuh ke sana dengan sendirinya.

Yang **belum** menyesuaikan sama sekali adalah pemilihan klipnya. Bobot di
`heuristics.py` (hook 0,30 · kelengkapan 0,20 · energi 0,15 · kerapatan 0,10 ·
kekhasan 0,15 · panjang 0,10) disusun untuk **orang berbicara**. Leksikon
hook-nya bahasa Indonesia percakapan, dan `density` menghitung kata per detik.
Pada gameplay tanpa komentar, atau kartun anak yang momen terbaiknya visual dan
bunyi alih-alih kalimat, seluruh timbangan itu mengukur hal yang salah, bukan
gagal dengan keras, tapi memilih bagian yang paling banyak bicaranya, yang
belum tentu bagian yang paling layak jadi klip.

Langkah yang jujur sebelum mengubah apa pun: **uji dulu**. Jalankan tiga jenis
video, catat klip yang dipilih, dan bandingkan dengan pilihan manusia. Kalau
timbangannya memang meleset, yang dibutuhkan kemungkinan besar bukan bobot baru
melainkan sinyal baru, puncak audio dan perpindahan adegan (`scdet` sudah
tersedia di ffmpeg mesin ini) untuk konten yang nilainya tidak ada di kata-kata.










<!-- ========================================================================
     BATAS. Semua di atas garis ini ditulis lebih dulu dan BELUM diperiksa
     ulang oleh pemilik proyek. Yang di bawah ini daftar baru, disepakati
     16 September 2026, dan berdiri sendiri.
     ===================================================================== -->

# ══════════════════════════════════════════════════════════════════════
# DAFTAR BARU, disepakati 16 September 2026
# ══════════════════════════════════════════════════════════════════════

Dipisahkan dari catatan di atas atas permintaan pemilik proyek: yang di atas
belum sempat diperiksa apakah benar-benar sudah dikerjakan, jadi keduanya tidak
boleh bercampur.

Sudah selesai hari ini dan TIDAK masuk daftar ini: lajur **Bingkai** di linimasa
klip, tiap potongan waktu punya caranya sendiri (ikuti wajah / kotak tetap /
main game / potong tengah / bilah kabur), bisa dibelah dengan klik dua kali atau
tombol "Potong bingkai", batasnya bisa diseret.

---

## 1. Kotak manual digambar di pratinjau, SELESAI 16 September 2026

Kotak mode "Kotak tetap" sekarang diseret dan diubah ukurannya langsung di
pratinjau **Video sumber**, dengan empat pegangan sudut, memakai mesin seret
yang sama (`beginRectDrag`) dengan bingkai susun-sendiri, supaya keduanya terasa
sama di tangan. Perubahannya ditulis balik ke kunci yang sedang berlaku di lajur
Bingkai, jadi tiap potongan waktu punya kotaknya sendiri.

Sekalian selesai di hari yang sama:

- Pratinjau mengikuti linimasa. Memindahkan garis main ke potongan lain langsung
  mengubah apa yang terlihat, dan label pratinjaunya menyebut mode yang benar
  (diuji keempat mode satu per satu).
- Menekan nama cara = memotong di posisi garis main. Sebelumnya ia mengubah
  SELURUH potongan, yang memaksa dua gerakan untuk satu maksud: belah dulu, baru
  pilih. Diuji: 1 potongan -> tekan "Kotak" di 30% -> 2 potongan -> tekan "Game"
  di 70% -> 3 potongan, batas-batasnya tepat di posisi garis main.
- Empat kolom angka x/y/w/h di panel Bingkai tetap ada sebagai jalan untuk
  angka yang persis, tapi tidak lagi menjadi satu-satunya cara.

Kekurangan yang paling dekat dengan pekerjaan hari ini. Mode **K (kotak tetap)**
sudah bisa dipasang per potongan waktu, tapi ukuran kotaknya masih diisi lewat
empat kolom angka (x/y/w/h dalam persen) di panel Bingkai.

Yang seharusnya: pilih potongan di lajur Bingkai, lalu seret kotaknya langsung
di atas pratinjau **Video sumber**. Bahannya sudah ada, `FrameStage.jsx` sudah
bisa menggambar dan menyeret persegi untuk mode "Susun sendiri", lewat
`rectDrag.js`. Yang perlu dikerjakan adalah menyambungkan potongan yang sedang
terpilih ke editor persegi yang sama, dan menahan kotak itu tetap terlihat
selama playhead berada di dalam rentangnya.

Ini yang membuat contoh "lima orang bereaksi" benar-benar enak dipakai: kotaknya
digambar sekali mengelilingi kelima orang, bukan ditebak lewat angka persen.

## 2. Klip gaming, sebagian SELESAI 16 September 2026

Dua hal selesai hari itu:

- **Diuji pada rekaman gameplay SUNGGUHAN**, bukan lagi facecam tempelan di
  atas pola buatan. Pada video Windah Basudara `qgTmLOW-coo`, facecam-nya
  ditemukan di pojok kiri-bawah (x=0%, y=59,5%, lebar 35,6%, tinggi 40,5%) dan
  hadir di 99,2% sampel. Ini menutup lubang yang dicatat di bawah.
- **Tidak perlu disetel tangan.** Memilih "Main game" memanggil
  `POST /api/clip-facecam`, yang mengembalikan susunan dua bidang siap pakai.
  Kedua kotaknya digambar di pratinjau sumber dengan label "Permainan" dan
  "Reaksi", dan pratinjau 9:16 menampilkan hasil susunnya, jadi apa yang akan
  dirender terlihat sebelum dirender. Sebelumnya mode ini otomatis tapi tak
  terlihat, dan "otomatis tapi tak terlihat" sulit dibedakan dari "tidak
  bekerja".

Sisa pekerjaannya di bawah ini masih berlaku.

## 2-lama. Klip gaming: dari deteksi jadi benar-benar bisa diandalkan

Yang sudah ada: mode **Main game** menyusun wajah di atas, permainan utuh di
bawah, dan letak facecam dicari sendiri (`reframe.deteksi_facecam`).

Sudah diuji pada satu rekaman gameplay sungguhan dan hasilnya tepat (lihat
bagian di atas). Yang masih belum diperiksa:

- facecam berbentuk lingkaran, banyak dipakai streamer, dan detektor sekarang
  mengasumsikan persegi;
- facecam yang berpindah sisi di tengah video;
- video tanpa facecam sama sekali, yang harus jatuh ke mode `smart`;
- penajaman batas panel. Dua cara sudah dicoba dan dibuang (kontras gerakan,
  lalu tepi lurus yang tidak berpindah); catatannya ada di `reframe.py`. Cara
  kedua sempat menemukan tepi kanan dan bawah TEPAT, jadi ia layak dicoba lagi
  dengan ambang yang disetel pada bahan nyata, bukan dengan algoritma lain.

## 3. Jumpscare: berpindah sendiri ke reaksi penuh

Sekarang perpindahan gaming → reaksi penuh harus ditandai tangan di lajur
Bingkai. Yang diinginkan: sistem menemukannya sendiri.

Bahannya sudah tersedia dan belum dipakai: `scdet` (deteksi potongan adegan) dan
`silencedetect`/`astats` sudah ada di ffmpeg mesin ini, dan jejak energi audio
sudah dihitung di `heuristics.py`. Jumpscare punya tanda tangan yang tajam,
lonjakan energi audio mendadak sesudah periode tenang, sering bersamaan dengan
potongan adegan. Begitu titiknya ditemukan, yang dilakukan tinggal menyisipkan
kunci bingkai: mode `box` seputar facecam, mulai di titik itu, selama 2-3 detik.

Perlu diputuskan lebih dulu: rasio bidang reaksinya. "Full reaksi dalam ratio
yang tepat" berarti facecam 16:9 yang dijadikan 9:16 harus dipotong, dan
memotongnya asal tengah akan memenggal wajah pada facecam yang orangnya duduk
di pinggir. Jejak wajah dari `plan_reframe` bisa dipakai di sini.

## 4. Beberapa reaksi sekaligus, otomatis

Contoh yang diberikan: lima narasumber, satu melempar lelucon, lalu semuanya
bereaksi. Yang diinginkan sistem tahu sendiri kapan harus berpindah dari satu
wajah ke bidikan yang memuat semuanya.

Yang sudah ada dan bisa dipakai: `plan_reframe` sudah mengembalikan `people`
(jejak tiap orang), `people_seen` (kapan ia benar-benar terlihat), dan
`speaker_faces` (peta penutur ke wajah). Jadi "siapa yang sedang bicara" dan
"siapa saja yang ada di kamera" keduanya sudah diketahui.

Aturan yang masuk akal untuk dicoba pertama: saat satu orang bicara terus →
ikuti wajahnya; saat giliran bicara berhenti dan gerak mulut BEBERAPA orang
naik bersamaan → sisipkan kunci `box` yang memuat semua wajah yang terlihat.
Kotaknya dihitung dari `people` di rentang itu, bukan digambar.

Risiko yang harus dijaga: bingkai yang berpindah terlalu sering lebih buruk
daripada tidak berpindah sama sekali. Perlu jarak minimum antar perpindahan,
dan lama minimum tiap bidikan.

## 5. Bahan dari luar: highlight yang diimpor ikut ke dalam klip

Contoh yang diberikan: orang membahas sepak bola di bidang atas, cuplikan
pertandingannya di bidang bawah.

Ini yang paling jauh dari kode sekarang, dan bukan karena susunannya,
`build_layout_graph` sudah bisa menyusun beberapa bidang. Yang belum ada adalah
**sumber kedua**: seluruh jalur render hari ini berangkat dari SATU berkas
masukan, dan tiap bidang adalah jendela ke dalam berkas yang sama. Menambah
berkas kedua berarti menyentuh `_build_segment_graph`, penyelarasan waktu antara
dua sumber, dan pertanyaan yang belum punya jawaban: bagian mana dari cuplikan
yang dipakai, dan apakah audionya ikut atau dibisukan.

Sebaiknya dikerjakan paling akhir, dan sebaiknya dimulai dari versi manual,
pengguna memilih berkasnya dan menentukan rentangnya sendiri, sebelum ada
apa pun yang dikerjakan otomatis.

---

### Catatan yang berlaku untuk seluruh daftar ini

Nomor 3, 4, dan 5 semuanya menambah keputusan yang diambil sistem tanpa diminta.
Tiap keputusan otomatis yang meleset lebih mahal daripada ketiadaannya, karena
pengguna harus menemukannya dulu sebelum bisa membetulkannya. Jadi masing-masing
sebaiknya lahir sebagai kunci bingkai yang BISA DILIHAT dan bisa dihapus di lajur
Bingkai, bukan sebagai perilaku tersembunyi di dalam renderer.

---

## 6. Bug yang ditemukan sambil jalan, belum diperbaiki

`group_people()` melempar `too many values to unpack (expected 2)` pada sebagian
video. Terlihat di log sebagai `Pengelompokan orang gagal: …`.

Bukan kegagalan keras, `plan_reframe` menangkapnya dan jatuh ke penomoran
berdasarkan tempat duduk, jadi render tetap jalan dan bingkai tetap mengikuti
wajah. Akibatnya halus dan justru karena itu perlu dicatat: nomor orang jatuh ke
urutan duduk, yang benar untuk bidikan lebar dan keliru begitu kamera berpindah
ke close-up. Tanda arah bingkai menyimpan NOMOR, jadi tanda yang dipasang saat
penomorannya meleset akan menunjuk orang yang salah.

Sudah dipastikan BUKAN akibat pekerjaan 16 September: `git diff` pada
`reframe.py` hari itu hanya berisi penambahan (199 baris, nol penghapusan) dan
`group_people` tidak tersentuh sama sekali.

---

## 7. Catatan: dua sumber kebenaran untuk cara membingkai, SELESAI 16 September 2026

Dilaporkan sebagai "timeline bingkai tidak sinkron dengan menu bingkai", dan
diagnosisnya persis itu: panel menulis ke `frameMode`, lajur menulis ke
`frame_keys`, dan tidak ada yang membaca tulisan yang lain. Akibatnya memilih
"Susun sendiri" di panel lalu menggambar dua bingkai, sementara lajurnya tetap
menyala di "Wajah".

Sekarang keduanya lewat satu pintu (`pilihCaraBingkai`):

- Lajur menggambar `modeDasar`, cara milik klip, selama linimasanya kosong,
  jadi ia tidak lagi selalu menulis "Ikuti wajah".
- Panel menampilkan mode **efektif** di posisi garis main, bukan `frameMode`
  mentah.
- Mengganti mode saat linimasanya kosong mengganti cara seluruh klip; saat
  sudah ada potongan, yang berubah hanya potongan tempat garis main berdiri.
- "Susun sendiri" ikut jadi pilihan di lajur, dan tiap potongan waktu bisa
  punya susunannya sendiri (`frame_keys[].layout`).

Pelajaran untuk yang berikutnya: setiap kali ada dua tempat di layar yang
menjawab pertanyaan yang sama, salah satunya harus menjadi cermin, bukan
penyimpan kedua.

---

## 8. Empat perbaikan dari peninjauan hasil render, 16 September 2026 (sore)

**Susunan klip gaming.** Versi pertama salah di dua hal sekaligus, dan keduanya
baru terlihat setelah hasilnya benar-benar dilihat: wajah pemain muncul DUA
KALI (sekali diperbesar di bidang atas, sekali lagi kecil di dalam gambar
permainan), dan bidang permainannya kecil dengan lubang kabur besar di bawahnya.

- Bidang permainan sekarang memakai petak yang TIDAK memuat facecam. Facecam
  selalu menempel di sudut, jadi membuang satu jalur di sisinya selalu
  menyisakan persegi utuh; yang dipilih adalah jalur yang menyisakan paling
  banyak. Pada video uji: facecam di kiri-bawah (0%, 59,5%, 35,6x40,5%) →
  permainan diambil dari x 35,6%-100%, tinggi penuh.
- Bidang wajah 38%, permainan 62%, keduanya "cover". Tidak ada sisa kosong.
  "Contain" yang dipakai sebelumnya menjaga gambar tetap utuh, tapi di bingkai
  tegak ruang layar terlalu mahal untuk dibuang jadi bilah.

**Layar hitam di editor.** Bukan isi videonya, bingkai aslinya di menit 23:25
terang (kecerahan 48/255, ada karakter di tengah layar). Pemutar berhenti di
detik 0 SUMBER sementara klip yang dipilih mulai di menit 23, dan detik 0 pada
video itu memang hampir gelap. `selectClip` sudah melompat ke awal klip, tapi
hanya saat klipnya DIKLIK, bukan saat editor pertama terbuka, dan bukan saat
`videoRef` belum terisi atau metadatanya belum termuat (menyetel `currentTime`
pada elemen yang belum siap tidak melakukan apa-apa, tanpa galat). Sekarang ada
efek yang memarkir pemutar di dalam klip, ikut mendengarkan `loadedmetadata`.

**Bingkai kecil tidak bisa diseret.** Bingkai digambar menurut urutan daftar,
jadi bingkai yang menutupi seluruh gambar berdiri di atas bingkai kecil di
dalamnya dan setiap klik mengenai yang besar. Sekarang bingkai yang lebih KECIL
berada di atas, yang dipilih orang hampir selalu yang kecil, karena yang besar
bisa diraih di mana saja di luarnya.

**Berpindah dari Main game ke Susun sendiri membuang kedua bingkainya.** Kini
diwariskan, jadi susunan otomatis itu bisa digeser sedikit lalu dipakai, bukan
dimulai ulang dari satu bingkai kosong.

---

## 9. Susunan gaming, tiga perbaikan lanjutan, 16 September 2026 (malam)

**Yang membuat perbaikan sebelumnya tidak terlihat: backend tidak dijalankan
ulang.** Kode `susun_layout_gaming` sudah benar, tapi proses uvicorn yang
melayani peramban masih memegang versi lama, jadi `/api/clip-facecam` tetap
mengirim susunan lama (`fit=contain`, sumber bingkai penuh). Render yang saya
uji memakai proses Python baru, jadi ia memakai kode baru, dan itulah yang
menyesatkan saya: dua jalur yang saya kira sama ternyata menjalankan versi yang
berbeda. Pelajarannya: setelah mengubah kode backend, yang harus diperiksa
adalah jawaban SERVER, bukan hasil pemanggilan fungsi langsung.

**Bidang wajah menarik masuk gambar permainan.** Potongan facecam dipaksa
mengikuti rasio bidang tujuan supaya tidak ada yang perlu diregangkan. Itu
salah arah: panel facecam sering TEGAK (pada video uji ~17% x 38% bingkai,
rasio 0,8) sementara bidang tujuannya melebar (rasio 1,48), jadi memaksakannya
melebarkan potongan sampai 28,5%, dan 11% kelebihan itu berisi permainan.
Sekarang potongannya dibentuk dari petak wajah saja (terukur jadi 16,4%, sesuai
panel sebenarnya), dan "cover" di tahap penyusunan yang memangkasnya. Memangkas
sedikit rambut selalu lebih baik daripada memasukkan permainan ke bidang wajah.

**Pratinjau kembali ke detik 0 saat deteksi selesai.** Terlacak langkah demi
langkah: memilih klip yang mulai di 1126 detik memarkir semua video di 1127,
dan tetap begitu saat tab Bingkai dibuka maupun saat "Main game" ditekan; baru
ketika deteksi facecam SELESAI dan bidang keduanya muncul, keempat elemen video
serentak kembali ke 0. Susunan pratinjau yang berubah membuat elemen <video>
dibuat ulang, dan yang baru lahir di detik 0 SUMBER. Penjaga posisi pemutar
sekarang ikut dipicu oleh jumlah bidang, bukan hanya oleh pergantian klip.

---

## 10. Tokoh bukan manusia, dan kecepatan muat, 16 September 2026 (malam)

**Mode bingkai baru: "Ikuti gerakan".** YuNet adalah pendeteksi wajah MANUSIA;
pada kartun, maskot, atau hewan ia tidak menemukan apa pun. Terukur pada video
Pinkfong di folder unduhan: mode wajah menemukan wajah di **4%** sampel, di
bawah ambang, jadi seluruh klip jatuh ke bilah kabur dan tokohnya tidak pernah
diikuti. Mode gerak pada klip yang sama: **89%**, bingkainya bergerak 265 piksel
mengikuti tokoh.

Cara kerjanya tidak memerlukan model apa pun: pusat massa perubahan antar
bingkai. Pada video bertokoh, yang bergerak paling banyak hampir selalu yang
sedang jadi pusat perhatian. Seluruh penghalusan, deteksi potongan adegan, dan
penyusunan keyframe dipakai bersama mode wajah, yang berbeda hanya APA yang
dijejak. Batasnya jujur dan sudah ditulis di kodenya: pada bidikan diam tidak
ada yang bisa diikuti, dan pada panning kamera pusatnya melayang ke tengah.

**Kecepatan muat.**

| | sebelum | sesudah |
|---|---|---|
| `/api/projects` | 0,60 dtk | **0,03 dtk** |
| `/api/clips` | 0,86 dtk | **0,06 dtk** |

- `list_projects` mengurai JSON analisis UTUH untuk tiap proyek, 50 KB sampai
  343 KB per proyek, sepuluh megabita untuk lima puluh dua analisis, padahal
  kartunya hanya perlu judul, durasi, mesin, dan BERAPA klipnya. Sekarang
  keempatnya dibaca lewat `json_extract` SQLite, jadi penguraian itu tidak
  pernah terjadi di Python.
- `list_local_clips` membaca satu `stat` dan satu sidecar JSON per klip setiap
  kali dipanggil, 49 klip di cakram luar. Sekarang ditahan di memori dengan
  kunci waktu-ubah FOLDER, jadi klip yang baru dirender tetap langsung terlihat.

**Regresi yang saya buat dan perbaiki di sini juga.** Penggantian blok saat
menulis ulang susunan gaming ikut MENGHAPUS `build_frame_keys_graph`,
`_cabang_kunci`, dan `_urut_kunci`, seluruh pembangun graf linimasa bingkai.
Tidak ketahuan karena sesudahnya saya hanya menguji `frame_mode='gaming'`, bukan
`frame_keys`. Ketiganya sudah ditulis ulang dan diuji dengan render dua kunci
(`motion` -> `center`). Pelajarannya: penggantian yang dipatok pada DUA jangkar
akan membuang semua yang kebetulan berada di antaranya, dan berkas yang belum
pernah di-commit tidak punya jalan pulang.

---

## 11. Gerak yang benar-benar mengikuti, panjang klip tanpa preset, dan subtitle

### Mode "Ikuti gerakan": salah pertanyaan, bukan salah angka

Versi pertama memakai **pusat massa** seluruh gerakan di layar. Itu menjawab
pertanyaan yang salah. Ketika dua tokoh bergerak di sisi berlawanan, pusat
massanya jatuh di antara keduanya, bingkai memuat tepi kiri yang satu dan tepi
kanan yang lain, dan tidak memuat satu pun secara utuh. Ketika latar ikut
bergerak, pusatnya ditarik ke tengah. Hasilnya bingkai yang nyaris diam sambil
bergetar sedikit.

Yang dipakai sekarang menjawab pertanyaan yang sungguh ditanyakan oleh crop:
**jendela selebar crop mana yang memuat gerakan paling banyak?** Dijawab dengan
jumlah berjalan di atas profil kolom, jadi ongkosnya tetap satu lintasan.

Diukur sebagai bagian energi gerak yang masuk ke dalam kotak (kartun Pinkfong,
crop 9:16 = 32% lebar, jadi 32% adalah dasar untuk kotak yang diletakkan
sembarangan):

| | t=90 | t=300 | t=550 |
|---|---|---|---|
| pusat massa (lama) | 60,6% | 44,6% | 63,7% |
| jendela dominan (baru) | **68,6%** | **54,4%** | **71,0%** |

Dan bingkainya benar-benar berpindah: simpangan posisi naik dari 46-87 px
menjadi 126-139 px. Sesudah penghalusan, pada t=300 versi lama hanya bergerak
96 px sepanjang dua puluh detik, praktis parkir, versi baru 386 px.

**Dua penangkal yang diuji lalu DIBUANG,** karena diukur dan ternyata tidak
membantu:

- *Pengurangan latar* (membandingkan dengan rata-rata bergerak, bukan bingkai
  sebelumnya): 59,9% / 51,6% / 60,7%, lebih buruk di ketiga titik, karena
  kamera yang bergeser membuat seluruh layar jadi latar depan.
- *Kompensasi geser kamera* (korelasi silang profil tepi): 65,1% → 64,8%
  agregat. Tidak ada keuntungan, tapi ada ongkos per sampel.

**Batas yang tersisa, jujur:** pada kompilasi kartun dengan transisi menyapu
beranimasi, sapuannya menghasilkan gerakan yang jauh lebih besar daripada
tokohnya, dan jendela ikut ke sana. Pada gameplay, diuji pada Minecraft
1920×1080, hasilnya justru bagus: kotak mendarat pada domba yang bergerak,
pada tokoh pemain, dan pada minecart yang menyala.

### Panjang klip: preset dihapus seluruhnya

Pendek/Sedang/Panjang hilang dari Pengaturan, dari halaman tonton, dan dari
Partitur; `PanjangKlip.jsx` dihapus; `clip_length` hilang dari API dan dari
kunci dedupe. Yang tersisa cuma lantai 10 detik dan langit-langit 240 detik,
dan keduanya bukan gaya.

Menghapus presetnya ternyata bagian yang mudah. Yang sulit: **hampir setiap
komponen skor naik ketika jendelanya diperpanjang**, jadi tanpa target panjang,
setiap klip tumbuh sampai langit-langit, batas kaku yang sama dengan nama lain.
Terukur pada podcast satu jam, skor rata-rata naik monoton 0,52 (20 dtk) →
0,63 (240 dtk). Tiga sebabnya ditemukan satu per satu:

1. **`koherensi`** dihitung di dalam jendela: 0,53 pada 20 detik → 0,99 pada
   220 detik. Ia bukan mengukur keterpaduan, melainkan durasi dengan nama lain.
   Diganti kohesi yang diukur dalam lingkungan selebar **tetap** (±20 detik).
   Sesudahnya: 0,641 → 0,651, datar.
2. **`salience`** memakai jumlah lima tf-idf tertinggi, dinormalisasi ke
   maksimum global. Jendela panjang pasti menemukan kelimanya; jendela pendek
   tidak. Diganti rata-rata per kata isi, dipatok pada persentil 95.
3. **`batas topik` (baru, TextTiling).** Ini yang benar-benar memutuskan di mana
   klip berhenti, karena ia milik SATU TITIK dalam transkrip, bukan milik sebuah
   rentang, nilainya sama saja apakah jendela yang berakhir di situ dua belas
   detik atau tiga menit.

Dan satu bug yang tersingkap di jalan: **leksikon hook hanya kena di 3-6%
kalimat** (75 dari 1498; 96 dari 1605; 43 dari 1284), padahal bobotnya terbesar
di seluruh rumus, nilai rata-ratanya 0,057 dari 1,0. Jadi komponen yang paling
menentukan hampir tidak pernah bersuara. Diperlebar dari 17 pola ke 34, dan yang
lebih penting, `_hook_score` tidak lagi bergantung pada leksikon saja: dua
sinyal baru di sana **rapat**, lonjakan energi suara tepat di pembuka, dan
denda untuk pembuka yang dibuka kata penyambung ("jadi", "terus", "tapi",
"nah"), yang pada transkrip percakapan kena di seperempat kalimat.

Dua angka terakhir dipilih dari sapuan pada lima transkrip nyata, dilihat dari
SEBARAN panjangnya (bukan rata-ratanya, karena yang diminta memang keragaman):

| toleransi | cukup | <30dtk | 30-60 | 60-120 | >120 | median |
|---|---|---|---|---|---|---|
| 0,02 | 0,6 | 7 | 7 | 24 | 22 | 102 dtk |
| 0,04 | 0,6 | 13 | 15 | 22 | 10 | 66 |
| **0,04** | **0,4** | **15** | **20** | **18** | **7** | **48** |
| 0,09 | 0,4 | 40 | 13 | 6 | 1 | 22 |

Hasilnya, dalam satu video yang sama, klip 15 detik dan klip 138 detik berdiri
berdampingan.

### Subtitle: saklar, pelat, dan bahasa

- **Saklar hidup/mati** (`aktif`). Baris, waktu, dan seluruh gayanya tetap
  tersimpan; yang ditahan cuma penggambarannya. Hook dan tanda air TIDAK ikut
  mati. Dihormati di render DAN di pratinjau.
- **`highlight_words` dipisah dari animasi masuk.** Tanpa ini, gaya bersih
  mustahil dibuat: sorotan menyala pada setiap animasi kecuali "tanpa animasi",
  dan "tanpa animasi" juga mematikan pudarnya.
- **Pelat di belakang teks** (`bg`), padanan BorderStyle 3 di libass,
  pengganti garis luar tujuh piksel. Empat template baru memakainya: **Apple**,
  **Sinema**, **Stiker**, plus **Ketik** (animasi `typewriter`).
- **Bahasa tidak lagi terkunci di Indonesia.** Dua perbaikan terpisah:
  `transcribe_audio` dulu berbawaan `language="id"` dan **tidak ada satu pun
  pemanggil yang mengirim nilai lain**, setiap video tanpa caption dipaksa
  ditranskrip sebagai bahasa Indonesia. Sekarang dikenali sendiri. Dan
  pengambil caption, yang dulu berhenti di id/en, sekarang melanjutkan ke
  bahasa yang **benar-benar dimiliki videonya** (maksimal 5 percobaan, karena
  permintaan beruntun ke YouTube memicu 429). Urutan pilihan bisa disetel di
  Pengaturan.

### Dua bug transkrip yang tersingkap saat menguji render

Keduanya sudah ada sebelum pekerjaan ini, dan keduanya merusak setiap subtitle
dari takarir resmi kanal:

1. **43% "kata" hanya spasi tak terlihat.** Pada satu transkrip: 7.550 dari
   17.426. Akibatnya berantai dan tidak satu pun terlihat seperti kesalahan,
   kerapatan kata jadi dua kali lipat yang sebenarnya, pemecah baris
   menghitungnya sebagai kata, dan sorotan karaoke berhenti 60 milidetik pada
   kata yang tidak kelihatan.
2. **Blok kata terduplikasi utuh.** `_dedupe` hanya membandingkan dengan kata
   SEBELUMNYA, sedangkan rolling caption mengulang seluruh BARIS, tujuh kata
   yang sama dengan timestamp identik sampai milidetik. Kata kedua dari
   pengulangan dibandingkan dengan kata terakhir baris pertama, dan keduanya
   memang berbeda, jadi tidak pernah tertangkap. Hasilnya dua baris subtitle
   identik yang bertumpuk di layar.

Dibersihkan di pintu masuk (`_parse_json3`) DAN di pintu keluar penyimpanan
(`repos/transcripts._hydrate`), dengan urutan yang sama persis di keduanya,
supaya transkrip yang sudah terlanjur tersimpan ikut terbetulkan tanpa diunduh
ulang. Terukur: 17.426 kata → 4.924; satu klip delapan detik yang tadinya
menghasilkan 18 baris subtitle (banyak yang kembar dan bertumpuk) sekarang
menghasilkan 6.

**Sisa yang belum dikerjakan di sini:** takarir rolling menaruh dua kalimat
BERBEDA pada rentang waktu yang tumpang tindih, bukan kembar lagi, tapi masih
dua baris di layar sekaligus. Itu cacat waktu di sumbernya dan butuh
penjadwalan ulang batas baris, bukan sekadar pembersihan.

---

## 12. Sutradara otomatis, sisipan media, dan tiga cacat render yang tersingkap, 18 September 2026

### "Lacak gerakan" yang loading tanpa akhir

Dua sebab. (1) Berpindah dari "Ikuti wajah" ke "Ikuti gerakan" saat pelacakan
wajah masih berjalan membatalkan permintaannya, tapi tanda sibuknya tidak
pernah dimatikan, `Editor.jsx` kini mematikannya di cabang yang tidak
melacak. (2) Pratinjau mode gerak tidak pernah meminta apa pun ke server; ia
menggambar kotak diam. Sekarang `/api/clip-reframe` menerima `subjek: "gerak"`
dan pratinjaunya bergeser mengikuti rencana yang sama dengan render.

Yang membuatnya TERASA macet: video 4K VP9. Membaca 20 detik 3840x2160 VP9
memakan 5,1 detik, dan membaginya jadi empat proses paralel tidak membantu
(4,8 dtk). Jawabannya **salinan analisis** (`services/proksi.py`): 1280 px
H.264, dibuat sekali di latar begitu video diunduh, dipakai oleh semua
analisis. Terukur: klip 60 dtk 31 → **3,3 dtk**; baca 20 dtk 5,1 → 0,5 dtk.
Wajah terdeteksi 66,7% / 66,9% / 66,0% pada crf 26/30/33, kompresinya tidak
mengubah deteksi, jadi dipakai crf 30 (± 9 MB per menit video). Salinan yang
sumbernya sudah dihapus ikut dibuang.

### Sisipan: berkas dari luar video sumber

Tab baru **Sisipan** di Studio. Impor video, gambar, musik; taruh di waktu
dan posisi tertentu (penuh, separuh atas, separuh bawah, tengah, pojok).
Musik bisa "dikecilkan saat orang bicara", terukur, musik -21 dB turun ke
-39,5 dB saat ada ucapan. Enam efek suara bawaan (dentum, whoosh, ding, pop,
naik, gedebuk) DISINTESIS oleh ffmpeg, jadi tidak ada lisensi yang perlu
diperiksa dan tidak butuh internet.

Bug yang ditemukan saat mengujinya: `loudnorm` mengeluarkan 192 kHz, dan
mencampurnya dengan sisipan 48 kHz memotong audio klip, 10 detik keluar 7,1
detik. Audio utama kini diseragamkan ke 48 kHz sebelum dicampur.

### Sutradara otomatis (`services/sutradara.py`)

Tombol "Susun otomatis" di tab Sisipan. Untuk gameplay berfacecam: wajah di
atas + permainan di bawah, lalu **wajah penuh 9:16 selama 2,6 detik** saat
pemainnya kaget, plus dentum di titik itu. Semua keluarannya kunci bingkai dan
sisipan biasa bertanda "otomatis" dengan alasannya, bisa dihapus satu-satu.

Yang dikenali adalah **reaksi kaget**, BUKAN "jumpscare", dan itu disengaja.
Versi pertama (lonjakan suara saja) menandai satu kejutan tiap 6-15 detik, dan
dilihat bingkai demi bingkai tidak satu pun kandidat terkuatnya jumpscare:
yang tertangkap adalah pemain tertawa di layar kredit dan kamera berbalik.
Suara permainan dan suara mikrofon ada di SATU trek. Syarat tambahan, keras
di atas kebiasaan orang itu sendiri (persentil 90 klipnya) dan datang mendadak,
menurunkannya ke kira-kira satu per menit, dan pada empat yang diperiksa
pemainnya memang terlihat kaget (mulut terbuka, kamera berbalik mendadak).

**Belum:** pola untuk podcast (beberapa orang bereaksi sekaligus) dan kartun
(perpindahan adegan). Belum ada AI yang memilih musik.

### Tiga cacat render yang tersingkap di jalan

1. **Latar kabur 0,2x waktu nyata.** `boxblur=28:6` langsung di kanvas
   1080x1920: 18,8 detik untuk 4 detik video. Dipakai di SETIAP render
   berbilah kabur. Kini dikerjakan di seperempat ukuran lalu dibesarkan
   (`render.kabur`): tidak bisa dibedakan di samping-sampingan, 3,6 detik.
2. **Linimasa bingkai dengan dua susunan macet.** Dua kunci gaming memakai
   label graf yang SAMA (`[lsrc0]`, `[lbg]`…). Kesalahan saya dari sesi
   sebelumnya, waktu itu hanya diuji dengan satu kunci susunan. Kini tiap
   susunan diberi awalan, dan seluruh linimasa dirakit dengan `concat` per
   potongan, bukan tumpukan `overlay`: gaming → kotak → gaming 6 detik dari
   macet ke 3,0 detik.
3. **Satu kunci diabaikan.** Linimasa berisi satu kunci jatuh kembali ke mode
   dasar; usulan "gaming untuk seluruh klip" dirender sebagai ikuti wajah.

### Unduhan berlubang, PERLU DIUNDUH ULANG

`AKU_PERGI_SHOLAT_PADA_MALAM_HARI…_qgTmLOW-coo.mp4` punya **tiga celah, total
15,2 detik** tanpa gambar (mis. 32:35,7 dan 32:50,9, masing-masing 5,08 dtk),
sementara audionya utuh. yt-dlp secara bawaan MELEWATI potongan yang gagal
lalu tetap merakit berkasnya. Kini `skip_unavailable_fragments=False` dan
`fragment_retries=15`: unduhan yang kehilangan potongan berhenti dengan pesan
yang jelas dan bisa dilanjutkan. Render juga dibuat tahan celah (`fps=30` di
depan linimasa), jadi gambar dan suara tetap sinkron, tapi bagian yang hilang
tetap tampil beku sampai videonya diunduh ulang. `services/lubang.py` bisa
memeriksa berkas mana pun dalam hitungan detik; dari semua unduhan sekarang,
hanya video itu yang berlubang.

---

## 13. "Selalu loading", penyebabnya, render, lajur Sisipan, dan Lanjutkan proses, 19 September 2026

### Penyebab utama semua loading lambat: ffmpeg liar (kesalahan saya)

Beban mesin 98 pada delapan inti, swap penuh: SEPULUH ffmpeg berjalan, enam
membuat salinan analisis video yang SAMA, lima di antaranya yatim (induknya,
backend yang sudah dimatikan, tidak ada lagi). Sumbernya `proksi.py` versi
pertama: kunci hanya di dalam satu proses, tanpa batas jumlah, prioritas
penuh. Diperbaiki:

- `services/proses.py`: ffmpeg anak ikut mati bersama backend, di Linux
  lewat `PR_SET_PDEATHSIG` (terbukti: backend dibunuh paksa, anaknya mati),
  di semua sistem lewat daftar yang dihentikan saat backend berhenti.
- Salinan analisis: SATU antrean, satu salinan di seluruh mesin (berkas
  `.kunci` berisi PID), prioritas terendah (`nice 19`), dua inti.

Sesudahnya, terukur di peramban: Partitur 1,0 dtk · Studio (29 klip, video
108 menit) 0,4 dtk · Klip jadi 0,8 dtk · Pengaturan 0,5 dtk · Beranda 3,6 dtk
(menunggu YouTube).

### Tiga pemborosan lain yang tersingkap

1. **Energi suara mendekode seluruh videonya** (tanpa `-vn`): 94,8 dtk untuk
   dua menit video 1440p, 3,1 dtk dengan `-vn`. Pada video 108 menit, tahap
   "Mengukur energi bicara…" turun dari ± 85 menit ke ± 3 menit. Bug lama.
2. **Gelombang suara Studio dihitung dua kali bersamaan** untuk video yang
   sama (dua pembacaan berkas 3 GB di cakram eksternal). Kini permintaan
   kedua menunggu yang pertama, dan pipeline sudah menghitungnya dari WAV
   pendek sebelum Studio dibuka.
3. **`/api/clips` 357 KB**, subtitle setiap klip ikut terkirim di dalam
   `metadata` padahal tidak ditampilkan. Kini 29 KB. **`/api/aset`** 1,5 dtk
   (ffprobe enam efek tiap kali) → 22 ms.

### Render

- `fps=30` langsung sesudah pemotongan segmen, semua mode: separuh bingkai
  sumber 60 fps tidak lagi melewati crop/scale/blur; celah sumber berlubang
  terisi sehingga gambar dan suara selalu sinkron.
- x264 tanpa `-threads 4`: ± 10% lebih cepat.
- Klip 10 dtk gaming → reaksi → gaming: 96 dtk → 46 dtk (keduanya diukur saat
  mesin sibuk).
- Yang DITOLAK: preset `superfast`, 17% lebih cepat pada mutu setara (SSIM
  0,9897 vs 0,9895) tapi berkasnya 30% lebih besar. Separuh waktu render
  adalah mendekode sumber VP9, yang tidak bisa dipercepat tanpa GPU.

### Lajur Sisipan di linimasa

Seret untuk memindah, tarik ujung untuk mengubah panjang (ujung kiri memotong
awal cuplikan, bukan menggesernya), klik untuk membuka rinciannya di panel,
panel menyorot dan menggulir ke sana. Blok selebar minimal 44 px: efek suara
0,8 dtk pada zoom 1× tadinya 15 px, seluruhnya tertutup pegangan ujung.

### Lanjutkan proses

Kartu gagal/terputus di Partitur punya tombol **Lanjutkan proses**: pekerjaan
dijalankan ulang dengan setelan yang sama, dan yang sudah selesai dilewati,
video yang sudah terunduh, transkrip yang tersimpan, unduhan `.part` yang
setengah jadi. Diuji pada pekerjaan 108 menit yang terputus di 82%: selesai,
29 klip. Bar kemajuan kini tidak pernah mundur (tadinya 82% → 56% saat audio
disiapkan untuk perkiraan narasumber).

---

## 14. Penutur gameplay, subtitle terjemahan, dan dua subtitle, 19 September 2026

### Satu pemain terbaca tujuh orang

Jumlah penutur ditebak dari SUARA. Pada gameplay horor, bisikan dan teriakan
pemain, suara tokoh permainan, dan efek suara terbaca sebagai orang berbeda:
"AKU MENCOBA HOROR KELAS SEKOLAH…" (Windah, sendirian) keluar 7 penutur,
ditandai yakin. Porsi bicara saja tidak bisa membedakannya, 41/27/14/6/5/4/3%
pada gameplay itu, sementara podcast lima orang sungguhan juga punya penutur
4,2%.

Yang membedakan ada di gambar: facecam KECIL (≤ 30% x 50%) berisi satu wajah
(sebaran ≤ 0,12). `sutradara.perkiraan_pemain` memeriksanya di dua titik video
sebelum pengelompokan suara, di analisis klip DAN di deteksi ulang penutur.

| video | hasil |
|---|---|
| gameplay Windah (2 video) | 1 orang, pengelompokan suara dilewati |
| podcast 5 orang, dr. Tirta, kartun anak | tidak ada facecam → tebakan suara |
| wawancara Elon, Andry/Atta | "facecam" 53-79% lebar = close-up → ditolak |

Proyek MYXRsvydCb4 sudah dideteksi ulang: 1 narasumber, 553 baris.

**Belum:** gameplay TANPA facecam (hanya suara pemain) tetap bergantung pada
tebakan suara, dan di sana kesalahan yang sama masih mungkin terjadi.

### Subtitle terjemahan + dua subtitle

Tab Subtitle → "Subtitle kedua / terjemahan". Baris subtitle utama
diterjemahkan SATU LAWAN SATU lewat Gemini (`services/terjemah.py`), menyalin
waktu baris aslinya, jadi keduanya muncul bersamaan. Gaya sendiri: font,
ukuran, warna, posisi (atas/tengah/bawah + jarak dari tepi), huruf besar,
pelat; "Tukar dengan asli" menukar posisi keduanya. Untuk subtitle terjemahan
saja: matikan subtitle asli.

- Hasil terjemahan disimpan (tabel `terjemahan`, kunci sidik teks + bahasa):
  menerjemahkan baris yang sama lagi tidak memakai kuota (terukur 0,00 dtk).
- Terjemahan TIDAK punya sorotan per kata: urutan kata berubah antar bahasa,
  jadi tidak ada cara jujur menandai kapan kata terjemahan "diucapkan".
- Bila subtitle utama diubah sesudah diterjemahkan, panel memberi peringatan
  untuk menerjemahkan ulang.
- Diuji: 104 baris wawancara Elon → 68 dtk; render Inggris di atas (karaoke) +
  Indonesia di bawah (Poppins kuning) benar.

**Belum:** subtitle kedua belum bisa diseret langsung di pratinjau (posisinya
diatur dari panel), dan belum ada terjemahan tanpa kunci Gemini.

## 15. Warna tiap orang, deteksi ulang yang cepat, dan bingkai yang menyorot pembicara, 19 September 2026

### Warna subtitle tiap orang

Paletnya sudah lama ada, tapi hanya di Gaya → Warna → "Warna per narasumber",
bagian yang tertutup dan jauh dari tempat orang-orangnya ditandai. Sekarang tab
**Subtitle** punya deretan keping "Orang N · sekian baris"; klik keping untuk
memilih warnanya (8 warna siap pakai + pemilih bebas). Keduanya menulis ke palet
yang sama. Memilih warna menyalakan kembali warna per orang bila sedang
diseragamkan.

Subtitle terjemahan bisa ikut: centang "Ikuti warna tiap orang" di panel
terjemahan. Bukan bawaan, tanpa diminta, warna terjemahan tidak boleh tertimpa
warna orang pertama. Penuturnya dibaca dari subtitle UTAMA pada titik tengah
baris (pratinjau dan ASS), bukan disimpan di baris terjemahan, supaya deteksi
ulang tidak membuat warnanya basi.

### Deteksi ulang jumlah orang

Terukur pada gameplay 1 jam 48 menit (3,9 GB, cakram NTFS):

| | sebelum | sesudah |
|---|---|---|
| 1 orang | 61 dtk | 0,6 dtk |
| jumlah lain, pertama kali | 148 dtk | 91 dtk |
| jumlah lain, berikutnya | ~105 dtk | 1,0 dtk |

Tiga sebab: (1) audio diekstrak ulang dari video 3,9 GB setiap kali, 64 dtk
hanya untuk membaca berkasnya, bahkan untuk 1 orang yang tidak butuh audio;
(2) WAV-nya dibuang sesudahnya; (3) sidik suara per jendela (bagian mahal,
tidak bergantung pada jumlah orang) dihitung ulang setiap kali, dan dua kali
bila jalur wajah ikut jalan.

- `services/suara.py`: WAV 16 kHz per sumber di `OmniClip_Storage/suara/`
  (~115 MB/jam, gitignored), dipakai pipeline, deteksi ulang, dan gelombang
  suara Studio. Dibuang bersama videonya; yatim dibersihkan saat mulai.
- `diarize._embeddings`: sidik suara disimpan di sebelah WAV-nya, kuncinya
  daftar kalimat. Proyek baru mengisinya saat analisis, jadi deteksi ulang
  pertama pun langsung cepat.
- 1 orang tidak menyentuh audio sama sekali (pipeline dan deteksi ulang).
- Bilah kemajuan kini bergerak selama hitungan pertama ("Mendengarkan suara
  tiap orang… 40%"), tidak diam 90 detik.

### Bingkai yang mengikuti wajah

Diukur dengan dua alat (skrip di luar repo): bingkai tanpa orang hidup padahal
ada orang di layar, dan pada bidikan berisi ≥2 orang, apakah bingkai memuat
orang yang sedang bicara menurut suara. 24 klip dari 6 video.

| | awal | akhir |
|---|---|---|
| bidikan lebar memuat pembicara (1.409 → 1.566 sampel) | 92,3% | 99,8% |
| klip dr. Tirta 2 / Yono 3 | 16% / 64% | 100% / 100% |
| penutur yang terpetakan ke wajah | 22 | 30 |
| sampel tanpa orang hidup di bingkai (10.874, 27 klip) | 46 (0,42%) | 17 (0,16%) |

"Pembicara" di sini = orang yang terpetakan ke penutur aktif menurut suara;
dua klip diperiksa dengan mata (Yono 3, dr. Tirta 2) dan satu render 16 dtk.
Ukuran "lompatan per menit" dibuang: ia tidak membedakan perpindahan salah
dari perpindahan LANGSUNG di potongan kamera yang kini dikenali (dr. Tirta 3
naik 0 → 20 padahal bingkainya memuat wajah yang terlihat 100% waktu).

Enam cacat:

1. **Penutur yang hanya muncul saat ia sendiri bicara tidak pernah terpetakan.**
   Statistiknya membandingkan mulut saat bicara vs saat TIDAK bicara; orang yang
   hanya tampil di close-up gilirannya tidak punya sampel kedua. Di bidikan
   lebar bingkai lalu jatuh ke wajah terbesar, di Yono klip 3, tamu yang sedang
   tertawa. Sekarang potongan kamera ikut jadi bukti (`SOLO_*`): selama giliran
   penutur, sebagian besar bidikan tunggal menampilkan orang yang sama, dan saat
   orang itu sendirian sebagian besar yang terdengar memang penutur itu.
2. **Jeda antar kalimat melepas subjek.** Bingkai melompat ke wajah terbesar
   selama pembicara menarik napas lalu kembali. Kini ditahan sampai 2,5 dtk
   (`JEDA_TAHAN_SECONDS`).
3. **Wajah tak bersidik diundi ulang tiap sampel.** Dua tamu kecil yang jaraknya
   ke kursi seseorang hampir sama bergantian memenangkannya; bingkai melayang di
   RUANG KOSONG di antara keduanya (dr. Tirta klip 2). Kini perjodohan lewat
   tempat duduk dipegang selama jejaknya berlanjut.
4. **Jalur cadangan `group_people` selalu gagal** (membongkar deteksi 3-nilai
   sebagai pasangan), bidikan lebar tanpa sidik wajah kehilangan seluruh daftar
   orangnya. Tidak mengenai 24 klip uji (semuanya bersidik), tapi pasti gagal
   di rekaman yang wajahnya kecil semua.
5. **Pemetaan menyerah bila baru satu orang dikenali.** Klip pendek yang dibuka
   close-up pembicara lalu memotong ke bidikan lebar berisi wajah kecil tak
   bersidik: `assign_faces_to_speakers` mensyaratkan ≥2 orang, jadi bingkai
   jatuh ke tamu terbesar. Ditemukan dengan RENDER sungguhan (16 dtk), bukan
   oleh alat ukur 60 dtk, di sana klipnya kebetulan memuat close-up tamu juga.
   Bukti potongan kamera kini jalan dengan satu orang; statistik mulut
   dipisah ke `_peta_dari_mulut`. Keterlihatannya juga kini dari `seen`, bukan
   dari jejak posisi yang menahan nilai (yang membuat semua orang "terlihat"
   selamanya setelah sekali muncul).
6. **Potongan kamera di studio yang sama tidak terbaca histogram.** Close-up →
   bidikan berdua di ruangan yang sama: warna nyaris sama, potongan terlewat,
   bingkai menunggu 0,8 dtk di tempat orang yang sudah tidak ada lalu MENGGESER
   ke orang lain. Kini: bila tidak satu pun wajah yang terlihat barusan
   berlanjut dan semua wajah sekarang baru, itu potongan.

**Wajah yang bukan orang** (logo, lukisan, pola daun): tanda hidup per jejak,
selisih petak wajah terhadap dirinya setengah detik sebelumnya, setelah
kecerahan dinormalkan (`HIDUP_*`). Jejak di bawah 0,06 disingkirkan dari calon
subjek, daftar orang, dan pemetaan penutur. Terukur: logo berwajah di Najwa
0,0 (semua tertangkap); wajah asli paling diam 0,092 (orang yang wajahnya
terpotong di tepi bingkai); dari 27 klip tidak ada wajah asli yang tercoret.

**Belum:**
- Lukisan yang direkam kamera GOYANG (dipegang tangan) tidak tertangkap: kotak
  deteksinya ikut bergoyang terhadap gambar, jadi terlihat hidup (uji tiruan:
  0,14 dan 0,46). Di kamera diam tertangkap, kecuali derau sangat berat.
- Keyakinan detektor TIDAK bisa memisahkan daun dari wajah asli yang menoleh
  (keduanya 0,69), jangan dipakai sebagai ambang.
- Bukti mulut (`speaking_evidence`) keliru di bidikan lebar yang riuh: tawa
  terbaca sebagai bicara. Jangan dipakai sebagai kebenaran acuan.
- Nomor orang bisa berbeda antar klip bergantung klip mana yang dipindai lebih
  dulu (daftar orang per video disimpan di memori).
- Hitungan sidik suara pertama untuk video panjang masih 1,5-3 menit.

## 16. Warna orang yang berganti, dan Cari ulang klip, 19 September 2026 (siang)

### Satu orang, beberapa warna

Laporan: A bicara, lalu B, lalu A lagi, dan A kembali dengan warna orang lain.
Terbukti pada Titik Kumpul klip D (dideteksi ulang dengan 6 orang): cerita Kang
Sule tentang anaknya (dtk 29-61, dikonfirmasi dengan gambar) berlabel
1,1,1,1,1,5,5,5,1,1.

Sebabnya: k-means dengan k melebihi jumlah orang sebenarnya MEMBELAH suara yang
paling banyak bicara. Pusat kelompok (sidik mentah, kosinus) dua belahan satu
suara 0,90-0,96; dua orang berbeda paling tinggi 0,82, pada lima video.
`diarize._gabung_kembar` menggabungkan kelompok ≥ 0,88 (`SUARA_KEMBAR`) setelah
pengelompokan, termasuk bila jumlahnya diminta pengguna; pesan deteksi ulang
menyebut "Diminta 6 orang, tapi 1 kelompok ternyata suara orang yang sama".

| | sebelum | sesudah |
|---|---|---|
| Sule klip D, 6 diminta | Sule 3 warna | 1 warna (jadi 5 orang) |
| Andry & Atta, 3-6 diminta (konsisten, acuan wajah sendirian) | 0,53-0,58 | 0,88-0,89 |
| Elon (2 orang) dipaksa 3 / 4 | terbelah | 2 |
| mode tebak sendiri (semua video), Yono |, | tidak berubah |

Dicoba dan DITOLAK: pengelompokan bertingkat (average linkage) sebagai
pengganti k-means, lebih baik di Andry, lebih buruk di Yono (0,53-0,63 vs
0,64-0,67). Acuan "wajah sendirian di layar" berderau (shot reaksi), jadi hanya
selisih besar yang dipercaya.

**Belum:** Sule klip D dtk 10-29 masih berlabel orang ketiga (dari gambar, itu
Sule juga, kemiripannya dengan kelompok Sule di bawah 0,88). Bingkai di situ
tetap salah (tangkapan layar pengguna, dtk 12) karena penutur itu tidak bisa
dicocokkan ke wajah mana pun. Menurunkan ambang berisiko menggabung dua orang
berbeda (0,82). Proyek lama perlu "Deteksi ulang" untuk mendapat penggabungan.

### Cari ulang klip (Studio → tombol "Cari ulang")

Beralih mesin (lokal ↔ Gemini, atau model lain) tanpa menghapus proyek dan
mengunduh ulang. `POST /api/projects/{id}/cari-ulang {mesin, gemini_model,
max_clips}` menjalankan auto_clip dengan `ulang: true`: transkrip dan kalimat
TERSIMPAN dipakai (tanpa unduh, tanpa ambil caption), label penutur dibawa dari
analisis sebelumnya (`label_kalimat`, kini disimpan pipeline dan deteksi ulang;
analisis lama tanpa itu dihitung ulang dari sidik suara tersimpan dengan jumlah
yang sama). Analisis sebelumnya dicatat di `sebelumnya`;
`POST /api/projects/{id}/pulihkan` mengembalikannya (dan bisa dibalik lagi).
Suntingan yang belum tersimpan disimpan dulu.

Terukur (Elon, 85 menit): mesin lokal 31 dtk; tahap energi kemudian dibaca
dari audio tersimpan (18 → 4 dtk); Gemini 107 dtk (94 dtk menunggu model). Diuji di browser:
22 → 23 klip → kembali 22, hook dan label 59/45 utuh.

### Server yang tidak mau berhenti

Uvicorn menunggu SEMUA sambungan tertutup sebelum berhenti, dan Studio yang
terbuka menahan sambungan (aliran video, pantau job) selamanya, proses lama
tetap hidup setelah diminta berhenti. `timeout_graceful_shutdown=5` di run.py;
terukur berhenti dalam 5,3 dtk dengan sambungan terbuka.

### Cari ulang yang tidak pernah selesai (sore)

Laporan: "Cari ulang" dengan Gemini masih memuat setelah setengah jam. Job
berjalan 1,5 jam: gemini-3.8-flash dan 3.6-flash menjawab 503 ("high demand"),
lalu satu permintaan berikutnya tidak pernah dijawab, `refine_candidates`
membuat klien Gemini TANPA batas waktu (fungsi judul di berkas yang sama sudah
punya 90 dtk). Sekarang: 150 dtk per permintaan, 360 dtk untuk seluruh
rangkaian model; 503/timeout langsung pindah ke model berikutnya (dulu diulang
dulu); pembatalan diperiksa di antara percobaan; tiap percobaan dilaporkan
("gemini-3.6-flash sedang sibuk, mencoba gemini-3.5-flash…"); bila semua gagal,
klip dari mesin lokal dan pesannya MENGATAKAN itu (`gemini_gagal`). Pesan akhir
menyebut model yang benar-benar menjawab. Diuji ulang di proyek Kang Sule:
76 dtk, 3.6-flash sibuk → 3.5-flash, 20 klip (19 lama bisa dikembalikan).

Bilah kemajuan (`components/BilahProses.jsx`, di Partitur dan dialog Cari
ulang): lima bagian per tahap, masing-masing terisi sendiri, jadi persen tahap
tidak lagi terbaca sebagai angka yang turun. Tahap Gemini (tidak terukur)
ditampilkan sebagai garis bergerak + lama menunggu, bukan persen karangan.
Job kini membawa `started_at` dan `eta_seconds` ke kartu.

## 17. Klip ulang yang kehilangan konteks, dan "pakai AI paling kuat"

**Laporan:** video lama yang dulu klipnya 60+ detik, setelah "Cari ulang" berisi klip 16 detik yang tidak bisa dimengerti (ohJbKVkrZ4U, 339-354 dtk: "Setelah di smash mulu…", topiknya mulai di 296 dtk, lucunya keluar di 370 dtk).

**Penyebab (tiga, saling menguatkan):**
- Prompt tidak pernah menuntut klip bisa dimengerti penonton baru; kandidat heuristik memang cenderung pendek dan model meniru panjangnya.
- `_apply_selections` hanya mengizinkan awal mundur 8 kalimat, pada obrolan berkalimat pendek itu belasan detik. Model yang ingin mundur ke awal topik dibatalkan diam-diam.
- `end_sentence` dibaca sebagai "sesudah yang terakhir" tanpa pernah diberitahukan ke model, sementara daftar kandidat menulis rentang inklusif. Sekarang inklusif di kedua sisi.

**Perbaikan:**
- Prompt: "uji penonton baru" (awal tidak merujuk ke belakang, akhir sampai puncak, padat), kolom `konteks` yang ditulis SEBELUM nomor kalimat (`property_ordering`), dan permintaan memenuhi jumlah klip.
- Batas dari model diterima apa adanya selama sah; pilihan yang tumpang tindih >50% dengan pilihan lebih kuat dibuang.
- Pemeriksaan kedua `rapikan_batas`: model melihat ±25/15 kalimat di sekitar tiap klip dan hanya memperbaiki awal/akhir (~45 dtk; gagal → batas pertama dipakai). Terukur 9/14 dan 7/20 klip dirapikan.
- `services/peringkat_model.py`: urutan model disusun dari daftar kunci, pro > flash, generasi terbaru dulu; lite/Gemma/agen dibuang. Model yang menjawab 429 "limit: 0" atau 404 dicatat di `settings` (`ai.model_tak_terpakai`) dan dilewati 24 jam. Dipakai oleh pencarian klip, tulis-ulang judul, dan terjemahan. `OMNICLIP_GEMINI_MODELS` tetap menang bila diisi.
- `/settings/models` menambah `cocok`, `terkuat`, `tanpa_kuota`; menu model di Pengaturan dan Cari ulang hanya menampilkan yang cocok.

**Fakta kunci:** paket gratis Gemini memberi kuota **0** untuk seri Pro (`gemini-3.1-pro`); `gemini-2.5-pro` 404. Terkuat yang bisa dipakai kunci ini: `gemini-3.8-flash`, tetapi 3.8/3.7/3.6 sering 503, jadi yang benar-benar menjawab hari ini 3.5-flash.

**Hasil:** ohJbKVkrZ4U 14 klip 35-147 dtk (dulu 16-149 dengan klip teratas 16 dtk tanpa konteks); XtAoIx6-EWw tetap 20 klip. Sisa: transkrip otomatis tanpa tanda baca masih membuat sebagian awal berupa potongan ucapan ("Al program yang enggak nyangka.").

## 18. Bingkai mengikuti wajah di iklan sponsor

**Laporan:** JHrjjPbD7I4 klip P (40:33), bingkai mengunci wajah di iklan Flimeal yang ditempel di pojok kiri video, bukan orang yang bicara.

**Penyebab:** tanda hidup membandingkan petak wajah di kotak deteksi SEKARANG dengan petak setengah detik lalu. Wajah iklan hanya ±21 px; kotak detektor bergoyang 1-2 px sehingga tepi kontras (kacamata, batas ungu) terbaca sebagai perubahan, wajah iklan yang diam dinilai 0,19-0,34, setara orang bicara.

**Perbaikan (`reframe.py`):**
- Petak pembanding diambil di KOTAK YANG SAMA dengan setengah detik lalu (`rujukan_kotak`). Gambar diam → 0,00-0,05; orang yang diam mendengarkan terendah 0,07 (30 klip, 10 video). `HIDUP_AMBANG` 0,06 → 0,05 untuk jarak aman.
- Aturan tempat diperluas ke jejak panjang: jejak di koordinat & ukuran gambar yang sudah terbukti mati (`HIDUP_UKURAN` 25%), posisinya diam (`HIDUP_DIAM` 0,003), median < 0,15 → mati. Menangkap wajah iklan yang sesekali tertutup mikrofon/kepala (0,07-0,11).
- `_TEMPAT_MATI` mengingat tempat gambar yang terbukti mati per video (hanya bukti langsung, bukan hasil aturan tempat), jadi klip lain dari video yang sama langsung tahu.
- Diagnosa: `_HIDUP_TERAKHIR["waktu"]` berisi detik setiap jejak terlihat.

**Hasil:** JHrjjPbD7I4 3 klip: tidak ada jejak iklan yang lolos (dulu 2); 7 video lain: 0 wajah orang dinyatakan mati. Klip P dari 40:33 mengikuti orang berkacamata-berheadphone, iklan hanya di tepi.

## 19. Sutradara bingkai AI (tahap 1-2 dari rencana; belum di-commit)

Rencana lengkap: bingkai berganti per momen, podcast: tawa → wajah yang bereaksi (bergantian atau ditumpuk) → kembali ikut wajah; game horor: jumpscare → wajah penuh → kembali gameplay. Gemini utama, OpenRouter cadangan (belum), tombol di Studio (sudah) + otomatis setelah auto-klip (belum).

**Sudah jadi:**
- `reframe.py`: `ReframePlan.people_box` (cy, lebar wajah per orang per sampel), `cut_times`, `kotak_orang()` (None bila orangnya tak terlihat di rentang, jangan pakai posisi dari bidikan lain).
- `peristiwa_suara.py`: YAMNet ONNX (16 MB, sha256 diperiksa, `backend/models/yamnet.onnx`, di-.gitignore) → tawa/sorak/teriak. Caption YouTube Indonesia tidak pernah menandai tawa dan meregangkan kata sampai 100% klip, jadi YAMNet satu-satunya sinyal tawa yang andal. Ambang: skor mutlak ≥0,015 DAN ≥20× median klip.
- `momen.py`: gabungan kejut, tanpa-kata, mulut bersama, potong kamera, dan YAMNet → momen kandidat ber-id.
- `penyedia_ai.py`: `tanya_gemini(bahan=[video|gambar|teks])`, rantai model + catat_gagal seperti gemini.py.
- `sutradara_ai.py`: proksi 360p dengan JAM KLIP ditulis di pojok (tanpa itu Gemini menaruh momen di detik 100 dari video 70 detik), lembar wajah P0…Pn (OpenCV), menu bingkai tetap, validasi (tempel ke bukti lokal ±2 dtk, bidikan ≥0,6 dtk, momen ≤5 dtk, jarak ≥3 dtk, kekuatan ≥0,55, wajah <44 px → bidikan lebar, pecah di potongan kamera), `susun_lokal` tanpa AI, job `sutradara` (lajur net), `POST /api/clip-sutradara-ai`.
- Bidikan wajah/terbagi = susunan dengan bingkai `follow` + `person` eksplisit (FrameModel.person, render, serializeLayout, followX).
- Studio: kartu "Sutradara bingkai" di panel Sisipan (AI / Mesin lokal / Buang), bilah kemajuan, konfirmasi bila lajur sudah diatur tangan; lajur Bingkai menandai kunci ✦ dengan alasannya; menyunting kunci melepas `asal`.
- **Bug lama diperbaiki:** pratinjau terlempar ke awal klip setiap kali pemutaran masuk kunci "Susun"/"Game", elemen <video> baru lahir di detik 0 sumber dan penjaga "parkir" Editor menariknya ke awal klip. `ClipPreview.pasangUtama` kini menyerahkan posisi+status putar ke elemen pengganti SEKETIKA.
- **ffmpeg bundelan (`backend/bin/ffmpeg` 7.0.2 statis) TIDAK punya `drawtext`.** Jangan pakai drawtext di mana pun; jam proksi ditulis lewat ASS/libass.

**Terukur:** job lewat API 74-104 dtk (sebagian besar menunggu model sibuk), ±5-13 rb token/klip. Render dengan kunci AI berhasil (mode `keys`).

**Sisa:** setengah detik hitam saat masuk susunan di pratinjau; sel terbagi bisa berisi orang yang sama bila kamera berpindah di tengah momen (jalur lokal); model memberi kekuatan 1,0 hampir ke semua momen; nomor orang di render bergantung pada roster yang sama (restart backend di antara susun dan render → risiko nomor tertukar); tahap 3 game horor (butuh video uji, minta izin unduh), tahap 4 OpenRouter, tahap 5 otomatis setelah auto-klip + cache.

## 20. Unduhan paralel dan lebih cepat (belum di-commit)

- **Kecepatan.** Satu sambungan ke YouTube diperlambat setelah ±30 dtk (terukur 9,8 → 2-5 MB/s di internet 100 Mbps).
  `ytdlp._opsi_paralel`: `extractor_args youtube formats=dashy` + `concurrent_fragment_downloads=8`
  (`OMNICLIP_SAMBUNGAN_UNDUH`). Terukur 10-12 MB/s stabil. Bila gagal, diulang sekali dengan satu sambungan.
- **Paralel.** Auto-klip pindah ke lajur baru `klip` (lebar 3, `OMNICLIP_LANE_KLIP`). Pekerjaan berat bergiliran
  lewat `jobs.gerbang_cpu` (semafor selebar lane `cpu`): job lane `cpu` memegangnya penuh, auto-klip mengambilnya
  sesudah unduhan (`ctx.giliran_cpu`) dengan pesan "menunggu giliran analisis". Job antre versi lama dipindah
  lajurnya saat start (`repos.jobs.pindah_lajur`).
- **"Macet di 100%".** Pesan "Menggabungkan…" dibuang pembatas laju tulis (datang <0,25 dtk sesudah kabar unduhan
  terakhir). `ctx.progress(paksa=True)` untuk pesan pergantian langkah, dan `_make_pp_hook` melaporkan lama
  penggabungan tiap 2 dtk (terukur 2,5 menit untuk 1,3 GB di hard disk NTFS eksternal).

## 21. Main game bisa disetel, dan Susun sendiri yang tidak memotong diam-diam (belum di-commit)

- `render.susun_layout_gaming(facecam, src_w, src_h, out_w, out_h, wajah=40, permainan="utuh"|"isi")`.
  "utuh" = seluruh layar permainan (31,6% kanvas untuk 16:9) di bawah wajah, sisanya latar kabur;
  "isi" = memenuhi sisa kanvas dengan kotak sumber berasio sama dengan bidangnya (`_pas_rasio`).
  `_petak_tanpa_facecam` dibuang: permainan tidak lagi dipangkas seperempat demi menghindari facecam.
- Render mode gaming memakai `frame_layout` kiriman Studio bila ada; kunci "gaming" di linimasa diberi
  `layout` yang sama oleh `Editor.renderPayload`.
- Studio: `FramePanel.GamingSetelan` (Permainan utuh / Penuhi bawah, penggeser tinggi wajah, cari ulang);
  kotak di meja bingkai bisa diseret, sudutnya berasio terkunci (`beginRectDrag({aspek})`). Setelan per video
  di localStorage `omniclip.gaming` (`muatGaming`/`simpanGaming`).
- Bug: Main game → Susun sendiri membuat dua kotak "menyatu", susunan dari server tanpa `id`. Sekarang id baru.
- Susun sendiri: `frames.selaraskanBentuk`, mengubah ukuran kotak sumber menyesuaikan tinggi bidang tujuan,
  mengubah bidang tujuan menyesuaikan kotak sumber (cover saja). Terlapor: notifikasi donasi terpotong kiri-kanan.

## 22. Main game per klip dengan wajah yang berpindah; potongan Susun sendiri yang mandiri (belum di-commit)

- Letak facecam kini per klip, dipindai per 8 dtk (`reframe.deteksi_facecam_waktu`); pusat bergeser >8% = letak baru.
  Susunan membawa `reaksi: [{t, src, kotak}]`; render memecah kunci gaming per letak (`render.pecah_reaksi`).
  Main game tanpa linimasa sekarang lewat jalur kunci (satu kunci "gaming").
- Kotak Reaksi dibentuk DI DALAM panel facecam (`_pas_rasio(dalam=True)`), bukan dilebarkan ke layar permainan.
- Kotak Permainan bebas bentuk; bidangnya selebar kanvas setinggi bentuknya (`bidangPermainan` / `_bidang_permainan`).
- Setelan disimpan di klip (`susunan_game`, ikut Simpan); hasil deteksi yang belum disentuh hanya di-cache di Editor.
  Setelan per video di localStorage (bagian 21) dibuang, itulah yang membuat klip M dibingkai di kiri atas.
- Susun sendiri: tiap potongan memegang salinan susunannya (`Editor.setFrameKeys` + `frameCuts` membawa `layout`).
  Teruji: potong di 0:10, ubah potongan kedua, kembali ke 0:00 → potongan pertama tetap.
- Sisa: kotak facecam hasil deteksi sedikit lebih lebar dari panel aslinya (strip tipis permainan di tepi panel wajah).

## 23. Main game: memenuhi layar, tanpa facecam ganda, bebas diatur (belum di-commit)

- Bawaan "isi": wajah 40% atas, permainan mengisi 60% sisanya; potongan permainan dipilih yang tidak memuat
  facecam (`render._permainan_tanpa_wajah` / `frames.permainanTanpaWajah`). "utuh" tetap tersedia.
- Tepi panel facecam ditajamkan dari garis diam lintas waktu (`reframe._tepi_panel`): puncak gradien ≥2,5×
  median jalurnya DAN kuat di ≥70% panjang sisinya; sisi di pinggir bingkai tidak dicari; ditolak bila panel
  hampir selebar wajah. Terukur: 96GQgDkHC64 → 0-18,4% × 71,5-100% (tepat); Devour (facecam tanpa bingkai,
  orang dipotong dari latar) tetap memakai perkiraan dari awan wajah.
- Pindah letak facecam harus dibenarkan potongan 8 dtk berikutnya; ukuran dianggap berubah bila >2,5×.
- Studio: kedua bingkai Main game bebas seperti Susun sendiri (kotak sumber di meja bingkai, bidang di layar
  hasil). Preset/penggeser menyusun ulang dari awal. Garis putus-putus `.frame-rect-tampil` menandai bagian
  kotak yang sungguh tampil (cover), juga di Susun sendiri.

## 24. Subtitle bahasa asli, tab Sutradara, dan bingkai lebar saat tak ada wajah (belum di-commit)

- **Subtitle ikut bahasa video.** `CAPTION_LANGS` menaruh "id" di depan, dan YouTube MENERJEMAHKAN caption
  otomatis ke bahasa apa pun yang diminta, video Inggris keluar dengan subtitle Indonesia hasil mesin
  (terlapor pada "I Survived 100 Days on One Block"). `ytdlp.get_video_info` kini membawa `language`,
  `captions.fetch_youtube_captions(asli=…)` memintanya lebih dulu, dan hasil ASR dalam bahasa yang bukan
  bahasa video dianggap terjemahan lalu diulang. Teruji: kJu5VMN3yow → en manual 6.024 kata;
  96GQgDkHC64 → id ASR 7.516 kata. Menerjemahkan tetap ada, lewat panel Terjemah (pilihan pengguna).
- **Sutradara punya tabnya sendiri** (`SutradaraPanel.jsx`, tab "Sutradara"), keluar dari panel Sisipan.
- **Tanpa wajah → bingkai lebar.** `sutradara_ai._tanpa_wajah` + aturan di `jadikan_kunci`: rentang ≥2,5 dtk
  tanpa satu wajah pun jadi kunci `blur`, lalu kembali ke bingkai dasar. Teruji pada klip Minecraft:
  4 bagian dilebarkan (6,9-11,4 / 17,5-20,4 / 22,4-26,9 / 29,4-36,8 dtk).
- Sisa untuk sutradara: gaya subtitle per penutur (font, warna, letak), belum ada sama sekali; bidikan
  reaksi masih kurang rapi; mode otomatis setelah auto-klip; cadangan OpenRouter.

## 25. Kemajuan yang terlihat untuk setiap proses (belum di-commit)

- Render: `waitForJob(onProgress)`; baris catatan per klip menampilkan tahap, bilah, persen, dan sisa waktu
  (atau lama berjalan untuk tahap tanpa angka, mis. melacak wajah). Tombol Render menyebut "2/5 · 43%".
  Pesan server yang membawa persennya sendiri dirapikan (`bersihkanPesan`) supaya satu baris satu angka.
  Teruji di browser: 13% → 100% dengan "sisa 2 mnt 47 dtk" menurun sampai selesai.
- Deteksi ulang narasumber dan Tulis ulang judul kini tampil berjalan dengan kemajuannya (dulu diam sampai gagal).
- Unggah: bilah + persen dari job. Klip jadi: tombol simpan/hapus menunjukkan sedang bekerja.

## 26. Jalur audio, video yang hilang, dan transkrip berbahasa lain (belum di-commit)

- **Jalur audio.** `ytdlp.jalur_audio(info)` → `audio_tracks` di /api/video-info (asli dulu). Unduhan menerima
  `audio_lang` (auto-klip, /api/download); tanpa itu `format_sort` diawali `lang` sehingga suara ASLI yang
  diambil. Sebelumnya bitrate menentukan: 13 jalur 129,474-129,476 kbps pada video MrBeast → bahasa acak.
  Bila berkas di disk bertag bahasa lain (`bahasa_audio` lewat ffprobe), berkasnya disingkirkan (.lama) lalu
  diunduh ulang; dipulihkan bila unduhan gagal. Partitur: pilihan "Unduh suara" muncul di bawah kolom tautan.
- **Video hilang.** /api/projects menaruh `local_url` SESUDAH `**result`, sebelumnya `local_url` lama dari
  hasil tersimpan menimpanya dan Studio memutar berkas yang tidak ada (layar hitam). Studio kini menampilkan
  `VideoHilang` dengan tombol unduh ulang + pilihan audio + bilah kemajuan. Teruji: MrBeast pulih, 1080p, eng.
- **Transkrip berbahasa lain.** Cari ulang tidak memakai lagi transkrip caption tersimpan yang bahasanya bukan
  bahasa video; `transcripts.get_best` memilih yang terbaru bila peringkat sumber sama.
- Gerbang unduhan (bagian 25) teruji ulang di dalam proses: 3 bersamaan, 2 menunggu, batal saat menunggu OK.
- Catatan proses: pola `pgrep` "Projek Coding/.../python run.py" tidak cocok dengan perintah backend
  ("venv/bin/python run.py"), pakai `pgrep -f "python run.py"` (tidak mengenai aplikasi desktop).

## 27. Sutradara tanpa bilah kabur (belum di-commit)

- Keputusan pemilik: sutradara hanya memakai `smart`, `motion`, `gaming`, `layout` (`sutradara_ai.MODE_SUTRADARA`).
  Menu model: "lebar" diganti "ikuti_gerakan"; prompt melarang latar kabur. Bingkai dasar saat wajah jarang
  terlihat = `motion` (dulu `blur`); wajah terlalu kecil = bingkai dasar (dulu `blur`); bagian tanpa wajah
  ≥2,5 dtk = `motion` (jeda wajah <1,5 dtk di antaranya disatukan). "reaksi_penuh" = susunan satu bingkai
  (dulu kotak tetap). `_tanpa_kabur` menyaring semua kunci di jalur AI dan lokal.
- Render: kunci ber-`asal` ai/otomatis yang rencana wajah/gerakannya tak terpakai jatuh ke potong tengah,
  bukan bilah kabur. Pilihan manual pengguna tidak berubah.
- Teruji: Minecraft 0-40 dtk → smart/motion bergantian, nol blur; horor klip M → gaming → layout → gaming.

## 28. Bingkai dasar per saat: game / wajah / gerakan (belum di-commit)

- Aturan pemilik: game + wajah bersamaan → bingkai game; hanya game → ikuti gerakan; hanya wajah → ikuti wajah.
- `sutradara_ai._label_per_sampel`: wajah "facecam" = lebar ≤14% bingkai DAN di pojok (x <25%/>75%, y <30%/>55%),
  angka dari rekaman MrBeast (wajah pemain 6-12,6%, x 9-20%/83-91%; wajah kamera orang x 52-55%).
  Potongan <1,5 dtk disatukan (`_rapikan_potongan`). Tiap potongan game mencari panel facecam-nya sendiri
  (`deteksi_facecam` pada potongan itu; cadangan `_kotak_dari_wajah`) dan membawa `layout`-nya di kunci.
- `jadikan_kunci(dasar_waktu=…)` + `_pasang_dasar_waktu`: momen reaksi tetap di atasnya, dan sesudahnya kembali
  ke dasar yang berlaku di detik itu. Dipakai bila tidak ada facecam sepanjang klip (jalur AI dan lokal).
- Studio: kunci game yang membawa susunannya sendiri ditampilkan dan disunting dari kuncinya.
- Teruji MrBeast 0-40 dtk: gerak / game (11,4-17,5) / gerak / game (20,4-22,4) / gerak / wajah (36,8); dirender
  dan diperiksa bingkainya. Podcast Sule dan horor klip M tidak berubah.
- Sisa: potongan game yang sangat pendek (2 dtk) memakai kotak perkiraan dari ukuran wajah, tepi panel ikut masuk.

## 29. Pratinjau tidak lagi melacak ulang di tiap potongan (belum di-commit)

- Penyebab: efek jejak di `Editor.jsx` bergantung pada `frameModeEfektif`/`subjekLacak`, yang berganti di setiap
  batas potongan hasil sutradara (wajah → gerak → game). Tiap pergantian membuang jejak dan meminta ulang tanpa
  menyimpannya; memutar ulang klip mengulang semuanya.
- Sekarang: `cacheJejakRef` menyimpan jejak per (video, segmen, rasio, gaya gerak, subjek, tanda orang, penutur);
  `ambilJejak` menyatukan permintaan yang sama; semua subjek yang dibutuhkan linimasa (`subjekDibutuhkan`)
  diambil di latar sejak awal. Server sudah punya `_REFRAME_CACHE` untuk muat ulang halaman.
- Teruji di browser (MrBeast klip A, 4 potongan wajah/gerak): dua pemutaran penuh termasuk putar ulang,
  0 permintaan jejak baru, tanda "Melacak" 0 dtk.

## 30. Bingkai bawaan dipilih dari isi klip (2026-09-21)

Dulu klip dibuka dengan cara bingkai terakhir untuk videonya (biasanya ikut wajah), jadi klip game jadi close-up facecam.
- `sutradara_ai.jenis_klip` memakai penggolong per sampel yang sama dengan sutradara (`_label_per_sampel`):
  - game ≥70%, atau ≥30% ditambah panel facecam yang terbaca → `gaming`;
  - tanpa wajah / wajah jarang ≥60% → `motion`;
  - selainnya → `smart`.
  - Klip tanpa satu wajah pun langsung `motion`: pemindai panel tertipu kartun.
- `jenis_klip_tersimpan` menyimpan hasilnya di `search_cache` berkunci `jenis:`, yang tidak ikut dibersihkan saat startup. Endpoint `POST /api/clip-jenis`.
- Studio: pilihan manual disimpan per klip (`cara_bingkai`) dan selalu menang. Panel Bingkai menampilkan "Membaca isi klip…", lalu alasan pilihannya, dan tombol "Kembali ke otomatis".
- Render: klip yang belum pernah dibuka dikirim `frame_mode: "otomatis"`, lalu `run_render` menggolongkannya sendiri.
- Hasil uji:
  - 9 klip game (3 video horor) → game;
  - podcast Sule → ikut wajah;
  - kartun pemadam → gerakan.
- Waktu deteksi pertama 20-140 dtk per klip; pembukaan ulang ±3 dtk.

## 31. Verifikasi bot: runtime JS, PO Token, cookies yang kini berfungsi (2026-09-21)

**Masalah:** IP ditandai YouTube; 5 dari 6 video ditolak "Sign in to confirm you're not a bot", termasuk di pemutar Firefox.

**Akar masalah:** yt-dlp berjalan tanpa runtime JS ("JS runtimes: none", jalur yang ia sebut usang). Karena itu cookies pun gagal ("The page needs to be reloaded"), dan catatan lama menyimpulkan cookies "memperburuk".

| Kombinasi (dari IP yang ditandai) | Hasil |
|---|---|
| polos | ditolak |
| Deno | ditolak |
| Deno + PO Token | ditolak |
| cookies + Deno | 1080p |
| cookies + Deno + PO Token | 2160p, unduhan penuh lewat antrean aplikasi berhasil |

**Perubahan:**
- `services/alat_yt.py` baru:
  - mengunduh sekali Deno 2.9.7, bgutil-pot 0.8.1 (Rust), dan plugin HTTP-nya ke `STORAGE/alat/`, dengan versi dan SHA-256 dikunci;
  - menyalakan server token hanya di 127.0.0.1;
  - `terapkan(opts)` menambah `js_runtimes`, `remote_components={'ejs:github'}`, dan `base_url` token.
  - Plugin dan server berlisensi GPL-3.0, jadi sengaja TIDAK dibundel.
- `yt-dlp-ejs==0.8.0` masuk requirements dan `collect_all` di spec. `--periksa` memeriksa skrip ejs.
- `ytdlp._ekstrak/_unduh`: berhenti pada galat bot pertama. Sebelumnya bisa sampai sekitar 17 permintaan player per percobaan.
- Pesan galat bot kini berisi langkah nyata: tunggu, ganti jaringan, atau cookies akun cadangan.
- `yt_klien.urutan_coba`: klien bawaan yt-dlp dulu saat cookies aktif.
- `UNDUH_BERSAMAAN` 3 → 2.
- `cookies.py`:
  - video uji diganti ke jNQXAC9IVRw, karena Rick Astley tetap lolos saat IP ditandai;
  - saran baru untuk kasus "polos 0, dengan cookies > 0".
- Teks kartu Cookies diperbarui.

**Yang perlu diingat:**
- Aplikasi desktop terpasang (1.0.6) baru mendapat semua ini lewat rilis baru.
- Pemasangan pertama mengunduh sekitar 90 MB dari GitHub.

## 32. Bingkai: ikut wajah ke yang bicara, kepala utuh di game, render GPU (2026-09-21)

**Ikut wajah:**
- Diukur di 7 klip podcast: pada sampel ≥2 wajah dengan bukti mulut kuat, bingkai menyorot orang lain 46% waktunya.
- Sebab: penutur yang tak terpetakan ke wajah (ohJbKVkrZ4U: 3 penutur, 1 terpetakan) jatuh ke wajah cadangan.
- Perbaikan: `reframe._ikuti_mulut`, dengan pemungutan suara bukti mulut per jendela ±0,75 dtk, porsi ≥60%, hold 0,6 dtk, dan hanya wajah ≥4,5% lebar bingkai.
- Hasil: 46% → 27%. Diperiksa mata di ohJbKVkrZ4U (pembicara bergestur kini disorot, sebelumnya pendengarnya).
- Bidikan lebar berwajah kecil sengaja tidak disentuh.

**Game:**
- `render.kotak_reaksi` memuat kepala utuh dari `awan_kotak` (+35% atas, 22% bawah, 25% samping).
- `tinggi_wajah_otomatis` memilih tinggi bidang wajah 40-50% sesuai bentuk panel (luapan ≤8%).
- `_permainan_tanpa_wajah(wajah_saja=...)` hanya menghindari kepala bila menghindari panel menggeser >3%.
- Cermin JS di `frames.js` (`kotakReaksi`, `permainanTanpaWajah`) terverifikasi 0 beda pada 7 klip.
- Ruang di atas alis: dulu ~17% tinggi wajah, kini 35%.

**Render:**
- `services/enkoder.py` menguji encoder GPU (VA-API/NVENC/QSV/AMF) sekali saat startup. Render GPU yang gagal otomatis diulang dengan x264.
- Terukur 27,9 vs 45,4 dtk untuk klip 70 dtk, SSIM 0,990.
- ffmpeg statis Linux (johnvansickle) tanpa encoder GPU, jadi ffmpeg lain di PATH (/usr/bin) ikut dicoba.
- Latar kabur tersembunyi di susunan game tidak berpengaruh ke kecepatan (diukur).

**Temuan lingkungan:**
- Data OmniClip ada di HDD 5400 rpm NTFS lewat FUSE: 67 MB/s, melawan SSD 523 MB/s.
- Pembacaan pertama sumber membuat render ~2x lebih lambat (33 vs 17 dtk untuk 30 dtk).
- Saran ke pengguna: pindahkan folder data ke SSD.

**Belum:** build Linux bisa diganti ke ffmpeg dengan VA-API (BtbN) bila ukuran diterima.

## 33. Pratinjau yang tidak macet, dan profil dengan akun Google sendiri (2026-09-21)

**Video hitam/tidak jalan di Studio:**
- Firefox memutar sumber 4K VP9 pada 0,44x kecepatan (5 dtk putar = 2,2 dtk maju), dan lompat 2,6 dtk. Chromium lancar, jadi gejalanya "kadang-kadang".
- `proksi.py` v2: salinan H.264 1280 px kini membawa suara (AAC) dan faststart, dan ikut diputar Studio (`preview_url`, `pratinjau_disiapkan`).
- Studio yang menunggu mendahulukan dan menaikkan prioritas pembuatan salinan (`_diburu`), lalu berpindah sendiri di detik yang sama.
- `proksi` masuk MEDIA_DIRS. Salinan v1 (tanpa suara) dibuang `bersihkan_yatim`.
- Terukur di Firefox: lompat 0,15 dtk, putar penuh kecepatan. Render tetap memakai sumber asli.
- GPU (VA-API) justru lebih lambat untuk salinan 4K (70 vs 36 dtk per 30 dtk): hwdownload mahal.

**Profil** (migrasi 4, cadangan DB: `OmniClip_Storage/omniclip.db.cadangan-sebelum-profil`):
- Tabel `profil` (nama, warna, minat, folder_klip, unggah) dan `profil_video`. `profil_id` di search_history dan uploads. Semua data lama menjadi milik profil 1 "Utama".
- Header `X-Omniclip-Profil` (api.js, localStorage `omniclip.profil`) → middleware → contextvar `profil.kini()`.
- `queue.enqueue` mencatat `profil_id` di payload, dan `_run` memasang profil itu selama job berjalan.
- Per profil:
  - folder klip (Utama = edited_clips; lainnya `edited_clips/<nama> (<id>)`, jalur disimpan saat dibuat), media kategori `klip_<id>`;
  - token Google `akun/<id>/google_token.json`; token lama pindah ke profil 1. OAuth `prompt=select_account consent`, dan state mengingat profil peminta;
  - Partitur (profil_video; menghapus kartu yang dipakai profil lain hanya melepas);
  - riwayat pencarian (`/api/riwayat-cari`), dengan chip "Terakhir dicari" di beranda;
  - beranda dari minat (bobot 2) + 8 pencarian terakhir;
  - jeda unggah YouTube per kanal.
- Unggah otomatis sesudah render dijalankan server (`services/unggah.py`, `setelah_render`), sesuai setelan profil, atau pilihan YouTube/Drive di Studio untuk render itu.
- UI: pemilih profil di kepala aplikasi, halaman /profil (buat/pakai/hapus, minat, akun Google, unggah otomatis, templat deskripsi `{judul}` `{hashtag}`).

**Diuji:**
- Profil uji: Partitur 0 vs 25, klip 0 vs 55.
- Beranda berisi Phasmophobia dari minat/riwayat.
- Render masuk folder profil (klip_2).
- Unggah otomatis tanpa akun menjawab "Akun Google profil ini belum tersambung." dan render tetap sukses.
- Profil uji sudah dihapus.

**Belum diuji:** unggah sungguhan ke YouTube/Drive per akun. Mesin pengembangan ini tidak punya berkas OAuth client.

## 34. Poin B dan D dari tinjauan 21 September (2026-09-22)

**B4, sisa unduhan terputus:**
- `ytdlp.bersihkan_sisa_unduhan()` dijalankan saat startup: buang .part / .part-FragN / .ytdl berumur >24 jam bila tidak ada unduhan berjalan. Terukur 6 berkas, 1 GB lega.
- Berkas perantara `.fNNN.mp4` (video tanpa suara dari penggabungan yang gagal) tidak lagi dipakai sebagai sumber (`paths.berkas_perantara`), dan tidak didaftar di Unduhan.
- `…IqHjpESyE_Y.f623.mp4` (17 GB) TIDAK dihapus: yt-dlp memakainya ulang bila video itu diunduh lagi. Keputusan pemilik.

**B5:** kartu akun Google di Pengaturan diganti penunjuk ke halaman Profil.

**D9, ikut wajah:**
- `reframe._lengkapi_peta_dari_mulut`: penutur tanpa wajah dipetakan dari mulut dominan selama gilirannya (≥1,5 dtk bukti, ≥60%).
- `_ikuti_mulut` tidak lagi menimpa subjek hasil peta kecuali mulut orang terpetakan diam dan orang lain ≥80%.
- Sule klip D: 5/6 titik benar (dulu 2/6 tanpa perbaikan mulut, 4/6 dengan perbaikan pertama); render dicek mata.

**D10:**
- Potongan game pendek memakai letak panel dari seluruh klip (`panel_di`) sebelum menebak dari ukuran wajah.
- Video tanpa wajah (`sutradara.tanpa_wajah`, porsi berwajah <0,25; kartun tanpa orang 0,18, video berorang 0,62-1,00): penutur <12% dilebur ke penutur besar terdekat. Berlaku di analisis dan deteksi ulang.

**D11, sutradara:**
- Pratinjau memakai pemutar utama yang tetap + cermin yang disiapkan lebih dulu (hanya untuk klip yang punya potongan Susun/game). Masuk ke susunan tanpa bingkai hitam (kecerahan 6,7 → 88). Klip biasa tidak terbebani (63 vs 61 bingkai terbuang per 6 dtk).
- Susunan terbagi menyaring orang yang tidak terlihat bersamaan (<30%) atau kotaknya bertumpuk >50%; bila sisa satu → wajah tunggal.
- Kekuatan momen = 0,5 × model + 0,5 × bukti suara lokal (0,35 tanpa bukti).

**D12, subtitle:**
- `subtitles._tanpa_tumpang`: baris berakhir saat baris berikutnya mulai (takarir rolling).
- Subtitle kedua bisa diseret dan diubah ukurannya di pratinjau.
- Terjemahan tanpa kunci / saat Gemini gagal → Google Terjemahan web. Gemini dibatasi 45 dtk total (dulu >2 menit mencoba 6 model).

**D13:** penyaring pencarian durasi (<4 / 4-20 / >20 mnt) dan tanggal unggah lewat `sp_pencarian` (protobuf SearchParams YouTube, dicocokkan dengan nilai youtube.com). Terukur: pendek 17-233 dtk, panjang 1.203-10.117 dtk.

**D14:** bahan dari berkas lain SUDAH ADA di Sisipan (video diunggah, posisi bawah/atas/tengah/sudut/penuh, waktu mulai dan potong). Catatan nomor 5 di atas usang.

## 35. Impor video dari komputer, dan subtitle bahasa Jepang (2026-09-22)

**Laporan:**
- Impor anime gagal diproses, dan berkasnya muncul di halaman Unduhan.
- Sebab gagal: id impor ("L" + 10 heks) berbentuk id YouTube, dan `run_auto_clip` selalu meminta metadata ke YouTube ("This video is unavailable"). Impor tidak pernah bisa sampai ke klip.

**Perbaikan impor:**
- Folder `impor/` sendiri (MEDIA_DIRS "impor"); impor lama dipindah saat startup (`paths.pindahkan_impor_lama`).
- `paths.adalah_impor` (baris video berkanal "Impor lokal"); `find_local_video` mencari di unduhan lalu impor; `kategori_berkas` untuk URL pemutar.
- Pipeline: metadata dari basis data + probe; tanpa caption YouTube, langsung ke Whisper; berkas hilang → pesan jelas.
- Sampul kartu Partitur dari bingkai video (`/api/impor/{id}/sampul`).
- Bilah kemajuan kirim berkas (`apiUnggah`, XHR).
- Diuji: impor 60 dtk → 2 klip, pratinjau jalan, sampul tampil, tidak ada di Unduhan.

**Subtitle Jepang/Mandarin** (Whisper memecah per huruf):
- `services/teks.py`: `sambung` tanpa spasi di sisi CJK, `pecah`, `bobot_kata` (huruf CJK = 1/3 kata, lebar 2), `titik_patah` / `patah_teks` (libass tidak membungkus teks tanpa spasi → `\N` sendiri sesuai `box_w` dan ukuran font).
- Dipakai di clipmodel (pembentukan baris), transcript, subtitles (`reconcile_words` kini sadar-aksara; karaoke, typewriter, baris utuh), pratinjau (`berjarak`), dan hook `_wrap`.
- Dulu "あ ぁ 白 で あ った"; kini "さっきグゼールフィーとゾロが温", 15 huruf per baris, dua baris di kanvas, sorotan per huruf.

**Risiko belum diuji:** font subtitle bawaan tidak punya huruf Jepang. Di Linux libass meminjam Noto CJK sistem; di Windows belum dicek (bisa kotak kosong). Pilihan: bundel Noto Sans JP.

## 36. Subtitle asli + terjemahan otomatis, dan impor tanpa salin (2026-09-22)

**Permintaan:** anime Jepang tampil dengan subtitle Jepang DAN terjemahan Indonesia/Inggris.

**Terjemahan otomatis:**
- `terjemah.kedua_untuk_klip` dijalankan di akhir auto-klip bila bahasa video ≠ tujuan.
- Setelan `terjemah.otomatis` (bawaan "id"), diatur di kartu Pengaturan "Terjemahan otomatis".
- Tombol "Terjemahkan semua klip" di tab Subtitle, untuk proyek lama.
- Tata letak: terjemahan kuning 70 px di margin 560 (DI ATAS subtitle asli di 300). Bukan di bawah: anime fansub membawa subtitle tertanam di 15% bawah dan terjemahan tertimpa (terlihat di render uji).

**Impor tanpa salin:**
- Unggah lewat peramban selalu menyalin berkas (anime 248 MB tersalin dua kali).
- "Dari komputer" kini membuka penjelajah OmniClip (`FolderPicker modeVideo`, `/settings/jelajah?video=true`), lalu `POST /api/impor/jalur`: jalur disimpan di meta video, berkas dibaca di tempatnya.
- Pemutar untuk berkas di luar folder OmniClip: `/api/impor/{id}/berkas`. Jalur yang sama → kartu yang sama.
- Unggah lewat peramban tetap ada untuk HP/perangkat lain.

**"Macet di 2%" yang dilaporkan:**
- Job impor pengguna menunggu jatah CPU karena uji saya berjalan bersamaan; impornya sendiri selesai (8 klip).
- Pesan "Video sudah terunduh" diganti "Video dari komputer siap" untuk impor.
- Salinan impor ikut terhapus bersama kartunya; salinan yatim dibersihkan saat startup (1 × 248 MB).

**Catatan:** Whisper "base" banyak salah dengar pada bahasa Jepang, dan terjemahannya ikut salah. Model yang lebih besar dipilih di Pengaturan.
