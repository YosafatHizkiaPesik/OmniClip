# JOB-5: Orisinalitas dan algoritma (lanjutan JOB-2, untuk Montase)

Diminta pemilik 5 November 2026: "saran fitur ... untuk menunjang editing dan
meningkatkan kualitas video saya agar bisa dinilai sebagai konten original
hasil klip saya dan bisa masuk algoritma youtube. jadi coba analisis ketentuan
youtube sekarang dan buatkan fitur yang menunjang".

Format centang sama dengan JOB-2/JOB-4: `- [x] **O1** ... (selesai <tanggal>, commit <hash>)`.

## 0. Papan status (perbarui SETIAP tugas selesai atau terhenti)

Disetujui pemilik 5 November 2026: "lanjut saja kerjakan hingga o7 dan jangan
lupa untuk selalu mencatatnya agar ... sesi lain masih bisa melanjutkannya".

| Tugas | Status | Catatan singkat |
|---|---|---|
| O1 Meter orisinalitas | ✅ 298209a | |
| O2 Rekam narasi dari naskah | ✅ fc2e23d | teleprompter, direkam bukan sintetis |
| O3 Kemiripan antar video | ✅ 8fad116 | sidik ekspor, pola trigram |
| O4 Pembuka kuat | ✅ a1e7e6e | cek 3 detik + cuplikan |
| O5 Rekam reaksi kamera | 🟨 sebagian 20828c7 | server selesai, sisa perekam peramban |
| O6 Akhir menyambung | ⬜ | |
| O7 Keterangan unik + bab | ⬜ | |

**Tugas berikutnya:** `O5` (lanjutan: perekam di peramban).

**Melanjutkan di sesi baru:** baca papan ini dan bagian 4. Kerjakan tugas
berikutnya; bila ada catatan "SEBAGIAN" di bawah butirnya, lanjutkan dari
situ. Sesudah setiap tugas: tes (`cd backend && python -m unittest discover
tests`, `cd frontend && npm test && npm run lint && npm run build`), commit
kode, centang butir di bagian 4 dengan hash-nya, perbarui papan ini, commit,
push ke cabang kerja. Cabang: `claude/ecstatic-davinci-scqbbm` (sesi ini).
Sesudah O7: satu PR untuk JOB-5, CI (`bangun-aplikasi.yml`, workflow_dispatch),
merge bila hijau, UJI-LANGSUNG tes 103 dan seterusnya.

Kebiasaan Montase tetap berlaku (lihat JOB-4 bagian 5 dan 15): batas modul
(`test_montase_batas.py`), semua teks lewat `t()` dengan kunci di id.js dan
en.js, pesan server baru masuk `kamus_en.py`, fitur otomatis MENGUSULKAN
(lewat `model/usulan.js` bila mengubah linimasa).

## 1. Ketentuan YouTube yang berlaku (dibaca 5 November 2026)

Dari halaman resmi YouTube Help (kebijakan monetisasi kanal, FAQ konten yang
digunakan ulang, kebijakan spam) dan YouTube Blog:

1. **Konten yang digunakan ulang (reused content)**: konten yang "bukan
   jelas ciptaan Anda sendiri" tanpa komentar yang berarti, modifikasi
   substansial, atau nilai edukasi/hiburan tambahan. Yang diterima: ulasan
   kritis, reaksi yang MENGOMENTARI aslinya. Yang ditolak secara tegas:
   - klip dari acara yang disambung "dengan sedikit atau tanpa narasi";
   - konten yang diunduh/disalin tanpa modifikasi substansial;
   - reaksi yang sebagian besar tanpa kata (tanpa komentar suara).
   Ukuran peninjau: penonton bisa melihat **perbedaan yang berarti** antara
   video asli dan video Anda. **Izin dari pemilik asli tidak menyelesaikan
   ini**: kebijakan ini terpisah dari hak cipta.
2. **Konten tidak autentik (inauthentic content)**, nama baru "repetitious
   content" sejak Juli 2025: konten **diproduksi massal, bertemplat, atau
   berulang** dengan sedikit perbedaan antar video. Pelanggaran bisa mencabut
   monetisasi **seluruh kanal**, bukan satu video.
3. **Kebijakan spam**: produksi massal otomatis/AI dengan perubahan kecil, dan
   unggah ulang dari tempat lain tanpa tambahan sendiri, bisa berujung
   penghentian kanal.
4. **AI boleh**, selama hasilnya jelas orisinal. Label konten sintetis wajib
   untuk konten REALISTIS yang diubah/dibuat AI (suara tiruan orang nyata,
   wajah, kejadian palsu); suara TTS umum di atas rekaman asli tidak wajib
   label (OmniClip sudah menandainya secara jujur, JOB-2 F0-7).
5. **Algoritma Shorts** (YouTube Help + ringkasan komunitas, angka pastinya
   tidak resmi): sinyal utama adalah **"Viewed vs swiped away"** (berapa yang
   memilih menonton, ditentukan detik-detik pertama) dan **persentase yang
   ditonton** (termasuk menonton ulang). Short diuji ke penonton kecil dulu dan
   diperluas bila mereka tidak menggeser.

Laporan pihak ketiga tentang perubahan Juli dan Oktober 2026 (tiga kategori
konten tidak autentik, distribusi Shorts daur ulang yang diturunkan) belum
terlihat di catatan perubahan resmi; tidak dipakai sebagai dasar aturan.

## 2. Yang sudah ada di OmniClip

Studio Klip (JOB-2): komentar/opini per klip, rekam suara sendiri, kredit
sumber, gerbang tinjau, batas unggah harian, kategori, label sintetis,
punch-in, nama penutur, kartu konteks, transisi, intro/outro, skor nilai
tambah, analitik dengan/tanpa komentar.

Montase (JOB-4): narasi TTS dan rekam, asisten dengan narasi per peringkat,
animasi, kredit banyak sumber, wajib narasi untuk video orang lain (T-3),
skor nilai tambah dari lapisan.

## 3. Celah, dan fitur yang menutupnya

| No | Celah | Fitur |
|---|---|---|
| O1 | Skor nilai tambah baru terlihat SESUDAH ekspor/unggah; tidak menunjuk bagian mana yang masih "potongan ulang" | **Meter orisinalitas langsung** di editor Montase: persen, rincian, dan daftar rentang video orang lain yang belum diberi tambahan, dengan tombol lompat |
| O2 | Narasi asisten berupa TTS; suara pemilik sendiri jauh lebih jelas "ciptaan sendiri" | **Rekam narasi dari naskah**: naskah tampil seperti teleprompter, rekam per peringkat, rekaman menggantikan item TTS di tempatnya |
| O3 | Kebijakan konten tidak autentik menilai KANAL: video yang semuanya berstruktur, bersuara, bertemplat sama | **Pemeriksa kemiripan antar video**: sidik tiap ekspor (struktur, suara, musik, tema, pola judul) dibandingkan dengan video terakhir di kanal yang sama; peringatan beserta apa yang sama |
| O4 | Detik-detik awal menentukan "viewed vs swiped"; belum ada yang menilai pembuka video Montase | **Pembuka kuat**: pemeriksaan 3 detik pertama (ada ucapan/teks/gerak?) dan usulan asisten "cuplikan pembuka" dari momen terkuat |
| O5 | Reaksi wajah pemilik kanal adalah tambahan paling jelas, baru ada di Studio | **Rekam reaksi kamera** di Montase: webcam menjadi bahan video, ditaruh sebagai gambar-dalam-gambar |
| O6 | Shorts yang ditonton ulang dihitung; akhir yang mati menurunkan persentase ditonton | **Akhir menyambung**: periksa ekor sunyi/diam, usulkan potong ekor dan akhir yang menyambung ke awal |
| O7 | Deskripsi dari templat yang sama di setiap video juga pola "bertemplat" | **Keterangan unik + bab**: peringatan deskripsi/judul yang terlalu mirip video sebelumnya; bab otomatis untuk video panjang dari penanda/peringkat |

Yang sengaja TIDAK dibuat (sama dengan penolakan Fitur E di JOB-2): apa pun
yang bertujuan menyamarkan duplikat dari sistem deteksi (noise, geser warna,
geser nada). Variasi harus berasal dari isi, bukan dari pengelabuan.

## 4. Tugas

Urutan dari dampak terbesar terhadap penilaian orisinalitas.

- [x] **O1** Meter orisinalitas langsung di editor Montase.
  (selesai 5 Nov 2026, commit 298209a) Lencana + panel di kepala editor; rumus sama dengan gerbang tinjau; celah = video orang lain > 12 dtk tanpa tambahan dan tanpa narasi pengantar 3 dtk sebelumnya.
- [x] **O2** Rekam narasi dari naskah (teleprompter).
  (selesai 5 Nov 2026, commit fc2e23d) editor/Teleprompter.jsx + hook rekamMikrofon.js; rekaman menggantikan item narasi lewat gantiBahanItem dengan narasi.direkam=true; pintu: saran meter, tab Asisten, panel properti. Server: narasi direkam = rekam, bukan sintetis. Diuji Playwright dengan mikrofon palsu Chromium 4/4.
- [x] **O3** Pemeriksa kemiripan antar video.
  (selesai 5 Nov 2026, commit 8fad116) montase/kemiripan.py: sidik di sidecar ekspor (versi 1), GET /proyek/{id}/kemiripan, tampil di panel meter. Struktur dibandingkan sebagai pola trigram (Top 2 dan Top 10 bersusunan sama = sama); mirip = skor >= 0,75 ATAU >= 3 dimensi inti sama. Ekspor LAMA tanpa sidik tidak ikut dibandingkan. Data uji: Top 5 lawan Uji unggah narasi = waspada (susunan, animasi, suara).
- [x] **O4** Pembuka kuat.
  (selesai 5 Nov 2026, commit a1e7e6e) orisinalitas.periksaPembuka + bagian Pembuka di panel meter; montase/pembuka.py (POST /proyek/{id}/pembuka) mengusulkan geser_semua 2 dtk + klip momen terkuat + teks pengait. Momen dicari di SELURUH bahan lalu disaring: pendeteksi lonjakan butuh suara sebelum lonjakan (terukur: rentang mulai 4 dtk sebelum puncak tidak menemukan apa pun). Playwright 4/4 termasuk Ctrl+Z.
- [ ] **O5** Rekam reaksi kamera.
  **SEBAGIAN (commit 20828c7):** server selesai (POST /rekam-video -> narasi.simpan_reaksi, lapisan `reaksi` di ekspor, nilai_tambah menghitungnya penuh, tes test_montase_reaksi.py). Sisa: perekam di peramban (kamera + putar pratinjau dari garis putar), taruh sebagai gambar-dalam-gambar di lajur video kedua, meter menghitung video `rekam` sebagai suara sendiri.
- [ ] **O6** Akhir menyambung.
- [ ] **O7** Keterangan unik dan bab.

## Sumber

- YouTube channel monetization policies: https://support.google.com/youtube/answer/1311392
- FAQ: Reused Content & YouTube's Partner Program: https://support.google.com/youtube/community-guide/271248162
- What kind of content can I monetize?: https://support.google.com/youtube/answer/2490020
- Spam policy: https://support.google.com/youtube/answer/2801973
- YouTube Shorts monetization policies: https://support.google.com/youtube/answer/12504220
