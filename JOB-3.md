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

- [ ] **J3-1** Sistem terjemahan: `lib/i18n.js` (kamus `id` dan `en`, fungsi
  `t()`, hook `useT`), pilihan bahasa di Pengaturan dan di menu akun,
  disimpan per peramban + setelan server. Bawaan mengikuti bahasa peramban.
- [ ] **J3-2** Header: hapus "Mesin Gemini + mesin lokal". Menu samping gaya
  YouTube: Beranda, Langganan, Riwayat / Studio Anda (Partitur, Klip jadi,
  Analitik, Unduhan) / Langganan (avatar channel) / Akun, Pengaturan, Mesin.
  Mode ringkas (ikon saja) di layar sempit.

## Fase B: YouTube

- [ ] **J3-3** Avatar channel di kartu video; avatar dan nama channel bisa
  diklik ke halaman channel.
- [ ] **J3-4** Halaman channel: banner, avatar, nama, @handle, subscriber,
  jumlah video, tab Video / Shorts / Live, urutkan Terbaru / Populer, tombol
  "Ikuti" dan "Klip video ini" di tiap kartu.
- [ ] **J3-5** Ikuti channel (Langganan) per akun OmniClip, disimpan lokal:
  daftar di menu samping, halaman Langganan berisi video terbaru dari
  channel yang diikuti.
- [ ] **J3-6** Halaman tonton lengkap: video terkait di samping, deskripsi yang
  bisa dibuka, info channel + Ikuti, tombol klip yang jelas.
- [ ] **J3-7** Riwayat tontonan per akun + filter pencarian (durasi, tanggal
  unggah, jenis: video / shorts / live, urutan).

## Fase C: seluruh UI dua bahasa

- [ ] **J3-8** Terjemahkan kerangka, beranda, channel, tonton, Klip jadi,
  Unduhan, Analitik.
- [ ] **J3-9** Terjemahkan Studio (semua panel).
- [ ] **J3-10** Terjemahkan Akun, Pengaturan, Mesin, formulir unggah.
- [ ] **J3-11** Pesan dari server (galat, kabar pekerjaan) mengikuti bahasa
  pilihan (header `Accept-Language`).
- [ ] **J3-12** Teks yang dihasilkan AI (draf komentar, judul, caption)
  mengikuti bahasa pilihan atau bahasa video.

## Fase D: sesudahnya

- [ ] **J3-13** Rekam ulang tangkapan dan render ulang video portofolio
  dengan UI berbahasa Inggris.
