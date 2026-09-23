# Rencana OmniClip

Daftar hidup: apa yang **belum dikerjakan**, apa yang **masih lemah**, dan apa
yang **belum pernah diuji**. Diperbarui 23 September 2026 pada versi 1.0.7.

Berkas ini menggantikan `SISA-PEKERJAAN.md`, yang sekarang jadi arsip. Aturannya
satu: **poin yang selesai dicoret dari sini**, bukan ditinggalkan dengan catatan
"sudah". Yang sudah selesai tercatat di riwayat git.

---

## A. Keputusan yang menunggu pemiliknya

**A1. Data masih di cakram NTFS yang lambat.** Terukur: 67 MB/detik di cakram
kerja sekarang, 523 MB/detik di SSD. Faktor lingkungan terbesar pada kecepatan
render — lebih besar daripada semua perbaikan kode yang sudah dilakukan.
Memindahkan `OmniClip-Data` ke SSD tidak butuh kode apa pun.

**A2. Berkas sisa 17 GB.** Satu `.f623.mp4` tanpa suara, nol klip jadi.
Sekarang terlihat di Pengaturan → Ruang cakram, tinggal dicentang dan dihapus.

**A3. Mendaftarkan aplikasi Google, TikTok, dan Meta.** Kodenya sudah ada dan
menunggu kunci; langkahnya ada di dalam aplikasi (Akun → Tambah akun) dan di
[PANDUAN-AKUN.md](PANDUAN-AKUN.md). Sampai ini dikerjakan, unggah ke mana pun
tidak bisa dipakai — dan tidak bisa diuji (lihat E1).

---

## B. Diminta, belum dibangun

**B1. Sutradara AI untuk gaya subtitle.** Tema dan sorotan katanya sekarang
sudah banyak (26 tema, enam cara menyorot kata), tapi MEMILIHNYA masih
pekerjaan tangan. Yang belum ada: AI yang memilih tema per klip menurut isinya,
dan warna berbeda per penutur di dalam satu tema.

---

## C. Saran perbaikan yang belum dikerjakan

**C0. Tema subtitle per bahasa.** Tema yang memakai huruf kapital semua tidak
berlaku untuk aksara Jepang, Korea, dan Arab; sekarang pilihannya tetap
ditawarkan walau tidak berpengaruh.

**C1. Pratinjau yang benar-benar menampilkan hasil rapat.** Sesudah "Rapatkan
jeda", pemutar Studio memutar segmen barunya, tapi peralihan antar potongan di
pratinjau tidak semulus hasil rendernya.

**C2. Templat deskripsi per platform.** Sekarang satu templat dipakai untuk
semua tujuan; TikTok dan YouTube punya kebiasaan tagar yang berbeda.

**C3a. Tandai terbit dari halaman Klip jadi** tanpa harus membuka "Siapkan
terbit" dulu — sekarang penandanya hanya ada di dalam jendela itu.

**C3. Statistik sesudah unggah.** Berapa tayangan tiap klip, ditarik dari API
masing-masing, supaya terlihat jenis klip mana yang berhasil.

---

## D. Kelemahan yang masih ada

**D1. Ikut wajah salah sorot ±27% waktu** pada bidikan berisi beberapa orang
(turun dari 46%). Bidikan lebar dengan wajah kecil sengaja belum ditangani:
gerak mulut di sana tidak bisa dipercaya.

**D2. Kartun berwajah jelas** masih dianggap "ada orang", jadi jumlah penuturnya
ditebak dari suara dan efek suara bisa terhitung sebagai orang.

**D3. Pindah ke "Susun sendiri" secara manual masih berkedip hitam sesaat.**
Yang sudah mulus hanya potongan susunan sutradara dan bingkai game.

**D4. Subtitle bisa bertabrakan dengan subtitle yang sudah tertanam** di video
fansub. Terjemahan sudah dipindah ke atas, tapi posisinya tetap, bukan dihitung
dari isi gambar.

**D5. Pola reaksi otomatis untuk kartun belum ada.**

**D6. Merapatkan jeda memakai transkrip**, jadi klip tanpa transkrip (musik,
gameplay tanpa bicara) tidak bisa dirapatkan sama sekali.

---

## E. Belum pernah diuji (risiko nyata)

**E1. Unggah sungguhan ke mana pun.** Belum ada berkas OAuth Google di komputer
ini, dan aplikasi TikTok/Meta belum didaftarkan. Yang sudah diuji hanya jalur
galatnya: kunci kosong, akun belum tersambung, dan bentuk alamat izin.

**E2a. Bundel Windows tanpa konsol.** Ikon, keterangan versi, penyembunyian
jendela proses anak, dan tombol Keluar semuanya dikerjakan dan diuji di Linux;
yang tidak bisa diuji dari sini justru bagian yang khusus Windows. Rilis
berikutnya harus dicoba langsung di Windows.

**E2. Semua fitur baru di Windows:** unduhan Deno dan server PO Token, encoder
GPU, profil, impor lewat jalur, dan unduhan font Noto.

**E3. Render GPU pada aplikasi desktop Linux.** Ffmpeg statis yang dibundel
dibangun tanpa encoder GPU, jadi di sana render masih x264 walau kartunya
mampu.

**E4. Pemulihan cadangan sampai tuntas.** Membuat cadangan sudah diuji
(74 MB, lolos `PRAGMA integrity_check`, 105 analisis utuh). Menukarnya saat
aplikasi dimulai belum pernah dijalankan sungguhan.

---

## Pengujian

```bash
cd backend && ./venv/bin/python -m unittest discover -s tests -t .
```

100 uji, tanpa memasang apa pun, selesai dalam sepersekian detik. Yang diuji
adalah bagian yang rusaknya paling tidak terlihat: penyusun teks dan subtitle,
tema dan sorotan kata, caption dan tagar, perapatan jeda, geometri bingkai,
penilaian isi klip,
skema dan jawaban model AI, pemilihan model Whisper, serta pemeriksaan jalur
berkas yang datang dari peramban.

Uji pertama yang ditulis langsung menemukan satu cacat: `"Cek 天井 mix"`
kehilangan kedua spasinya karena aturan lama menghapus spasi bila salah satu
sisinya CJK. Sekarang syaratnya kedua sisi.
