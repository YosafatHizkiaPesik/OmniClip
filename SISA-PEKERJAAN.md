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

## 4. Online, hanya untuk yang diberi akses

Belum dimulai. Yang sudah disepakati:

- Di-host di layanan **gratis**, bisa dibuka dari semua perangkat.
- Hanya pemilik dan orang yang sengaja diberi tahu yang bisa mengakses.

Hal yang perlu diputuskan saat mengerjakannya, dan sebaiknya diputuskan
sebelum menulis kode:

1. **Yang mana yang dionlinekan.** Aplikasi ini memuat unduhan video, render
   ffmpeg, dan model ONNX. Hosting gratis biasanya tidak punya CPU, RAM, atau
   ruang penyimpanan untuk itu. Kemungkinan besar yang di-host hanya
   antarmukanya, sementara pekerjaan berat tetap di mesin sendiri lewat
   terowongan (mis. Cloudflare Tunnel) — itu juga yang paling murah.
2. **Cara membatasi akses.** Pilihan paling sederhana yang tetap aman:
   satu kata sandi bersama, atau daftar email yang diizinkan.
3. **Hal yang tidak boleh ikut terbuka.** `backend/.env` berisi `GEMINI_API_KEY`,
   dan `OmniClip_Storage/google_client_secret.json` serta `google_token.json`
   masing-masing cukup untuk mengunggah ke kanal YouTube pemilik. Ketiganya
   sudah diabaikan git dan berizin 600; saat dionlinekan, ketiganya tidak boleh
   ikut ter-deploy dan tidak boleh bisa dibaca lewat jaringan.
4. **CORS dan alamat bind.** Sekarang backend sengaja hanya mendengar di
   `127.0.0.1` dan CORS-nya dikunci ke `localhost:5173`. Keduanya harus diubah
   dengan sadar, bukan dilonggarkan jadi `*`.

---

## Catatan cara kerja yang terbukti mahal kalau dilanggar

- **Lihat datanya, jangan cuma hitung.** Perbaikan bingkai terbesar sesi ini
  datang setelah petak mulutnya ditampilkan sebagai gambar. Sebelum itu, berjam-
  jam dihabiskan menyetel statistik di atas petak yang isinya dinding bambu.
- **Ukur sebelum dan sesudah, pada video yang tidak dipakai menyetel.**
  Beberapa "perbaikan" ternyata hanya cocok pada satu video.
- **Kontrol negatif itu perlu.** Rekaman stand-up satu orang adalah yang
  membuktikan bahwa pemisahan penutur tidak mengarang orang kedua.
