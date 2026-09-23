# Menambahkan akun untuk mengunggah

Ditulis untuk pemilik OmniClip, bukan untuk pemrogram.

Ada satu hal yang harus dikerjakan **sekali seumur hidup**, dan sesudah itu
menambah akun kedua, ketiga, dan seterusnya cuma satu tekan.

---

## Kenapa tidak bisa langsung "login"

Google tidak menerima unggahan dari program sembarangan. Ia hanya menerima dari
**aplikasi yang terdaftar**, dan kuota unggah YouTube dihitung **per aplikasi**
— bukan per akun. Kalau OmniClip membawa satu kunci bawaan untuk semua
penggunanya, kuota satu orang akan menghabiskan kuota semua orang, dan pada
hari yang sibuk tidak ada satu pun yang bisa mengunggah.

Karena itu aplikasinya harus atas nama Anda sendiri. Gratis, dan sekitar
sepuluh menit.

---

## Langkah 1 — daftarkan aplikasinya (sekali saja)

Semua langkah ini juga ada **di dalam aplikasi**: buka **Akun → Tambah akun →
Tunjukkan langkahnya**, lengkap dengan alamat yang tinggal disalin.

1. Buka <https://console.cloud.google.com/projectcreate> dan buat satu project.
   Namanya bebas, misalnya `OmniClip`.
2. Masuk ke **APIs & Services → Library**, lalu nyalakan dua ini:
   - **YouTube Data API v3**
   - **Google Drive API**
3. Masuk ke **OAuth consent screen**:
   - Pilih **External**.
   - Isi nama aplikasi dan alamat surel Anda.
   - Pada **Test users**, tambahkan **setiap alamat Gmail** yang akan Anda pakai
     di OmniClip. Ini bagian yang paling sering terlewat: akun yang tidak
     terdaftar di sini akan **ditolak Google** saat login, dengan pesan yang
     tidak menjelaskan sebabnya.
4. Masuk ke **Credentials → Create credentials → OAuth client ID**:
   - Pilih jenis **Desktop app** (paling mudah).
   - Kalau Anda memilih **Web application**, tambahkan alamat pengalihan yang
     ditampilkan aplikasi ke daftar **Authorized redirect URIs**. Alamatnya
     memuat nomor port yang sedang dipakai, jadi salin dari layar — jangan
     diketik dari ingatan.
5. Unduh berkas JSON-nya.
6. Di OmniClip: **Akun → Tambah akun → Pasang berkas OAuth client**.

---

## Langkah 2 — tambah akun (berkali-kali)

Sesudah langkah 1 selesai, kartu **Tambah akun** berubah jadi satu tombol:

> **Masuk dengan Google**

Menekannya akan:

1. membuat akun baru di OmniClip,
2. membuka halaman izin Google di tab baru,
3. dan sesudah Anda memilih akun dan menekan izinkan, akun itu **diberi nama
   sendiri** dari alamat surelnya.

Ulangi untuk akun kedua, ketiga, dan seterusnya. Google akan selalu menanyakan
akun mana yang dipakai, jadi tidak ada risiko dua akun tersambung ke akun yang
sama.

---

## Apa yang berbeda antar akun

Tiap akun punya **miliknya sendiri**:

- folder klip hasil render,
- riwayat pencarian dan beranda (jadi akun "Horor" tidak menampilkan podcast),
- kanal YouTube dan Drive tujuan unggahan,
- akun TikTok, Facebook, dan Instagram,
- setelan unggah otomatis, termasuk jam tayang dan templat deskripsi.

Yang **dipakai bersama** hanya satu: aplikasi Google yang Anda daftarkan di
langkah 1, beserta kuota hariannya.

---

## TikTok, Facebook, dan Instagram

Polanya sama persis — daftarkan aplikasi sekali, lalu sambungkan akun per
akun — hanya portalnya yang berbeda:

- **TikTok**: <https://developers.tiktok.com/apps>
- **Facebook dan Instagram**: <https://developers.facebook.com/apps> (satu
  aplikasi Meta untuk keduanya)

Semuanya ada di **Akun → TikTok, Facebook, dan Instagram**, lengkap dengan
alamat pengalihan yang harus didaftarkan.

Dua hal yang perlu diketahui sebelum mencoba:

- **TikTok** memasukkan unggahan ke **kotak draf**; Anda yang menekan terbit di
  aplikasinya. Terbit langsung butuh izin yang harus ditinjau TikTok lebih
  dulu.
- **Instagram** hanya menerima akun **Bisnis/Kreator** yang tertaut ke Halaman
  Facebook, dan yang terkirim lewat API **pasti terbit** — tidak ada draf.

---

## Kalau ada yang tidak jalan

Buka **Pengaturan → Kesehatan sistem**. Di sana tertulis apa yang sudah siap
dan apa yang belum, beserta akibatnya masing-masing — termasuk akun mana yang
belum tersambung.
