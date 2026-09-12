# OmniClip sebagai Aplikasi Desktop

OmniClip dibungkus menjadi satu aplikasi yang dijalankan tiap orang di
komputernya sendiri: servernya ada di dalam, penyimpanannya sendiri-sendiri,
tidak ada hosting, tidak ada domain, tidak ada biaya bulanan.

Tersedia untuk **Windows** dan **Linux**.

---

## Untuk pengguna

1. Unduh — tautan ini selalu menunjuk versi terbaru, tanpa perlu akun GitHub:

   - Windows: <https://github.com/YosafatHizkiaPesik/OmniClip/releases/latest/download/OmniClip-windows.zip>
   - Linux: <https://github.com/YosafatHizkiaPesik/OmniClip/releases/latest/download/OmniClip-linux.tar.gz>

2. Ekstrak ke mana saja — Desktop, Documents, diska mana pun. **Jangan** ke
   Program Files: pembaruan otomatis butuh folder yang bisa Anda tulis sendiri.
3. Jalankan `OmniClip.exe` (Windows) atau `./OmniClip` (Linux).

Sebuah jendela hitam terbuka dan menuliskan alamatnya, lalu peramban terbuka
sendiri. **Jendela itu jangan ditutup** selama OmniClip dipakai — itulah
aplikasinya. Menutupnya sama dengan mematikan OmniClip.

### Saat pertama dipakai

Beberapa model diunduh sendiri, sekali seumur pemasangan:

| model | ukuran | untuk apa |
|---|---|---|
| YuNet | sudah ikut | menemukan wajah |
| SFace | 37 MB | mengenali SIAPA wajah itu — tanpanya nomor orang memakai tempat duduk |
| CAM++ | 27 MB | membedakan suara per orang |
| Whisper | ± 150 MB | menyalin ucapan, hanya untuk video yang tidak punya subtitle di YouTube |
| Piper | 63 MB | membacakan judul, hanya bila dipakai |

### Memperbarui

Aplikasi menanyakan sendiri ke GitHub apakah ada versi baru. Kalau ada, muncul
pita kecil di kepala halaman — klik, lalu **Pengaturan → Pembaruan aplikasi →
Unduh dan pasang**.

Yang terjadi setelah itu: berkasnya diunduh, diperiksa, lalu aplikasi menutup
sendiri dan terbuka kembali pada versi baru. Klip, setelan, API key, dan model
yang sudah diunduh tidak tersentuh — semuanya tinggal di folder terpisah.

Kalau tombol **Unduh dan pasang** tidak muncul padahal ada versi baru,
alasannya tertulis di situ. Yang paling sering: aplikasi dipasang di folder
yang tidak bisa ditulis. Pindahkan ke Documents, lalu coba lagi.

Menukar folder dikerjakan proses penolong yang menunggu aplikasi benar-benar
mati — sebuah `.exe` yang sedang berjalan tidak bisa menimpa dirinya sendiri.
Folder lama tidak dihapus melainkan diganti nama dulu, jadi kalau langkah
terakhir gagal, yang lama masih utuh di sebelahnya.

### Di mana berkas saya disimpan

| sistem | tempat |
|---|---|
| Windows | `C:\Users\<nama>\AppData\Local\OmniClip` |
| Linux | `~/.local/share/OmniClip` |

**Bukan** di dalam folder aplikasi — sengaja, supaya memperbarui OmniClip tidak
menghapus klip Anda.

Mau memindahkannya ke diska lain? Setel `OMNICLIP_STORAGE`:

```
Windows : set OMNICLIP_STORAGE=D:\OmniClip & OmniClip.exe
Linux   : OMNICLIP_STORAGE=/mnt/data/OmniClip ./OmniClip
```

### Membukanya dari HP

Aplikasi berjalan di PC, HP membukanya lewat Wi-Fi yang sama. Tanpa domain,
tanpa biaya:

1. Buka **Pengaturan → Kata sandi & akses**, pasang kata sandi. **Lakukan ini
   lebih dulu** — tanpa kata sandi, siapa pun di Wi-Fi yang sama bisa masuk,
   termasuk ke kanal YouTube yang tersambung.
2. Jalankan dengan alamat terbuka:
   ```
   Windows : set OMNICLIP_HOST=0.0.0.0 & OmniClip.exe
   Linux   : OMNICLIP_HOST=0.0.0.0 ./OmniClip
   ```
3. Cari alamat IP PC (`ipconfig` di Windows, `ip a` di Linux), lalu buka
   `http://<ip-itu>:8000` dari HP.

Di Windows, izinkan saat Windows Firewall bertanya, dan pilih **jaringan
privat** saja — jangan publik.

### Kalau ada masalah

| gejala | sebab yang paling sering |
|---|---|
| Peramban tidak terbuka sendiri | Buka alamat yang tertulis di jendela hitam secara manual |
| "Address already in use" tidak muncul lagi | Aplikasi mencari port kosong sendiri, 8000 sampai 8019 |
| Windows Defender menahan aplikasinya | Aplikasi belum bertanda tangan digital. **More info → Run anyway**, atau bangun sendiri dari sumbernya |
| Unduhan YouTube gagal, "not a bot" | Lihat **Pengaturan → Cookies YouTube** |

Untuk memeriksa apakah pemasangannya lengkap:

```
OmniClip.exe --periksa      (Windows)
./OmniClip --periksa        (Linux)
```

---

## Untuk yang membangun

### Lewat GitHub, tanpa komputer Windows

Ini jalur yang dipakai. Repositori ini publik, jadi menit GitHub Actions gratis
tanpa batas.

```bash
# 1. naikkan nomor di backend/app/version.py
# 2. tag dengan angka yang SAMA PERSIS
git tag v1.0.2 && git push --tags
```

Alur build menolak tag yang tidak cocok dengan `app/version.py`. Itu bukan
kerewelan: rilis `v1.0.2` yang isinya mengaku `1.0.1` akan membuat setiap
pemasangan menawarkan pembaruan yang sama, memasangnya, lalu menawarkannya
lagi — selamanya.

Beberapa menit kemudian, `.exe` Windows dan `.tar.gz` Linux muncul di halaman
Releases. Alurnya ada di `.github/workflows/bangun-aplikasi.yml`, dan bisa juga
dijalankan tanpa tag lewat tombol **Run workflow**.

### Di komputer sendiri

```bash
cd frontend && npm ci && npm run build     # antarmuka HARUS lebih dulu
cd ../backend
pip install -r requirements.txt -r requirements-build.txt
python ../tools/ambil_ffmpeg.py            # ffmpeg statis -> backend/bin/
pyinstaller omniclip.spec --noconfirm
./dist/OmniClip/OmniClip --periksa
```

PyInstaller **tidak bisa** membangun untuk sistem lain: `.exe` Windows harus
dibangun di Windows. Itulah sebabnya GitHub Actions ada di sini.

### `--periksa` adalah gerbangnya, bukan pelengkap

Sebuah bundel bisa terbangun mulus dan tetap kehilangan satu pustaka biner atau
satu berkas font. Kehilangan seperti itu tidak muncul saat membangun — ia
muncul di mesin pengguna, berminggu-minggu kemudian, sebagai satu fitur yang
diam-diam tidak bekerja.

`--periksa` menjalankan setiap bagian yang bisa hilang, **di sistem yang sama
dengan yang akan memakainya**: 16 pustaka, berkas yang dibundel, ffmpeg beserta
7 filter dan 2 encoder yang benar-benar dipakai, detektor wajah yang sungguhan
dibuat, migrasi basis data, dan satu subtitle yang benar-benar dibakar ke
gambar. CI menjalankannya dan **menggagalkan build** kalau ada yang kurang.

Uji subtitle itu ada karena satu cacat nyata. Parser filtergraph ffmpeg
memperlakukan `:` sebagai pemisah opsi, dan `fontsdir` di Windows berbentuk
`C:\Program Files\...`. Tanpa penyiapan, ffmpeg membaca `C` sebagai akhir opsi
dan mengira sisanya adalah nama berkas subtitle:

```
Could not create a libass track when reading file 'uji/OmniClip/fonts'
```

Setiap render bersubtitle akan gagal — **hanya di Windows**, dan hanya di mesin
pengguna. Di Linux ketiga tempat yang menyusun path tampak benar karena path
Linux tidak punya `:` maupun `\`. Sekarang ketiganya memakai satu fungsi,
`services/paths.ffpath()`, dan `--periksa` membuktikannya di path sungguhan.

### Anggaran ukuran

| bagian | ukuran |
|---|---|
| ffmpeg + ffprobe statis | 160 MB |
| opencv + pustakanya | 137 MB |
| ctranslate2 + pustakanya | 135 MB |
| av (PyAV) + pustakanya | 104 MB |
| onnxruntime | 61 MB |
| piper | 45 MB |
| numpy | 42 MB |
| sisanya | ± 86 MB |
| **total terpasang** | **± 770 MB** |

Dua pemangkasan yang sudah dilakukan, keduanya tanpa kehilangan fungsi:

- **101 MB**: `googleapiclient` membawa deskripsi setiap layanan Google — 586
  berkas. OmniClip memakai dua (`youtube`, `drive`). Sisanya dibuang di dalam
  spec, bukan lewat `excludes`, karena paketnya sendiri tetap dibutuhkan.
- **185 MB**: ffmpeg dari BtbN berukuran 345 MB sepasang; build statis
  johnvansickle 160 MB, dengan ketujuh filter dan kedua encoder yang dipakai
  OmniClip. Diukur, bukan ditebak — `tools/ambil_ffmpeg.py` menjalankan binernya
  dan menanyakan kemampuannya sebelum menyatakan berhasil.

### Lisensi ffmpeg

Build yang dipakai adalah varian **GPL**, dan itu memang harus: varian LGPL
tidak memuat libx264, dan tanpa x264 tidak ada satu klip pun yang bisa
di-encode. OmniClip memanggil ffmpeg sebagai **proses terpisah**, bukan
menautkannya sebagai pustaka.

### Kenapa peramban, bukan jendela aplikasi

Antarmuka OmniClip adalah halaman web yang sudah matang. Membungkusnya lagi
dengan Electron menambah ± 150 MB dan satu lapis yang bisa rusak sendiri;
membungkusnya dengan pywebview menambah ketergantungan pada WebView2 yang
belum tentu ada. Peramban yang sudah terpasang di komputer pengguna
mengerjakannya lebih baik daripada keduanya.
