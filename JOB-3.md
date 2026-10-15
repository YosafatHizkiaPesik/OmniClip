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
- [ ] **J3-11** Pesan dari server (galat, kabar pekerjaan) mengikuti bahasa
  pilihan (header `Accept-Language`).
  **SEBAGIAN** (15 Oktober 2026, commit e0747ef): mekanismenya selesai
  (`bahasa.py`, middleware + SSE `?lang=`, katalog `kamus_en.py`). Sudah
  terjemah: galat umum, antrean, unduh, transkrip, analisis, render, unggah,
  gerbang tinjau, nilai tambah, punch-in, kesehatan sistem. Belum: temuan
  Analitik/FYP, daftar model/font/suara/tema dari server, pesan cookies,
  pembaruan, sutradara AI, dan galat-galat kecil lain (±200 kalimat).
- [ ] **J3-12** Teks yang dihasilkan AI (draf komentar, judul, caption)
  mengikuti bahasa pilihan atau bahasa video.

## Fase D: sesudahnya

- [ ] **J3-13** Rekam ulang tangkapan dan render ulang video portofolio
  dengan UI berbahasa Inggris.
