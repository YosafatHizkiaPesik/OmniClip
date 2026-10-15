# UJI-LANGSUNG: yang masih kurang dan yang harus dites pemilik

Dicatat 12 Oktober 2026, sesudah rilis **v1.3.7** (JOB-2 selesai sejauh yang
bisa dikerjakan tanpa pemilik). Berkas ini menjawab dua pertanyaan: "apa yang
masih kurang?" dan "apa yang harus saya tes sendiri?".

Aturan: setiap kali satu tes selesai, centang `[x]`, tulis tanggal dan hasilnya
(lolos, atau apa yang salah). Yang gagal dipindah ke "Yang masih kurang" atau
jadi pekerjaan baru. Rincian tiap fitur ada di `JOB-2.md`.

## Yang masih kurang

- [x] **Pratinjau Studio belum memperlihatkan komentar dan punch-in.**
  Selesai 15 Oktober 2026, commit d123bd2. Kartu konteks dan nama penutur
  ternyata sudah tampil (sisipan Tulisan). Komentar "bekukan" menjeda
  pratinjau selama komentar, "timpa" tampil tanpa menjeda. Suara klip yang
  diredam oleh reaksi kamera BELUM ikut diredam di pratinjau, hanya di render.
- [ ] **F3-3 retensi YouTube Analytics.** Butuh izin `yt-analytics.readonly`
  dan persetujuan ulang setiap akun Google, jadi menunggu pemilik.
- [ ] **Tiga masalah pembingkaian lama** (bawaan JOB-2). Butuh alat ukur
  bingkai kosong yang dulu dijalankan di luar repo, dengan beban CPU berat.
  - Ukur ulang bingkai kosong sesudah commit `06958e0`.
  - Klip 5 Mancing: 6,6% bingkai kosong di 2,0 perpindahan per menit.
  - `reframe.group_people` kehilangan `people_seen` di video FANNY.
- [ ] **Belum diuji dengan layanan sungguhan:**
  - unggahan nyata ke YouTube (menunggu izin pemilik);
  - Pexels (belum ada kunci API).
- [x] **Galat unduhan "open() got an unexpected keyword argument
  'metadata_errors'"** (dilaporkan 15 Oktober 2026, build v1.3.7). Sebabnya
  PyAV 19 menghapus argumen yang dipakai faster-whisper untuk membaca audio.
  Selesai 15 Oktober 2026, commit 0aef7fe: `av>=12,<19`. **Butuh build baru**
  supaya terpasang di aplikasi rilis.
- [x] **Sisipan Tulisan / kartu konteks tidak membungkus baris** (ditemukan
  12 Oktober 2026 saat merender klip demo). Teks panjang, misalnya "Kai Cenat
  shows Tota around the States" pada ukuran 3,2, terpotong di tepi kanvas 9:16.
  Kartu opini komentar sudah dibungkus (satu `drawtext` per baris); sisipan
  Tulisan belum. Selesai 15 Oktober 2026, commit dd992a3: dibungkus per kata,
  maksimal 4 baris, satu `drawtext` per baris.
- [x] **Bingkai menyorot ruang kosong sesaat dan bergerak lambat ke wajah**
  (dilaporkan pemilik 15 Oktober 2026; termasuk kasus IShowSpeed IRL).
  Selesai, commit ff3e070. Diukur pada 6 klip: bingkai kosong 2,59% -> 0,74%,
  luncuran 138 -> 60 bingkai. Sisa terbesar: siaran IRL handheld (3%).
- [ ] **(Sebagian, commit 4b1ae6f)** **Mesin lokal bisa memilih potongan iklan atau sisipan** di dalam episode
  podcast (klip demo Diary of a CEO: potongan wawancara CEO Uber di menit 36
  terpilih sebagai klip skor tertinggi saat Gemini tidak terjangkau).
  Bacaan sponsor ("disponsori oleh", "pakai kode", "link di deskripsi",
  "sponsored by", "use code") kini memotong skor kandidat sampai 80%. Sisipan
  wawancara lain di dalam episode belum bisa dikenali dari teks saja.
- [ ] **Klip lama tidak punya skor nilai tambah.** Skor hanya ada di klip yang
  dirender dengan v1.3.7 ke atas; klip lama tanpa komentar akan ditahan
  gerbang tinjau untuk unggah otomatis ke publik.

## Yang harus dites langsung oleh pemilik

Urutannya sama dengan jalur pemakaian normal.

- [ ] **1. Akun.**
  - Langkah: isi "Gaya komentar Anda" dan teks penutup kanal (misalnya
    "Ikuti @kanal untuk klip lainnya"), lalu muat ulang halaman.
  - Diharapkan: kedua isian masih ada.
- [ ] **2. Studio, tab Komentar.**
  - Langkah: tekan "Susun draf AI".
    - Diharapkan: pembuka, sela, dan penutup menyebut isi klip itu, bukan
      kalimat umum.
  - Langkah: tekan "Rekam suara saya".
    - Diharapkan: peramban minta izin mikrofon, dan rekamannya bisa diputar
      ulang.
  - Langkah: coba juga "Bacakan (TTS)" untuk komentar lain.
  - Langkah: pasang Kartu konteks dan Nama penutur.
    - Diharapkan: kotak "Nilai tambah" bertuliskan "cukup".
- [ ] **3. Tab Bingkai.**
  - Langkah: tekan "Cari momen otomatis", lalu hapus satu titik.
  - Diharapkan: muncul daftar momen dengan alasan "suara melonjak N dB".
- [ ] **4. Tab Batas.**
  - Langkah: pada klip berpotongan lebih dari satu, pilih Sambungan "Redup
    sekejap".
- [ ] **5. Render klip itu, lalu tonton hasilnya (paling penting).**
  - Jalur Studio → render dengan data pemilik belum pernah dicoba utuh.
  - Diharapkan:
    - gambar berhenti saat komentar diucapkan, lalu klip lanjut;
    - suara komentar sekeras suara klip;
    - punch-in hanya membesarkan gambar, subtitle tetap ukurannya;
    - teks penutup kanal muncul di akhir.
- [ ] **6. Klip jadi.**
  - Diharapkan: klip barusan bertuliskan "Nilai tambah X%" berwarna hijau.
- [ ] **7. Unggah ke YouTube sebagai Pribadi** (bila pemilik mengizinkan).
  - Diharapkan, di YouTube Studio:
    - deskripsi memuat kredit sumber;
    - kategorinya benar;
    - bila memakai TTS, label "konten diubah atau sintetis" menyala.
- [ ] **9. Bingkai wajah (sesudah build baru).**
  - Langkah: buka klip podcast yang sering berganti kamera dan satu klip
    vlog/IRL, putar pratinjau dan render.
  - Diharapkan: saat kamera memotong, kotak langsung di wajah tanpa meluncur;
    wajah yang bergerak cepat tetap di dalam kotak.
- [ ] **10. Unduh + transkrip lokal (sesudah build baru).**
  - Langkah: auto-clip video yang tidak punya caption.
  - Diharapkan: tidak ada lagi galat "unexpected keyword argument
    'metadata_errors'".
- [ ] **11. Pratinjau komentar dan punch-in.**
  - Langkah: di klip yang punya komentar pembuka + sela dan titik punch-in,
    putar pratinjau dari awal.
  - Diharapkan: kartu pembuka muncul dan gambar diam dulu, lalu klip jalan;
    di detik sela gambar berhenti lagi; di titik punch-in gambar membesar
    sekejap tanpa subtitle ikut membesar.
- [ ] **12. Reaksi kamera.**
  - Langkah: tab Komentar, "Nyalakan kamera", izinkan kamera dan mikrofon,
    "Rekam dari 00:00", bicara 5-10 detik, "Berhenti". Pakai headset.
  - Diharapkan: muncul "Reaksi 00:00 · N dtk", wajah Anda tampil di pojok
    pratinjau, nilai tambah naik. Sesudah render: wajah di pojok, suara Anda
    jelas, suara klip mengecil selama Anda bicara.
- [ ] **13. Bilah progres.**
  - Langkah: tab Komentar, "Bilah progres: Di bawah", putar lalu render.
  - Diharapkan: garis kuning tipis terisi dari kiri ke kanan sampai penuh di
    akhir klip, juga selama gambar ditahan untuk komentar.
- [ ] **8. (Opsional) Pexels.**
  - Langkah: isi kunci API gratis di tab Sisipan, cari gambar, pasang satu.
  - Diharapkan: gambar masuk sebagai sisipan 3 detik di posisi pemutar.

## Riwayat hasil tes

| Tanggal | Tes | Hasil | Catatan |
|---|---|---|---|
| 12 Okt 2026 | 5 (sebagian, oleh Claude di akun Demo Studio) | Lolos | Klip Kai Cenat dirender lewat `/api/render-clip` dengan komentar pembuka + penutup (kartu teks, bekukan) dan kartu konteks: durasi 26,93 dtk sesuai hitungan, nilai tambah 41% "cukup", gerbang lolos. Klip MrBeast dengan punch-in otomatis: zoom terlihat di titiknya. Suara komentar (rekaman/TTS) belum dicoba di jalur ini. |
| 12 Okt 2026 | Gerbang tinjau (bagian dari 7) | Lolos | `/api/uploads/gerbang`: klip tanpa komentar ditahan dengan alasan "Belum ada komentar…", klip berkomentar lolos. |
