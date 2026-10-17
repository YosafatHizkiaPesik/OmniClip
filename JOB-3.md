# JOB-3: OmniClip seperti YouTube, dan dua bahasa

Diminta pemilik 15 Oktober 2026:

- tampilan beranda dan channel semirip mungkin dengan YouTube (avatar
  channel, halaman channel, ikuti channel, halaman tonton, riwayat, filter),
  dengan fitur klip tetap ada dan tanpa tombol suka;
- header tanpa tulisan "Mesin Gemini + mesin lokal", menu dirapikan;
- banyak pilihan bahasa, karena aplikasi akan dipasarkan ke luar negeri.
  Video portofolio kemarin bernarasi Inggris tapi UI-nya masih Indonesia.

Keputusan pemilik:
- Bahasa: **English + Indonesia** dulu. Struktur terjemahan disiapkan supaya
  bahasa lain tinggal menambah satu berkas kamus.
- Fitur YouTube: **halaman channel, ikuti channel, halaman tonton lengkap,
  riwayat + filter pencarian** (keempatnya).
- Menu: **seperti YouTube**, dikelompokkan.
- Urutan: **header + menu + YouTube dulu, bahasa sesudahnya.** Teks baru
  langsung ditulis lewat sistem terjemahan supaya tidak diterjemahkan dua kali.

Format centang sama dengan JOB-2: `- [x] **J3-n** ... (selesai <tanggal>,
commit <hash>)`. Hash = commit kodenya; centangan ikut commit berikutnya.

## Fase A: fondasi dan kerangka

- [x] **J3-1** Sistem terjemahan: `lib/i18n.js` (kamus `id` dan `en`, fungsi
  `t()`, hook `useT`), pilihan bahasa di Pengaturan dan di menu akun,
  disimpan per peramban + setelan server. Bawaan mengikuti bahasa peramban.
  (selesai 15 Oktober 2026, commit d1d5b1c) Bawaan masih Indonesia sampai
  Fase C selesai; pilihan bahasa di header. Server belum memakai
  Accept-Language (J3-11).
- [x] **J3-2** Header: hapus "Mesin Gemini + mesin lokal". Menu samping gaya
  YouTube: Beranda, Langganan, Riwayat / Studio Anda (Partitur, Klip jadi,
  Analitik, Unduhan) / Langganan (avatar channel) / Akun, Pengaturan, Mesin.
  Mode ringkas (ikon saja) di layar sempit.
  (selesai 15 Oktober 2026, commit d1d5b1c) Kotak cari dengan dropdown
  riwayat dipindah dari Beranda ke header. Mode ringkas: bilah bawah di
  layar < 900 px berisi menu utama dan Studio.
## Fase B: YouTube

- [x] **J3-3** Avatar channel di kartu video; avatar dan nama channel bisa
  diklik ke halaman channel.
  (selesai 15 Oktober 2026, commit d1d5b1c) Satu panggilan per layar;
  YouTube Data API bila ada kunci, yt-dlp bila tidak; disimpan seminggu.
- [x] **J3-4** Halaman channel: banner, avatar, nama, @handle, subscriber,
  jumlah video, tab Video / Shorts / Live, urutkan Terbaru / Populer, tombol
  "Ikuti" dan "Klip video ini" di tiap kartu.
  (selesai 15 Oktober 2026, commit d1d5b1c) Tab yang tidak dimiliki
  channel (Live) tampil kosong, tidak galat. "Populer" diurutkan dari
  jumlah tayangan karena YouTube tidak menyediakan urutan lewat yt-dlp.
- [x] **J3-5** Ikuti channel (Langganan) per akun OmniClip, disimpan lokal:
  daftar di menu samping, halaman Langganan berisi video terbaru dari
  channel yang diikuti.
  (selesai 15 Oktober 2026, commit d1d5b1c) Feed bergiliran antar channel:
  daftar datar yt-dlp tidak membawa tanggal unggah.
- [x] **J3-6** Halaman tonton lengkap: video terkait di samping, deskripsi yang
  bisa dibuka, info channel + Ikuti, tombol klip yang jelas.
  (selesai 15 Oktober 2026, commit d1d5b1c) "Video lain" = 6 video channel
  yang sama lalu hasil pencarian terkait.
- [x] **J3-7** Riwayat tontonan per akun + filter pencarian (durasi, tanggal
  unggah, jenis: video / shorts / live, urutan).
  (selesai 15 Oktober 2026, commit 29bfb8e) Riwayat tontonan di commit
  d1d5b1c; filter jenis lewat parameter `sp` YouTube, semua filter tampil
  sebagai pil. Sekalian (commit 63a3e61): beranda tidak pecah lagi ("t is
  not a function" karena variabel lokal `t`), tombol topik jadi pil
  berikon, batas tunggu feed 75 detik.
## Fase C: seluruh UI dua bahasa

- [x] **J3-8** Terjemahkan kerangka, beranda, channel, tonton, Klip jadi,
  Unduhan, Analitik.
  (selesai 15 Oktober 2026, commit 3c79412) Termasuk menu
  akun, kotak galat, kemajuan pekerjaan, grafik harian. Tanggal dan angka
  ikut bahasa (`lokal()`, `angka()`). Tes `i18n.test.js` menjaga: kunci id
  dan en sama, setiap `t('kunci')` ada di kamus, isian `{nama}` cocok.
  Tes penjaga backend membaca komponen + kamus lewat `tests/teks_ui.py`.
  Kalimat yang dibuat server (temuan analitik, alasan nilai tambah, pesan
  galat) masih Indonesia sampai J3-11.
- [x] **J3-9** Terjemahkan Studio (semua panel).
  (selesai 15 Oktober 2026, commit 29f7951; bertahap sejak 1757b90) Partitur,
  editor, semua tab, linimasa, pratinjau, bilah proses. Tabel konstanta
  (mode bingkai, preset, tema subtitle, gaya kartu, pasangan warna)
  menyimpan kunci kamus. Penjaga baru di i18n.test.js: tidak ada variabel
  lokal bernama `t` di berkas yang memakai useT(), dan literal kunci di
  tabel konstanta harus ada di kamus. Yang masih Indonesia karena datang
  dari server (J3-11): daftar font, tema judul, suara pembaca, alasan
  bingkai/punch-in, pesan pekerjaan.
- [x] **J3-10** Terjemahkan Akun, Pengaturan, Mesin, formulir unggah.
  (selesai 15 Oktober 2026, commit 76ef58a; bertahap sejak ae45bee)
  Diminta pemilik di tengah jalan: halaman setelan penuh ruang kosong. Ketiga
  halaman kini memakai `HalamanSetelan.jsx`: daftar bagian di kiri
  (`?bagian=` di alamat), isi satu bagian dalam satu kolom; di layar sempit
  daftarnya jadi pil. Pilihan bahasa juga ada di Pengaturan > Tampilan dan
  bahasa. Termasuk kunci aplikasi, pemilih folder, kartu cookies di Beranda,
  pesan galat `api.js`. `tebal()`: `**kata**` di kamus dirender tebal.
- [x] **J3-11** Pesan dari server (galat, kabar pekerjaan) mengikuti bahasa
  pilihan (header `Accept-Language`).
  (selesai 16 Oktober 2026, commit 07d15ce; bertahap sejak e0747ef)
  Mekanisme `bahasa.py` + katalog `kamus_en.py` (±650 kalimat), dikumpulkan
  otomatis dari literal di seluruh backend lalu diperiksa lewat pemindaian
  semua endpoint GET dalam mode English. Pesan yang disusun dari potongan
  diterjemahkan lewat templat berantai `{sisa}`. Isi milik pengguna (kata
  transkrip, judul, caption) tidak pernah disentuh: `bahasa.LEWATI`. Yang
  sengaja tidak diterjemahkan: nilai id internal (`kartu-putih`, `pilih-klip`).
- [x] **J3-12** Teks yang dihasilkan AI (draf komentar, judul, caption)
  mengikuti bahasa pilihan atau bahasa video.
  (selesai 16 Oktober 2026, commit 07d15ce) `services/bahasa_ai.py`; setelan
  per akun Pengaturan > Klip > Bahasa teks AI (ikut antarmuka / ikut video /
  Indonesia / English). Bahasa antarmuka ikut tersimpan di muatan pekerjaan
  (`bahasa_ui`). Semua prompt (pilih klip, judul, batas, caption, komentar,
  tema, sutradara) memakai bahasa keluaran itu. Suara Microsoft English
  ditambahkan; teks Inggris otomatis dibacakan suara Inggris.
- [x] **Bawaan bahasa** mengikuti peramban (16 Oktober 2026, commit 07d15ce).
  Negara konten ikut bahasa antarmuka kecuali dipilih sendiri (laporan
  pemilik: topik mode Indonesia sama dengan English).

## Temuan pemilik dari uji 14-21 (15 Oktober 2026 malam)

Semua dikerjakan; uji langsungnya tes 22-27 di UJI-LANGSUNG.md.

- Topik Beranda = kategori resmi YouTube (`chart=mostPopular` per kategori,
  negara konten dari peramban atau Pengaturan), alamat `?topik=`, kotak cari
  tetap kosong. Tanpa kunci YouTube Data API: pencarian nama kategori.
- Pencarian tanpa cookies: kueri OmniClip tidak lagi masuk riwayat
  penelusuran YouTube pemilik.
- Kolam Beranda umum mengikuti bahasa (English: podcast/interview
  internasional); daftar ramai mengikuti negara konten.
- Avatar: `channel_id` yang kosong diisi dari kartu sejenis, ingatan
  nama→id, atau channel pertama video kolaborasi.
- Partitur: kartu tautan besar diganti dua tombol kecil. "Tempel tautan"
  menerima situs apa pun yang dikenal yt-dlp (`/impor/tautan`, video
  `KANAL_TAUTAN`, diunduh tahap unduh pipeline).
- Alasan Gemini gagal dibedakan (kuota habis / kunci ditolak / tidak sah /
  sibuk). Kunci pemilik sendiri: 429 dan 403 "project denied access".
- "Cari klip lagi" dengan transkrip + audio tersimpan tidak menunggu giliran
  analisis; giliran diambil hanya bila perlu Whisper/pemisahan penutur.
- Unggahan yang sedang berjalan tampil di Klip jadi dengan persennya.

## Lepas dari ketergantungan API (17 Oktober 2026)

Semua proyek Google AI Studio pemilik berstatus "Restricted". Diminta: AI
lokal yang bagus dan ringan, pengaturan API universal (Gemini, OpenRouter,
Claude, dan lainnya) dengan pilihan mana yang utama, dan tautan non-YouTube
yang bisa diputar.

- `services/koneksi_ai.py`: daftar koneksi berurutan (yang teratas dan aktif
  = utama). Penyedia: gemini, openrouter, anthropic (SDK `anthropic`,
  `penyedia_anthropic.py`), openai, groq, mistral, deepseek, cerebras, kustom
  (Ollama/LM Studio), lokal. Kunci lama dimigrasikan; `.env` tampil sebagai
  koneksi bersumber env. Pemilihan klip (pipeline), komentar, caption, tema,
  dan sutradara mengikuti urutan itu.
- `services/ai_lokal.py`: llama.cpp b11390 + GGUF (Qwen3 4B disarankan,
  Qwen2.5 3B, Qwen2.5 1.5B), semuanya dipatok sha256; menyala saat dipakai,
  mati sesudah 90 dtk menganggur, menolak bila RAM bebas kurang, nice 10.
  Diuji pada wawancara 78 menit: Qwen3 4B memilih 8 klip dengan judul spesifik
  dalam ±8 menit; Qwen2.5 3B lebih cepat tapi judulnya seragam.
- Halaman Tonton: pemutar sematan resmi untuk TikTok, Instagram, Vimeo,
  Dailymotion, Facebook, Twitch, Bilibili; klip lewat /impor/tautan.

## Fase D: sesudahnya

- [ ] **J3-13** Rekam ulang tangkapan dan render ulang video portofolio
  dengan UI berbahasa Inggris.
