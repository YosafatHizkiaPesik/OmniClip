# Membuka OmniClip dari Luar Rumah

Panduan ini membuat OmniClip bisa dibuka dari HP, laptop, atau tablet mana pun
lewat **Cloudflare Tunnel**, tanpa membuka satu port pun di router, dan tanpa
memindahkan pekerjaan berat ke mesin lain.

Yang mengerjakan klip tetap komputer ini. Cloudflare hanya menyampaikan.

> **Syarat yang tidak bisa ditawar:** komputer ini harus menyala saat dipakai.
> Kalau tidur, aplikasinya mati. Itu harga dari menjalankan render di mesin
> sendiri — dan alasan angkanya masuk akal: render di sini 0,5–0,9× durasi
> klip pada 8 inti, sesuatu yang tidak diberikan hosting gratis mana pun.

---

## Bagian 1 — Tiga hal yang harus beres sebelum menyalakan terowongan

### 1a. Bangun frontend

Selama pengembangan, antarmuka dilayani Vite di port 5173 dan backend di 8000 —
dua alamat. Untuk akses jarak jauh keduanya harus jadi satu, supaya hanya ada
satu terowongan dan CORS tidak lagi ikut bermain:

```bash
cd frontend
npm run build
```

Hasilnya masuk ke `frontend/dist`, dan backend otomatis menyajikannya di `/`
saat berikutnya dijalankan. Ia akan mencatat ini di log:

```
Frontend hasil build disajikan dari .../frontend/dist
```

Ulangi `npm run build` setiap kali antarmuka diubah. Tanpa itu, yang dilihat
HP adalah versi lama.

### 1b. Pasang kata sandi

**Ini bagian yang paling penting di seluruh dokumen.**

Sampai sekarang OmniClip tidak punya pemeriksaan siapa pun — dan itu memang
cukup selama ia hanya mendengar di `127.0.0.1`. Begitu ia punya alamat publik,
"tidak ada yang memeriksa" berubah artinya: siapa pun yang sampai ke alamatnya
bisa **mengunggah ke kanal YouTube Anda**, membaca API key Anda, dan mengunduh
seluruh isi penyimpanan.

Buka **Pengaturan → Kata sandi & akses**, isi kata sandi minimal 8 karakter.
Setelah tersimpan, aplikasi langsung terkunci di semua perangkat.

Dari terminal juga bisa:

```bash
cd backend
venv/bin/python reset_password.py
```

### 1c. Paksa gerbangnya menyala

Jalankan backend dengan:

```bash
OMNICLIP_AUTH=on venv/bin/python run.py
```

Bedanya dengan bawaan: `OMNICLIP_AUTH=on` menolak **start sama sekali** bila
kata sandinya belum ada, dan menolak permintaan untuk melepas kata sandi lewat
antarmuka. Tanpa itu, satu klik "Lepas kata sandi" dari HP membuka aplikasi
yang sedang terbit ke internet.

| nilai | arti |
|---|---|
| `auto` (bawaan) | gerbang aktif kalau kata sandi ada |
| `on` | gerbang wajib; gagal start tanpa kata sandi |
| `off` | gerbang mati — **jangan pernah** dipakai bersama terowongan |

### Memeriksa bahwa ketiganya benar

```bash
curl -s localhost:8000/api/auth/status     # required:true, has_password:true
curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/api/settings   # 401
```

Kalau baris kedua menjawab `200`, gerbangnya belum menyala. Berhenti di sini.

---

## Bagian 2 — Cloudflare Tunnel

### Biayanya

| barang | harga |
|---|---|
| `cloudflared` | gratis, sumber terbuka |
| Cloudflare Tunnel | gratis |
| Cloudflare Access (Zero Trust) | gratis sampai 50 pengguna |
| **Nama domain** | **± US$10,44/tahun ≈ Rp 170.000** di Cloudflare Registrar (harga modal, tanpa markup). TLD murah seperti `.xyz` bisa di bawah Rp 50.000 tahun pertama. |

Domain adalah satu-satunya yang berbayar, dan ia **wajib**: terowongan dengan
alamat tetap dan Cloudflare Access hanya bisa dipasang pada domain yang Anda
kendalikan di Cloudflare.

> **Terowongan cepat (`cloudflared tunnel --url`) memang tanpa domain dan tanpa
> biaya — dan tidak boleh dipakai di sini.** Alamatnya berubah tiap restart,
> dan yang lebih penting: **Cloudflare Access tidak bisa dipasang di atasnya**.
> Artinya satu-satunya penjaga adalah kata sandi OmniClip, di alamat yang
> terbuka untuk seluruh internet. Boleh untuk mencoba lima menit, bukan untuk
> dipakai.

### 2a. Pasang cloudflared

```bash
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
  | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" \
  | sudo tee /etc/apt/sources.list.d/cloudflared.list
sudo apt update && sudo apt install cloudflared
```

### 2b. Sambungkan ke akun

```bash
cloudflared tunnel login
```

Akan membuka peramban; pilih domain Anda.

### 2c. Buat terowongan dan alamatnya

```bash
cloudflared tunnel create omniclip
cloudflared tunnel route dns omniclip omniclip.domain-anda.com
```

Perintah pertama mencetak sebuah UUID dan menulis berkas kredensial di
`~/.cloudflared/<UUID>.json`. **Berkas itu setara kunci terowongan** — jangan
disalin ke mana pun, jangan masuk git.

### 2d. Konfigurasi

`~/.cloudflared/config.yml`:

```yaml
tunnel: omniclip
credentials-file: /home/ynot/.cloudflared/<UUID>.json

ingress:
  - hostname: omniclip.domain-anda.com
    service: http://127.0.0.1:8000
  - service: http_status:404
```

Perhatikan `127.0.0.1`. **Alamat dengar backend tidak perlu diubah sama
sekali** — `cloudflared` menyambung dari dalam mesin ini, jadi tidak ada satu
port pun yang terbuka ke jaringan. `OMNICLIP_HOST` hanya dipakai kalau suatu
saat Anda ingin dijangkau dari LAN.

### 2e. Jalankan

```bash
cloudflared tunnel run omniclip          # untuk mencoba
sudo cloudflared service install         # supaya hidup sendiri saat booting
```

### 2f. Pasang pintunya — Cloudflare Access

**Jangan lewati bagian ini.** Tanpa Access, alamat `https://omniclip.domain-anda.com`
terbuka untuk seluruh internet, dan satu-satunya yang menjaganya adalah kata
sandi OmniClip.

Di dasbor Cloudflare → **Zero Trust → Access → Applications → Add an application
→ Self-hosted**:

- Domain aplikasi: `omniclip.domain-anda.com`
- Kebijakan: **Allow**, dengan aturan *Emails* → daftar email yang boleh masuk
- Metode masuk: **One-time PIN** (kode lewat email — tanpa perlu akun apa pun)

Setelah ini, pengunjung diminta emailnya lebih dulu, dapat kode, baru sampai ke
layar masuk OmniClip. Dua lapis, dan lapisan luar tidak pernah membiarkan orang
asing menyentuh aplikasi sama sekali.

### 2g. Uji dari luar

Buka `https://omniclip.domain-anda.com` dari HP **dengan data seluler, bukan
wifi rumah**. Ini satu-satunya pengujian yang berarti — lewat wifi rumah, HP
bisa saja sampai lewat jaringan lokal dan Anda tidak menguji apa pun.

Yang harus terjadi berurutan: halaman email Cloudflare → kode → layar "OmniClip
terkunci" → kata sandi → aplikasi.

---

## Bagian 3 — Yang tidak boleh ikut terbit

Tiga berkas yang masing-masing cukup untuk menyakiti Anda:

| berkas | kalau bocor |
|---|---|
| `backend/.env` | API key Gemini — kuota dan tagihan Anda |
| `OmniClip_Storage/google_client_secret.json` | identitas OAuth aplikasi Anda |
| `OmniClip_Storage/google_token.json` | **cukup untuk mengunggah ke kanal YouTube Anda** |

Ketiganya diabaikan git. Ketiganya juga sudah diuji tidak bisa dijangkau lewat
jaringan, termasuk dengan sesi yang sah dan dengan jalur `../`:

```
/../backend/.env                                    -> shell aplikasi, bukan berkasnya
/api/media/local_downloads/../../../backend/.env    -> 404
/api/file/edited_clips/../../../backend/.env        -> 404
/storage/                                           -> shell aplikasi (mount lama sudah dihapus)
```

Catatan yang perlu diketahui: penyimpanan proyek ini berada di partisi
`fuseblk`, yang **tidak menghormati izin berkas** — `backend/.env` terbaca
`-rwxrwxrwx` walau di-`chmod 600`. Itu tidak berpengaruh pada akses lewat
jaringan, tapi berarti siapa pun yang memakai komputer ini bisa membacanya.

---

## Bagian 4 — Lupa kata sandi

Tidak ada pemulihan lewat email; tidak ada email di sini. Pemulihannya dari
terminal komputer ini:

```bash
cd backend
venv/bin/python reset_password.py           # pasang kata sandi baru
venv/bin/python reset_password.py --lepas   # kembali ke mode lokal
```

Mengganti kata sandi **mencabut seluruh sesi di semua perangkat** — itu juga
cara mengeluarkan HP yang hilang atau orang yang tidak lagi perlu akses.

Kalau backend menolak start karena `OMNICLIP_AUTH=on` tanpa kata sandi:
jalankan sekali tanpa variabel itu, pasang kata sandinya, lalu nyalakan lagi.

---

## Bagian 5 — Risiko yang jujur

### Cloudflare, bukan YouTube, yang paling mungkin menegur

Ketentuan layanan Cloudflare membatasi penyaluran berkas non-HTML besar (video)
lewat jaringan gratis mereka. Memutar klip 40 MB sesekali untuk meninjau hasil
tidak akan diributkan. Menjadikan alamat ini tempat menonton rutin — atau
membagikannya ke banyak orang untuk streaming — bisa.

Penawarnya sederhana: **tinjau di sini, simpan ke perangkat, tonton dari
perangkat.** Tombol unduh sudah ada di setiap klip.

### Batas teknis Cloudflare yang menyentuh aplikasi ini

| batas | pengaruh |
|---|---|
| Unggahan ≤100 MB per permintaan (paket gratis) | tidak menyentuh apa pun: klip mengalir keluar, bukan masuk |
| Tanggapan pertama harus datang <100 detik | aman: pekerjaan berat masuk antrean dan langsung menjawab `202`, kemajuannya lewat SSE |
| Proxy menyangga aliran | sudah ditangani: SSE mengirim `no-transform`, `X-Accel-Buffering: no`, dan denyut tiap 15 detik |

### YouTube

Mengunduh dari YouTube melanggar ketentuan layanan mereka. Yang perlu dibedakan:

- **Pemblokiran unduhan** — hampir pasti terjadi sesekali, sudah terjadi.
  Bukan penindakan, hanya pemeriksaan bot. Penawarnya cookies dan `yt-dlp`
  yang mutakhir.
- **Penindakan terhadap alat** — yang pernah kena adalah **layanan publik**:
  situs pengunduh yang mengiklankan diri, terbuka untuk siapa saja. Instansi
  pribadi di balik Cloudflare Access, tidak diindeks, tidak diiklankan, tidak
  berada dalam kategori itu.
- **Yang benar-benar berisiko bagi Anda adalah mengunggah.** Menaikkan potongan
  video orang lain ke kanal sendiri bisa berujung teguran hak cipta atau
  penandaan "konten daur ulang" — dan itu menyasar **kanal Anda**, bukan alat
  ini. Risiko ini jauh lebih besar daripada risiko apa pun dari mengunduh.

Aplikasi ini sudah menolak diindeks (`X-Robots-Tag: noindex`, `robots.txt`
melarang semuanya), jadi ia tidak akan muncul di hasil pencarian siapa pun.

---

## Ringkasan perintah harian

```bash
# sekali, setiap kali antarmuka berubah
cd frontend && npm run build

# backend
cd backend && OMNICLIP_AUTH=on venv/bin/python run.py

# terowongan (kalau belum dipasang sebagai service)
cloudflared tunnel run omniclip
```
