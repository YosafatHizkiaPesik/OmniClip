# Rencana: unggah ke semua platform, tanpa setelan

Tujuannya satu kalimat: **pengguna memasang OmniClip, menekan "Masuk dengan
YouTube", dan klipnya naik.** Tidak ada kunci API, tidak ada Google Cloud
Console, tidak ada istilah yang harus dipelajari dulu.

Ditulis 23 September 2026 sebagai rencana, bukan sebagai pekerjaan yang sudah
jadi. Angka-angka di dalamnya diperiksa hari itu juga.

---

## 1. Bentuk yang benar

Yang berubah bukan cara mengunggahnya — kodenya sudah ada dan bekerja. Yang
berubah **siapa yang memiliki aplikasinya**.

**Sekarang:** tiap pengguna mendaftarkan aplikasinya sendiri di Google Cloud,
lalu menempel kuncinya. Benar secara teknis, dan mustahil untuk dijual.

**Yang dituju:** *Anda* mendaftarkan **satu** aplikasi per platform, sekali.
ID-nya ikut di dalam OmniClip. Pengguna tidak pernah melihatnya — yang ia lihat
hanya halaman login resmi Google/TikTok/Meta, persis seperti masuk ke aplikasi
lain.

Ini bentuk yang dipakai semua produk sejenis. Tidak ada jalan lain yang sah.

---

## 2. Tiga hal yang menghalangi, dan besarnya

### 2.0 Video terkunci privat — ini yang paling menentukan

Diperiksa 23 September 2026, dan ini lebih menentukan daripada kuota:

> **Video yang diunggah lewat API dari proyek yang BELUM lolos audit dikunci
> sebagai privat.** Bukan "bawaannya privat" — dikunci, dan menurut aturan
> Google tidak bisa dijadikan publik sampai auditnya lolos. Berlaku untuk
> semua proyek yang dibuat sejak 28 Juli 2020.

Akibatnya langsung ke keputusan bisnisnya:

- Model "tiap pengguna pasang kunci sendiri" **tidak pernah bisa menghasilkan
  video publik**, berapa pun pengguna yang memasangnya. Tiap pengguna membuat
  proyek baru, dan tiap proyek baru belum diaudit.
- Jadi audit itu **bukan** cara menaikkan kuota saja. Ia satu-satunya cara
  membuat unggahan YouTube berguna sama sekali.

Yang TIDAK terkena aturan ini: Google Drive, TikTok, Facebook, dan Instagram.
Ketiganya punya urusan reviewnya sendiri, tapi tidak ada yang mengunci
hasilnya jadi privat selamanya.

### 2.1 Kuota YouTube

Tiap proyek Google mendapat **10.000 unit per hari**. Satu unggahan video
memakan **1.600 unit**.

> **6 unggahan per hari. Untuk SELURUH pengguna OmniClip digabung.**

Bukan enam per orang — enam per aplikasi. Dengan sepuluh pengguna, dua orang
pertama menghabiskan jatah semua orang sebelum makan siang.

Menaikkannya bisa, lewat **quota extension request**, tapi Google mewajibkan
**audit kepatuhan** lebih dulu: aplikasinya diperiksa manusia terhadap YouTube
API Services Terms of Service. Yang diperiksa antara lain: aplikasi tidak boleh
jadi alat unggah massal, harus menampilkan branding YouTube dengan benar, dan
harus punya kebijakan privasi yang sah.

**Waktu:** hitungan minggu sampai bulan. **Biaya:** gratis. **Kepastian:**
tidak ada.

### 2.2 Verifikasi OAuth Google

`youtube.upload` termasuk **sensitive scope**. Selama aplikasinya belum
diverifikasi Google:

- maksimal **100 test user**, yang alamat surelnya harus didaftarkan satu per
  satu;
- layar izinnya memperingatkan "aplikasi ini belum diverifikasi".

Verifikasi butuh kebijakan privasi yang bisa diakses publik, domain yang
terbukti milik Anda, dan video demo yang menunjukkan alur izinnya.

### 2.3 TikTok dan Meta: rahasia aplikasi tidak boleh ikut dibagikan

Google punya jenis klien **Desktop app** yang secara resmi memperlakukan
"client secret" sebagai **bukan rahasia** — ia memang dirancang untuk aplikasi
yang dipasang di komputer orang, dengan PKCE sebagai pengamannya. Jadi untuk
Google, kuncinya boleh ikut di dalam OmniClip.

TikTok dan Meta **tidak** punya itu. Keduanya:

- mewajibkan alamat balik **HTTPS** (bukan `http://127.0.0.1`);
- menukar kode izin jadi token memakai **client secret yang benar-benar
  rahasia** — siapa pun yang mengambilnya dari dalam aplikasi bisa menyamar
  jadi OmniClip.

Artinya harus ada **satu titik di internet** milik Anda yang: (a) menerima
alamat balik, dan (b) memegang rahasianya.

**Itu tidak berarti menyewa server.** Yang dibutuhkan satu fungsi kecil di
lapisan gratis — Cloudflare Workers (100.000 permintaan/hari gratis), Deno
Deploy, atau Vercel. Tidak ada yang harus dijaga, tidak ada tagihan, dan laptop
Anda tidak jadi server.

Alurnya:

```
OmniClip (komputer pengguna)
   │  buka halaman izin, bawa nomor port di parameter `state`
   ▼
TikTok / Meta  ──►  https://<worker-anda>/balik   (alamat balik terdaftar)
                         │  tukar kode jadi token memakai rahasia
                         ▼
                    kirim balik ke http://127.0.0.1:<port> di komputer pengguna
```

Worker-nya tidak menyimpan apa pun. Token tinggal di komputer pengguna, sama
seperti sekarang.

---

## 3. Yang harus Anda kerjakan sekali (bukan kode)

| Platform | Yang didaftarkan | Yang ditunggu | Perkiraan |
|---|---|---|---|
| Google/YouTube | OAuth client jenis **Desktop app** | verifikasi OAuth + audit kuota | 2–8 minggu |
| TikTok | App di developers.tiktok.com, scope `video.publish` | app review | 1–4 minggu |
| Meta (FB+IG) | App Meta + verifikasi bisnis | App Review untuk `pages_manage_posts` dan `instagram_content_publish` | 2–6 minggu |

Yang dibutuhkan bersama untuk ketiganya:

1. **Kebijakan privasi** yang bisa dibuka publik (halaman statis gratis cukup —
   GitHub Pages).
2. **Halaman produk** sederhana dengan nama dan penjelasannya.
3. **Video demo** alur izinnya (dituntut Google dan Meta).
4. Untuk Meta: **badan usaha** yang bisa diverifikasi.

---

## 4. Urutan pengerjaan yang saya usulkan

### Tahap 1 — kunci bawaan (kode, ±1 hari)

OmniClip membawa ID aplikasinya sendiri; halaman Akun berubah jadi satu tombol
"Masuk dengan Google". Mode lama (pengguna memasang kunci sendiri) **tetap
ada** sebagai jalan cadangan — untuk Anda sendiri, dan untuk pengguna yang
kuotanya habis karena dipakai bersama.

Bisa dikerjakan **sekarang**, sebelum satu pun pendaftaran selesai: selama ID
bawaannya kosong, perilakunya persis seperti hari ini.

### Tahap 2 — ajukan audit YouTube SEKARANG, bukan nanti

Daftarkan Desktop app dan ajukan audit kepatuhan **paling awal**, karena ia
yang paling lama dan yang paling menentukan. Sampai lolos, unggahan YouTube
hanya menghasilkan video terkunci privat — jadi jangan menjanjikannya ke
pembeli, dan jangan menjadikannya fitur utama di halaman jualan.

Sementara menunggu, yang bisa dijanjikan: Drive, TikTok (draf), dan nanti
Reels.

### Tahap 3 — relay TikTok (kode ±1 hari + review TikTok)

Worker kecil untuk alamat balik dan penukaran token, lalu TikTok tersambung
tanpa setelan apa pun.

### Tahap 4 — Meta (paling lama)

Jalur yang sama dengan TikTok, tapi review-nya paling ketat dan butuh badan
usaha.

### Tahap 5 — jujur soal kuota

Selama kuota YouTube masih 6 unggahan/hari untuk semua orang, aplikasi harus
**mengatakannya** — bukan gagal diam-diam pada unggahan ketujuh. Sudah ada
tempatnya: penjadwal unggah dan halaman Kesehatan sistem.

---

## 5. Yang saya tolak, dan alasannya

**Mengotomatiskan peramban** (Playwright membuka tiktok.com lalu mengunggah
seperti manusia) menghilangkan seluruh urusan API. Tapi:

- melanggar syarat layanan keempat platform;
- akun penggunanya yang kena, bukan akun Anda — dan mereka yang membayar;
- rusak setiap kali tampilan situsnya berubah, tanpa pemberitahuan.

Untuk perangkat lunak yang dijual, ini bukan risiko yang boleh diambil atas
nama orang lain.

**Menanam rahasia TikTok/Meta ke dalam aplikasi** melanggar syarat keduanya dan
bisa mematikan aplikasi Anda untuk semua pengguna sekaligus.

---

## 6. Kalau audit kuota ditolak

Rencana cadangan yang tetap terasa mudah, dan tidak melanggar apa pun:

- **Unggah setengah otomatis.** OmniClip menyiapkan berkas, judul, deskripsi,
  dan tagar, lalu membuka halaman unggah platformnya dengan semua itu siap
  disalin. Pengguna menekan satu tombol terbit.
- **Folder terpantau.** Klip jadi ditaruh di folder yang disinkronkan ke HP,
  sehingga mengunggah dari aplikasi resmi tinggal beberapa ketukan.

Keduanya jauh lebih baik daripada unggahan otomatis yang gagal pada klip
ketujuh setiap hari.

---

## 7. Keputusan yang saya butuhkan dari Anda

1. **Mulai Tahap 1 sekarang?** Ia tidak menunggu pendaftaran apa pun dan tidak
   mengubah perilaku sampai ID-nya diisi.
2. **Badan usaha** — sudah ada, atau perlu dijadikan syarat sebelum Meta?
3. **Nama dan domain** untuk kebijakan privasi dan halaman produk; keduanya
   dituntut ketiga platform, dan keduanya bisa gratis di GitHub Pages.
