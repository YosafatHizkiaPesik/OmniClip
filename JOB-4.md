# JOB-4: Montase, studio penyunting video lengkap dengan animasi buatan AI

> **Diminta pemilik:** 3 November 2026 (OmniClip versi 1.3.9).
> **Nama kerja:** *Montase*. Label menu lewat kamus terjemahan, jadi nama ini
> bisa diganti kapan saja tanpa mengubah kode (keputusan terbuka T-1).
> **Dokumen ini adalah satu-satunya sumber rencana Montase.** Setiap tugas yang
> selesai dicentang di sini, setiap keputusan baru dicatat di sini.

---

## Daftar isi

**Bagian A: Pahami dulu** (bahasa sederhana, 5 menit)
1. [Apa itu Montase](#1-apa-itu-montase)
2. [Papan status](#2-papan-status)
3. [Keputusan](#3-keputusan)
4. [Gambaran cara kerja](#4-gambaran-cara-kerja)

**Bagian B: Rencana kerja** (tahap demi tahap, bisa dicentang)

5. [Aturan main pengerjaan](#5-aturan-main-pengerjaan)
6. [Tahap 0: Uji teknis](#tahap-0-uji-teknis)
7. [Tahap 1: Kerangka](#tahap-1-kerangka)
8. [Tahap 2: Penyuntingan dasar](#tahap-2-penyuntingan-dasar)
9. [Tahap 3: Teks, suara, dan efek](#tahap-3-teks-suara-dan-efek)
10. [Tahap 4: AI pembuat animasi](#tahap-4-ai-pembuat-animasi)
11. [Tahap 5: Asisten penyunting AI](#tahap-5-asisten-penyunting-ai)
12. [Tahap 6: Rapikan dan rilis](#tahap-6-rapikan-dan-rilis)
13. [Kapan saja: suara AI baru (ElevenLabs dan lainnya)](#kapan-saja-suara-ai-baru)

**Bagian C: Acuan teknis** (untuk yang menulis kodenya)

14. [Struktur folder](#14-struktur-folder)
15. [Batas modul](#15-batas-modul)
16. [Dokumen proyek (format data)](#16-dokumen-proyek)
17. [Basis data](#17-basis-data)
18. [API](#18-api)
19. [Mesin Montase (Node + Remotion)](#19-mesin-montase)
20. [Pratinjau dan kotak pasir](#20-pratinjau-dan-kotak-pasir)
21. [Kontrak komponen animasi AI](#21-kontrak-komponen-animasi-ai)
22. [Hasil ekspor dan Klip jadi](#22-hasil-ekspor-dan-klip-jadi)
23. [Risiko](#23-risiko)

**Bagian D: Lampiran**

24. [Hasil uji teknis (diisi di Tahap 0)](#24-hasil-uji-teknis)
25. [Daftar uji permintaan animasi](#25-daftar-uji-permintaan-animasi)
26. [Di luar cakupan (nanti)](#26-di-luar-cakupan)
27. [Kamus istilah](#27-kamus-istilah)
28. [Melanjutkan di sesi baru](#28-melanjutkan-di-sesi-baru)

---

# BAGIAN A: PAHAMI DULU

## 1. Apa itu Montase

**Singkatnya:** CapCut di dalam OmniClip, ditambah AI yang bisa diminta membuat
animasi lalu hasilnya Anda koreksi sendiri.

OmniClip sekarang punya **Studio Klip** (Partitur): tempat memotong video
panjang jadi klip pendek secara otomatis. Montase adalah **studio kedua yang
terpisah**, untuk menyunting video secara bebas:

| | Studio Klip (sudah ada) | Montase (baru) |
|---|---|---|
| Untuk apa | Memotong satu video panjang jadi banyak klip | Menyusun video apa pun dari banyak bahan |
| Bahan | Satu video sumber | Bebas: unduhan, Klip jadi, berkas sendiri, musik, gambar, suara |
| Cara kerja | Otomatis, lalu disetel | Linimasa banyak lajur seperti CapCut/Premiere |
| AI | Memilih momen, membingkai | Membuat animasi, menyusun video, menulis narasi |
| Format | Pendek vertikal | Bebas (9:16, 16:9, 1:1, 4:5, ukuran sendiri) |

Tiga kemampuan besar, dibangun berurutan:

1. **Editor linimasa.** Seret bahan ke linimasa, potong, belah, susun di banyak
   lajur, beri teks, transisi, musik, narasi, lalu ekspor.
2. **AI pembuat animasi.** Ketik "buat hitung mundur #5 bergaya neon". AI
   menulis animasinya, mesin memeriksanya, lalu animasi itu muncul di linimasa.
   Teks, warna, kecepatan, dan posisinya bisa diubah lewat panel tanpa
   menyentuh kode, atau minta revisi lewat chat ("lebih cepat", "warna merah").
3. **Asisten penyunting.** Ketik "susun Top 5 momen paling lucu dari klip-klip
   ini". AI menyusun linimasa lengkap (urutan, kartu peringkat, narasi, musik,
   animasi), dan Anda tinggal mengoreksi.

**Yang bukan tujuannya:** menyamai Premiere di rilis pertama. Fitur kelas berat
(masking, chroma key, koreksi warna lanjut) ada di [daftar nanti](#26-di-luar-cakupan).

## 2. Papan status

> **Perbarui tabel ini setiap kali sebuah tugas selesai.** Inilah yang pertama
> dibaca di sesi baru.

| Tahap | Isi singkat | Status | Tugas |
|---|---|---|---|
| 0 | Uji teknis: membuktikan Remotion jalan di dalam OmniClip | ✅ Selesai 3 Nov 2026 | 8/8 |
| 1 | Kerangka: menu, daftar proyek, media, pratinjau, ekspor | ✅ Selesai 3 Nov 2026 | 10/10 |
| 2 | Penyuntingan dasar: linimasa sungguhan | ✅ Selesai 3 Nov 2026 | 8/8 |
| 3 | Teks, suara, efek, transisi, keyframe | 🟨 Sedang dikerjakan | 5/10 |
| 4 | AI pembuat animasi | ⬜ Belum mulai | 0/10 |
| 5 | Asisten penyunting AI | ⬜ Belum mulai | 0/6 |
| 6 | Rapikan dan rilis | ⬜ Belum mulai | 0/8 |
| ✱ | Suara AI baru (ElevenLabs dan lainnya), kapan saja | ⬜ Menunggu pilihan pemilik | 0/3 |

Tanda status: ⬜ belum mulai · 🟨 sedang dikerjakan · ✅ selesai · ⛔ tertahan (tulis alasannya).

**Tugas berikutnya:** `M3.5`.

## 3. Keputusan

### Sudah diputuskan

| No | Tanggal | Keputusan | Alasan singkat |
|---|---|---|---|
| K-1 | 3 Nov 2026 | Montase dibangun **di dalam OmniClip** sebagai modul terpisah, bukan proyek baru. | AI, suara, media, antrean render, akun, unggah, dan pembangun rilis sudah ada. Proyek baru berarti membangun dan merawat dua salinan. |
| K-2 | 3 Nov 2026 | Montase **terpisah dari Studio Klip**. Bahan tidak harus dari Klip jadi. | Permintaan pemilik: studio penyunting yang benar-benar baru. |
| K-3 | 3 Nov 2026 | **Format bebas**: preset 9:16, 16:9, 1:1, 4:5, plus ukuran dan fps sendiri. | Permintaan pemilik. |
| K-4 | 3 Nov 2026 | Mesin pratinjau, render, dan animasi: **Remotion**. | Berbasis React (sama dengan antarmuka OmniClip). Pratinjau dan hasil akhir memakai kode yang sama. Dirancang untuk kode buatan AI. |
| K-5 | 3 Nov 2026 | Narasi memakai **suara yang sudah ada** (Piper, Edge). ElevenLabs atau yang lain menyusul sebagai mesin suara tambahan. | Pemilik sedang mencari layanannya. |
| K-6 | 3 Nov 2026 | Animasi AI berbentuk **komponen Remotion dengan skema properti**. Studio membuat panel pengaturannya otomatis. | Koreksi tanpa menyentuh kode. |
| K-7 | 3 Nov 2026 | Animasi memakai **fungsi bawaan Remotion** (`interpolate`, `spring`), **bukan GSAP**. | Lisensi GSAP melarang pemakaian di alat pembuat animasi visual yang menyaingi Webflow. |
| K-8 | 3 Nov 2026 | **AI mengusulkan, orang memutuskan.** Semua buatan AI tampil sebagai item biasa bertanda AI beserta alasannya, dan bisa diubah atau dihapus. | Prinsip yang sama dengan `sutradara.py` dan `sutradara_ai.py`. |
| K-9 | 3 Nov 2026 | Mesin render (Node, Remotion, Chrome headless) **diunduh saat Montase pertama dipakai**, bukan dibundel. | Ukuran aplikasi tidak membengkak. Pola yang sama dengan Deno di `alat_yt.py`. |
| K-10 | 3 Nov 2026 | Usaha OmniClip saat ini **perorangan / paling banyak 3 orang**, jadi Remotion dipakai dengan lisensi gratis. | Jawaban pemilik. Diperiksa ulang bila usaha bertambah orang (R-9). |
| K-11 | 3 Nov 2026 | Tempat uji: **Linux mode pengembangan, Linux aplikasi build, Windows aplikasi build**. Tidak ada Windows mode pengembangan. | Jawaban pemilik. Uji Windows (M0.7) lewat build CI yang dipicu manual (`workflow_dispatch`). |
| K-12 | 3 Nov 2026 | Urutan AI untuk Montase: **Claude → Gemini → OpenRouter → AI lokal**, dan pengguna bisa memilih sendiri mana yang dipakai. | Jawaban pemilik. `koneksi_ai.py` sudah punya daftar berurutan yang bisa diatur pengguna; Montase menambah pilihan "AI untuk Montase". |
| K-13 | 3 Nov 2026 | Langganan Claude Pro **tidak bisa** disambungkan ke OmniClip sebagai pengganti API key. Claude di dalam aplikasi lewat **API key** (bayar per pemakaian, terpisah dari Pro), ditambah **mode salin-tempel** (M4.10) yang memakai Claude.ai biasa. | Pro dan API adalah produk terpisah. Untuk produk yang dibagikan ke orang lain, jalur yang aman menurut sumber yang ada adalah API key, bukan login langganan. |
| K-14 | 3 Nov 2026 | Penggabungan: **PR dokumen sekarang**, lalu **satu PR per tahap** sesudah gerbangnya lolos. | Jawaban pemilik. Dokumen langsung terbaca dari branch utama. |
| K-15 | 3 Nov 2026 | Pemilik **tidak punya API key Anthropic**, hanya Claude Pro. Jalur Claude utama di aplikasi = **mode salin-tempel lewat Project Claude.ai** (M4.10). Jalur API (M4.3) tetap dibangun untuk pengguna yang punya kunci. Animasi bawaan (M4.2) ditulis saat pengembangan lewat Claude Code. | Jawaban pemilik atas T-7. |
| K-16 | 3 Nov 2026 | Mengubah K-9: **paket mesin dan bundel komposisi ikut di dalam aplikasi**; yang diunduh saat pertama dipakai hanya **Node** dan **Chrome Headless Shell**. | Build uji dari `workflow_dispatch` tidak punya rilis untuk diunduhi, dan dengan begitu versi mesin selalu sama dengan versi komposisinya. Biayanya ±24 MB terkompresi di unduhan aplikasi. |
| K-17 | 3 Nov 2026 | Pemilik **tidak bisa menguji sekarang** dan akan menguji semuanya sekaligus di akhir. Gerbang tiap tahap diganti: (1) tes otomatis + uji CI di Windows dan Linux sungguhan, (2) tangkapan layar dan cuplikan video dari Claude, dikirim ke pemilik di setiap tahap. Tes UJI-LANGSUNG.md tetap ditulis per tahap untuk uji akhir. **T-5 memakai angka usulan:** render paling lama 4x durasi. | Jawaban pemilik: "lanjutkan saja pengerjaannya, nanti saya tes semua sekaligus". |

### Masih terbuka (pemilik yang memutuskan)

| No | Pertanyaan | Saran | Perlu diputuskan sebelum |
|---|---|---|---|
| T-1 | Nama menu: "Montase" atau lainnya? | Montase (id) / Montage (en) | M1.4 |
| T-2 | Ekspor 60 fps tersedia? | Ya, sebagai pilihan. Bawaan 30 fps. | M1.9 |
| T-3 | Apakah video Montase yang memakai video orang lain wajib bernarasi sebelum boleh diunggah publik? | Ya, ikut gerbang tinjau (`gerbang.py`) dan nilai tambah. Narasi dihitung seperti komentar. | M6.1 |
| T-4 | Layanan suara AI tambahan: ElevenLabs atau lainnya? | Menunggu pemilik | MS.1 |
| ~~T-5~~ | ~~Ambang kecepatan render~~ Dipakai angka usulan: paling lama 4x durasi (K-17). Terukur 2,3-2,9x. | | |
| T-6 | Montase bisa dipakai di HP? | Tidak di rilis pertama. Di HP hanya daftar proyek dan ekspor. | M1.7 |
| ~~T-7~~ | ~~Apakah pemilik membuat API key Claude?~~ Dijawab 3 Nov 2026: tidak, hanya Claude Pro. Lihat K-15. | | |

**Catatan lisensi Remotion:** gratis, termasuk untuk komersial, bagi perorangan
atau usaha dengan paling banyak 3 karyawan. Kalau usaha OmniClip melewati itu,
perlu lisensi perusahaan dari remotion.pro. Karena proyek disimpan sebagai JSON
milik OmniClip sendiri ([bagian 16](#16-dokumen-proyek)), mesin render masih
bisa diganti tanpa membuang proyek yang sudah dibuat.

## 4. Gambaran cara kerja

**Singkatnya:** proyek disimpan sebagai *resep* (JSON). Pratinjau dan render
membaca resep yang sama dengan kode yang sama, jadi yang terlihat saat
menyunting sama dengan hasil MP4-nya.

```
┌──────────────────────────── Peramban (antarmuka OmniClip) ─────────────────────────────┐
│  /montase/:id                                                                           │
│  ┌───────────┐  ┌──────────────────────────────┐  ┌──────────────────┐                  │
│  │ Bahan     │  │ Pratinjau                    │  │ Panel properti   │                  │
│  │ (video,   │  │ Remotion Player di dalam     │  │ (dibuat otomatis │                  │
│  │ musik,    │  │ iframe kotak pasir           │  │ dari skema)      │                  │
│  │ gambar,   │  └──────────────────────────────┘  └──────────────────┘                  │
│  │ animasi)  │  ┌─────────────────────────────────────────────────────┐ ┌────────────┐  │
│  └───────────┘  │ Linimasa banyak lajur: Video · Teks · Motion · Audio│ │ Chat AI    │  │
│                 └─────────────────────────────────────────────────────┘ └────────────┘  │
└──────────────────────────────────────────┬──────────────────────────────────────────────┘
                                           │ /api/montase/*
┌──────────────────────────── Server OmniClip (Python, FastAPI) ─────────────────────────┐
│  backend/app/montase/   proyek · bahan · AI animasi · asisten · render                   │
│  Layanan bersama yang dipakai: koneksi_ai, tts, aset, stok, whisper, momen, jobs, unggah │
└──────────────────────────────────────────┬──────────────────────────────────────────────┘
                                           │ menjalankan sebagai proses anak
┌──────────────────────────── Mesin Montase (Node 22, diunduh sekali) ───────────────────┐
│  kompilasi kode animasi AI · periksa (render bingkai contoh) · render MP4               │
│  @remotion/renderer + Chrome Headless Shell                                              │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

**Perjalanan satu video, dari awal sampai unggah:**

1. Buat proyek baru dan pilih format (misalnya Shorts 1080x1920, 30 fps).
2. Masukkan bahan: Klip jadi, unduhan, berkas sendiri, musik dari pustaka aset.
3. Susun di linimasa: potong, belah, atur urutan, beri teks dan transisi.
4. Minta AI membuat animasi, misalnya kartu "#5". Koreksi lewat panel properti.
5. Tambah narasi: ketik teks, pilih suara, dan narasi jadi item audio.
6. Ekspor. Mesin Montase merender MP4, hasilnya masuk **Klip jadi**.
7. Unggah dari Klip jadi seperti klip biasa, lewat gerbang tinjau yang sama.

**Tujuh prinsip yang tidak boleh dilanggar:**

| No | Prinsip | Artinya |
|---|---|---|
| P-1 | Satu resep | Dokumen proyek JSON adalah satu-satunya sumber kebenaran. Tidak ada keadaan tersembunyi di tempat lain. |
| P-2 | Pratinjau = hasil | Pratinjau dan render memakai komponen komposisi yang sama persis (`features/montase/komposisi/`). |
| P-3 | AI mengusulkan | Semua buatan AI terlihat, bertanda, beralasan, dan bisa dihapus (K-8). |
| P-4 | Batas modul | Montase tidak menyentuh isi Studio Klip ([bagian 15](#15-batas-modul)). |
| P-5 | Gagal dengan anggun | Kalau mesin Montase tidak ada atau rusak, menu Montase menjelaskan sebabnya dan bagian OmniClip lainnya tetap berjalan. |
| P-6 | Dua bahasa | Semua teks antarmuka lewat `t()` dengan kunci `montase.*` di `id.js` dan `en.js`. |
| P-7 | Klien menyebut id, bukan jalur | Peramban tidak pernah mengirim jalur berkas, hanya id bahan (aturan yang sama dengan `aset.py`). |

---

# BAGIAN B: RENCANA KERJA

## 5. Aturan main pengerjaan

**Cara mencentang tugas:**

```
- [x] **M1.3** Judul tugas (selesai 12 Nov 2026, commit abc1234)
  Catatan singkat: apa yang berbeda dari rencana, angka yang terukur.
```

`commit` adalah hash commit kodenya. Centangan boleh ikut commit yang sama atau
commit berikutnya.

**Aturan:**

1. **Jangan melompati gerbang tahap.** Setiap tahap punya bagian *Selesai bila*.
   Tahap berikutnya baru dimulai sesudah gerbangnya lolos dan dicatat.
2. **Tahap 0 menentukan semuanya.** Kalau hasilnya buruk, rencana diubah dulu
   (lihat *Rencana B* di Tahap 0) sebelum menulis Tahap 1.
3. **Setiap tugas disertai tes.** Backend: `backend/tests/test_montase_*.py`
   (unittest). Frontend: `*.test.js` (vitest) di samping kodenya.
4. **Sebelum push, jalankan pemeriksaan:**
   ```bash
   cd backend && python -m unittest discover tests
   ```
   ```bash
   cd frontend && npm test && npm run lint && npm run build
   ```
5. **Setiap tahap ditutup dengan bukti, bukan janji** (K-17): tes otomatis
   lolos, uji CI Windows/Linux lolos bila mesin atau build tersentuh, dan
   tangkapan layar/cuplikan video dikirim ke pemilik. Tes bernomor untuk uji
   akhir pemilik tetap ditambahkan di `UJI-LANGSUNG.md` (bagian "Montase").
6. **Keputusan baru masuk tabel [Keputusan](#3-keputusan)**, bukan hanya chat.
7. **Satu PR ke `main` per tahap** (K-14). Kerja harian di branch kerja; PR
   dibuka dan digabung sesudah gerbang tahap lolos (aturan 5).
8. **Perubahan rencana ditulis di sini juga.** Coret tugas yang dibatalkan
   (`~~M3.8~~`) beserta alasannya. Jangan dihapus diam-diam.
9. **Gaya kode mengikuti repo:** nama Indonesia, docstring menjelaskan *kenapa*
   (bukan hanya *apa*), dan angka hasil ukur ditulis di komentar.

---

## Tahap 0: Uji teknis

**Tujuan:** membuktikan bagian yang paling berisiko **sebelum** membangun
apa pun. Hasilnya berupa angka, ditulis di [bagian 24](#24-hasil-uji-teknis).

**Kenapa perlu:** belum pernah ada Node maupun Chrome headless yang berjalan di
dalam OmniClip, dan Windows belum pernah diuji sungguhan (CATATAN.md 1.4).
Kalau salah satunya gagal, lebih baik ketahuan di sini daripada sesudah dua
bulan bekerja.

- [x] **M0.1** Pasang `remotion`, `@remotion/player`, dan `@remotion/media` di
  `frontend/` dengan **versi persis yang sama** untuk semua paket `@remotion/*`
  (aturan Remotion). Buat rute uji `/montase-uji` (dimuat lambat dengan
  `React.lazy`). Isinya satu komposisi berisi satu video, satu teks, dan satu
  animasi, diputar di Player. Periksa kecocokan dengan React 19 yang dipakai
  frontend.
  (selesai 3 Nov 2026, commit 8ffab2c) Remotion 4.0.537 berjalan di React 19.2.8 tanpa galat
  konsol. Bagian Remotion dipecah ke potongan terpisah (±330 KB gzip) yang hanya
  dimuat di halaman Montase. Komposisi sudah memakai format dokumen bagian 16
  (lajur video, teks, motion, audio).
- [x] **M0.2** Buat folder `montase-mesin/` (paket Node) berisi skrip `render.mjs`
  yang merender komposisi M0.1 ke MP4 lewat `@remotion/bundler` dan
  `@remotion/renderer`. Ukur di mesin pemilik untuk 30 detik video 1080x1920
  30 fps: lama render, RAM puncak, dan ukuran berkas.
  (selesai 3 Nov 2026, commit 8ffab2c) Diukur di container pengembangan 4 inti (bukan mesin
  pemilik, itu tes 62): 87-89 detik, RAM puncak ±2,4 GB, 40 MB. Bundel tanpa
  source map 16 MB. Render memegang `giliran_cpu` seperti render klip.
- [x] **M0.3** `backend/app/montase/mesin.py`: Python menjalankan mesin sebagai
  proses anak, membaca kemajuan (JSON per baris di stdout), dan bisa
  membatalkannya. Pakai pembantu `services/proses.py` supaya jendela konsol
  tidak muncul di Windows.
  (selesai 3 Nov 2026, commit 8ffab2c) Grup proses sendiri (Linux) / `taskkill /T` (Windows),
  batas waktu, ekor stderr di pesan galat, izin eksekusi berkas biner Remotion
  dipulihkan bila hilang. Tes `test_montase_mesin.py`.
- [x] **M0.4** Unduh saat pertama dipakai: Node 22 LTS portabel, paket mesin, dan
  Chrome Headless Shell (`ensureBrowser()` Remotion) masuk ke
  `STORAGE_DIR/mesin_montase/`. Versi dan SHA-256 dipatok, polanya sama dengan
  `alat_yt.py`. Ukur total ukuran unduhannya.
  (selesai 3 Nov 2026, commit 8ffab2c) Diubah oleh K-16: paket mesin ikut di aplikasi, yang
  diunduh hanya Node (`montase/unduh.py`, terbukti: 31 MB, 3-5 detik, 126 MB
  sesudah npm dibuang) dan Chrome (`siapkan.mjs`). Unduhan Chrome tidak bisa
  dibuktikan di container (jaringan memblokir `remotion.media` dan
  `storage.googleapis.com`); dibuktikan oleh langkah CI M0.7 dan tes 60.
- [x] **M0.5** Satu animasi buatan AI: komponen sesuai
  [kontrak](#21-kontrak-komponen-animasi-ai) ditulis Claude (lewat Claude Code,
  karena belum ada API key, K-15), dikompilasi dengan `sucrase`, diperiksa,
  lalu diputar di Player **dan** dirender di mesin. Bingkainya harus sama. Jalur
  memanggil AI dari dalam aplikasi baru dibangun di Tahap 4.
  (selesai 3 Nov 2026, commit 8ffab2c) `montase-mesin/uji/komponen_ai.jsx` ("GILA!" lalu pecah)
  lolos pemeriksaan; kode berisi `fetch`, `window`, `Date`, `constructor`,
  `Math.random`, `import()` ditolak dengan alasan per baris. Pratinjau kotak
  pasir dan render sama secara kasat mata di bingkai 15, 90, 240, 270, termasuk
  letak serpihan acak (`random(seed)`).
- [x] **M0.6** Kotak pasir: Player berjalan di iframe
  `sandbox="allow-scripts"` (tanpa `allow-same-origin`), dikendalikan lewat
  `postMessage`, dan tetap bisa memutar video dari backend (perlu CORS dan
  token, lihat [bagian 20](#20-pratinjau-dan-kotak-pasir)).
  (selesai 3 Nov 2026, commit 8ffab2c) Diuji dengan Playwright: asal iframe `null`; membaca
  DOM editor, cookie, dan localStorage dari dalamnya ditolak; video bertoken
  dimuat dengan Range + CORS; putar, jeda, dan geser dari tombol di luar
  iframe bekerja. Token palsu dan nama berkas di luar daftar menjawab 404.
- [x] **M0.7** Ulangi M0.2 sampai M0.6 di **Windows** lewat aplikasi hasil build
  (K-11: tidak ada Windows mode pengembangan). Karena itu `bangun-aplikasi.yml`
  harus lebih dulu ikut membangun paket mesin dan bundel komposisi. Build
  dipicu manual (`workflow_dispatch`) dari branch kerja, lalu pemilik
  mengunduh artefaknya dan menjalankannya. Ulangi juga di Linux aplikasi build.
  (selesai 3 Nov 2026, commit 8ffab2c, f65f820, 1ab124a) Langkah CI
  `OmniClip --periksa-montase` mengunduh Node dan Chrome lalu merender 10 detik
  di aplikasi terbungkus. Build pertama (run 41610381956) menemukan bug: Chrome
  terunduh ke FOLDER APLIKASI (`_internal/montase_mesin/node_modules/.remotion`)
  dan ikut terkemas, arsip naik 130-151 MB. Diperbaiki: CWD mesin =
  `<data>/mesin_montase/kerja` (`mesin.folder_kerja`), `uji_lengkap` gagal bila
  Chrome di luar folder data, dan langkah uji dipindah sesudah "Kemas". Run
  41612685962: Linux dan Windows lolos, Chrome di folder data, arsip Linux 371 MB
  (+25 MB dari v1.3.9), Windows 298 MB (+28 MB). Bagian "pemilik menjalankan
  artefaknya" dipindah ke uji akhir (K-17).
- [x] **M0.8** Tulis semua angka ke [bagian 24](#24-hasil-uji-teknis), lalu
  pemilik memutuskan T-5.
  (selesai 3 Nov 2026) Angka container dan CI ada di bagian 24. Pemilik tidak
  bisa menguji sekarang dan meminta pengerjaan dilanjutkan (K-17); T-5 memakai
  angka usulan (paling lama 4x durasi), dan semua render terukur 2,3-2,9x.

**Selesai bila:** M0.1 sampai M0.7 berhasil di Linux dan Windows, dan render 60
detik video lolos ambang T-5.

**Rencana B, bila render terlalu lambat:** Remotion hanya merender lapisan
teks dan animasi sebagai video transparan (ProRes 4444 atau urutan PNG). Lapisan
video dasar disusun ffmpeg OmniClip dari dokumen proyek yang sama, memakai
encoder GPU yang sudah ada. Harganya ada dua jalur render, jadi perlu tes
pembanding bingkai pratinjau lawan hasil. Rencana B baru dipakai kalau
angkanya memaksa.

---

## Tahap 1: Kerangka

**Tujuan:** bisa membuat proyek, memasukkan bahan, menaruhnya berurutan,
menyimpan, membuka lagi, dan mengekspor. Linimasanya masih sederhana.

- [x] **M1.1** Migrasi basis data: tabel `montase_proyek`, `montase_bahan`,
  `montase_komponen` ([bagian 17](#17-basis-data)) ditambahkan ke `MIGRATIONS`
  di `db.py`. Repo `backend/app/repos/montase.py`.
  (selesai 3 Nov 2026, commit 5ac34ee, d8803d5) Migrasi 13. Bedanya dengan rancangan: tanpa FK ke `profil` (sama dengan tabel lain yang memakai `profil_id`), `montase_bahan` punya kolom `nama` dan `siap`, dan salinan sunting tidak punya kolom; letaknya tetap `<data>/montase/bahan/<id>/sunting.mp4`.
- [x] **M1.2** `montase/skema.py`: validasi dokumen proyek (pydantic), nomor
  `versi`, dan fungsi migrasi dokumen. Migrasi hanya di backend; frontend selalu
  menerima versi terbaru.
  (selesai 3 Nov 2026, commit 5ac34ee, d8803d5) `montase/skema.py`: kolom tak dikenal dipertahankan (`extra="allow"`), versi lebih baru ditolak, `durasi` dihitung ulang dari ujung item terakhir, item hanya di lajur yang cocok, ukuran genap, fps 24/25/30/50/60, batas 2 MB dan 2000 item.
- [x] **M1.3** `montase/router.py`: buat, baca, simpan, hapus, dan gandakan
  proyek. Simpan memakai nomor `revisi`, jadi dua tab yang menyimpan bersamaan
  mendapat 409, bukan saling menimpa diam-diam. Semua per profil
  (`profil.kini()`).
  (selesai 3 Nov 2026, commit 5ac34ee, d8803d5) Revisi basi menjawab 409 `REVISI_BENTROK`; bahan dari profil lain ditolak saat simpan. Tes `test_montase_proyek.py`.
- [x] **M1.4** Menu: item "Montase" (ikon `Clapperboard`) di kelompok Studio
  `NAV_STUDIO`, sesudah Partitur. Rute `/montase` dan `/montase/:id`. Bilah
  menu menutup sendiri di editor (perluas `isEditorPath` di `App.jsx`). Sakelar
  "Montase (beta)" di Pengaturan. Kunci kamus `montase.*` di `id.js` dan
  `en.js`.
  (selesai 3 Nov 2026, commit 5ac34ee, d8803d5) Ikon `Clapperboard`, sakelar di Pengaturan > Tampilan (bawaan menyala), `/montase-uji` tetap ada untuk memeriksa mesin.
- [x] **M1.5** Daftar proyek (`MontaseHome.jsx`): kartu dengan sampul, nama,
  durasi, dan waktu diubah. "Proyek baru" dengan preset kanvas:

  | Preset | Ukuran | Untuk |
  |---|---|---|
  | Shorts / TikTok / Reels | 1080x1920 | Vertikal |
  | YouTube | 1920x1080 | Horizontal |
  | Persegi | 1080x1080 | Feed |
  | Potret | 1080x1350 | Instagram 4:5 |
  | Sendiri | bebas | |

  Pilihan fps: 24, 25, 30, 60 (60 tergantung T-2).
  (selesai 3 Nov 2026, commit 5ac34ee, d8803d5) Hapus meminta konfirmasi; bahan dan video yang sudah diekspor tidak ikut terhapus.
- [x] **M1.6** Panel bahan: impor berkas (pakai `apiUnggah`), ambil dari
  Unduhan, Klip jadi, Aset (musik, efek suara, gambar), dan Stok Pexels.
  Metadata dibaca ffprobe. Sampul, strip gambar (*filmstrip*), dan gelombang
  suara dibuat di latar.
  (selesai 3 Nov 2026, commit 5ac34ee, d8803d5) Impor masuk pustaka aset (terlihat juga di Studio Klip). Sampul, strip, dan gelombang disajikan lewat alamat BERTOKEN: `<img>` tidak membawa header profil, jadi lewat sesi bahan profil selain Utama tidak terbaca. Strip baru diminta sesudah bahan siap (404 awal disimpan peramban). Stok Pexels masuk lewat pustaka aset, belum ada tab sendiri.
- [x] **M1.7** Tata letak editor dengan empat area yang ukurannya bisa diatur:
  bahan (kiri), pratinjau (tengah), properti (kanan), linimasa (bawah). Di
  layar < 900 px tampil pemberitahuan "Montase butuh layar lebar" (T-6).
  (selesai 3 Nov 2026, commit 5ac34ee, d8803d5) Ukuran area disimpan per peramban. Linimasa Tahap 1: lajur, item sebanding waktu, strip, gelombang, garis putar, klik penggaris, tukar urutan, hapus. Simpan otomatis sudah ada di sini (M2.8 tinggal pemberitahuan).
- [x] **M1.8** Pratinjau: Player di kotak pasir, dengan putar/jeda, geser,
  maju/mundur satu bingkai, layar penuh, dan garis zona aman (tombol
  TikTok/Shorts) yang bisa dinyalakan. Memakai salinan sunting kecil
  ([bagian 20](#20-pratinjau-dan-kotak-pasir)).
  (selesai 3 Nov 2026, commit 5ac34ee, d8803d5) Zona aman vertikal: kiri 6%, kanan 16%, atas 10%, bawah 22% (`pratinjau/zonaAman.js`).
- [x] **M1.9** Ekspor: pekerjaan `montase_render` di antrean `jobs.py`, kemajuan
  tampil di `JobProgress`, bisa dibatalkan. Hasilnya masuk Klip jadi
  ([bagian 22](#22-hasil-ekspor-dan-klip-jadi)).
  (selesai 3 Nov 2026, commit 5ac34ee, d8803d5) Pekerjaan `montase_render`, nama berkas `<judul>_montase_<tanggal>.mp4`, sidecar `jenis: montase` dengan `sumber_banyak`. Klip jadi menampilkannya seperti klip biasa (nilai tambah 0%: dihitung di M6.2). Tes ekspor sungguhan: tiga video berwarna, 90 bingkai, warnanya tepat per potongan.
- [x] **M1.10** Tes penjaga batas modul `test_montase_batas.py`
  ([bagian 15](#15-batas-modul)).
  (selesai 3 Nov 2026, commit 5ac34ee, d8803d5) `test_montase_batas.py` kini mencakup semua berkas Tahap 1 (backend dan frontend).

**Selesai bila:** pemilik bisa membuat proyek, menaruh tiga video berurutan,
menutup aplikasi, membukanya lagi, dan mengekspor MP4 yang isinya sama dengan
pratinjau.

**Gerbang lolos 3 Nov 2026 (K-17):** dijalankan di Chromium lewat Playwright:
proyek baru, tiga video diimpor berurutan, teks dan animasi, muat ulang (lima
item kembali utuh), ekspor 270 bingkai, tampil di Klip jadi. Bingkai pratinjau
editor dan MP4 sama di bingkai 15, 45, 105, 225. Tangkapan layar dikirim ke
pemilik. Tes 64-67 di UJI-LANGSUNG.md untuk uji akhir.

---

## Tahap 2: Penyuntingan dasar

**Tujuan:** linimasa yang terasa seperti CapCut.

- [x] **M2.1** `features/montase/model/`: semua operasi penyuntingan sebagai
  **fungsi murni** (masuk dokumen, keluar dokumen baru), dengan tes vitest.
  Batal/ulang menyimpan sampai 100 langkah. Operasi yang sama dipakai tangan
  manusia **dan** AI (Tahap 5).
  (selesai 3 Nov 2026, commit be61ef3) `model/suntingan.js` (belah, pangkas, pindah, sisip, hapus beriak, rapatkan, salin/tempel/gandakan, bekukan, kecepatan, transformasi, lajur, penanda, magnet) dan `model/riwayat.js`. Ketikan beruntun digabung dalam 0,9 detik; satu seretan selalu satu langkah (`gabung` unik, jendela tak terbatas), dan seretan yang kembali ke awal tidak meninggalkan langkah kosong. Riwayat di ref dan state: ref kebenarannya, jadi dua operasi dalam satu peristiwa tidak saling menimpa.
- [x] **M2.2** Banyak lajur: video/gambar, teks, motion, audio. Urutan tumpuk
  mengikuti urutan lajur. Setiap lajur bisa dikunci, dibisukan, disembunyikan,
  dan diganti namanya.
  (selesai 3 Nov 2026, commit be61ef3) Lajur baru disisipkan sesudah lajur terakhir sejenisnya (video kedua tergambar di atas yang pertama). Lajur hanya bisa dihapus bila kosong dan bukan satu-satunya dari jenisnya. Item di lajur terkunci tidak bisa diubah oleh fungsi model mana pun, bukan hanya disembunyikan tombolnya.
- [x] **M2.3** Operasi item: seret (antar waktu dan antar lajur), pangkas
  kiri/kanan, belah di garis putar, hapus, hapus beriak, salin/tempel,
  gandakan, pilih banyak (Shift dan kotak seret).
  (selesai 3 Nov 2026, commit be61ef3) Tambahan di luar rencana: satu item yang dilepas di atas item lain DISISIPKAN di situ dan sisanya bergeser (`titikSisip`, `sisipkan`), karena tanpa itu menyusun ulang Top 5 berarti menumpuk klip. Bahan bisa diseret dari panel Bahan ke lajur dan bingkai tertentu. Tombol "rapatkan celah" untuk celah sesudah ubah kecepatan.
- [x] **M2.4** Magnet ke garis putar, tepi item, dan penanda (ambang 8 piksel,
  bisa dimatikan). Penanda bernama. Perbesar/perkecil linimasa. Daftar
  pintasan:

  | Tombol | Aksi |
  |---|---|
  | Spasi | Putar / jeda |
  | ← / → | Mundur / maju 1 bingkai |
  | Shift + ← / → | Mundur / maju 1 detik |
  | Ctrl + B | Belah di garis putar |
  | Delete | Hapus |
  | Shift + Delete | Hapus beriak |
  | Ctrl + Z / Ctrl + Shift + Z | Batal / ulang |
  | Ctrl + C / V / D | Salin / tempel / gandakan |
  | M | Tambah penanda |
  | N | Magnet nyala/mati |
  | + / − | Perbesar / perkecil linimasa |
  | Home / End | Ke awal / akhir |

  (selesai 3 Nov 2026, commit be61ef3) Semua pintasan di tabel, ditambah Ctrl+A, Ctrl+X, Ctrl+Y, Esc. Tombol yang ditekan saat fokus di dalam iframe pratinjau diteruskan lewat jembatan (`tombol`), jadi pintasan tetap jalan sesudah pratinjau diklik. Esc di kotak isian keluar dari kotak itu. Perbesar berjangkar di garis putar (tombol, + / −) atau di penunjuk (Ctrl+gulir).
- [x] **M2.5** Transformasi: posisi, ukuran, putar, transparansi, potong
  (*crop*), dengan pegangan yang bisa diseret langsung di pratinjau. Pegangan
  digambar di **luar** iframe dan menerjemahkan koordinat ke kanvas.
  (selesai 3 Nov 2026, commit be61ef3) `komposisi/kotak.js` menentukan kotak dasar item (video "muat" = persegi sesuai rasio bahannya), jadi potong dalam persen gambar. Pegangan memakai `setPointerCapture`: tanpa itu gerakan di atas iframe hilang dan seretan berhenti di tengah. Kotak teks hanya perkiraan (0,56 em per huruf) sampai M3.1.
- [x] **M2.6** Kecepatan 0,25x sampai 4x (nada suara dipertahankan dengan
  `preservePitch`). Bekukan bingkai.
  (selesai 3 Nov 2026, commit be61ef3) Mengubah kecepatan menjaga potongan bahan (10 detik bahan di 2x = 5 detik linimasa). Bekukan bingkai = belah + item `beku` 3 detik dengan `<Freeze>`, yang sesudahnya bergeser; dicek sama di render.
- [x] **M2.7** Volume per item dan per lajur, lembut masuk/keluar
  (*fade*), gelombang suara di item audio dan video.
  (selesai 3 Nov 2026, commit be61ef3) Fade berupa pengali volume linear (`pengaliFade`), dipendekkan sebanding bila masuk + keluar melebihi item. Gelombang satu jalur SVG per item, paling banyak satu titik per dua piksel.
- [x] **M2.8** Simpan otomatis 1,5 detik sesudah perubahan terakhir, dan
  pemberitahuan bila penyimpanan gagal.
  (selesai 3 Nov 2026, commit be61ef3) Gagal simpan: pemberitahuan dengan tombol "Coba sekarang" dan dicoba lagi sendiri tiap 5 detik (diuji dengan server yang menolak: pulih 4,8 detik setelah server kembali).

**Selesai bila:** pemilik bisa membuat video "Top 5" sederhana secara manual,
tanpa AI, dalam kurang dari 10 menit, dan tidak ada operasi yang terasa
tersendat pada proyek 5 menit berisi 50 item.

**Gerbang lolos 3 Nov 2026 (K-17):** skrip Playwright membuat Top 5 lewat
antarmuka sungguhan: impor lima klip, susun ulang jadi 5-4-3-2-1 dengan
seret-sisip, batal/ulang, belah + hapus beriak, pangkas tepi, lima penanda
bernama dan judul teks, lajur video kedua dengan bahan diseret dari panel,
pegangan skala/geser/putar/potong, kunci/bisu/sembunyi/ganti nama lajur,
kecepatan 2x, beku 3 detik, fade, pilih kotak + salin/tempel + batal, muat
ulang, ekspor. 15 pemeriksaan lolos, tanpa galat konsol, 96 detik termasuk
ekspor. MP4 sama dengan pratinjau di 6 bingkai (SSIM 0,92-0,96). Proyek 5
menit 50 item: 60 fps (p95 16,7 ms) saat seret, pangkas, pilih kotak,
pintasan, dan pemutaran; nol *long task*. Tangkapan layar dikirim ke pemilik.
Tes 69-75 di UJI-LANGSUNG.md untuk uji akhir.

---

## Tahap 3: Teks, suara, dan efek

**Tujuan:** semua bahan sebuah video jadi bisa dibuat di Montase.

- [x] **M3.1** Item teks: font bawaan (`app/assets/fonts`, semuanya OFL), warna,
  garis tepi, bayangan, pelat latar, perataan. Gaya siap pakai diambil dari
  `tema_judul.py` (diterjemahkan ke komponen komposisi). Font dimuat dengan
  `delayRender` supaya bingkai pertama tidak memakai font cadangan.
  (selesai 3 Nov 2026, commit 35f5daf) Tema TIDAK disalin ke komposisi: `GET /api/montase/gaya-teks` menerjemahkan `tema_judul.TEMA` ke `item.gaya`, dan memilih tema menulis nilainya ke dokumen. Font didaftarkan dengan FontFace tanpa ketebalan dan teks memintanya 400, karena meminta 800 membuat peramban memalsukan tebal. CSP bundel mesin perlu `font-src` OmniClip (sebelumnya hanya 'self'). Diuji: sepuluh tema, pratinjau = ekspor di 10 bingkai (SSIM 0,87-0,93 pada tangkapan 232 px).
- [x] **M3.2** Subtitle otomatis: suara di linimasa ditranskrip dengan
  `whisper.py` (atau memakai transkrip yang sudah ada kalau bahannya dari
  unduhan atau Klip jadi). Waktu per kata menjadi lajur subtitle yang bisa
  disunting, dengan gaya sorot kata seperti Studio Klip.
  (selesai 3 Nov 2026, commit 9496abb) Kata per bahan disimpan di `kata.json` (sekali per bahan, dipakai ulang di setiap potongan). Ucapan dua sumber yang bertumpuk tidak diselang-seling: lajur audio menang, lalu lajur video terbawah. Belum diuji dengan Whisper sungguhan (HuggingFace ditolak proxy container); diuji dengan simpanan kata, jadi tes 77 di UJI-LANGSUNG.md wajib dijalankan pemilik.
- [x] **M3.3** Narasi: ketik teks, pilih suara dari katalog `tts.py`, dan hasilnya
  jadi item audio. Mengubah teksnya membuat ulang suaranya. Rekam suara sendiri
  lewat mikrofon (MediaRecorder) juga menjadi item audio.
  (selesai 3 Nov 2026, commit ff852c8) Teks yang diubah TIDAK membuat ulang suara per ketukan: tombol "Buat ulang suara" menyala dan mengganti bahan item sekali (item tetap di tempatnya). Narasi dan rekaman masuk lajur audio yang kosong di rentang itu, atau lajur audio baru. Rekaman WebM diubah ke M4A di server. Belum diuji dengan suara sungguhan (container tanpa akses suara Microsoft/unduhan Piper): tes 78 di UJI-LANGSUNG.md.
- [x] **M3.4** Musik latar dengan perendam otomatis (*ducking*): volume musik
  turun saat ada narasi atau ucapan. Hasilnya berupa keyframe volume biasa,
  jadi terlihat dan bisa diubah.
  (selesai 3 Nov 2026, commit d7db00b) Ucapan = item lajur subtitle dan item audio di lajur audio lain (narasi, rekaman); suara klip tanpa subtitle tidak dihitung, karena tanpa tahu di mana orang berbicara perendaman jadi musik yang pelan sepanjang video. Terukur di ekspor: musik -27,2 dB, -39,3 dB saat narasi (turun ke 20%), -27,1 dB sesudahnya.
- [ ] **M3.5** Transisi antar item di lajur yang sama: potong, larut, geser,
  usap, perbesar, kilat, glitch (pakai `@remotion/transitions`).
- [ ] **M3.6** Penyesuaian warna: kecerahan, kontras, saturasi, suhu, plus
  preset bernama sama dengan `VIDEO_FILTERS` di `render.py`.
- [x] **M3.7** Keyframe untuk posisi, ukuran, putar, transparansi, dan volume,
  dengan kurva (linear, masuk, keluar, masuk-keluar, pegas). Penanda keyframe
  berbentuk wajik di item linimasa.
  (selesai 3 Nov 2026, commit d7db00b) `t` keyframe relatif ke awal item; `kurva` adalah cara menuju keyframe itu. Sifat berkeyframe mengabaikan nilai dasarnya, dan mengubah nilainya (panel atau pegangan) menulis keyframe di garis putar. Keyframe sebelum 0 sesudah belah/pangkas tidak dibuang supaya gerak bersambung. Pratinjau = ekspor (SSIM 0,92-0,94).
- [ ] **M3.8** Efek bawaan: punch-in (zoom sekejap), guncang, Ken Burns untuk
  gambar diam, stiker/emoji, bilah progres.
- [ ] **M3.9** Penyamaan kekerasan suara saat ekspor: `loudnorm` dua lintasan
  dengan ffmpeg sesudah Remotion selesai (target −14 LUFS), video disalin tanpa
  dikode ulang (`-c:v copy`).
- [ ] **M3.10** Uji langsung pemilik: satu video Top 5 lengkap (teks, narasi,
  musik, transisi) dibuat manual dari awal sampai ekspor.

**Selesai bila:** M3.10 lolos dan hasilnya sama dengan pratinjau.

---

## Tahap 4: AI pembuat animasi

**Tujuan:** ketik permintaan, dapat animasi yang pas, koreksi tanpa kode.

**Alurnya dalam bahasa sederhana:**

```
Anda mengetik permintaan
      ↓
AI menulis komponen animasi + daftar properti yang boleh diubah
      ↓
Mesin memeriksa: bisa dikompilasi? aman? bergerak? sesuai permintaan?
      ↓  (gagal → AI diberi tahu galatnya, mencoba lagi paling banyak 2 kali)
Animasi muncul sebagai item di lajur Motion, bertanda AI
      ↓
Anda mengoreksi lewat panel properti, atau minta revisi lewat chat
      ↓
Yang disukai disimpan ke pustaka animasi, bisa dipakai di proyek lain
```

- [ ] **M4.1** Kontrak komponen ditulis sebagai kode dan dokumentasi
  ([bagian 21](#21-kontrak-komponen-animasi-ai)).
- [ ] **M4.2** Pustaka bawaan berisi 10 animasi yang ditulis tangan. Gunanya
  dua: siap dipakai, dan menjadi contoh bagi AI. Ditulis saat pengembangan dan
  ikut di dalam aplikasi, jadi memakainya tidak butuh koneksi AI sama sekali.

  | Animasi | Pemakaian |
  |---|---|
  | Hitung mundur peringkat | "#5 … #1" untuk konten Top N |
  | Judul kinetik | Kata muncul satu per satu mengikuti irama |
  | Label nama (*lower third*) | Nama dan peran penutur |
  | Ledakan emoji | Saat tawa |
  | Garis kejut | Saat kaget atau jumpscare |
  | Lingkaran + panah penunjuk | Menunjuk sesuatu di layar |
  | Kartu ajakan berlangganan | Penutup |
  | Bilah peringkat | Kemajuan 5 segmen di atas layar |
  | Angka menghitung naik | Statistik |
  | Transisi kilat | Antarmomen |

- [ ] **M4.3** `montase/motion_ai.py`: prompt sistem = panduan resmi Remotion
  untuk LLM + kontrak kita + contoh dari pustaka bawaan + konteks proyek (ukuran
  kanvas, durasi, palet, font tersedia, zona aman). Keluarannya satu blok kode
  dan satu blok JSON metadata. Model dipilih dari rantai `koneksi_ai` dengan
  urutan K-12 (Claude → Gemini → OpenRouter → lokal), dan pengguna bisa memilih
  koneksi tertentu lewat setelan "AI untuk Montase". Pemakaiannya dicatat di
  `pemakaian_ai`. Kalau koneksi yang tersedia hanya AI lokal, tampilkan
  peringatan bahwa model kecil jarang menulis kode animasi yang baik.

  Perkiraan biaya per animasi dengan API Claude (harga per 1 juta token,
  Oktober 2026), untuk ±15 ribu token masukan dan ±8 ribu token keluaran:

  | Model | Masukan / keluaran per 1 juta token | Kira-kira per animasi |
  |---|---|---|
  | Claude Opus 5.5 (`claude-opus-5-5`) | $4 / $20 | ±$0,22, turun ke ±$0,17 dengan prompt caching |
  | Claude Sonnet 5.5 (`claude-sonnet-5-5`) | $2 / $10 | ±$0,11 |

  Angka sebenarnya diukur di M4.9 dan ditulis di sana. Prompt sistem yang
  panjang dan tetap (panduan Remotion, kontrak, contoh) diletakkan di depan
  supaya bisa di-cache.
- [ ] **M4.4** `montase/periksa.py` beserta perintah `periksa` di mesin:
  1. kompilasi (sucrase);
  2. pemeriksaan statis: hanya impor yang diizinkan, tidak ada yang dilarang
     ([bagian 21](#21-kontrak-komponen-animasi-ai));
  3. render 5 bingkai contoh (`renderStill`) dengan `contohProps`;
  4. bingkai kosong, atau kelima bingkai sama persis, dianggap gagal karena
     animasinya tidak bergerak;
  5. bila koneksi AI bisa melihat gambar: bingkai contoh dinilai terhadap
     permintaannya.
- [ ] **M4.5** Panel properti otomatis dari skema zod:

  | Tipe skema | Kontrol |
  |---|---|
  | `z.string()` | Kotak teks |
  | `z.number().min().max()` | Penggeser |
  | `zColor()` | Pemilih warna |
  | `z.enum()` | Pilihan |
  | `z.boolean()` | Sakelar |
  | `z.object({x, y})` bertanda posisi | Titik yang bisa diseret di pratinjau |

- [ ] **M4.6** Revisi lewat chat: AI menerima kode yang sekarang + perintah, lalu
  menghasilkan versi baru (`komponen@versi+1`). Riwayat versi tersimpan, dan
  bisa kembali ke versi mana pun.
- [ ] **M4.7** Animasi yang **pas dengan video**. Kalau sebuah rentang atau item
  dipilih, AI menerima lembar fakta rentang itu:
  - kata-kata yang diucapkan beserta waktunya;
  - momen tawa, sorak, teriak, dan lonjakan suara (`momen.py`,
    `peristiwa_suara.py`);
  - letak wajah bila tersedia (`reframe.py`);
  - warna dominan bingkai dan zona aman.

  Animasi diletakkan di waktu bukti terdekat (paling jauh ±2 detik, seperti
  `TEMPEL_DETIK` di `sutradara_ai.py`). Posisi yang mengikuti wajah dikirim
  sebagai keyframe properti, bukan dikarang AI.
- [ ] **M4.8** Pustaka animasi per profil: simpan, beri nama, cari, dan pakai di
  proyek lain. Animasi AI yang belum lolos pemeriksaan tidak bisa disimpan.
- [ ] **M4.9** Uji 10 permintaan dari [bagian 25](#25-daftar-uji-permintaan-animasi),
  hasilnya dicatat di sana, termasuk biaya API sebenarnya.
- [ ] **M4.10** Mode salin-tempel lewat **Project Claude.ai**, untuk memakai
  langganan Claude Pro (atau chat AI lain) tanpa API key (K-13, K-15).

  **Persiapan sekali saja:**
  1. Tombol "Unduh paket Project Claude" memberi satu berkas `.md` berisi
     instruksi proyek, kontrak komponen ([bagian 21](#21-kontrak-komponen-animasi-ai)),
     daftar font dan zona aman, serta contoh dari pustaka bawaan.
  2. Pengguna membuat Project baru di Claude.ai (misalnya "OmniClip Montase"),
     menempel bagian instruksinya ke *Project instructions*, dan mengunggah
     berkasnya ke *Project knowledge*. Langkah ini tampil di layar bergambar.
  3. Paket punya nomor versi. Kalau kontrak berubah di versi OmniClip
     berikutnya, aplikasi memberi tahu bahwa paketnya perlu diunggah ulang.

  **Setiap permintaan:**
  1. Tombol "Salin permintaan" menyalin pesan pendek: permintaan pengguna,
     konteks rentang video (kata yang diucapkan, momen tawa/kaget, letak
     wajah), ukuran kanvas, durasi, dan nomor versi paket.
  2. Tombol "Buka Claude.ai" membuka tab baru. Prefill alamat (`?q=`) tidak
     resmi dan pernah berhenti bekerja, jadi papan klip tetap jalan utamanya.
  3. Pengguna menempel di chat baru dalam Project itu, lalu menyalin seluruh
     balasan Claude.
  4. Tombol "Tempel hasil" menerima balasan itu. OmniClip mengambil blok kode
     dan metadata, lalu memeriksanya dengan pemeriksa M4.4 yang sama.
  5. Kalau gagal, galatnya disusun jadi pesan perbaikan untuk ditempel di chat
     yang sama. Revisi ("lebih cepat", "warna merah") juga lewat chat itu.

  Lebih lambat daripada lewat API, tapi tanpa biaya tambahan di luar
  langganan. Format permintaan dan balasan sama dengan jalur API (M4.3), jadi
  pemeriksa, panel properti, dan pustaka tidak tahu jalur mana yang dipakai.

**Selesai bila:** paling sedikit 8 dari 10 permintaan uji lolos pemeriksaan
tanpa campur tangan, dan semuanya bisa dikoreksi lewat panel properti.

---

## Tahap 5: Asisten penyunting AI

**Tujuan:** satu perintah menghasilkan draf video lengkap.

**Prinsip penting:** AI **tidak pernah menulis dokumen proyek langsung**. Ia
mengeluarkan daftar **operasi** (tambah item, potong, beri teks, dan
seterusnya). Daftar itu dijalankan oleh fungsi `model/` yang sama dengan yang
dipakai tangan manusia, lalu ditampilkan sebagai **usulan perubahan**. Anda
memilih untuk menerima semua, sebagian, atau menolaknya.

- [ ] **M5.1** `montase/asisten_ai.py`: perintah tingkat proyek, misalnya "susun
  Top 5 momen paling lucu dari klip-klip ini". AI menerima daftar bahan
  (transkrip, skor klip bila dari Klip jadi, momen), lalu mengeluarkan daftar
  operasi.
- [ ] **M5.2** Tampilan usulan perubahan: item usulan tampil bergaris putus di
  linimasa, dengan tombol Terima semua / Terima yang dipilih / Tolak.
- [ ] **M5.3** Naskah narasi per peringkat dalam bahasa dari `bahasa_ai.py`,
  dibacakan dengan suara pilihan (M3.3).
- [ ] **M5.4** Buang jeda sunyi dan kata isian ("eh", "em") memakai waktu per
  kata, sebagai usulan potongan.
- [ ] **M5.5** Bingkai ulang otomatis ke 9:16 untuk bahan horizontal: jejak wajah
  dari `reframe.py` menjadi keyframe posisi dan ukuran.
- [ ] **M5.6** Saran judul, deskripsi, dan tagar saat ekspor (pakai
  `keterangan.py`).

**Selesai bila:** dari 5 Klip jadi, satu perintah menghasilkan video Top 5 yang
tinggal dikoreksi, dan pemilik menilai hasilnya layak sebagai draf.

---

## Tahap 6: Rapikan dan rilis

- [ ] **M6.1** Unggah dari Montase lewat alur yang sudah ada (`UploadModal`,
  `gerbang.py`). Kredit **banyak sumber** di deskripsi, label konten sintetis
  bila ada suara TTS (keputusan T-3).
- [ ] **M6.2** Skor nilai tambah untuk video Montase (`nilai_tambah.py`):
  narasi dihitung seperti komentar, sedangkan teks, animasi, dan sisipan
  setengah bobot.
- [ ] **M6.3** Kinerja: proyek 10 menit dengan 100 item tetap lancar
  (linimasa tervirtualisasi, sampul di-cache).
- [ ] **M6.4** Riwayat versi proyek (10 simpanan terakhir) dan pemulihan sesudah
  aplikasi tertutup mendadak.
- [ ] **M6.5** Pembersihan penyimpanan: salinan sunting, render sementara, dan
  bahan yatim ditangani `sampah.py` dan `bersih_otomatis.py`.
- [ ] **M6.6** Proyek dan pustaka animasi ikut fitur cadangan.
- [ ] **M6.7** `UJI-LANGSUNG.md` bagian Montase lengkap, dan halaman bantuan
  singkat di dalam aplikasi.
- [ ] **M6.8** Rilis: label "beta" dilepas, versi dinaikkan di `version.py`.

---

## Kapan saja: suara AI baru

Menunggu pemilik memilih layanan (T-4). Dirancang supaya layanan apa pun masuk
dengan cara yang sama.

- [ ] **MS.1** `tts.py` mendapat mesin baru (`"engine": "elevenlabs"` atau
  lainnya) di katalog yang sama dengan Piper dan Edge. Kunci API disimpan lewat
  `kunci_ai.py` / koneksi AI. Daftar suara diambil dari API layanannya.
- [ ] **MS.2** Simpanan hasil: suara yang sama untuk teks + suara + setelan yang
  sama tidak dibuat ulang (kunci = hash ketiganya), supaya tidak membayar dua
  kali.
- [ ] **MS.3** Label sintetis dan catatan pemakaian (biaya per karakter) tampil di
  Pengaturan.

---

# BAGIAN C: ACUAN TEKNIS

## 14. Struktur folder

```
backend/app/montase/              ← semua kode server Montase
  __init__.py
  router.py                       /api/montase/*
  proyek.py                       buat, simpan, versi, gandakan
  skema.py                        validasi + migrasi dokumen proyek
  bahan.py                        impor/rujukan bahan, ffprobe, sampul, gelombang, salinan sunting
  mesin.py                        unduh + jalankan Mesin Montase (pola alat_yt.py)
  render.py                       pekerjaan montase_render, kemajuan, batal, loudnorm
  motion_ai.py                    AI pembuat + perevisi animasi
  asisten_ai.py                   AI penyusun (Tahap 5)
  periksa.py                      pemeriksaan kode AI
  token.py                        token sekali pakai untuk mesin render dan iframe
backend/app/repos/montase.py
backend/tests/test_montase_*.py

montase-mesin/                    ← paket Node, dibangun di CI per sistem operasi
  package.json                    versi @remotion/* dipatok persis
  package-lock.json
  src/bundel.mjs                  membundel komposisi (dijalankan di CI)
  src/render.mjs                  render MP4, kemajuan JSON per baris
  src/periksa.mjs                 renderStill bingkai contoh
  src/kompilasi.mjs               TSX → JS (sucrase) + pemeriksaan statis

frontend/src/features/montase/    ← semua kode antarmuka Montase
  MontaseHome.jsx                 daftar proyek
  MontaseEditor.jsx               editor
  pratinjau/                      iframe kotak pasir + jembatan postMessage
  linimasa/                       lajur, item, garis putar, magnet, penanda
  panel/                          bahan, properti (dari skema), chat AI
  model/                          operasi murni + batal/ulang + *.test.js
  komposisi/                      ← DIPAKAI BERSAMA pratinjau dan mesin render
    Komposisi.jsx                 membaca dokumen proyek, menggambar semua lajur
    item/                         Video, Gambar, Teks, Audio, Motion
    efek/  transisi/  motion/     (motion/ = pustaka animasi bawaan)
    muatKomponen.js               memuat komponen AI hasil kompilasi
  pratinjau.html                  titik masuk Vite kedua, untuk isi iframe
```

**Kenapa `komposisi/` ada di frontend:** kode itu dijalankan di dua tempat,
Player di peramban dan Chrome headless di mesin render. Ia ditulis sekali di
frontend, lalu `montase-mesin/src/bundel.mjs` membundelnya di CI. Itulah yang
menjamin P-2 (pratinjau = hasil).

## 15. Batas modul

**Singkatnya:** Montase boleh memakai layanan bersama OmniClip, tapi tidak boleh
menyentuh isi Studio Klip. Tes `test_montase_batas.py` membaca semua berkas
Montase dan gagal kalau aturan ini dilanggar (pola yang sama dengan tes penjaga
di `test_cacat_diperbaiki.py`).

| Boleh dipakai Montase | Dilarang |
|---|---|
| `services/`: `media` (ffprobe), `paths` (`safe_media_path`), `tema_judul` (tema teks), `subtitles` (hanya `BUNDLED_FONTS`), `koneksi_ai`, `penyedia_ai`, `kunci_ai`, `pemakaian_ai`, `bahasa_ai`, `tts`, `aset`, `stok`, `soundboard`, `whisper`, `transcript`, `momen`, `peristiwa_suara`, `reframe` (hanya fungsi publik jejak wajah), `proses`, `paths`, `jobs`, `events`, `profil`, `fonts`, `enkoder`, `unggah`, `google_upload`, `gerbang`, `keterangan`, `nilai_tambah`, `sampah` | `services/pipeline.py`, `services/render.py` (render klip), `services/sutradara*.py`, `routers/clips.py`, `routers/projects.py` |
| `app/config.py`, `app/db.py`, `app/bahasa.py`, `app/errors.py`, `repos/media.py` (unduhan, kredit sumber), `repos/settings.py` | Tabel `projects` dan `clips` (Montase punya tabelnya sendiri) |
| Frontend: `lib/*`, `components/*`, `hooks/*`, `utils/*` | `features/studio/*` |

Kalau sesuatu di `features/studio/` dibutuhkan Montase (misalnya
`WaveformCanvas.jsx` atau `rectDrag.js`), **pindahkan dulu ke folder bersama**
(`components/` atau `lib/`) dalam commit tersendiri. Jangan diimpor dari
tempatnya sekarang.

## 16. Dokumen proyek

**Singkatnya:** satu proyek = satu JSON. Isinya daftar bahan, lajur, dan item.
Videonya sendiri tidak disalin ke dalam proyek, hanya dirujuk lewat id.

```json
{
  "versi": 1,
  "id": "mt_8f3a2c",
  "nama": "Top 5 Momen Podcast",
  "kanvas": { "lebar": 1080, "tinggi": 1920, "fps": 30, "latar": "#000000" },
  "durasi": 2700,
  "bahan": {
    "b1": { "jenis": "video", "durasi": 32.4, "lebar": 1080, "tinggi": 1920,
            "fps": 30, "ada_suara": true }
  },
  "lajur": [
    { "id": "L1", "jenis": "video", "nama": "Video 1",
      "kunci": false, "bisu": false, "sembunyi": false, "volume": 1,
      "item": [
        { "id": "i1", "jenis": "video", "bahan": "b1",
          "mulai": 0, "durasi": 300, "potong_awal": 45,
          "kecepatan": 1, "volume": 1, "fade_masuk": 15, "fade_keluar": 30,
          "isi": "contain", "beku": false,
          "ubah": { "x": 0, "y": 0, "skala": 1, "putar": 0, "opasitas": 1,
                    "potong": { "kiri": 10, "kanan": 0, "atas": 0, "bawah": 0 } },
          "keyframe": { "skala": [ { "t": 0, "v": 1 },
                                   { "t": 30, "v": 1.15, "kurva": "keluar" } ] },
          "warna": { "preset": "vibrant" },
          "transisi_masuk": { "jenis": "geser", "durasi": 12 } }
      ] },
    { "id": "L3", "jenis": "motion", "nama": "Animasi",
      "item": [
        { "id": "i9", "jenis": "motion", "komponen": "ko_hitung_mundur", "versi": 3,
          "mulai": 0, "durasi": 60,
          "props": { "angka": 5, "judul": "Momen paling kacau", "warna": "#FF3355" },
          "asal": "ai", "alasan": "Pembuka peringkat #5" }
      ] },
    { "id": "L4", "jenis": "audio", "nama": "Narasi", "item": [] }
  ],
  "penanda": [ { "t": 300, "label": "#4" } ],
  "ekspor": { "kualitas": "tinggi" }
}
```

**Aturan dokumen:**

| Aturan | Alasan |
|---|---|
| Semua waktu (`mulai`, `durasi`, `potong_awal`, `t` keyframe) dalam **bingkai** (bilangan bulat). Detik hanya untuk tampilan. | Remotion bekerja dalam bingkai. Pecahan detik menumpuk jadi selisih satu bingkai. |
| `bahan` di dokumen hanya menyimpan metadata. Jalur berkasnya ada di tabel `montase_bahan`. | P-7: klien tidak pernah menyebut jalur. |
| Lajur pertama di daftar digambar paling bawah. Antarmuka menampilkannya terbalik (lajur teratas di layar = paling depan). | Sama dengan CapCut dan Premiere. |
| Setiap item punya `id` tetap. | Batal/ulang, usulan AI, dan komentar menunjuk item lewat id. |
| `asal`: `"tangan"` (bawaan) atau `"ai"`, plus `alasan` bila `ai`. | P-3. |
| `versi` naik setiap bentuk dokumen berubah, dengan fungsi migrasi di `skema.py`. | Proyek lama tetap terbuka. |
| `ubah.x`/`ubah.y` dalam piksel kanvas dari letak asal; `skala` 1 = asli; `putar` derajat; `potong` persen KOTAK DASAR item per sisi (dua sisi berhadapan menyisakan ≥ 5%). Kotak dasar ditentukan `komposisi/kotak.js`: video/gambar "muat" = persegi sesuai rasio bahannya di tengah kanvas, "penuh" dan animasi = seluruh kanvas, teks = kotak teksnya. | Satuan kanvas membuat pratinjau kecil dan render penuh sama; kotak sesuai bahan membuat potong berarti potong gambar. |
| `fade_masuk`/`fade_keluar` dalam bingkai, untuk volume. `beku: true` = bingkai `potong_awal` ditahan tanpa suara. | M2.6, M2.7. |
| Menambah kolom baru tidak menaikkan `versi` selama kolom lama tetap berarti sama (Tahap 2 hanya menambah). | Kolom tak dikenal dipertahankan server. |

## 17. Basis data

Ditambahkan sebagai satu entri baru di `MIGRATIONS` (`db.py`).

```sql
CREATE TABLE montase_proyek (
  id            TEXT PRIMARY KEY,
  profil_id     INTEGER NOT NULL DEFAULT 1,
  nama          TEXT NOT NULL,
  dokumen_json  TEXT NOT NULL,
  revisi        INTEGER NOT NULL DEFAULT 1,
  sampul        TEXT,
  durasi_detik  REAL,
  updated_at    REAL NOT NULL,
  created_at    REAL NOT NULL
);
CREATE INDEX idx_montase_proyek ON montase_proyek(profil_id, updated_at DESC);

CREATE TABLE montase_bahan (
  id            TEXT PRIMARY KEY,
  profil_id     INTEGER NOT NULL DEFAULT 1,
  asal          TEXT NOT NULL CHECK (asal IN
                  ('impor','unduhan','klip_jadi','aset','stok','tts','rekam','render')),
  rujukan       TEXT,          -- id di asalnya (video_id, nama klip, id aset)
  nama          TEXT NOT NULL,
  rel_path      TEXT NOT NULL,
  jenis         TEXT NOT NULL CHECK (jenis IN ('video','audio','gambar')),
  durasi        REAL, lebar INTEGER, tinggi INTEGER, fps REAL,
  ada_suara     INTEGER NOT NULL DEFAULT 0,
  siap          INTEGER NOT NULL DEFAULT 0,  -- turunan dan salinan sunting sudah jadi
  created_at    REAL NOT NULL
);
-- unik per (profil_id, asal, rujukan): merujuk berkas yang sama dua kali
-- mengembalikan bahan yang sudah ada.
-- Turunan tinggal di <data>/montase/bahan/<id>/: sampul.jpg, strip.jpg,
-- gelombang.json, sunting.mp4.

CREATE TABLE montase_komponen (
  id            TEXT NOT NULL,
  versi         INTEGER NOT NULL,
  profil_id     INTEGER NOT NULL DEFAULT 1,
  nama          TEXT NOT NULL,
  asal          TEXT NOT NULL CHECK (asal IN ('bawaan','ai','tangan')),
  sumber_tsx    TEXT NOT NULL,
  hasil_js      TEXT,
  skema_json    TEXT,
  contoh_props  TEXT,
  durasi_bawaan INTEGER,
  permintaan    TEXT,          -- prompt yang melahirkannya, bila asal = ai
  status        TEXT NOT NULL CHECK (status IN ('draf','lolos','gagal')),
  catatan       TEXT,          -- hasil pemeriksaan
  disimpan      INTEGER NOT NULL DEFAULT 0,  -- masuk pustaka
  created_at    REAL NOT NULL,
  PRIMARY KEY (id, versi)
);
```

Animasi bawaan tidak disimpan di tabel. Ia ikut kode di `komposisi/motion/`.

## 18. API

Semua di bawah `/api/montase`, membawa profil aktif lewat header
`X-Omniclip-Profil` seperti endpoint lain.

| Metode | Jalur | Guna |
|---|---|---|
| GET | `/proyek` | Daftar proyek profil aktif |
| POST | `/proyek` | Buat proyek `{nama, kanvas}` |
| GET | `/proyek/{id}` | Dokumen + `revisi` |
| PUT | `/proyek/{id}` | Simpan `{dokumen, revisi}`. Jawab 409 bila revisi sudah berubah. |
| DELETE | `/proyek/{id}` | Hapus proyek. Bahan yang tidak dipakai proyek lain dibersihkan oleh M6.5. |
| POST | `/proyek/{id}/gandakan` | Salin proyek |
| POST | `/proyek/{id}/ekspor` | Mulai pekerjaan render, menjawab `job_id` |
| GET | `/bahan` | Daftar bahan |
| POST | `/bahan/impor` | Unggah berkas (multipart) |
| POST | `/bahan/rujuk` | `{asal, rujukan}`: ambil dari Unduhan, Klip jadi, Aset, atau Stok |
| GET | `/bahan/sumber?asal=` | Berkas yang bisa dijadikan bahan (unduhan, klip_jadi, aset), tanpa jalur |
| POST | `/bahan/impor` | (sudah disebut di atas) unggahan masuk pustaka aset lalu jadi bahan `impor` |
| DELETE | `/bahan/{id}` | Hapus bahan; 409 `BAHAN_DIPAKAI` bila masih dipakai proyek |
| GET | `/token` | Token `bahan:<profil>` (6 jam) untuk iframe dan `<img>` |
| GET | `/t/{token}/bahan/{id}` | Berkas asli (render) atau salinan sunting (`?sunting=1`). Tanpa sesi. |
| GET | `/t/{token}/bahan/{id}/{sampul,strip,gelombang}` | Turunan bahan. Lewat token karena `<img>` tidak membawa header profil. |
| GET, POST | `/setelan` | Sakelar "Montase (beta)" (`{aktif}`) |
| POST | `/proyek/{id}/subtitle` | Subtitle otomatis (pekerjaan `montase_subtitle`), menjawab potongan untuk dipasang editor (M3.2) |
| GET | `/suara` | Katalog suara narasi (`tts.py`) dan kesiapannya (M3.3) |
| POST | `/rekam` | Rekaman mikrofon (WebM) -> M4A -> bahan `rekam` (M3.3) |
| GET | `/gaya-teks` | Tema teks dari `tema_judul.py` dalam bentuk `item.gaya`, dan daftar font bawaan (M3.1) |
| GET | `/t/{token}/font/{keluarga}` | Berkas font bawaan untuk iframe dan mesin render |
| POST | `/narasi` | `{teks, suara, kecepatan}`: hasil TTS menjadi bahan audio `tts`, narasi yang sama dipakai ulang |
| GET | `/komponen` | Pustaka animasi (bawaan + tersimpan) |
| GET | `/komponen/{id}/{versi}.js` | Hasil kompilasi, untuk iframe dan mesin. Menerima token. |
| POST | `/motion/buat` | `{permintaan, proyek_id, rentang?}`: pekerjaan AI, menjawab `job_id` |
| POST | `/motion/{id}/revisi` | `{perintah}`: versi baru |
| POST | `/motion/{id}/simpan` | Masukkan ke pustaka |
| POST | `/asisten` | `{perintah, proyek_id}`: menjawab daftar operasi usulan |
| GET | `/mesin` | Status mesin: terpasang, versi, ukuran |
| POST | `/mesin/siapkan` | Mulai mengunduh mesin |

Kemajuan pekerjaan (render, AI, unduh mesin) memakai saluran peristiwa yang
sudah ada (`events.py`, `JobProgress`), bukan saluran baru.

Status 3 Nov 2026: semua baris di atas sudah ada **kecuali** `/komponen*` dan
`/motion/*` (Tahap 4), dan `/asisten` (Tahap 5). `/narasi` menerima juga
`kecepatan` (tempo 0,6-1,6).

## 19. Mesin Montase

**Singkatnya:** program Node kecil yang dijalankan Python setiap kali perlu
merender. Ia tidak berjalan terus.

**Isi dan asalnya:**

| Bagian | Asal | Ukuran (terukur 3 Nov 2026, Linux) |
|---|---|---|
| Node v22.23.4 portabel | **Diunduh** dari nodejs.org saat Montase disiapkan, SHA-256 dipatok (`montase/unduh.py`), npm/header dibuang sesudah dibongkar | unduh 31 MB (Windows 36 MB), terbongkar 126 MB |
| Paket mesin (`node_modules` produksi + `src/` + `uji/`) | **Ikut di dalam aplikasi** (K-16), dibangun CI per sistem operasi | 75 MB terbongkar, ±24 MB terkompresi |
| Bundel komposisi | **Ikut di dalam aplikasi**, dibangun CI (`src/bundel.mjs`, tanpa source map) | 16 MB |
| Chrome Headless Shell | **Diunduh** Remotion (`ensureBrowser()`) ke `node_modules/.remotion` milik paket mesin | belum terukur (diblokir jaringan container, lihat bagian 24) |

Node disimpan di `STORAGE_DIR/mesin_montase/node-v<versi>/`. Di aplikasi
terbungkus, paket mesin dan bundel ada di `<bundel>/montase_mesin/`.

**Mode pengembangan:** sekali `cd montase-mesin && npm ci && node src/bundel.mjs`,
lalu `mesin.py` memakai Node sistem (`node` di PATH, versi ≥ 22). Bundel harus
dibangun ulang setiap kali `frontend/src/features/montase/komposisi/` berubah.

**Variabel lingkungan untuk uji:** `OMNICLIP_NODE` (Node tertentu) dan
`OMNICLIP_MONTASE_BROWSER` (Chrome/Chromium headless tertentu, untuk komputer
yang tidak bisa mengunduh Chrome Headless Shell).

**Antarmuka Python → Node:** satu perintah per pemanggilan, masukan JSON di
stdin, keluaran JSON per baris di stdout:

```
node src/render.mjs  < {"serve_url": "...", "dokumen": {...}, "sumber": {...}, "keluar": "...", "crf": 18}
→ {"tahap": "menyiapkan"}
→ {"kemajuan": 0.42, "bingkai": 380, "total": 900}
→ {"selesai": true, "berkas": "...", "detik": 87.0, "bingkai": 900}
```

Perintah yang ada: `render`, `kompilasi`, `siapkan` (Chrome), dan `bundel`
(hanya CI/pengembangan). Pemanggilnya `backend/app/montase/mesin.py`.

**Aturan menjalankan:**

| Aturan | Alasan |
|---|---|
| Pegang `gerbang_cpu` (`jobs.py`) selama render | Supaya render tidak berebut CPU dengan Whisper dan render klip |
| `concurrency` Remotion ditentukan dari RAM bebas. Tolak dengan pesan jelas bila RAM kurang. | Setiap tab Chrome memakan ratusan MB. Pola yang sama dengan `ai_lokal.py`. |
| Batal = matikan seluruh pohon proses | Chrome meninggalkan proses anak |
| Bahan dibaca lewat URL `127.0.0.1` dengan token sekali pakai (`montase/token.py`) | Chrome headless tidak membawa cookie sesi. Token dibatasi ke bahan proyek itu dan kedaluwarsa sesudah render. |
| Remotion mengode H.264 sendiri. Encoder GPU OmniClip belum terpakai di jalur ini. | Diukur di Tahap 0. Bila terlalu lambat, lihat Rencana B. |

## 20. Pratinjau dan kotak pasir

**Singkatnya:** pratinjau berjalan di dalam "kotak tertutup" (iframe kotak
pasir), karena animasi AI adalah kode yang tidak kita tulis sendiri.

- Iframe memuat `pratinjau.html` dengan `sandbox="allow-scripts"`. Tanpa
  `allow-same-origin`, kode di dalamnya tidak bisa membaca cookie, penyimpanan,
  atau memanggil API OmniClip atas nama pengguna.
- Jembatan `postMessage` dua arah:

  | Dari editor ke iframe | Dari iframe ke editor |
  |---|---|
  | `muat {dokumen, sumber}` (tiap berubah; `sumber` berisi alamat bertoken) | `siap`, `bingkai {bingkai}`, `main {main}` |
  | `putar`, `jeda`, `ke {bingkai}` | `galat {pesan}`, `tombol {key, shift, ctrl, meta, alt}` |

  Iframe TIDAK pernah melaporkan ukuran atau letak item: pegangan dihitung
  dari dokumen di luar iframe (`model/geometri.js`). Laporan `bingkai` yang
  datang sesudah editor melompat ke bingkai lain (laporan basi) diabaikan
  selama 0,6 detik saat tidak diputar.

- Bahan dan komponen dimuat dengan URL bertoken, dan endpoint-nya menjawab CORS
  untuk asal `null`. Ini juga berlaku untuk berkas JS dan CSS milik
  `pratinjau.html` sendiri, karena skrip modul selalu dimuat dengan CORS dan
  iframe tanpa `allow-same-origin` beralamat `null`. Diuji di M0.6.
- **Salinan sunting:** setiap bahan video dibuatkan salinan 540p H.264 dengan
  keyframe rapat (GOP 15), supaya penggeseran pratinjau mulus. Pembuatannya
  mengikuti disiplin `proksi.py`: satu antrean, prioritas terendah, dua inti.
  Render akhir selalu memakai berkas asli.
- Pegangan transformasi (M2.5) dan garis zona aman digambar di **luar** iframe,
  di atasnya, supaya tidak bergantung pada kode di dalam kotak pasir. Pegangan
  menangkap penunjuk (`setPointerCapture`) karena gerakan di atas iframe
  dikirim ke dokumen iframe, bukan ke editor.
- Kode komponen AI dimuat lewat `muatKomponen.js`: unduh teks hasil kompilasi,
  lalu jalankan dengan `new Function(require, module, exports)`. `require`
  hanya mengembalikan modul yang diizinkan kontrak. Hanya iframe yang
  mengizinkan `unsafe-eval`, editornya tidak.

## 21. Kontrak komponen animasi AI

**Singkatnya:** aturan yang wajib diikuti setiap animasi supaya aman, bisa
diatur lewat panel, dan hasil rendernya sama dengan pratinjau.

**Bentuk berkas:**

```tsx
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { z } from "zod";
import { zColor } from "@remotion/zod-types";

export const skema = z.object({
  angka: z.number().int().min(1).max(10),
  judul: z.string().max(60),
  warna: zColor(),
});

export const contohProps = { angka: 5, judul: "Momen paling kacau", warna: "#FF3355" };
export const durasiBawaan = 60;            // bingkai, pada fps proyek
export const kategori = "peringkat";

export default function HitungMundur({ angka, judul, warna }: z.infer<typeof skema>) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const masuk = spring({ frame, fps, config: { damping: 12 } });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center" }}>
      <div style={{ transform: `scale(${masuk})`, color: warna, fontSize: 280 }}>#{angka}</div>
      <div style={{ opacity: interpolate(frame, [10, 25], [0, 1], { extrapolateRight: "clamp" }) }}>
        {judul}
      </div>
    </AbsoluteFill>
  );
}
```

**Impor yang diizinkan:** `react`, `remotion`, `zod`, `@remotion/zod-types`,
`@remotion/shapes`, `@remotion/paths`, `@remotion/transitions`, dan
`@remotion/noise`. Paket tambahan masuk daftar ini lewat keputusan di
[bagian 3](#3-keputusan).

**Dilarang** (pemeriksaan statis menolaknya):

| Dilarang | Kenapa |
|---|---|
| `fetch`, `XMLHttpRequest`, `WebSocket`, `EventSource`, `navigator.sendBeacon` | Tidak boleh ada jaringan |
| `eval`, `new Function`, `import()` dinamis, `importScripts` | Tidak boleh memuat kode lain |
| `Math.random`, `Date.now`, `new Date()`, `performance.now` | Hasil render harus sama setiap kali. Pakai `random(seed)` dari `remotion`. |
| `setTimeout`, `setInterval`, `requestAnimationFrame`, animasi/transisi CSS | Gerak hanya boleh berasal dari `useCurrentFrame()`. Selain itu tidak tertangkap saat render. |
| `localStorage`, `sessionStorage`, `indexedDB`, `document.cookie` | Tidak ada penyimpanan |
| `window.parent`, `window.top`, `postMessage`, `document.domain` | Tidak boleh keluar dari kotak pasir |
| Gambar/font/berkas dari URL luar | Bahan masuk lewat props (URL bertoken dari OmniClip) |

**Batas ukuran:** sumber paling panjang 30 KB. Satu bingkai contoh harus selesai
dirender dalam 5 detik.

**Sumber panduan untuk prompt sistem:** halaman resmi Remotion "Generate
Remotion Code using LLMs" (remotion.dev/docs/ai/generate). Dokumentasi Remotion
bisa dibaca sebagai markdown dengan menambahkan `.md` di ujung alamat halaman.
Dibaca ulang saat M4.3 dikerjakan, karena isinya ikut berubah setiap versi.

## 22. Hasil ekspor dan Klip jadi

**Singkatnya:** hasil Montase masuk ke Klip jadi seperti klip biasa, supaya
unggah, analitik, dan pembersihan langsung bekerja.

Daftar Klip jadi dibaca dari folder klip profil (`render.py`, daftar `*.mp4`
beserta sidecar `.json`). Ekspor Montase menulis ke folder yang sama:

```
<folder klip profil>/Top-5-Momen-Podcast_montase_2026-11-12.mp4
<folder klip profil>/Top-5-Momen-Podcast_montase_2026-11-12.json   ← sidecar
<folder klip profil>/Top-5-Momen-Podcast_montase_2026-11-12.srt    ← bila ada subtitle
```

Sidecar memakai kunci yang sudah dikenal Klip jadi, ditambah penanda Montase:

```json
{
  "jenis": "montase",
  "montase_id": "mt_8f3a2c",
  "file_name": "Top-5-Momen-Podcast_montase_2026-11-12.mp4",
  "title": "Top 5 Momen Podcast",
  "hashtags": [],
  "duration": 92.0,
  "aspect_ratio": "9:16",
  "subtitles": [],
  "sumber_banyak": [ { "video_id": "...", "judul": "...", "channel": "..." } ],
  "suara_sintetis": true,
  "motion_ai": true,
  "nilai_tambah": { "skor": 0.0, "cukup": false },
  "created_at": 0
}
```

Tugas M1.9 harus memastikan Klip jadi, unggah, dan analitik **tidak pecah**
karena kunci yang tidak ada (misalnya `start`, `video_id` tunggal). Ini ditulis
sebagai tes.

## 23. Risiko

| No | Risiko | Kemungkinan | Penanganan |
|---|---|---|---|
| R-1 | Render terlalu lambat | Sedang | Diukur di Tahap 0. Rencana B. Batas `concurrency` dari RAM. |
| R-2 | Unduhan mesin besar (Node + Chrome) | Pasti | Diunduh hanya saat Montase dipakai, ukuran dan kemajuan ditampilkan, bisa dilanjutkan bila terputus. |
| R-3 | Kode AI rusak atau berbahaya | Pasti terjadi sesekali | Kontrak, pemeriksaan statis, render contoh, kotak pasir, token bahan terbatas. |
| R-4 | Belum pernah diuji di Windows | Tinggi | M0.7 dikerjakan sebelum Tahap 1. |
| R-5 | RAM penuh (Chrome + Whisper + AI lokal) | Sedang | `gerbang_cpu`, pemeriksaan RAM sebelum render, pesan yang jelas. |
| R-6 | Pratinjau berbeda dari hasil | Rendah (satu komposisi) | Tes pembanding: `renderStill` lawan tangkapan Player untuk 10 animasi bawaan. |
| R-7 | Kebijakan konten YouTube yang digunakan ulang | Tinggi untuk kompilasi | Gerbang tinjau dan nilai tambah berlaku (T-3, M6.1, M6.2). |
| R-8 | Lingkup membengkak (mengejar Premiere) | Tinggi | Yang tidak ada di dokumen ini masuk [di luar cakupan](#26-di-luar-cakupan) dulu. |
| R-9 | Lisensi Remotion bila usaha tumbuh | Rendah sekarang | Pantau jumlah karyawan. Dokumen proyek milik sendiri, jadi mesin bisa diganti. |
| R-10 | API Remotion berubah antarversi | Sedang | Versi dipatok persis, naik versi = tugas tersendiri dengan uji ulang Tahap 0. |

---

# BAGIAN D: LAMPIRAN

## 24. Hasil uji teknis

Diisi saat Tahap 0. Kolom **Container** = lingkungan pengembangan Claude (Linux,
4 inti, 16 GB, tanpa GPU, Chromium headless 153 bawaan container). Kolom
**CI** = aplikasi hasil build di GitHub Actions (`--periksa-montase`, render 10
detik). Kolom **Pemilik** = komputer pemilik (tes 60-63 di UJI-LANGSUNG.md).

| Ukuran | Container (3 Nov) | CI Linux / Windows | Pemilik | Catatan |
|---|---|---|---|---|
| Versi Remotion yang dipatok | 4.0.537 | sama | | Rilis 19 Okt 2026. Semua `@remotion/*` sama persis (dijaga tes). |
| Player jalan di React 19 (M0.1) | Ya, 19.2.8, tanpa galat konsol | | | |
| Render 30 dtk 1080x1920 30 fps: lama | 87-89 dtk (2,9x) | | | Lewat antrean backend dan langsung, hasilnya sama. |
| Render 10 dtk (uji CI) | 28 dtk (2,8x) | Linux 23-25 dtk (2,3-2,5x) · Windows 25-28 dtk (2,5-2,8x) | | Run 41610381956 dan 41612685962, aplikasi terbungkus, Node dan Chrome hasil unduhan. |
| Render 30 dtk: RAM puncak | ±2,4 GB di atas dasar | | | Total semua proses 2,9 GB. |
| Render 30 dtk: ukuran berkas | 40 MB (crf 18, ±10,3 Mbps) | | | |
| Perkiraan render 60 dtk (lawan ambang T-5) | ±175 dtk ≈ 2,9 menit | | | Di bawah ambang usulan 4 menit. |
| Ukuran unduhan Node | 31 MB, 3-5 dtk; 126 MB terbongkar | Linux 2,8 dtk · Windows 1,9 dtk (36 MB) | | npm dan header C dibuang. |
| Paket mesin di dalam aplikasi (K-16) | 75 MB terbongkar, ±24 MB terkompresi | arsip Linux 371 MB (+25), Windows 298 MB (+28) | | Dibanding v1.3.9 (346 / 270 MB). Termasuk bundel komposisi 16 MB. |
| Unduhan Chrome Headless Shell | tidak bisa diuji (403 dari proxy) | Linux 1,9 dtk · Windows 4,1 dtk | | Container memakai `OMNICLIP_MONTASE_BROWSER`. Build pertama menemukan Chrome terunduh ke folder APLIKASI; diperbaiki di f65f820 (lihat M0.7). |
| Animasi AI: pratinjau = render (M0.5) | Ya, kasat mata sama di 4 bingkai | | | SSIM 0,84 karena tangkapan pratinjau hanya 316x561 lalu diskalakan. |
| Kotak pasir memutar video bertoken (M0.6) | Ya (Playwright) | | | Asal `null`; DOM, cookie, localStorage ditolak. |
| Keputusan: lanjut / Rencana B | Lanjut, tanpa Rencana B | Lanjut | ditunda ke uji akhir (K-17) | Gerbang Tahap 0 ditutup 3 Nov 2026. |
| Tahap 2: proyek 5 menit 50 item | 60 fps, p95 16,7 ms, nol *long task* | | | Seret 90 langkah, pangkas, pilih kotak 50 item, batal/ulang/belah, putar 4 detik. |
| Tahap 2: ekspor = pratinjau | SSIM 0,92-0,96 di 6 bingkai | | | Gambar-dalam-gambar terputar dan terpotong, 2x, beku, teks. Selisihnya hanya halus huruf. |

## 25. Daftar uji permintaan animasi

Dipakai di M4.9. Setiap permintaan dicoba sekali, tanpa campur tangan.

| No | Permintaan | Lolos periksa? | Sesuai permintaan? | Catatan |
|---|---|---|---|---|
| 1 | Hitung mundur "#5" bergaya neon dengan judul "Momen paling kacau" | | | |
| 2 | Teks "GILA!" memantul masuk lalu pecah jadi serpihan | | | |
| 3 | Label nama "Dr. Tirta, dokter" di kiri bawah, masuk dari kiri | | | |
| 4 | Ledakan emoji 😂 di sekitar satu titik yang bisa diatur | | | |
| 5 | Garis kejut gaya manga dari tepi ke tengah selama 1 detik | | | |
| 6 | Lingkaran merah menggambar dirinya mengelilingi satu titik, lalu panah menunjuk | | | |
| 7 | Kartu ajakan berlangganan, tombolnya ditekan kursor | | | |
| 8 | Bilah peringkat 5 segmen di atas layar, segmen aktif menyala | | | |
| 9 | Kilat putih dengan guncangan sebagai transisi | | | |
| 10 | Angka "1.000.000 penonton" menghitung naik dari nol | | | |

## 26. Di luar cakupan

Dicatat supaya tidak hilang, **tidak** dikerjakan sebelum Tahap 6 selesai:

- masking dan bentuk topeng;
- chroma key (latar hijau);
- koreksi warna lanjut (LUT, kurva, roda warna);
- multikamera dan urutan bersarang (*nested sequence*);
- stabilisasi gambar dan pelacakan objek;
- efek 3D;
- penyuntingan bersama oleh beberapa orang;
- penyuntingan penuh di HP;
- templat proyek yang bisa dibagikan atau dijual.

## 27. Kamus istilah

| Istilah | Arti sederhana |
|---|---|
| Linimasa | Garis waktu tempat bahan disusun dari kiri (awal) ke kanan (akhir) |
| Lajur | Satu baris di linimasa. Lajur yang lebih atas tampil di depan. |
| Item | Satu potong bahan di lajur (satu video, satu teks, satu animasi) |
| Garis putar | Garis tegak penanda waktu yang sedang ditampilkan |
| Keyframe | Titik "pada detik ini nilainya sekian". Di antara dua titik, nilainya berubah halus. |
| Pangkas | Memendekkan item dari ujung kiri atau kanan |
| Belah | Memotong satu item menjadi dua di garis putar |
| Hapus beriak | Menghapus item dan menggeser item sesudahnya untuk menutup celah |
| Salinan sunting | Versi kecil sebuah video, khusus untuk pratinjau yang ringan |
| Render / ekspor | Mengubah proyek menjadi berkas MP4 jadi |
| Komposisi | Kode yang "menggambar" seluruh proyek bingkai demi bingkai |
| Komponen animasi | Satu animasi siap pakai yang propertinya bisa diatur |
| Skema properti | Daftar hal yang boleh diubah dari sebuah animasi, beserta batasnya |
| Kotak pasir | Ruang tertutup tempat kode yang tidak kita tulis sendiri dijalankan dengan aman |
| Remotion | Pustaka untuk membuat video dari kode React |
| Chrome headless | Chrome tanpa jendela, dipakai mesin untuk menggambar setiap bingkai |
| Mesin Montase | Program Node kecil yang merender dan memeriksa animasi |

## 28. Melanjutkan di sesi baru

Kalau sesi chat berganti, buka sesi baru di repo ini lalu tempel:

```
Lanjutkan pengerjaan Montase. Baca JOB-4.md, mulai dari "Tugas berikutnya" di
Papan status. Ikuti aturan main di bagian 5. Sesudah setiap tugas selesai,
centang tugasnya, perbarui Papan status, lalu commit dan push.
```

Berkas `CLAUDE.md` di akar repo juga menunjuk ke dokumen ini, jadi sesi baru
membacanya sendiri.

**Yang harus selalu benar di dokumen ini:**

- Papan status sesuai keadaan sebenarnya, dan "Tugas berikutnya" menunjuk
  tugas yang benar.
- Setiap tugas yang dicentang punya tanggal dan hash commit.
- Setiap keputusan baru ada di tabel Keputusan.
- Angka hasil ukur ditulis di bagian 24 atau di catatan tugasnya, bukan hanya
  diceritakan di chat.
