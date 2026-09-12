# Sisa Pekerjaan OmniClip

Catatan hal-hal yang **belum selesai**, ditulis 12 September 2026 setelah commit
`b4f991f`. Tiap poin memuat apa yang sudah terukur, bukan hanya apa yang terasa —
supaya saat dikerjakan nanti tidak perlu menebak ulang dari awal.

Urutan yang disepakati: **subtitle dulu**, lalu **membuat sistem bisa diakses
online**. Bingkai sengaja ditinggalkan dulu dalam keadaan sekarang.

---

## 1. Bingkai otomatis — ditunda, sekitar 80% benar

Sudah bekerja: bingkai mengikuti orang yang sedang bicara. Kuncinya bukan
algoritma pencocokannya melainkan cara mulut diukur — dulu petaknya diskalakan
jarak antar mata, yang menyusut sampai 0,30 lebar wajah ketika orang duduk
saling menghadap, sehingga yang terukur dinding di belakangnya. Sekarang
diskalakan lebar kotak wajah, dan yang diukur **bukaan** mulut ditambah
**ragam** bukaannya, bukan beda piksel antar bingkai.

| cara mengukur | pemisahan (simpangan baku) |
|---|---|
| beda piksel, petak lama | 0,023 — setara nol |
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
penawar murah sudah dicoba dan semuanya gagal — sampel diperbesar ke 960 px,
seluruh bingkai dijadikan abu-abu, kontras lokal dinaikkan (CLAHE), dan
gabungan CLAHE + sampel besar. Tidak satu pun menemukan wajahnya.

Perlu diputuskan nanti: ini soal **deteksi wajah** (butuh detektor yang tahan
oklusi) atau soal **pilihan editorial**. Momen itu adalah reaksi, bukan ucapan —
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

## 2. Subtitle — hasil render berbeda dari pratinjau

**Ini pekerjaan berikutnya.**

Sudah dibetulkan sebelumnya (commit `37aa145`): **ukuran huruf** dan
**pembungkus baris**. Penyebabnya, `size` adalah Fontsize pada berkas ASS, dan
libass tidak memperlakukannya seperti `font-size` CSS — terukur, tinggi kapital
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

## 3. Auto-subtitle per orang — yang paling sulit

Tujuannya: sistem sendiri yang menentukan **ada berapa orang**, lalu
memasangkan **suara** dengan **wajah**, lalu memberi warna subtitle per orang —
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
dan 4** — nomor 1 terpakai dua kali untuk orang berbeda.

Penyebab yang sudah diketahui dari video lain: kemiripan sidik wajah antar
orang **yang sama** bisa jatuh ke 0,133–0,175 saat wajahnya kecil atau
menyamping, sementara antar orang **berbeda** bisa naik ke 0,262–0,279. Kedua
sebaran itu bertumpang tindih, jadi tidak ada satu ambang yang memisahkannya.

Arah yang masuk akal: gunakan **posisi duduk** sebagai pengunci pada video
berkamera diam — dua orang yang terlihat bersamaan di tempat berbeda pasti
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
untuk enam klip), jadi yang tersisa hanya bukaan mulut — dan bukaan mulut saja
menghasilkan jangkar yang tercemar reaksi penyimak. Arah yang belum dicoba:
model deteksi penutur aktif sungguhan (TalkNet/SyncNet ONNX) untuk menggantikan
bukaan mulut sebagai sumber jangkar kedua.

---

## 4. Dipakai di mana saja — sebagai aplikasi desktop

**Arahnya berubah 12 September 2026.** Rencana hosting ditinggalkan: tidak ada
anggaran untuk domain, VPS, maupun mini PC selama clipping belum menghasilkan,
dan laptop tidak boleh dijadikan server. Bentuknya sekarang **satu aplikasi yang
dijalankan tiap orang di komputernya sendiri**, dengan penyimpanan
sendiri-sendiri. Lihat `PANDUAN-APLIKASI-DESKTOP.md`.

`.apk` tidak dikerjakan, dan alasannya terukur: keempat dependensi inti punya
**nol** wheel Android (ctranslate2, onnxruntime, opencv, av), sementara Windows
punya semuanya. Tiap satu harus dikompilasi silang dari sumber untuk
`aarch64-linux-android`, dan `ffmpeg-kit` — satu-satunya jalur ffmpeg praktis di
Android — sudah diarsipkan pengembangnya.

### Sudah selesai dan diuji

- **Bundel PyInstaller** (`backend/omniclip.spec`), satu-folder, ± 770 MB
  terpasang. Peluncur `omniclip_app.py` memilih port kosong sendiri dan membuka
  peramban.
- **Penyimpanan pindah ke folder pengguna** saat terbungkus
  (`%LOCALAPPDATA%\OmniClip`), supaya memperbarui aplikasi tidak menghapus klip.
  `OMNICLIP_STORAGE` menimpa keduanya.
- **ffmpeg statis dibundel**, ditaruh di depan `PATH` — satu baris, bukan
  sebelas suntingan di tempat pemanggilan, dan yt-dlp ikut menemukannya.
- **SFace mengunduh dirinya sendiri.** Dulu hanya bisa didapat lewat perintah
  curl di requirements.txt: cukup saat satu-satunya pengguna adalah penulis
  kodenya, dan berarti pengenal wajah tidak akan pernah menyala di komputer
  siapa pun begitu aplikasinya dibagikan.
- **`--periksa`**: bundel memeriksa dirinya sendiri — 16 pustaka, berkas
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

Bukan font yang keliru — **setiap render bersubtitle gagal**, hanya di Windows.
Tiga tempat menyusun path untuk filtergraph dengan tiga salinan kode yang tidak
sama, dan salinan `fontsdir` tidak pernah mendapat perlakuan itu sama sekali.
Sekarang ketiganya memakai `services/paths.ffpath()`.

### Bukti bundel Linux, menyeluruh

Dijalankan terhadap pustaka video asli: render 12 detik selesai dalam 15 detik,
1080x1920 h264 30fps, AAC 48kHz stereo. Bingkai diperiksa dengan mata — reframe
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
5. **Pembaruan masih manual** — unduh dan ekstrak ulang.

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
