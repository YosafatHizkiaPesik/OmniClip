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
  diredam oleh reaksi kamera kini ikut diredam di pratinjau (16 Oktober 2026,
  commit b4712e1), rumusnya sama dengan render.
- [x] **F3-3 retensi YouTube Analytics.** Kodenya selesai 16 Oktober 2026
  (commit b4712e1): tombol "Sambungkan YouTube Analytics" di Akun, kolom
  "Ditonton %" di Analitik. Yang perlu pemilik: nyalakan **YouTube Analytics
  API** di Google Cloud project yang sama, lalu sambungkan (tes 30).
- [ ] **Tiga masalah pembingkaian lama** (bawaan JOB-2). Butuh alat ukur
  bingkai kosong yang dulu dijalankan di luar repo, dengan beban CPU berat;
  sengaja tidak dijalankan tanpa izin pemilik (memori laptop). Video "FANNY"
  di catatannya tidak bisa dipastikan: ada 36 video FANNY di data.
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
- [ ] **(Sebagian, commit 4b1ae6f, b4712e1)** **Mesin lokal bisa memilih potongan iklan atau sisipan** di dalam episode
  podcast (klip demo Diary of a CEO: potongan wawancara CEO Uber di menit 36
  terpilih sebagai klip skor tertinggi saat Gemini tidak terjangkau).
  Bacaan sponsor ("disponsori oleh", "pakai kode", "link di deskripsi",
  "sponsored by", "use code") kini memotong skor kandidat sampai 80%.
  16 Oktober 2026: kandidat yang sebagian besar diucapkan penutur yang jarang
  muncul di episode (sisipan) dipotong 70%. Diperiksa pada klip demo itu
  sendiri: TIDAK tertangkap, karena pemisahan suara menggabungkan suara Dara
  (Uber) ke label pembawa acara. Mengukur ulang pemisahan suaranya berat untuk
  laptop ini; jalur Gemini tidak punya masalah ini.
- [x] **Klip lama tidak punya skor nilai tambah.** Selesai 16 Oktober 2026
  (commit b4712e1): skornya dihitung dari sidecar saat Klip jadi dibuka. Klip
  lama TANPA komentar tetap ditahan gerbang untuk unggah otomatis publik; itu
  memang aturannya.

- [ ] **Kunci Gemini tidak bisa dipakai (15 Oktober 2026, bukan bug kode).**
  17 Oktober 2026: semua proyek di AI Studio pemilik berstatus "Restricted"
  (akun Google Workspace organisasi). Solusi: akun Gmail pribadi, penyedia
  lain di Koneksi AI, atau AI lokal (tes 34-35).
  Kunci 1 menjawab 429 (kuota gratis harian habis), kunci 2 menjawab 403
  "Your project has been denied access" (proyek Google-nya diblokir). Akibatnya
  semua video memakai mesin lokal. Perlu kunci baru dari aistudio.google.com
  dengan proyek Google lain, isi di Pengaturan > Mesin AI. Kartu Partitur
  kini menulis alasannya ("Kuota harian Gemini habis", "Kunci Gemini ditolak
  Google"), bukan hanya "Gemini gagal".

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

### Tambahan JOB-3 (15 Oktober 2026): tampilan seperti YouTube dan dua bahasa

- [x] **14. Beranda cepat.**
  - Langkah: tutup tab OmniClip, buka lagi Beranda. Tekan tombol segarkan
    (ikon putar di kiri topik), lalu gulir ke bawah.
  - Diharapkan: kartu tampil dalam 1-2 detik (kecuali kunjungan pertama
    sesudah aplikasi baru dinyalakan); gulir ke bawah langsung menambah kartu.
- [x] **15. Baris topik.**
  - Langkah: sorot sebuah pil topik; putar roda tetikus di atas baris topik;
    tekan panah kanan/kiri.
  - Diharapkan: pil tidak terpotong; baris bergeser sampai topik terakhir,
    halaman tidak ikut menggulir. (Topiknya kini kategori resmi YouTube, tes 22.)
- [x] **16. Filter pencarian.**
  - Langkah: cari sesuatu, tekan tombol **Filter**, pilih Shorts.
  - Diharapkan: panel filter baru muncul setelah tombol ditekan; tombolnya
    menunjukkan angka 1; "Hapus filter" mengembalikan semuanya.
- [x] **17. Halaman Tonton.**
  - Langkah: buka video dari kartu, tunggu ±10 detik, tekan "Selengkapnya".
  - Diharapkan: tidak ada tombol Kembali/Cari video; deskripsi terbuka utuh
    (bukan cuplikan satu-dua baris); avatar dan nama channel bisa diklik.
- [x] **18. Channel, Langganan, Riwayat.**
  - Langkah: klik nama channel → Ikuti → buka menu Langganan → buka Riwayat.
  - Diharapkan: halaman channel dengan banner, tab Video/Shorts/Live; channel
    muncul di menu samping; video yang dibuka tercatat di Riwayat.
- [x] **19. Ganti bahasa ke English.**
  - Langkah: pilih English di pemilih bahasa header (atau Settings >
    Appearance and language). Buka Beranda, Tonton, Studio (semua tab),
    Klip jadi, Unduhan, Analitik, Akun, Pengaturan, Mesin.
  - Diharapkan: semua menu, tombol, dan penjelasan berbahasa Inggris. Yang
    masih Indonesia hanya: judul/isi video, sebagian teks dari server
    (temuan Analitik, nama tema/suara/font), dan teks buatan AI (J3-12).
- [x] **20. Kabar pekerjaan berbahasa Inggris.**
  - Langkah: dalam mode English, potong satu video jadi klip, lalu render satu
    klip di Studio.
  - Diharapkan: bilah kemajuan bertuliskan "Downloading…", "Finding the most
    interesting moments…", "Rendering clip… 45%", dst.
- [x] **21. Tata letak Akun, Pengaturan, Mesin.**
  - Langkah: buka ketiganya di layar laptop dan di layar sempit (perkecil
    jendela < 900 px).
  - Diharapkan: daftar bagian di kiri, isi satu kolom tanpa lubang kosong; di
    layar sempit daftarnya jadi pil yang bisa digeser.

### Tambahan 15 Oktober 2026 (malam): temuan pemilik dari tes 14-21

- [ ] **22. Topik resmi YouTube.**
  - Langkah: di Beranda tekan Gaming, lalu Musik, Olahraga, Sedang tren.
    Ganti Pengaturan > Tampilan dan bahasa > **Negara konten** ke Amerika
    Serikat, kembali ke Beranda, tekan Gaming lagi.
  - Diharapkan: kotak cari tetap KOSONG; isi Gaming benar-benar video game
    (daftar populer YouTube untuk negara itu); ganti negara = isi ikut
    berganti. Pil "Semua" mengembalikan Beranda biasa.
- [ ] **23. Riwayat pencarian YouTube Anda bersih.**
  - Langkah: cari beberapa kata di OmniClip dan tekan beberapa topik. Buka
    youtube.com > Riwayat > Riwayat penelusuran di peramban yang login.
  - Diharapkan: kata-kata dari OmniClip TIDAK muncul lagi di sana
    (pencarian sekarang dikirim tanpa cookies akun).
- [ ] **24. Avatar channel.**
  - Langkah: gulir Beranda dan hasil cari, perhatikan kartu "SEDANG RAMAI" dan
    video kolaborasi ("X and Y").
  - Diharapkan: foto profil tampil; inisial berwarna hanya untuk channel yang
    memang tidak dikenal.
- [ ] **25. Tempel tautan dari situs lain.**
  - Langkah: Partitur > **Tempel tautan** > tempel tautan TikTok, Instagram
    Reels, atau X > Potong jadi klip.
  - Diharapkan: kartu baru dengan judul dan "pengunggah · TikTok"; tahap Unduh
    berjalan dengan persen; klip bisa dibuka di Studio. Vimeo diblokir
    Internet Positif: pesannya menyarankan VPN.
  - Langkah: **Dari komputer** > Pilih dari komputer ini.
- [ ] **26. Cari klip lagi tidak ikut antre.**
  - Langkah: saat satu video baru sedang dianalisis, buka video LAIN yang
    sudah punya klip > Cari klip lagi > Gemini.
  - Diharapkan: langsung jalan (tidak "menunggu giliran analisis").
- [ ] **27. Unggah sambil pindah halaman.**
  - Langkah: Studio > centang unggah YouTube (Pribadi) > Render > pindah ke
    Beranda > kembali ke Studio, lalu buka Klip jadi.
  - Diharapkan: bilah render muncul lagi di Studio; di Klip jadi ada lencana
    "Mengunggah ke YouTube… N%" lalu berganti tautan ↗ YouTube.

### Tambahan 16 Oktober 2026: sisa JOB-3 dan catatan lama

- [ ] **28. Topik ikut bahasa.** Mode English > Gaming, lalu ganti ke Bahasa
  Indonesia. Diharapkan: isinya berganti (US → Indonesia). Pengaturan >
  Tampilan dan bahasa > Negara konten "Otomatis" mengikuti bahasa; memilih
  negara sendiri mengalahkannya.
- [ ] **29. Bahasa teks AI.** Pengaturan > Klip > Bahasa teks AI = English.
  Potong satu video (butuh kunci Gemini hidup), lalu Studio > Komentar >
  Susun draf AI dan tab Judul. Diharapkan: judul, tagar, alasan, draf
  komentar berbahasa Inggris; "Bacakan (TTS)" memakai suara Inggris (Andrew);
  pilihan suara menampilkan "· English".
- [ ] **30. Retensi YouTube Analytics.** Nyalakan YouTube Analytics API di
  Google Cloud, Akun > Google dan YouTube > Sambungkan YouTube Analytics.
  Diharapkan: Analitik punya kolom "Ditonton" berisi persen per klip yang
  sudah diunggah (angka YouTube biasanya tertunda 1-2 hari).
- [ ] **31. Pratinjau reaksi kamera.** Studio > klip dengan reaksi kamera >
  putar. Diharapkan: suara klip mengecil saat Anda bicara, seperti hasil
  render.
- [ ] **32. Klip lama di Klip jadi.** Diharapkan: klip lama juga
  bertuliskan "Nilai tambah X%".
- [ ] **33. Mode English menyeluruh.** Ulangi tes 19-20; kini termasuk nama
  tema subtitle, font, suara, alasan klip, temuan Analitik, pesan cookies dan
  pembaruan.

### Tambahan 17 Oktober 2026: koneksi AI universal dan AI lokal

- [ ] **34. Koneksi AI.** Pengaturan > Mesin AI > Koneksi AI. Tambah kunci
  (Gemini dari akun Gmail pribadi, atau Groq/Mistral gratis, atau Claude),
  tekan Uji, susun urutannya dengan panah, centang/hapus centang Aktif,
  Jadikan utama, Hapus.
  - Diharapkan: status per koneksi (Bekerja / Ditolak / Kuota habis), yang
    paling atas dan aktif bertanda UTAMA.
- [ ] **35. AI lokal.** Kartu AI lokal OmniClip > Qwen3 4B (sudah terpasang)
  > **Pakai sebagai AI utama**. Tutup tab peramban yang tidak dipakai, lalu
  potong satu video.
  - Diharapkan: kabar "Menyalakan AI lokal dan menilai kandidat klip…",
    lalu kartu Partitur bertuliskan "· AI lokal". Satu video ±5-10 menit
    tambahan. Bila RAM kurang, kabarnya menyebut berapa yang bebas dan
    klip tetap dipilih mesin lokal.
- [ ] **36. Tautan non-YouTube di kotak cari.** Tempel tautan TikTok atau
  Twitch di kotak cari Beranda, buka kartunya.
  - Diharapkan: video diputar dengan pemutar situs itu; tombol "Buka di
    TikTok" dan "Potong jadi klip".

### Tambahan 18 Oktober 2026: preset gaya, warna aksen, hasil AI lokal

- [ ] **37. Ulangi auto-klip dengan AI lokal.** Hasil Qwen3 untuk wawancara
  Ronaldo (Jk9uJRMvBIA) sebelumnya dibuang di 98,8% karena aturan database
  lama. Tekan Cari ulang dengan koneksi AI lokal.
  - Diharapkan: pekerjaan selesai, kartu Partitur bertuliskan "· AI lokal",
    tidak ada galat "CHECK constraint failed".
- [ ] **38. Bilah proses menyebut "AI".** Selama auto-klip berjalan.
  - Diharapkan: tahap bertuliskan "AI", bukan "Gemini".
- [ ] **39. Galeri Gaya berkategori.** Studio → Gaya → Gaya siap pakai.
  - Diharapkan: 24 model dalam Populer, Menyala, Pelat, Gaya huruf, Gerak.
    Klip lama tetap tampil seperti sebelumnya.
- [ ] **40. Warna aksen subtitle.** Pilih model (mis. Kotak sorot, Pendar,
  Label miring), lalu ganti warnanya dari baris Warna aksen atau pemilih
  warna bebas.
  - Diharapkan: modelnya tetap sama, hanya warnanya berganti; huruf di atas
    kotak berwarna tetap terbaca.
- [ ] **41. Kontrol baru di bagian huruf.** Warna garis, Pendar, Jarak huruf,
  Kemiringan, Huruf miring.
  - Diharapkan: pratinjau langsung berubah, dan hasil render sama dengan
    pratinjau (render satu klip pendek).
- [ ] **42. Warna aksen judul.** Studio → Judul → Judul di dalam video (atau
  kartu judul) → pilih tema → klik warna. Tombol "Warna asli" mengembalikan.
  - Diharapkan: pelat/huruf/garis tema berganti warna di pratinjau dan di
    hasil render; huruf di pelat hijau atau kuning berwarna hitam.
- [ ] **43. Studio tidak jatuh saat judul dinyalakan.** Sebelumnya
  menyalakan judul bertema bisa memunculkan "Bagian ini gagal ditampilkan".

### Tambahan 18 Oktober 2026 (lanjutan): subtitle Inggris, susunan game, v1.3.8

- [ ] **44. Preset menyalakan subtitle asli.** Di akun yang subtitle aslinya
  mati (entertainyhp), pilih model di Gaya.
  - Diharapkan: subtitle asli (Inggris) langsung muncul di pratinjau dengan
    model itu; sakelar "Subtitle mati" berubah jadi menyala.
- [ ] **45. Sembunyikan terjemahan di semua klip.** Studio Ronaldo → Subtitle →
  panel Terjemahan → "Sembunyikan terjemahan di semua klip", lalu Simpan.
  - Diharapkan: baris Indonesia hilang dari ke-25 klip; render hanya berisi
    subtitle Inggris.
- [ ] **46. Terjemahan otomatis ikut bahasa aplikasi.** Pengaturan →
  Terjemahan otomatis bertuliskan "Ikuti bahasa aplikasi". Dengan aplikasi
  English, analisis video Inggris baru.
  - Diharapkan: tidak ada subtitle kedua. Dengan aplikasi Indonesia, video
    Inggris tetap mendapat terjemahan Indonesia.
- [ ] **47. Seret pembatas wajah/game.** Klip game (MiawAug klip 2), seret
  garis "wajah 40% · game 60%" di pratinjau, lepas, Simpan, buka ulang.
  - Diharapkan: angkanya bertahan, kedua bidang berubah ukuran, dan render
    mengikuti.
- [ ] **48. Facecam tanpa bingkai tidak hanya kepala.** Studio MiawAug →
  Bingkai → tombol hitung ulang bingkai (kunci lama dibuat sebelum aturan
  baru), lalu buka klip game.
  - Diharapkan: bidang wajah memuat headset utuh dan bahu, bukan kepala saja.
- [ ] **49. Tulis ulang judul dengan AI lokal.** Studio → Judul → "Tulis
  ulang judul & tagar dengan AI" dengan Gemini mati dan AI lokal aktif.
  - Diharapkan: judul baru ditulis oleh koneksi yang tersedia (kabar
    menyebut modelnya), bukan galat "Kunci Gemini belum diisi".

### Tambahan 28 Oktober 2026: hapus klip, pembersihan otomatis, cookies, tampilan proses

- [ ] **50. Tombol hapus di Klip jadi.** Buka Klip jadi.
  - Diharapkan: setiap kartu (termasuk yang punya tombol SRT) punya ikon
    tempat sampah merah di kanan bawah; kotak "pilih" ada di pojok gambar.
- [ ] **51. Unggah tahan putus koneksi.** Unggah beberapa klip ke YouTube
  sekaligus (sebaiknya Pribadi).
  - Diharapkan: tidak ada lagi "EOF occurred in violation of protocol"; bila
    koneksi terputus, unggahan mencoba lagi sendiri dan melanjutkan.
- [ ] **52. Pembersihan otomatis.** Mesin → Ruang & cadangan → Pembersihan
  otomatis. Buka daftarnya, periksa isinya, lalu "Bersihkan sekarang" atau
  nyalakan sakelarnya.
  - Diharapkan: daftar menyebut alasannya (diam N hari / proyek selesai);
    sesudah dibersihkan, membuka proyeknya di Studio menawarkan "Unduh ulang
    video"; analisis dan suntingan tetap ada. Putaran harian berikutnya
    berjalan sendiri.
- [ ] **53. Kartu cookies di pemasangan baru.** Pemasangan baru (terutama
  Windows), buka Beranda.
  - Diharapkan: kartu "Boleh OmniClip memakai sesi YouTube Anda" langsung
    tampil, dengan "Memeriksa browser…" sampai pengujiannya selesai.
- [ ] **54. Peringatan cookies saat YouTube menolak.** Bila unduhan gagal
  dengan verifikasi bot dan cookies mati.
  - Diharapkan: jendela "YouTube meminta bukti bahwa Anda bukan bot" dengan
    tombol "Pakai cookies <browser>".
- [ ] **55. Tampilan proses.** Tempel tautan video baru dan lihat kartunya di
  Partitur.
  - Diharapkan: cincin persen di gambar mini, stepper lima langkah, satu
    baris nama langkah dan persennya, bilah bergaris saat menunggu AI.
- [ ] **56. Log berkas.** Sesudah memakai aplikasi, cek folder data → logs.
  - Diharapkan: ada `omniclip.log`. Bila ada galat aneh (mis. "Error -3 while
    decompressing data"), kirim berkas ini supaya penyebabnya bisa dilacak.

### Jalur fitur unggulan (urutan disarankan, ±30 menit)

Satu video podcast pendek (10-20 menit) cukup untuk semuanya:
**Tempel/klip video → 2 (draf komentar AI) → 12 (reaksi kamera) → 3 (punch-in)
→ 13 (bilah progres) → 5 (render, paling penting) → 6 (nilai tambah) → 7
(unggah Pribadi) → 27.** Butuh kunci Gemini yang hidup: lihat catatan Gemini
di atas.

## Riwayat hasil tes

| Tanggal | Tes | Hasil | Catatan |
|---|---|---|---|
| 15 Okt 2026 | 14-21 (pemilik) | Lolos dengan temuan | Temuan: avatar kadang kosong, kueri topik terlihat di kotak cari dan terikat Indonesia, topik Gaming (English) isinya bukan game, kueri OmniClip masuk riwayat YouTube, kotak tautan Partitur terlalu besar, sebagian kabar masih Indonesia, cari ulang menunggu antrean. Semua dikerjakan (tes 22-27). |
| 12 Okt 2026 | 5 (sebagian, oleh Claude di akun Demo Studio) | Lolos | Klip Kai Cenat dirender lewat `/api/render-clip` dengan komentar pembuka + penutup (kartu teks, bekukan) dan kartu konteks: durasi 26,93 dtk sesuai hitungan, nilai tambah 41% "cukup", gerbang lolos. Klip MrBeast dengan punch-in otomatis: zoom terlihat di titiknya. Suara komentar (rekaman/TTS) belum dicoba di jalur ini. |
| 12 Okt 2026 | Gerbang tinjau (bagian dari 7) | Lolos | `/api/uploads/gerbang`: klip tanpa komentar ditahan dengan alasan "Belum ada komentar…", klip berkomentar lolos. |
