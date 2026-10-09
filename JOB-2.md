# JOB-2: Klip yang lolos algoritma dan monetisasi YouTube

Dokumen pelacak. **Setiap sesi kerja: baca berkas ini dulu, kerjakan butir
berikutnya, lalu centang** dengan format:

```
- [x] **F0-1** ... (selesai 10 Oktober 2026, commit abc1234)
```

Butir yang dikerjakan sebagian tetap `- [ ]`, dengan keterangan
`**SEBAGIAN:**` di bawahnya. Urutan yang disepakati pemilik: **Fase 0, lalu
Fase 1**, baru Fase 2 dan 3.

---

## Kenapa JOB-2 ada

Pemilik melaporkan 9 Oktober 2026 bahwa klip hasil auto-clip OmniClip tidak
direkomendasikan dan tidak masuk algoritma YouTube. Penyebabnya terbaca di kode,
bukan ditebak:

- Klip OmniClip adalah **potongan + bingkai + subtitle**. Tidak ada satu pun
  lapisan komentar atau opini di badan klip. TTS hanya membaca kartu judul
  (`services/tts.py`, dipanggil hanya dari `titlecard.plan_card`). Ini persis
  kategori "klip tanpa narasi tambahan" di kebijakan *Reused Content* YPP.
- Gemini sudah menulis `konteks` per klip (skema `gemini._build_schema`), tapi
  medan itu **dibuang** di `gemini._apply_selections` dan tidak pernah sampai ke
  video.
- Unggahan **tanpa kredit sumber sama sekali**: deskripsi bawaan
  `{judul}\n\n{hashtag}` (`services/profil.py`, `services/unggah.deskripsi`),
  padahal judul dan kanal sumber ada di tabel `videos`.
- **Tidak ada gerbang tinjau**: render yang dimulai orang bisa langsung naik
  publik tanpa `fyp.periksa` (`unggah.setelah_render`). **Tidak ada batas
  harian**; hanya jeda 90 detik antar unggahan.
- `categoryId` dikunci `"22"` dan tidak ada label konten sintetis
  (`google_upload.upload_to_youtube`).

**Catatan jujur soal izin.** Pemilik menjawab 9 Oktober 2026: belum ada izin
dari kreator mana pun yang diklip. Tanpa izin, klaim Content ID bisa
mengalihkan pendapatan klip ke pemilik aslinya, setransformatif apa pun
klipnya. Pekerjaan di JOB-2 memperbesar peluang klip direkomendasikan dan lolos
peninjauan YPP, tapi tidak menghapus risiko itu. Yang menghapusnya hanya izin.

---

## Fase 0: Keamanan kanal

Murah, dan mengurangi risiko terbesar lebih dulu.

- [x] **F0-1** Simpan metadata sumber lengkap: `channel_id`, URL, lisensi
  (medan `license` dari yt-dlp), di tabel `videos` dan sidecar klip
  (`repos/media.py`, `ytdlp.get_video_info`). Sekarang `channel_id` kosong
  karena `get_video_info` tidak mengembalikannya.
  (selesai 9 Oktober 2026, commit fccb54e) Baris lama yang `channel_id`-nya
  kosong terisi sendiri saat video itu diambil ulang; tidak ada pengisian massal.
- [x] **F0-2** Baris kredit otomatis di deskripsi unggahan:
  `Sumber: <judul> oleh <kanal>, <url>`. Bisa diubah lewat templat profil
  (`{sumber}` di templat, `unggah.deskripsi`).
  (selesai 9 Oktober 2026, commit 1cc9ef8) Unggah otomatis dan formulir manual
  memakai `unggah.deskripsi` yang sama; templat lama tanpa `{sumber}` tetap
  mendapat kredit di akhir; bisa dimatikan per profil (`kredit: false`).
- [x] **F0-3** Peringatan risiko hak cipta saat menyiapkan unggahan. Tidak
  memblokir apa pun. Satu medan "izin" per kanal sumber (bawaan: belum), supaya
  kelak bisa diisi saat izin didapat dan peringatannya hilang untuk kanal itu.
  (selesai 9 Oktober 2026, commit 5829d9b) Tampil di formulir unggah dan di
  Siapkan terbit. Izin dicatat pada nomor DAN nama kanal, jadi klip lama tanpa
  nomor kanal ikut terbaca. Belum ada izin yang tercatat untuk kanal mana pun.
- [ ] **F0-4** Gerbang tinjau sebelum unggah PUBLIK: `fyp.periksa` + skor nilai
  tambah (F3-1) + kredit ada. Unggah otomatis yang tidak lolos gerbang turun ke
  *private*, dengan alasannya dicatat.
- [ ] **F0-5** Batas unggah per hari per kanal (setelan profil), dipaksa di
  jalur penjadwalan `unggah._jam_tayang`.
- [ ] **F0-6** `categoryId` dipilih (Hiburan 24, Game 20, dan seterusnya),
  bukan dikunci 22. Tebakan awal dari jenis video (gameplay atau bukan).
- [ ] **F0-7** Label konten sintetis saat narasi TTS dipakai. **Verifikasi dulu
  nama medan `status.containsSyntheticMedia` di dokumentasi YouTube Data API**
  sebelum dipasang.

## Fase 1: Komentar dan opini

Inti "nilai tambah" menurut kebijakan YPP: komentar yang menambah nilai di atas
klip orang lain.

- [ ] **F1-1** Simpan `konteks` dari Gemini ke klip (sekarang dibuang).
- [ ] **F1-2** Prompt baru: draf opini atau komentar pendek per klip dari
  transkrip + `konteks`, dalam gaya kanal pengguna. **Draf, bukan final**: narasi
  generik yang sama di semua klip justru tanda "produksi massal".
- [ ] **F1-3** Lajur "Komentar" di Studio: teks bisa disunting dan ditempatkan
  di waktu tertentu (sebelum klip, di jeda, sesudah punchline).
- [ ] **F1-4** Suara komentar, dua jalan (pilihan pemilik: keduanya):
  rekam mikrofon langsung di Studio (MediaRecorder, disimpan lewat
  `aset.simpan_unggahan`) didahulukan; TTS (`tts.synthesize`, Piper atau Edge)
  sebagai cadangan. Memakai TTS otomatis menyalakan label konten sintetis
  (F0-7).
- [ ] **F1-5** Render: audio komentar dicampur dan suara asli diredam (pakai
  `amix` + `rumus_redam` di `render.py`), dengan opsi membekukan gambar atau
  zoom pelan selama komentar.
- [ ] **F1-6** Kartu opini teks di layar (sisipan `jenis: teks`) untuk yang
  tidak mau bersuara.

## Fase 2: Transformasi visual

- [ ] **F2-1** Punch-in zoom dari lonjakan energi atau tawa
  (`media.energy_track`, `sutradara.cari_kejutan`, `momen.cari_momen`), sebagai
  kunci bingkai yang bisa disunting. Sekarang zoom hanya statis.
- [ ] **F2-2** Lower-third nama penutur (dari diarisasi + nama yang diketik
  sekali per video).
- [ ] **F2-3** Kartu konteks atau fakta otomatis dari `konteks` (siapa, sedang
  membahas apa), untuk penonton yang tidak tahu asal klipnya.
- [ ] **F2-4** Transisi antar segmen (`xfade` / `acrossfade`) di
  `render._build_segment_graph`. Sekarang klip multi-segmen potong keras.
- [ ] **F2-5** Intro dan outro bermerek per profil (sisipan tetap di awal dan
  akhir). Identitas seri kanal; sekarang belum ada intro/outro sama sekali.
- [ ] **F2-6** (Opsional) Saran gambar stok Pexels/Pixabay dari kata kunci,
  disetujui orangnya sebelum dipasang.

## Fase 3: Pengukuran

- [ ] **F3-1** Skor nilai tambah per klip: detik yang diberi lapisan buatan
  pengguna (komentar, kartu, sisipan) dibagi durasi. Tampil di Studio, disimpan
  di sidecar, dipakai gerbang F0-4.
- [ ] **F3-2** Analitik membandingkan klip dengan dan tanpa komentar (pakai
  `analitik._temuan_terbukti`, butuh minimal 8 video terbaca).
- [ ] **F3-3** (Opsional) YouTube Analytics API untuk retensi penonton. Butuh
  izin `yt-analytics.readonly` dan persetujuan ulang setiap akun.

## Bawaan dari pekerjaan sebelumnya

Dicatat di sini supaya tidak hilang.

- [ ] Ukur ulang bingkai kosong sesudah commit `06958e0` (subjek dan titiknya
  sejalan). Sebelum: NESSIE JUDGE 3,35%, Pundit 1,42%, Mancing 1,06%, Dokter
  Tirta 0,17%, Ujian 0,11%.
- [ ] Bingkai kosong pada perpindahan rendah: Mancing klip 5, 6,6% di 2,0
  perpindahan per menit. Sebabnya belum diketahui.
- [ ] `reframe.group_people` kehilangan `people_seen` di rentang panjang (video
  FANNY), walau YuNet mendeteksi wajahnya di 0,90-0,92.

---

# Lampiran: saran Gemini dan penilaiannya

Isi asli `Job2.md` (saran Gemini, 9 Oktober 2026), dipindah ke sini dan dinilai
terhadap apa yang sudah ada di OmniClip.

## Penilaian

| Saran | Keadaan di OmniClip | Sikap |
|---|---|---|
| A. Narasi/voiceover AI | Tidak ada. TTS ada, tapi hanya untuk kartu judul | **Diambil dengan koreksi** (F1): AI menulis draf, orangnya menyunting; suara sendiri didahulukan |
| B. B-roll otomatis | Sisipan lengkap (`build_sisipan_graph`, amix, redam), tanpa pencarian otomatis | **Diambil sebagian** (F2-3, F2-6): kartu konteks dulu, gambar stok opsional |
| C. Tracking + reactive zoom | Pelacakan wajah, facecam, sutradara AI sudah ada; punch-in berbasis suara belum | **Bagian yang kurang diambil** (F2-1) |
| D. Kinetic typography | Sudah ada: 15 animasi, 26 tema, sorot per kata, tema dipilih AI | Hanya tambahan kecil bila perlu |
| E. Procedural hashing | Tidak ada | **Ditolak**, lihat di bawah |
| Acak transisi agar tidak terdeteksi massal | Tema sudah dipilih per isi klip | Variasi **mengikuti isi**, bukan diacak untuk mengelabui |

**Kenapa Fitur E ditolak.** Menambah *noise* tak terlihat, menggeser warna 2%,
dan menaikkan *pitch* 1% tidak mengubah apa yang ditonton orang. Gunanya hanya
menyamarkan duplikat dari sistem deteksi, dan itu bertentangan dengan
kesimpulan dokumen Gemini sendiri: "YouTube menghargai transformasi, bukan
sekadar duplikasi". Content ID tetap mengenali audio yang digeser sekecil itu,
dan taktik pengelakan termasuk yang memicu penghentian kanal, bukan sekadar
demonetisasi.

## Saran asli Gemini (salinan utuh dari `Job2.md`)

Disalin kata per kata, tanpa dua baris penutup balasan obrolannya.

## Panduan Lengkap: Kebijakan YouTube, Pencegahan, dan Arsitektur AI Auto-Clipping
**Berdasarkan Pembaruan Kebijakan Monetisasi YouTube (YouTube Partner Program)**

Dokumen ini berisi panduan pengembangan AI *auto-clipping* agar hasil yang diproduksi (khususnya YouTube Shorts) tetap memenuhi syarat kelayakan monetisasi Program Partner YouTube (YPP) dan terhindar dari pelanggaran *Reused Content* (Konten yang Digunakan Ulang).

---

### 1. Ketentuan Resmi YouTube Terkait Monetisasi & Orisinalitas

Berdasarkan pedoman resmi dari laman Bantuan YouTube (Google Support), YouTube mewajibkan konten yang dimonetisasi harus orisinal dan "autentik". Algoritma dan peninjau manual YouTube akan mengevaluasi keseluruhan *channel* berdasarkan **Kebijakan Konten yang Digunakan Ulang (*Reused Content*)** dan **Konten Berulang (*Repetitious Content*)**.

#### 🚫 Apa yang TIDAK BISA Dimonetisasi (Melanggar Aturan):
*   **Klip Tanpa Narasi Tambahan:** Menggabungkan klip dari acara favorit atau video orang lain yang diedit menjadi satu dengan sedikit atau tanpa narasi sama sekali.
*   **Kompilasi Media Sosial:** Video pendek (*Shorts*) yang sekadar dikompilasi dari situs web media sosial lain tanpa modifikasi.
*   **Modifikasi Minimal:** Konten yang diunduh atau disalin dari sumber *online* lain **tanpa modifikasi substantif**.
*   **Reaksi Pasif:** Konten yang tayangannya didapatkan sebagian besar dari reaksi non-verbal (tanpa komentar suara yang menambahkan nilai).
*   **Produksi Massal (Generic/Template):** Konten yang diproduksi secara massal oleh mesin/sistem (*mass-produced*), generik, dan repetitif, yang dibuat semata-mata untuk mendapatkan *views* tanpa memberikan nilai edukasi atau hiburan yang unik.

#### ✅ Apa yang BISA Dimonetisasi (Praktik yang Diizinkan):
*   **Kritik & Ulasan:** Menggunakan klip video orang lain untuk keperluan ulasan kritis.
*   **Modifikasi Substantif (Visual & Audio):** Rekaman video editan dengan efek audio dan visual yang ditambahkan di atas video asli, yang **menunjukkan proses pengeditan substantif** dan menjadikannya unik untuk *channel* tersebut.
*   **Penambahan Alur Cerita / Komentar:** Rekaman editan dari kreator lain tempat Anda menambahkan alur cerita (*storyline*) atau komentar suara (*voiceover*).
*   **Perombakan Konteks:** Mengambil adegan tertentu lalu menulis ulang dialognya atau mengubah sulih suaranya secara keseluruhan.

**Penting tentang Penggunaan AI:** 
YouTube tidak melarang penggunaan AI untuk membuat *voiceover*, *script*, atau keseluruhan video, **asalkan** hasil akhirnya tidak repetitif/generik dan memberikan nilai tambah yang signifikan. Selain itu, YouTube mewajibkan kreator untuk memberikan label/keterangan jika konten tersebut diubah atau dibuat secara sintetis (AI-generated) agar audiens tidak tertipu.

---

### 2. Langkah-Langkah Pencegahan Agar Lolos Monetisasi (Bagi Pengguna AI)

Sebagai *developer*, Anda harus mengedukasi pengguna (klipper) dan merancang sistem AI Anda agar mencegah praktik "spam potong-tempel".

1.  **Hindari Konsep "Zero-Touch Generation":** Jangan membuat AI yang 100% berjalan sendiri memotong 50 video dan langsung mengunggahnya ke YouTube. Berikan ruang bagi pengguna (manusia) untuk melakukan pratinjau, menambahkan opini teks mereka, atau menyisipkan *voiceover* opini sebelum dirender.
2.  **Fokus pada "Added Value":** Mesin tidak boleh hanya melakukan pemotongan (*cutting*). Mesin harus melakukan "transformasi". Jika video aslinya adalah *podcast* statis, AI harus mengubahnya menjadi penceritaan visual yang dinamis.
3.  **Variasi Metadata dan Visual:** Mencegah algoritma mendeteksi konten sebagai produksi massal (*spam*) dengan cara mengacak transisi, animasi teks, dan rasio letak (*layout*) untuk setiap video yang dihasilkan.
4.  **Gunakan Label Konten Sintetis:** Jika AI Anda secara drastis mengubah suara (menggunakan *voice changer* AI) atau menghasilkan visual baru, sediakan fitur bagi pengguna untuk secara otomatis mencentang kotak "Altered or Synthetic Content" saat melakukan *auto-upload* via YouTube API.

---

### 3. Saran Fitur AI & Stack Teknologi (Arsitektur Auto-Clipping)

Untuk memenuhi syarat "modifikasi substantif" dari YouTube, AI Anda harus dibekali dengan fitur-fitur yang menyerupai keputusan kreatif editor manusia. Berikut adalah ide fitur dan teknologi pendukungnya:

#### Fitur A: Smart Narrative Injector (AI Voiceover & Opini)
**Tujuan:** Memenuhi syarat YouTube yang mengharuskan adanya "narasi/komentar tambahan" pada konten yang digunakan ulang.
*   **Cara Kerja:** Daripada hanya memotong momen lucu, AI akan membuat "Hook" di awal video. Contoh: AI menganalisis klip, lalu men-*generate* suara di awal video: *"Lihat apa yang terjadi ketika [Nama Kreator] ditanya soal ini..."*, baru kemudian klip asli diputar.
*   **Stack Teknologi:**
    *   *Transkripsi:* **OpenAI Whisper** (mengubah audio video asli menjadi teks).
    *   *Pemahaman Konteks:* **LLM (GPT-4 / Claude 3)** (menganalisis teks transkripsi, menemukan klimaks, dan menulis *script* komentar pendek).
    *   *Voiceover Generation:* **ElevenLabs API** atau **Google Cloud Text-to-Speech** (untuk membaca *script* komentar dengan suara natural layaknya narator).

#### Fitur B: Substantive Visual Editing Engine
**Tujuan:** Memenuhi pedoman YouTube terkait "pengeditan visual yang menunjukkan modifikasi substantif".
*   **Cara Kerja:** AI mendeteksi topik yang sedang dibicarakan dan secara otomatis menempelkan elemen visual baru (B-Roll, gambar, atau *overlay*). Misalnya, saat pembicara menyebut "Elon Musk", AI menempelkan foto Elon Musk dengan animasi *pop-up* di atas video asli.
*   **Stack Teknologi:**
    *   *Keyword Extraction:* **spaCy** atau **NLTK** (untuk mengekstrak kata benda/entitas penting dari ucapan).
    *   *Aset Visual Media:* Integrasi dengan **Pexels API, Pixabay API, atau Giphy API** (untuk mencari gambar/video *overlay* secara otomatis berdasarkan *keyword*).
    *   *Compositing (Penggabungan):* **FFmpeg** atau **MoviePy** (Python) untuk merender gambar/B-roll tersebut di atas kanvas video (menggunakan *Picture-in-Picture*).

#### Fitur C: Dynamic Subject Tracking & Reactive Zoom
**Tujuan:** Menghindari kesan video yang diunduh mentah tanpa modifikasi. Membuat visual terasa dioperasikan oleh manusia (*cameraman* digital).
*   **Cara Kerja:** AI selalu menjaga wajah pembicara di tengah layar saat di-*crop* ke rasio vertikal 9:16. Jika ada tawa keras atau nada tinggi, layar otomatis *zoom-in* atau bergetar (*camera shake*).
*   **Stack Teknologi:**
    *   *Face & Object Tracking:* **MediaPipe (Google)** atau **YOLOv8** (untuk melacak *bounding box* wajah dan mempertahankan pusat gravitasi visual).
    *   *Audio Sentiment/Energy Analysis:* **Librosa** (Python) untuk mendeteksi lonjakan volume (dB) yang memicu perintah *zoom* di *keyframe* FFmpeg.

#### Fitur D: Kinetic Typography (Teks Animasi Anti-Template)
**Tujuan:** Mengganti *subtitle* standar (yang mudah ditandai sebagai *spam/template* otomatis) dengan teks yang interaktif dan mewakili emosi.
*   **Cara Kerja:** *Subtitle* muncul per kata (*word-by-word*) seiring ucapan, dengan kata penting (*keyword*) diwarnai secara kontras (misal: kuning/merah). Gaya kemunculan teks diacak (kadang berayun, kadang melompat).
*   **Stack Teknologi:**
    *   *Word-level Timestamp:* **WhisperX** (memberikan *timestamp* milidetik akurat per kata).
    *   *Rendering Animasi Teks:* Dapat menggunakan kombinasi **HTML5/CSS/Canvas (Puppeteer)** yang direkam, atau *library* seperti **Remotion** (React-based video rendering) untuk membuat animasi teks yang lebih kompleks dan organik ketimbang *hardcode* teks biasa.

#### Fitur E: Procedural Hashing & Anti-Repetition
**Tujuan:** Mencegah algoritma mendeteksi dua klip video memiliki struktur *file* / meta yang identik persis dengan video-video dari klipper bot lainnya.
*   **Cara Kerja:** Sistem secara otomatis menambahkan variasi matematis pada hasil *render*. 
*   **Stack Teknologi (via FFmpeg):** 
    *   Menambahkan filter warna mikroskopis (*Color Grading* acak ±2% saturasi).
    *   Menambahkan *noise* tak terlihat (film *grain* sangat transparan).
    *   Memodifikasi *pitch* audio secara sangat halus (misal: +1%). 

---
**Kesimpulan untuk AI Agent / Developer:**
Untuk bertahan sebagai penyedia alat *auto-clipping*, fokuskan pengembangan algoritma bukan pada seberapa **cepat** mesin bisa memotong video, melainkan seberapa **cerdas** mesin bisa "menambahkan opini, visual ekstra, dan efek" (Added Value) ke dalam video tersebut. YouTube menghargai transformasi, bukan sekadar duplikasi.
