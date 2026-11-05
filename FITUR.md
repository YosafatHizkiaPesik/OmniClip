# Katalog fitur OmniClip

Daftar SEMUA fitur OmniClip: apa itu, manfaatnya, dan contoh kasus
pemakaiannya. Disusun 5 November 2026 dari kode (`backend/app/services`,
`backend/app/montase`, `frontend/src`) dan catatan JOB-1 sampai JOB-5, untuk
versi sesudah JOB-5 (belum diberi tag; lihat `backend/app/version.py`).

Bagian terakhir ([12](#12-saran-fitur-penunjang)) berisi saran fitur yang
belum dibangun, diurutkan menurut manfaatnya.

## Daftar isi

1. [Gambaran besar](#1-gambaran-besar)
2. [Menjelajah dan mengunduh](#2-menjelajah-dan-mengunduh)
3. [Studio Klip: dari video panjang ke klip pendek](#3-studio-klip-dari-video-panjang-ke-klip-pendek)
4. [Kepatuhan YouTube dan nilai tambah](#4-kepatuhan-youtube-dan-nilai-tambah)
5. [Klip jadi dan unggah](#5-klip-jadi-dan-unggah)
6. [Analitik](#6-analitik)
7. [Montase: penyunting video lengkap](#7-montase-penyunting-video-lengkap)
8. [Montase: orisinalitas dan algoritma (JOB-5)](#8-montase-orisinalitas-dan-algoritma-job-5)
9. [Montase: preset dan templat](#9-montase-preset-dan-templat)
10. [Akun, profil, pengaturan, bahasa](#10-akun-profil-pengaturan-bahasa)
11. [Mesin dan pemeliharaan](#11-mesin-dan-pemeliharaan)
12. [Saran fitur penunjang](#12-saran-fitur-penunjang)
13. [Studi kasus dari awal sampai unggah](#13-studi-kasus-dari-awal-sampai-unggah)

---

## 1. Gambaran besar

OmniClip berjalan di komputer Anda sendiri (server lokal yang dibuka di
peramban). Ada dua studio dengan tujuan berbeda:

| | **Studio Klip** (menu Partitur) | **Montase** |
|---|---|---|
| Untuk apa | Memotong SATU video panjang jadi banyak klip pendek, otomatis | Menyusun video apa pun dari BANYAK bahan, bebas |
| Cara kerja | Mesin memilih momen, membingkai 9:16, memberi subtitle; Anda menyetel | Linimasa banyak lajur seperti CapCut, dengan asisten AI |
| Hasil | Klip pendek vertikal | Bebas: 9:16, 16:9, 1:1, 4:5, ukuran sendiri |

Alur yang paling sering:

```
Cari/tempel tautan → Unduh → Studio Klip (pilih momen, subtitle, komentar)
   → Render → Klip jadi → (opsional) Montase: gabung, narasi, animasi
   → Periksa orisinalitas → Unggah ke YouTube / Drive → Analitik
```

Prinsip yang berlaku di semua fitur otomatis/AI: hasilnya **diusulkan**,
tampil bertanda dan beralasan, dan bisa dihapus satu per satu. Tidak ada yang
diam-diam mengubah karya Anda.

---

## 2. Menjelajah dan mengunduh

| Fitur | Apa dan manfaatnya | Contoh kasus |
|---|---|---|
| **Beranda** | Video yang sedang ramai dan topik pilihan, seperti beranda YouTube. Menemukan bahan tanpa membuka YouTube. | Pagi hari membuka Beranda, melihat video podcast yang baru naik, langsung "Klip video ini". |
| **Kotak cari + riwayat cari** | Cari kata kunci atau tempel tautan (YouTube dan situs lain yang didukung yt-dlp). Filter durasi, tanggal unggah, jenis (video/Shorts/live), urutan. | Mencari "podcast horor" berdurasi > 20 menit dan diunggah minggu ini. |
| **Halaman channel** | Banner, subscriber, tab Video/Shorts/Live, urut Terbaru/Populer, tombol "Klip video ini" di tiap kartu. | Membuka channel kreator yang sudah memberi izin, mengurutkan Populer, memilih video terbaiknya. |
| **Ikuti channel (Langganan)** | Daftar channel yang diikuti per akun OmniClip, dengan feed video terbarunya. | Mengikuti 10 channel sumber tetap; tiap hari cukup buka Langganan. |
| **Halaman tonton** | Pemutar, deskripsi, video terkait, tombol klip. | Menonton dulu untuk memastikan isinya layak diklip. |
| **Riwayat tontonan** | Video yang pernah dibuka, per akun. | Kembali ke video kemarin yang belum sempat diklip. |
| **Unduhan** | Daftar video yang diunduh beserta kemajuannya; pemeriksaan "video berlubang" (aliran rusak) sebelum dipakai. | Mengunduh 5 video sekaligus semalaman. |
| **Cookies YouTube** | Diambil langsung dari peramban atau dari `cookies.txt`, supaya video yang butuh masuk akun bisa diunduh. | Video dengan batas umur gagal diunduh; pasang cookies sekali, lalu berhasil. |
| **Anti dicap bot** | Runtime JavaScript, PO Token, dan pemilihan player client yang menyembuhkan diri sendiri bila YouTube menolak. | YouTube mengubah sesuatu dan unduhan gagal; OmniClip berganti klien sendiri tanpa Anda mengatur apa pun. |

---

## 3. Studio Klip: dari video panjang ke klip pendek

### 3.1 Memahami videonya

| Fitur | Apa dan manfaatnya | Contoh kasus |
|---|---|---|
| **Transkrip** | Caption YouTube (waktu per kata) dulu; bila tidak ada, faster-whisper di CPU. | Video tanpa caption tetap dapat subtitle akurat per kata. |
| **Pemisahan penutur** | Menebak berapa orang bicara dan siapa mengucapkan apa; tiap penutur bisa diberi warna dan nama. | Podcast dua orang: subtitle tamu kuning, pembawa acara putih. |
| **Peristiwa suara** | Mendengar tawa, sorak/tepuk tangan, teriakan. | Momen yang disambut tawa penonton naik peringkatnya. |
| **Teks tertanam** | Menemukan subtitle yang sudah terbakar di gambar sumber, supaya subtitle OmniClip tidak menumpuk. | Anime fansub: subtitle OmniClip otomatis naik di atas teks Jepangnya. |
| **Salinan proksi** | Salinan kecil khusus analisis, supaya pemindaian cepat. | Video 4K dua jam dianalisis tanpa membuat komputer macet. |

### 3.2 Memilih momen

| Fitur | Apa dan manfaatnya | Contoh kasus |
|---|---|---|
| **Pemilih momen lokal (heuristik)** | Memilih momen dari transkrip dan energi suara tanpa internet dan tanpa biaya. | Tidak punya kunci AI; tetap dapat 10 kandidat klip. |
| **Pemilih momen AI** | Gemini, OpenRouter, Claude, atau AI lokal menonton/membaca video dan memilih momen, judul, alasan. Urutan penyedia bisa diatur; bila satu habis kuota, pindah ke berikutnya. | Kuota Gemini habis siang hari; OmniClip memakai OpenRouter tanpa Anda sadari. |
| **Cari ulang** | Meminta kandidat lain dengan arahan ("yang lucu saja"). | Hasil pertama terlalu serius; cari ulang dengan arahan "momen paling lucu". |
| **Klip panjang** | Klip lebih dari 3 menit tetap terbingkai benar: wajah dipindai dari 40 cuplikan tersebar, bukan seluruh video (12 menit: dari ±370 jadi 43 detik). | Membuat potongan 8 menit untuk kanal utama 16:9. |

### 3.3 Membingkai dan menyunting (tab Studio)

| Tab / fitur | Apa dan manfaatnya | Contoh kasus |
|---|---|---|
| **Batas** | Geser awal/akhir klip; untuk klip beberapa potongan, pilih "Sambungan". | Memotong 2 detik basa-basi di awal supaya hook langsung masuk. |
| **Subtitle** | Subtitle karaoke per kata, sunting kata, sensor kata kasar ("anj*ng"), buang gumaman ("eh", "emm"), terjemahan otomatis sebagai subtitle kedua. | Video Inggris: subtitle Inggris tetap, terjemahan Indonesia di bawahnya. |
| **Gaya** | Tema subtitle (huruf, warna, garis, sorot); tema bisa dipilih otomatis sesuai isi klip. | Klip horor otomatis memakai tema gelap bergaris merah. |
| **Bingkai** | Smart reframe 16:9 → 9:16 mengikuti wajah; mode game (facecam di atas, permainan di bawah); kunci bingkai per bagian. | Klip gaming: kamera pemain di atas, layar permainan di bawah, otomatis 23 bagian. |
| **Punch-in** | Gambar membesar sekejap di momen paling keras. | Teriakan kaget jadi lebih terasa. |
| **Sutradara** | Usulan cara membingkai dan efek suara per momen (mis. jumpscare → zoom + efek). AI sutradara bisa menonton klipnya. | Klip horor: tiga jumpscare diberi zoom dan efek suara, tiap usulan bisa dihapus. |
| **Judul** | Kartu judul di awal klip dengan tema (huruf, warna, latar, gerak), bisa dibacakan suara (TTS). | Klip dibuka "KUCING INI BISA NGOMONG?!" dibacakan suara AI. |
| **Komentar** | Draf komentar AI yang Anda sunting, rekam suara sendiri atau TTS, bekukan gambar atau timpa; kartu konteks; nama penutur. Inilah nilai tambah utama menurut kebijakan YouTube. | Di detik 12 gambar membeku, suara Anda menjelaskan kenapa momen itu penting. |
| **Sisipan** | Video, gambar, musik, efek suara dari pustaka; papan suara dari internet; gambar stok Pexels. | Menyisipkan meme "bruh" dan efek suara di momen canggung. |
| **Reaksi kamera** | Rekam wajah dan suara sendiri sambil klip diputar, menempel sebagai gambar-dalam-gambar; suara klip mengecil saat Anda bicara. | Format reaksi: wajah Anda di pojok bawah menanggapi klip. |
| **Rapatkan** | Membuang jeda dan gumaman seperti editor memotong. | Podcast yang lambat jadi 30% lebih pendek dan padat. |
| **Intro/outro bermerek** | Identitas kanal per akun, ditempel di awal/akhir. | Semua klip ditutup logo kanal 1 detik. |

### 3.4 Render

| Fitur | Apa dan manfaatnya | Contoh kasus |
|---|---|---|
| **Render ffmpeg** | Subtitle, bingkai, sisipan, kartu judul, suara digabung jadi MP4. | Render 10 klip sekaligus di antrean. |
| **Encoder GPU** | Memakai GPU bila ada dan terbukti bekerja; x264 bila tidak. | Laptop dengan NVIDIA merender lebih cepat tanpa diatur; bila driver bermasalah, otomatis kembali ke x264. |
| **Laju bingkai** | Ikut sumber atau 30 fps. | Video 60 fps dirender 30 fps supaya berkas kecil. |

---

## 4. Kepatuhan YouTube dan nilai tambah

Kebijakan YouTube menolak konten yang digunakan ulang tanpa tambahan berarti
dan konten yang diproduksi massal. Fitur ini menjaga kanal Anda.

| Fitur | Apa dan manfaatnya | Contoh kasus |
|---|---|---|
| **Skor nilai tambah** | Berapa persen klip berisi lapisan buatan Anda (komentar penuh, sisipan setengah). Subtitle, bingkai, tema tidak dihitung karena otomatis. | Skor 8%: tambahkan komentar 6 detik, skor naik ke "cukup". |
| **Gerbang tinjau** | Unggahan OTOMATIS hanya boleh publik bila lolos: tidak ada temuan berat, ada kredit, nilai tambah cukup. Yang tidak lolos diturunkan ke Pribadi dengan alasannya. | Klip tanpa komentar terunggah sebagai Pribadi; Anda menambah komentar lalu publikasikan. |
| **Pemeriksa sebelum unggah (FYP)** | Hal yang diketahui menurunkan jangkauan: terlalu pendek/panjang, 3 detik pertama sunyi, tanpa subtitle. Tidak menjanjikan FYP. | Peringatan "tiga detik pertama sunyi"; Anda memangkas awal klip. |
| **Kredit sumber** | Kredit video sumber otomatis di deskripsi. | Deskripsi berisi "Sumber: @kanal_asli" tanpa diketik. |
| **Izin per kanal sumber** | Catatan izin dari pemilik video sumber. | Mencatat bahwa kreator X mengizinkan lewat email tanggal sekian. |
| **Gaya komentar Anda** | Contoh gaya bicara Anda, supaya draf komentar AI terdengar seperti Anda. | Draf memakai "gais" dan gaya santai seperti Anda biasa bicara. |
| **Penanda konten sintetis** | Unggahan yang memakai suara AI realistis ditandai `containsSyntheticMedia` sesuai aturan pengungkapan YouTube. | Narasi TTS: kotak pengungkapan konten sintetis terisi otomatis. |

---

## 5. Klip jadi dan unggah

| Fitur | Apa dan manfaatnya | Contoh kasus |
|---|---|---|
| **Klip jadi** | Semua hasil render (Studio dan Montase) di satu tempat: putar, unduh, unggah, hapus. | Memilih 3 klip terbaik minggu ini untuk diunggah. |
| **Unggah ke YouTube dan Drive** | Lewat akun Google yang terhubung; judul, deskripsi, tagar, privasi, kategori. | Unggah langsung tanpa memindah berkas. |
| **Antrean dan jadwal** | Unggahan di atas jatah harian dijadwalkan ke hari berikutnya, bukan ditolak; jarak antar unggahan diatur. | Mengunggah 9 klip sekaligus; tiap 3 jam satu tayang. |
| **Keterangan per platform** | Caption dan tagar siap tempel untuk YouTube, TikTok, Instagram. | Menyalin caption TikTok untuk diunggah manual di HP. |
| **Siapkan terbit** | Satu panel untuk menyalin judul, caption, membuka folder, mengunduh berkas. | Unggah manual ke TikTok: semua yang perlu ditempel ada di satu tempat. |
| **Keunikan judul (O7)** | Memperingatkan bila judul terlalu mirip dengan unggahan sebelumnya (pola produksi massal). | "Judul ini 80% sama dengan 3 unggahan terakhir"; Anda menggantinya. |
| **Bab otomatis (O7)** | Video panjang Montase mendapat daftar bab (0:00, ≥3 bab, ≥10 detik) dari penanda atau kartu peringkat. | Kompilasi 10 menit: YouTube menampilkan bab "#5 ... #1". |
| **Identitas kanal** | Nama dan avatar kanal YouTube yang terhubung tampil di aplikasi. | Memastikan unggahan masuk ke kanal yang benar. |

---

## 6. Analitik

| Fitur | Apa dan manfaatnya | Contoh kasus |
|---|---|---|
| **Statistik tayangan** | Tayangan, suka, komentar per klip yang diunggah; grafik harian. | Melihat klip mana yang naik minggu ini. |
| **Seluruh video kanal** | Semua video di kanal, bukan hanya yang lewat OmniClip. | Membandingkan klip OmniClip dengan video lama. |
| **Retensi penonton** | Kurva bertahan dari YouTube Analytics. | Penonton banyak pergi di detik 4: hook perlu dipercepat. |
| **Komentar vs tanpa komentar** | Sesudah ≥3 klip publik dengan komentar dan ≥3 tanpa, menjawab apakah komentar menaikkan tayangan. | Bukti dari data sendiri bahwa klip berkomentar ditonton 2× lebih banyak. |
| **Temuan** | Kalimat yang menjelaskan arti angkanya, bukan hanya angka. | "Klip di bawah 20 detik Anda rata-rata ditonton 85%". |

---

## 7. Montase: penyunting video lengkap

### 7.1 Proyek dan bahan

| Fitur | Apa dan manfaatnya | Contoh kasus |
|---|---|---|
| **Proyek** | Ukuran bebas (Shorts, YouTube, Persegi, Potret, sendiri) dan fps; gandakan, hapus, versi. | Satu proyek 9:16 untuk Shorts, satu 16:9 untuk kanal utama. |
| **Bahan** | Dari Unduhan, Klip jadi, berkas sendiri (impor), aset, suara, rekaman. | Menggabungkan 5 Klip jadi menjadi satu kompilasi. |
| **Simpan otomatis + draf lokal** | Tersimpan sendiri; bila peramban tertutup, draf bisa dipulihkan. | Listrik padam; saat dibuka lagi muncul "pulihkan draf". |
| **Riwayat versi** | Kembali ke versi proyek sebelumnya. | Asisten mengubah terlalu banyak; pulihkan versi satu jam lalu. |
| **Cadangan** | Proyek ikut cadangan basis data. | Pindah komputer tanpa kehilangan proyek. |

### 7.2 Linimasa

| Fitur | Apa dan manfaatnya | Contoh kasus |
|---|---|---|
| **Banyak lajur** | Video, teks, animasi, subtitle, suara; sembunyikan, kunci, bisukan per lajur. | Lajur musik dikunci supaya tidak tergeser tidak sengaja. |
| **Seret, pangkas, belah, magnet** | Seperti CapCut; magnet merapatkan ke tepi item dan penanda. | Membelah klip di detik 5 dan membuang bagian tengah. |
| **Penanda** | Tekan M; penanda bernama, dipakai templat dan bab. | Menandai "Taruh klip #3 di sini". |
| **Zoom, pintasan keyboard, batal/ulang** | Spasi putar/jeda, panah per bingkai, Home/End, Delete (Shift+Delete hapus beriak), +/- zoom, Ctrl+Z; daftar lengkap di "Pintasan keyboard". | Menyunting cepat tanpa tetikus. |
| **Transformasi** | Posisi, skala, putar, opasitas; keyframe untuk gerak. | Zoom pelan ke wajah selama 3 detik. |
| **Kecepatan dan bekukan bingkai** | 0,25× sampai 4×; bekukan gambar. | Gerak lambat di momen gol. |
| **Volume dan fade** | Per item; perendam musik otomatis saat ada suara bicara. | Musik latar mengecil sendiri saat narasi masuk. |
| **Transisi, warna, efek** | Transisi antar klip, penyesuaian warna, efek bawaan. | Transisi kilat antara "sebelum" dan "sesudah". |
| **Loudnorm** | Kekerasan suara diratakan ke standar platform saat ekspor. | Video tidak terlalu pelan dibanding video lain di feed. |
| **Zona aman** | Garis bantu area yang tertutup tombol platform. | Judul tidak tertutup tombol suka di Shorts. |

### 7.3 Teks, subtitle, suara

| Fitur | Apa dan manfaatnya | Contoh kasus |
|---|---|---|
| **Teks bergaya** | Font, pelat, garis, bayang, gerak masuk, tema judul. | Judul kuning bergaris hitam yang "pop" masuk. |
| **Subtitle otomatis** | Dari ucapan bahan, per kata, dengan sorot kata aktif. | Kompilasi berbahasa campur tetap bersubtitle. |
| **Narasi TTS** | Tulis naskah, dibacakan suara AI, ditaruh di linimasa. | Narasi pembuka "Ini lima momen paling…". |
| **Rekam mikrofon** | Merekam suara sendiri langsung di editor. | Mengganti suara AI dengan suara Anda sendiri. |

### 7.4 Animasi dan AI

| Fitur | Apa dan manfaatnya | Contoh kasus |
|---|---|---|
| **10+ animasi bawaan** | Hitung mundur, judul kinetik, label nama, bilah peringkat/progres, ajakan berlangganan, angka naik, transisi kilat, dll.; props diatur lewat panel. | Kartu "#3" dengan warna kanal Anda. |
| **AI pembuat animasi** | Ketik "hitung mundur neon"; AI menulis animasi, mesin memeriksanya (render uji, bingkai kosong), lalu muncul di linimasa. Revisi lewat chat. | "Buat lebih cepat dan merah" lalu animasinya berubah. |
| **Asisten penyunting** | "Susun Top 5 momen paling lucu": AI menyusun urutan, kartu, narasi, musik sebagai usulan bergaris putus; terima per kelompok atau semua. | Satu perintah, linimasa Top 5 lengkap dalam 1 menit. |
| **Buang jeda** | Mencari jeda dan kata isian di bahan, usulan potong yang ikut menggeser lajur lain. | Narasi rekaman sendiri yang banyak "eh" jadi rapi. |
| **Bingkai ulang 9:16** | Usulan posisi/skala mengikuti wajah untuk bahan horizontal. | Klip 16:9 di proyek Shorts otomatis terpusat ke wajah. |
| **Saran keterangan** | Judul, deskripsi, tagar dari isi proyek. | Deskripsi lengkap dengan kredit dan bab. |

### 7.5 Ekspor

| Fitur | Apa dan manfaatnya | Contoh kasus |
|---|---|---|
| **Ekspor ke Klip jadi** | Render oleh mesin Montase, hasil masuk Klip jadi dengan sidecar (kredit, lapisan nilai tambah, sidik kemiripan). | Ekspor lalu unggah dari Klip jadi seperti klip biasa. |
| **Unggah dari Montase** | Langsung ke YouTube dengan saran keterangan. | Selesai menyunting, unggah tanpa pindah halaman. |
| **Nilai tambah Montase** | Lapisan Anda (narasi rekaman, reaksi, teks, animasi) dihitung ke skor yang sama dengan Studio. | Kompilasi berskor "cukup" karena ada narasi rekaman di tiap bagian. |

---

## 8. Montase: orisinalitas dan algoritma (JOB-5)

| Fitur | Apa dan manfaatnya | Contoh kasus |
|---|---|---|
| **Meter orisinalitas (O1)** | Lencana "Orisinal xx%" di atas editor: persen lapisan Anda, celah (bagian >12 detik video orang lain tanpa tambahan), saran perbaikan dengan tombol Lompat. | "Detik 40-58 belum ada tambahan" lalu Lompat dan rekam komentar di situ. |
| **Teleprompter (O2)** | Naskah narasi bergulir sambil Anda merekam suara sendiri; rekaman menggantikan suara AI dan dihitung sebagai suara Anda. | Membaca naskah AI dengan suara sendiri tanpa menghafal. |
| **Pemeriksa kemiripan (O3)** | Membandingkan proyek dengan 30 ekspor terakhir (struktur, suara, animasi, musik); memperingatkan pola bertemplat. | "Video ini 4 dari 5 dimensi sama dengan 3 video terakhir": ganti variasi templat. |
| **Pembuka kuat (O4)** | Mencari momen terkuat dan mengusulkannya sebagai cuplikan 2 detik di awal + teks hook. | Penonton langsung melihat puncak cerita di detik pertama. |
| **Rekam reaksi kamera (O5)** | Kamera + mikrofon direkam sambil pratinjau diputar, ditaruh sebagai gambar-dalam-gambar. | Video reaksi utuh dibuat di Montase. |
| **Akhir menyambung (O6)** | Memeriksa ekor tanpa gambar dan akhir yang tidak menyambung ke awal; usulan potong + sambung supaya Shorts terasa berulang mulus. | Musik lebih panjang 3 detik dari gambar; dipotong dan detik pertama ditaruh di ujung. |
| **Keunikan judul dan bab (O7)** | Lihat bagian 5. | |

---

## 9. Montase: preset dan templat

| Fitur | Apa dan manfaatnya | Contoh kasus |
|---|---|---|
| **Preset caption (P1)** | 10 gaya subtitle (sorot kuning, kotak ungu/hijau, pantul, tebal bayang, neon, stiker, berita, sinema, minimal) diterapkan ke seluruh lajur subtitle sekaligus dan dipakai untuk subtitle baru. | Mengganti seluruh subtitle ke gaya "pantul" dengan satu klik. |
| **Gaya teks saya (P2)** | Simpan gaya teks yang Anda suka dengan nama, dipakai lagi di proyek lain; per profil. | Gaya "Judul kanal" (Anton kuning, pelat hitam) dipakai di setiap video. |
| **Templat video bawaan (P3)** | 5 kerangka (Top 5 hitung mundur, Reaksi, Sorotan podcast, Fakta/edukasi, Sebelum/sesudah), masing-masing 3 variasi warna/caption/animasi; berisi kartu, judul, label, ajakan berlangganan, gaya caption, dan penanda tempat menaruh klip. Diusulkan, bukan dipaksakan. | Proyek baru "Top 5", variasi 3: tinggal menaruh 5 klip di penanda. |
| **Templat saya (P4)** | Simpan susunan proyek (teks, animasi beserta posisi, penanda, gaya caption) sebagai templat sendiri, tanpa klip/suara/isi subtitle; pas di fps berapa pun. Dipilih di formulir proyek baru atau tab Asisten. | Format seri mingguan "Podcast kanal saya" dipakai ulang setiap minggu, isinya berbeda. |

Catatan: templat yang dipakai PERSIS sama di setiap video adalah pola yang
dinilai YouTube sebagai konten tidak autentik. Ganti variasi, isi teks, dan
susunan klip; pemeriksa kemiripan (O3) memberi tahu bila terlalu mirip.

---

## 10. Akun, profil, pengaturan, bahasa

| Fitur | Apa dan manfaatnya | Contoh kasus |
|---|---|---|
| **Profil** | Satu orang atau satu kanal; preset, templat, riwayat, langganan terpisah per profil. | Satu komputer untuk kanal gaming dan kanal podcast. |
| **Akun Google** | Menghubungkan YouTube/Drive per profil; peringatan izin yang kurang. | Kanal kedua dihubungkan ke profil kedua. |
| **Pengaturan Klip** | Bawaan pemilihan klip, bahasa teks AI (ikut antarmuka / video / Indonesia / English). | Video Inggris, judul AI tetap bahasa Indonesia. |
| **Pengaturan Subtitle** | Sensor kata kasar, buang gumaman, warna penutur, terjemahan otomatis. | Menyalakan sensor untuk kanal ramah keluarga. |
| **Pengaturan Suara** | Suara pembaca (TTS) bawaan. | Memilih suara perempuan Indonesia untuk semua narasi. |
| **Tampilan dan bahasa** | Indonesia / English untuk seluruh antarmuka dan pesan server; mode ringkas di layar sempit. | Asisten berbahasa Inggris memakai OmniClip yang sama. |
| **Sakelar Montase** | Menyalakan/mematikan menu Montase. | Menyembunyikan Montase bagi pengguna yang hanya butuh Studio Klip. |

---

## 11. Mesin dan pemeliharaan

| Fitur | Apa dan manfaatnya | Contoh kasus |
|---|---|---|
| **Koneksi AI** | Satu daftar untuk semua penyedia (Gemini, OpenRouter, Claude, AI lokal), urutan pilihan, uji kunci per model. | Menambah kunci Claude sebagai cadangan kedua. |
| **AI lokal** | Model bahasa kecil di komputer sendiri, tanpa internet dan biaya. | Bekerja di tempat tanpa internet. |
| **Pemakaian AI** | Catatan setiap panggilan AI: berapa, oleh fitur apa, hasilnya. | Melihat bahwa kuota habis karena terlalu sering "Cari ulang". |
| **Penyimpanan** | Lokasi folder unduhan/klip, pindah folder dengan isinya. | Memindah klip ke cakram eksternal 2 TB. |
| **Sampah dan bersih otomatis** | Berkas yang tidak berguna lagi; video mentah dan klip lama yang tidak disentuh dibersihkan otomatis. | Cakram penuh; bersihkan 40 GB sekali klik. |
| **Cadangan basis data** | Cadangan dan ruang cakram. | Mencadangkan sebelum memperbarui aplikasi. |
| **Kesehatan** | Pemeriksaan ffmpeg, mesin Montase, model, dll. | Render gagal; kartu Kesehatan menunjukkan ffmpeg rusak. |
| **Pembaruan aplikasi dan pustaka** | Cek, unduh, pasang versi baru; yt-dlp diperbarui sendiri. | YouTube berubah; yt-dlp terbaru terpasang otomatis. |
| **Keamanan** | Satu kata sandi untuk membuka aplikasi; Cloudflare Access bila diakses dari luar. | Membuka OmniClip dari HP lewat internet dengan aman. |
| **Matikan dari halaman** | Mematikan server dari dalam aplikasi. | Selesai bekerja, matikan tanpa membuka terminal. |

---

## 12. Saran fitur penunjang

Belum dibangun. Diurutkan dari yang paling menunjang tujuan Anda (video yang
dinilai orisinal dan masuk algoritma), dengan perkiraan usaha: **K**ecil
(≤1 hari), **S**edang (2-4 hari), **B**esar (≥1 minggu).

| # | Saran | Kenapa | Usaha |
|---|---|---|---|
| 1 | **Pembuat thumbnail** (gambar mini) di Montase: bingkai terbaik + wajah + teks besar, beberapa variasi, diunggah bersama video lewat API. | Untuk video 16:9, thumbnail menentukan klik (CTR) lebih dari hampir semua hal lain. Saat ini OmniClip tidak membuat thumbnail sama sekali. | S |
| 2 | **Retensi di atas linimasa**: kurva bertahan video yang sudah terunggah digambar di atas linimasa proyek asalnya, menandai detik penonton pergi. | Menyambungkan Analitik dengan editor: Anda melihat persis bagian mana yang membuat orang menggeser, lalu memperbaikinya di video berikutnya. | S |
| 3 | **Analitik per templat/pola**: menggabungkan sidik kemiripan (O3) dengan retensi dan tayangan. "Templat Reaksi variasi 2 rata-rata ditonton 78%". | Memberi tahu kerangka mana yang benar-benar bekerja untuk kanal ANDA, bukan tebakan umum. | S |
| 4 | **Komentar penonton jadi ide**: membaca komentar di video Anda (YouTube API), mengelompokkan pertanyaan/permintaan, mengusulkan video tanggapan dan draf balasan. | Video yang menjawab komentar penonton adalah konten orisinal yang jelas, dan membalas komentar menaikkan keterlibatan. | S |
| 5 | **Chroma key (latar hijau)** untuk rekaman reaksi. | Reaksi dengan wajah tanpa kotak, langsung di atas klip; terlihat jauh lebih profesional. Dicatat di JOB-4 bagian 26. | S |
| 6 | **Pemeriksa musik berhak cipta**: memperingatkan musik dari sumber tak dikenal dan menyarankan pustaka bebas royalti. | Klaim Content ID memindahkan pendapatan ke pemilik musik atau memblokir video. | K |
| 7 | **Kompilasi mingguan otomatis**: tiap minggu mengusulkan proyek Montase berisi klip terbaik minggu itu (menurut tayangan), lengkap dengan bab dan narasi untuk direkam. | Video panjang dari klip yang sudah terbukti; jam tonton naik dengan usaha kecil. | S |
| 8 | **Dubbing / trek audio bahasa lain**: terjemahan narasi dibacakan TTS sebagai trek audio kedua. | YouTube mendukung banyak trek audio; menjangkau penonton luar negeri tanpa video terpisah. | B |
| 9 | **Kalender konten**: tampilan kalender dari jadwal unggah yang sudah ada, seret untuk memindah. | Konsistensi unggah lebih mudah dijaga bila terlihat. | K |
| 10 | **Masking dan pelacakan objek** (sensor wajah orang lewat, sorot objek bergerak). | Privasi orang yang tidak setuju tampil, dan efek sorot yang mengikuti benda. | B |

Rekomendasi urutan: **1 → 2 → 3** dulu, karena ketiganya menutup lingkaran
"buat → unggah → ukur → perbaiki" yang sekarang masih terputus di antara
Analitik dan editor.

---

## 13. Studi kasus dari awal sampai unggah

### A. Kanal klip podcast (Shorts harian)

1. **Langganan**: ikuti 5 channel podcast yang sudah memberi izin (catat di
   Izin per kanal).
2. Video baru muncul → **Klip video ini** → Studio Klip memilih 8 momen.
3. Per klip: **Batas** (hook langsung), **Subtitle** (buang gumaman, warna
   penutur), **Komentar** (draf AI disunting, rekam suara sendiri 5 detik).
4. Lihat **Nilai tambah** "cukup" → render → **Klip jadi**.
5. **Unggah** 8 klip sekaligus; antrean menjadwalkan 3 per hari.
6. Seminggu kemudian: **Analitik** → "Komentar vs tanpa" dan retensi.

### B. Kompilasi Top 5 mingguan (16:9, kanal utama)

1. **Montase → Proyek baru**, ukuran YouTube, templat **Top 5**, variasi
   yang belum dipakai minggu lalu.
2. Tarik 5 Klip jadi terbaik ke penanda "Taruh klip #n di sini".
3. **Teleprompter**: baca narasi pengantar tiap peringkat dengan suara
   sendiri.
4. **Meter orisinalitas** → tutup celah yang disarankan.
5. **Pemeriksa kemiripan** → aman (tidak sama dengan 3 kompilasi terakhir).
6. **Ekspor** → **Unggah**; bab #5 sampai #1 terisi otomatis.

### C. Video reaksi (Shorts)

1. Montase → templat **Reaksi** → taruh video yang ditanggapi.
2. **Rekam reaksi** sambil video diputar; wajah Anda di pojok.
3. **Pembuka kuat** → momen paling mengejutkan jadi 2 detik pertama.
4. **Akhir menyambung** → video berulang mulus.
5. **Preset caption** "kotak ungu" → ekspor → unggah.
6. Bila format ini berhasil: **Simpan sebagai templat** "Reaksi kanal saya"
   untuk seri berikutnya, dan ganti variasinya tiap beberapa video.
