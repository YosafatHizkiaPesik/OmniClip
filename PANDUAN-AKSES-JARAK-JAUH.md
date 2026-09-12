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

### Domain: mana yang murah

Domain adalah satu-satunya yang berbayar, dan ia **wajib** — terowongan
beralamat tetap dan Cloudflare Access hanya bisa dipasang pada domain yang
nameserver-nya Anda arahkan ke Cloudflare.

Yang **tidak** wajib: membelinya dari Cloudflare. Cloudflare menerima domain
dari registrar mana pun; yang diubah hanya nameserver-nya. Jadi belilah di
tempat termurah.

| pilihan | perkiraan harga | catatan |
|---|---|---|
| **`.my.id`** di registrar Indonesia (Rumahweb, DomaiNesia, Niagahoster, Jagoan Hosting) | **± Rp 15.000–30.000/tahun** | Paling murah, dan **perpanjangannya tetap murah**. Butuh KTP/NPWP saat daftar. Pilihan terbaik. |
| `.web.id` | ± Rp 25.000–55.000/tahun | Sama-sama lokal, sedikit lebih mahal |
| `.xyz` di Porkbun/Namecheap | ± US$1–3 tahun pertama, **US$12–15 perpanjangan** | Murah sekali di awal, mahal seterusnya |
| `.com` di Cloudflare Registrar | ± US$10,44/tahun ≈ Rp 170.000 | Harga modal tanpa markup, harga tetap tiap tahun |

**Saran: `.my.id`.** Alamat seperti `omniclip.namaanda.my.id` tidak perlu
terlihat profesional — tidak ada yang akan melihatnya kecuali Anda dan orang
yang Anda undang, dan halamannya menolak diindeks mesin pencari.

> Harga di atas berlaku saat dokumen ini ditulis (September 2026). Periksa lagi
> saat membeli, terutama harga **perpanjangan** — bukan harga tahun pertama.

**Yang harus dihindari:** penyedia domain gratis semacam Freenom (`.tk`, `.ml`)
— domainnya rutin ditarik kembali tanpa pemberitahuan, dan kehilangan domain
berarti kehilangan alamat OmniClip Anda.

Setelah membeli, di dasbor registrar ganti nameserver-nya ke dua alamat yang
diberikan Cloudflare saat Anda menambahkan domain itu (Cloudflare → Add a site
→ paket **Free**). Perubahan nameserver butuh beberapa jam sampai berlaku.

### Sisanya gratis

| barang | harga |
|---|---|
| `cloudflared` | gratis, sumber terbuka |
| Cloudflare Tunnel | gratis |
| Cloudflare Access, termasuk masuk dengan Google | gratis sampai 50 pengguna |
| Cloudflare paket Free (DNS + proxy) | gratis |

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

### 2f. Pasang pintunya — Cloudflare Access, dengan masuk lewat Google

**Jangan lewati bagian ini.** Tanpa Access, alamat `https://omniclip.domain-anda.com`
terbuka untuk seluruh internet, dan satu-satunya yang menjaganya adalah kata
sandi OmniClip.

**Inilah tempat "masuk dengan Google" berada.** Tidak perlu kode apa pun di
OmniClip: Cloudflare yang memegang tombolnya, dan OmniClip menerima hasilnya.

**1. Pasang Google sebagai penyedia identitas.**
Zero Trust → **Settings → Authentication → Login methods → Add new → Google**.
Ikuti langkahnya; Cloudflare memandu pembuatan OAuth client di Google Cloud
Console dan memberi tahu persis redirect URI mana yang harus ditempel.

> Kalau ingin lebih cepat, lewati langkah ini dan pakai **One-time PIN** —
> Cloudflare mengirim kode ke email, tanpa akun apa pun. Bisa diganti ke Google
> kapan saja.

**2. Buat aplikasinya.**
Zero Trust → **Access → Applications → Add an application → Self-hosted**:

- Application domain: `omniclip.domain-anda.com`
- Identity providers: **Google** (centang)
- Policy: **Allow**, aturan *Emails* → `yosafathizkiapesik@gmail.com`, ditambah
  email siapa pun yang Anda beri akses

**3. Salin tag AUD-nya.**
Di halaman aplikasi yang baru dibuat, bagian **Overview**, ada
**Application Audience (AUD) Tag** — deretan panjang huruf dan angka. Salin.

**4. Beri tahu OmniClip, supaya tidak minta masuk dua kali.**

```bash
OMNICLIP_AUTH=on \
OMNICLIP_CF_ACCESS_TEAM=nama-tim-anda \
OMNICLIP_CF_ACCESS_AUD=<tag-aud-yang-tadi-disalin> \
venv/bin/python run.py
```

`nama-tim-anda` adalah bagian depan alamat tim Anda: kalau tim Anda
`yosafat.cloudflareaccess.com`, isinya `yosafat`.

Setelah ini, membuka OmniClip dari luar berarti: klik **Sign in with Google** →
selesai. Layar kata sandi OmniClip tidak muncul lagi dari alamat itu.

Opsional, pagar kedua di sisi Anda sendiri:

```bash
OMNICLIP_CF_ACCESS_EMAILS=yosafathizkiapesik@gmail.com,teman@contoh.com
```

Kalau diisi, dua daftar harus sepakat — berguna kalau kebijakan Access suatu
saat tidak sengaja dilonggarkan.

**Cara OmniClip memeriksanya** (bukan sekadar percaya header):

- tanda tangan RS256 token dicocokkan dengan kunci publik tim Anda,
- `aud` harus **sama persis** dengan tag aplikasi Anda — tanpa ini, token sah
  dari aplikasi Access siapa pun di internet akan diterima,
- `iss` harus tim Anda, dan `exp` belum lewat,
- header hanya dipercaya bila permintaannya datang dari terowongan di mesin ini.

Kesebelas kasusnya bisa dijalankan ulang kapan saja:

```bash
cd backend && venv/bin/python uji_cf_access.py
```

**Kalau ternyata masih diminta kata sandi**, buka **Pengaturan → Kata sandi &
akses**. Di sana tertulis alasannya — `aud` yang keliru terlihat persis seperti
nama tim yang keliru, dan tanpa keterangan itu keduanya hanya tampak sebagai
"tidak berhasil".

### 2g. Uji dari luar

Buka `https://omniclip.domain-anda.com` dari HP **dengan data seluler, bukan
wifi rumah**. Ini satu-satunya pengujian yang berarti — lewat wifi rumah, HP
bisa saja sampai lewat jaringan lokal dan Anda tidak menguji apa pun.

Yang harus terjadi: halaman Cloudflare → **Sign in with Google** → langsung
masuk ke aplikasi. **Tanpa** layar "OmniClip terkunci" — kalau layar itu masih
muncul, berarti `OMNICLIP_CF_ACCESS_TEAM` atau `OMNICLIP_CF_ACCESS_AUD` belum
benar; alasan persisnya tertulis di Pengaturan → Kata sandi & akses.

Coba juga dari email yang **tidak** ada di kebijakan Access: harus ditolak
Cloudflare sebelum menyentuh OmniClip sama sekali.

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

## Bagian 4 — Lalu kata sandi OmniClip masih untuk apa?

Tiga hal, dan ketiganya tetap berlaku setelah Google terpasang:

1. **Membuka dari komputer ini.** Di `localhost` tidak ada Cloudflare sama
   sekali, jadi tidak ada identitas Google yang bisa diperiksa.
2. **Jaring pengaman saat Cloudflare salah setel.** Kebijakan Access yang
   keliru, atau terowongan yang menunjuk ke tempat yang salah, adalah kegagalan
   yang jauh lebih mungkin daripada kata sandi yang tertebak. Saat itu terjadi,
   kata sandi adalah yang tersisa.
3. **Saat Access belum dipasang.** Selama masa itu ia satu-satunya penjaga.

Yang tidak dilakukannya: ia **tidak** meminta Anda masuk dua kali. Begitu
Cloudflare Access disetel dengan benar, layar kata sandi tidak muncul lagi dari
alamat publik itu.

---

## Bagian 5 — Lupa kata sandi

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

## Bagian 6 — Risiko yang jujur

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
cd backend && OMNICLIP_AUTH=on \
  OMNICLIP_CF_ACCESS_TEAM=nama-tim-anda \
  OMNICLIP_CF_ACCESS_AUD=tag-aud-aplikasi \
  venv/bin/python run.py

# terowongan (kalau belum dipasang sebagai service)
cloudflared tunnel run omniclip
```
