# OmniClip: pegangan untuk setiap sesi

OmniClip adalah aplikasi auto-clipper: mengunduh video (YouTube dan situs
lain), memilih momen dengan AI atau heuristik lokal, membingkai ulang ke 9:16,
memberi subtitle dan judul, merender dengan ffmpeg, lalu mengunggah ke
YouTube/Drive. Aplikasinya berupa server lokal yang dibuka di peramban, dan
dibungkus PyInstaller untuk Windows dan Linux.

## Pekerjaan aktif

**JOB-4: Montase**, studio penyunting video lengkap (seperti CapCut) dengan
animasi buatan AI berbasis Remotion. **Baca `JOB-4.md` sebelum mengerjakan apa
pun tentang Montase.** Mulai dari "Tugas berikutnya" di Papan status, ikuti
aturan main di bagian 5. Sesudah setiap tugas: centang (tanggal + hash
commit), perbarui Papan status, commit, push.

## Peta dokumen

| Berkas | Isi |
|---|---|
| `FITUR.md` | Katalog semua fitur: apa, manfaat, contoh kasus, dan saran fitur berikutnya |
| `JOB-5.md` | Orisinalitas dan algoritma YouTube untuk Montase (aktif) |
| `JOB-4.md` | Rencana dan kemajuan Montase (selesai, menunggu uji pemilik) |
| `JOB-3.md` | Tampilan seperti YouTube dan dua bahasa (selesai, kecuali J3-13) |
| `JOB-2.md` | Kepatuhan kebijakan konten YouTube: komentar, kredit, nilai tambah, gerbang tinjau |
| `JOB-1.md` | Mengurus izin unggah dan daftar pekerjaan lama |
| `CATATAN.md` | Yang belum selesai di Studio Klip dan acuan teknis |
| `UJI-LANGSUNG.md` | Tes bernomor yang dijalankan pemilik di aplikasi sungguhan |

## Struktur

- `backend/app/`: FastAPI. `routers/` (endpoint), `services/` (logika),
  `repos/` (akses SQLite), `db.py` (skema + `MIGRATIONS`), `config.py` (jalur
  penyimpanan).
- `frontend/src/`: React 19 + Vite. `routes/`, `components/`,
  `features/studio/` (Studio Klip), `lib/` (`api.js`, `i18n.js`),
  `locales/` (`id.js`, `en.js`).
- `OmniClip_Storage/`: data pengguna saat pengembangan (tidak masuk git).

## Perintah

```bash
./start-backend.sh                       # backend di 127.0.0.1:8000
cd frontend && npm run dev               # antarmuka di :5173, /api diteruskan ke backend
cd backend && python -m unittest discover tests
cd frontend && npm test && npm run lint && npm run build
```

## Kebiasaan repo ini

- Nama, komentar, docstring, pesan commit, dan dokumen berbahasa Indonesia.
  Docstring menjelaskan **kenapa**, beserta angka hasil ukur bila ada.
- Semua teks antarmuka lewat `t('kunci')`, dengan kunci di `id.js` **dan**
  `en.js`. `i18n.test.js` menjaga keduanya sama. Pesan dari server
  diterjemahkan lewat `bahasa.py` dan `kamus_en.py`.
- Klien tidak pernah mengirim jalur berkas, hanya id. Jalurnya dicari di
  server.
- Fitur otomatis/AI **mengusulkan**: hasilnya tampil, bertanda, beralasan, dan
  bisa dihapus satu per satu.
- Bobot model, media, kredensial, dan `OmniClip_Storage/*` tidak pernah
  di-commit (lihat `.gitignore`).
- Menaikkan versi hanya di `backend/app/version.py`, dengan tag git yang sama.
