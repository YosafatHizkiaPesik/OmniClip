# Windows Defender dan tanda tangan digital

Ditulis untuk pemilik OmniClip. Harga dan syarat di bawah berlaku September
2026 — keduanya berubah, jadi periksa lagi sebelum membeli.

---

## Kenapa Defender curiga

Berkas `.exe` yang **tidak ditandatangani** dan **belum pernah diunduh banyak
orang** adalah bentuk yang paling mirip malware bagi Windows. Ia tidak punya
nama penerbit untuk diperiksa dan tidak punya riwayat untuk dibandingkan.
Ditambah lagi, OmniClip dibungkus PyInstaller — bentuk yang juga dipakai
sebagian besar malware Python, sehingga polanya sudah dikenali mesin pemindai.

Tidak ada cara membuat peringatan itu hilang seluruhnya tanpa tanda tangan.
Yang bisa dilakukan tanpa membayar sudah dikerjakan (lihat bagian terakhir).

---

## Tiga jalan, dari yang gratis

### 1. Laporkan sebagai salah deteksi — gratis, bisa hari ini

Microsoft menerima laporan salah deteksi dan biasanya menjawab dalam 1–3 hari.
Sesudah diterima, Defender berhenti menandai berkas itu **untuk semua orang**.

- Buka <https://www.microsoft.com/en-us/wdsi/filesubmission>
- Pilih **Software developer**, unggah `OmniClip.exe` (atau seluruh zip).
- Sebutkan bahwa berkas dibangun otomatis di GitHub Actions dan sertakan
  tautan rilisnya.

**Kekurangannya:** harus diulang **setiap rilis**, karena yang dikenali adalah
sidik berkasnya. Ini penambal, bukan penyelesaian — tapi ia gratis dan cepat.

### 2. Sertifikat gratis untuk proyek sumber terbuka — SignPath Foundation

<https://signpath.io/solutions/open-source-community> memberi sertifikat
penandatanganan **gratis** untuk proyek sumber terbuka.

**Syaratnya:** kode harus publik **dan** memakai lisensi sumber terbuka yang
diakui. OmniClip sudah publik di GitHub, tapi **belum punya berkas lisensi** —
tanpa itu, secara hukum ia "hak cipta penuh", dan pendaftaran akan ditolak.

Ini juga keputusan yang harus dipikirkan matang kalau OmniClip nanti dijual:
lisensi sumber terbuka mengizinkan orang lain memakai dan menyebarkan kodenya.
Menjual perangkat lunak sumber terbuka itu sah dan biasa, tapi yang dijual
menjadi kemudahan, dukungan, dan layanannya — bukan hak memakainya.

### 3. Beli sertifikat sendiri — ± Rp 4–7 juta per tahun

Yang dibutuhkan **OV Code Signing** (Organization Validation). Harga pasaran
US$250–400 per tahun dari penjual seperti Sectigo, SSL.com, atau Comodo.

Satu hal yang menghemat uang Anda: **sejak Maret 2024, sertifikat EV tidak lagi
memberi kekebalan SmartScreen seketika.** EV dan OV sekarang membangun reputasi
dengan cara yang sama, yaitu dari jumlah unduhan. Jadi **jangan bayar lebih
untuk EV** — itu dulu satu-satunya alasan orang membelinya.

Penerbit akan memverifikasi identitas Anda: badan usaha (PT/CV) dengan dokumen
resmi, atau perorangan dengan KTP/paspor pada sebagian penerbit.

**Azure Artifact Signing** (dulu Trusted Signing) hanya US$9,99/bulan dan jauh
lebih murah — tapi verifikasi peroranganya **baru terbuka untuk Amerika Serikat
dan Kanada**. Untuk Indonesia, jalur ini tertutup kecuali lewat badan usaha
yang bisa diverifikasi Microsoft.

---

## Kalau sertifikatnya sudah ada

Alur build sudah siap menerimanya. Pasang dua rahasia di GitHub
(**Settings → Secrets and variables → Actions**):

| Nama | Isi |
|---|---|
| `WINDOWS_PFX_BASE64` | berkas `.pfx` yang di-base64: `base64 -w0 sertifikat.pfx` |
| `WINDOWS_PFX_PASSWORD` | kata sandi berkas `.pfx` itu |

Selesai. Rilis berikutnya akan ditandatangani sendiri, lengkap dengan stempel
waktu — stempel waktu itu yang membuat tanda tangannya tetap sah bahkan setelah
sertifikatnya kedaluwarsa. Selama rahasianya belum ada, langkah itu dilewati
dan build tetap berhasil.

Sertifikat pada **token perangkat keras** (kebanyakan EV) tidak bisa dipakai di
GitHub Actions dengan cara ini; ia harus ditandatangani dari komputer sendiri,
atau lewat layanan seperti SignPath.

---

## Yang sudah dikerjakan tanpa membayar

Semuanya ada di rilis 1.0.8 ke atas:

- **Keterangan versi Windows** ditanam ke dalam `.exe`: nama produk, penerbit,
  nomor versi. Berkas tanpa keterangan apa pun adalah pola yang paling sering
  ditandai.
- **Ikon aplikasi** ikut ditanam. Berkas tanpa ikon lebih mencurigakan bagi
  penilai heuristik.
- **Tanpa UPX.** Pemampat berkas adalah salah satu pemicu terkuat, dan OmniClip
  memang tidak memakainya.
- **Bentuk satu-folder, bukan satu-berkas.** Berkas tunggal yang membongkar
  dirinya ke folder sementara saat dijalankan adalah persis perilaku yang
  dicari pemindai.
- **Sidik SHA-256** diterbitkan bersama tiap rilis, sehingga siapa pun bisa
  memastikan berkas yang ia unduh sama dengan yang dibangun.

Keempat hal pertama mengurangi kemungkinan ditandai. Tidak ada yang
menghilangkannya — hanya tanda tangan dan reputasi yang bisa.
