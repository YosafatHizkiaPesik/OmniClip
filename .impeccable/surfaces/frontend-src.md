---
version: 1
slug: "frontend-src"
primary_target: "frontend/src"
related_targets: []
---

Ruang lingkup: seluruh antarmuka OmniClip (frontend/src) — cangkang aplikasi,
YouTube Hub, halaman Tonton, Clip Studio, Editor, Klip Saya, Unduhan,
Pengaturan. Mode pengunjung: **Operate**.

Audiens: satu kreator berbahasa Indonesia, bekerja larut malam di mesinnya
sendiri, memotong podcast satu sampai dua jam jadi klip vertikal. Tugasnya:
meninjau 19–40 klip tawaran mesin, membetulkan subtitle baris per baris,
menandai penutur, memotong momen yang terlewat, lalu merender beberapa
sekaligus. Kendala: daftar panjang adalah keadaan normal; pekerjaan berat
berjalan di antrean latar; perkiraan mesin harus terbaca sebagai perkiraan.

Arah terpilih: **Partitur Bertanda** (kartu IMPECCABLE'S PICK, dipilih pengguna
di halaman keputusan — pilihan pengguna mengalahkan undian). Momen yang
diingat: satu tarikan mata ke sistem balok dan seluruh jam itu terbaca — siapa
bicara kapan, di mana klipnya, di mana energinya memuncak.

Belum diputuskan: apakah aplikasi akan dibuka dari HP lewat jaringan lokal
(butuh perubahan bind backend dan CORS) atau "fit untuk HP" hanya berarti tata
letak rapi di jendela sempit. Dirancang agar keduanya terlayani.

## Direction contract

THESIS: Satu jam rekaman dibaca seperti partitur — tiap narasumber satu balok
not, tiap klip satu huruf latihan. Menolak susunan bawaan kategori: papan
gelap beraksen neon dengan kartu kaca dan timeline gelombang tunggal di bawah.

OWN-WORLD: Panggung gelap (#0B0E14) mengelilingi pelat partitur terang
(#EDF1F6) — kertas yang disorot lampu meja, bukan layar yang digelapkan. Tinta
cetak musik #0E1420. Empat pensil konduktor sebagai peran fungsional, bukan
hiasan: merah latihan #D91E36 menandai klip, biru isyarat #1257C4 dan hijau
masuk #0B7A46 menandai penutur, stabilo #FFD400 menandai yang sedang aktif.
Balok bergaris tipis, huruf latihan dalam kotak tinta pekat, angka tabular,
lubang orkestra hitam sebagai satu-satunya tempat video hidup.

STORY: Pengguna membuka sebuah karya, membaca sistem baloknya sekali dan tahu
bentuk seluruh percakapan, lalu turun ke satu huruf latihan untuk membetulkan
liriknya, menandai suaranya, dan menambah huruf baru di birama yang terlewat.

FIRST VIEWPORT: Blok judul karya di atas pelat. Di bawahnya satu sistem balok
membentang selebar durasi: balok Orang 1, balok Orang 2, balok energi. Huruf
latihan merah berkotak duduk di atas tiap frasa klip; pita stabilo menandai
yang terpilih. Di bawah sistem, baris lirik yang bisa disunting langsung.
Kanan: lubang orkestra gelap berisi pratinjau 9:16 dan transport. Aksi utama
"Render & simpan" di blok judul, kanan atas.

FORM: Partitur orkestra bertanda pensil konduktor; peringkat 1 dari daftar
tujuh kandidat saya; dipilih pengguna sebagai IMPECCABLE'S PICK di atas undian
(indeks 6, Kotak Pita Lapangan). Seed key aac521b8.

FINISH: unreviewed and undocumented is unfinished; this build ends with the
finish review, the verdict, DESIGN.md, and every shipping raster carrying its
provenance.
