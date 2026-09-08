---
name: OmniClip
description: Partitur bertanda pensil konduktor — satu jam rekaman dibaca sekali pandang.
colors:
  stage: "#0B0E14"
  stage-2: "#151A24"
  ground: "#DDE4EC"
  plate: "#EDF1F6"
  plate-2: "#E3E9F1"
  plate-3: "#F6F8FB"
  ink: "#0E1420"
  ink-2: "#46536A"
  ink-3: "#6A7689"
  rule: "#B9C4D3"
  rule-2: "#CED7E3"
  reh: "#C81B32"
  reh-ink: "#FFFFFF"
  cue: "#0F52B8"
  entry: "#07683B"
  hl: "#F5C400"
  hl-wash: "#F5C40033"
  warn: "#B2560A"
  danger: "#B3182C"
typography:
  display:
    fontFamily: "Archivo Black, Archivo, sans-serif"
    fontSize: "clamp(1.35rem, 2.6vw, 1.95rem)"
    fontWeight: 400
    lineHeight: 1.08
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Archivo, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.84rem"
    fontWeight: 680
    lineHeight: 1.45
  body:
    fontFamily: "Archivo, ui-sans-serif, system-ui, 'Segoe UI', sans-serif"
    fontSize: "15px"
    fontWeight: 420
    lineHeight: 1.5
    fontFeature: "tabular-nums"
  label:
    fontFamily: "Archivo, sans-serif"
    fontSize: "0.68rem"
    fontWeight: 700
    letterSpacing: "0.1em"
    fontVariation: "'wdth' 80"
  caption:
    fontFamily: "Archivo, sans-serif"
    fontSize: "0.62rem"
    fontWeight: 700
    letterSpacing: "0.08em"
  rehearsal:
    fontFamily: "Archivo Black, sans-serif"
    fontSize: "0.72rem"
    fontWeight: 400
    letterSpacing: "0.02em"
rounded:
  sm: "2px"
  md: "3px"
  lg: "4px"
  hairline: "1px"
  full: "999px"
spacing:
  "2xs": "4px"
  xs: "6px"
  sm: "8px"
  md: "10px"
  lg: "14px"
  xl: "18px"
  "2xl": "22px"
components:
  button-primary:
    backgroundColor: "{colors.reh}"
    textColor: "{colors.reh-ink}"
    rounded: "{rounded.sm}"
    padding: "8px 14px"
    height: "36px"
    typography: "{typography.headline}"
  button-primary-disabled:
    backgroundColor: "{colors.plate-2}"
    textColor: "{colors.ink-3}"
    rounded: "{rounded.sm}"
    padding: "8px 14px"
  button-secondary:
    backgroundColor: "{colors.plate-3}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "8px 14px"
    height: "36px"
  button-secondary-hover:
    backgroundColor: "{colors.plate-2}"
    textColor: "{colors.ink}"
  field:
    backgroundColor: "{colors.plate-3}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "9px 11px"
  search-input:
    backgroundColor: "{colors.plate}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "11px 14px"
  chip:
    backgroundColor: "{colors.plate}"
    textColor: "{colors.ink-2}"
    rounded: "{rounded.sm}"
    padding: "7px 13px"
    height: "34px"
  chip-on:
    backgroundColor: "{colors.hl-wash}"
    textColor: "{colors.reh}"
    rounded: "{rounded.sm}"
    padding: "7px 13px"
  plate:
    backgroundColor: "{colors.plate}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
  plate-head:
    backgroundColor: "{colors.plate}"
    textColor: "{colors.ink}"
    padding: "10px 14px"
  pit:
    backgroundColor: "{colors.stage}"
    textColor: "#DCE4EE"
    rounded: "{rounded.md}"
  rehearsal-letter:
    backgroundColor: "{colors.reh}"
    textColor: "{colors.reh-ink}"
    rounded: "{rounded.hairline}"
    padding: "0 5px"
    height: "20px"
    typography: "{typography.rehearsal}"
  rehearsal-letter-manual:
    backgroundColor: "{colors.cue}"
    textColor: "{colors.reh-ink}"
  nav-item:
    backgroundColor: "{colors.stage}"
    textColor: "#93A2B8"
    padding: "11px 18px"
  nav-item-active:
    backgroundColor: "{colors.stage}"
    textColor: "#FFFFFF"
    padding: "11px 18px"
  tab-btn:
    backgroundColor: "transparent"
    textColor: "{colors.ink-3}"
    padding: "10px 4px"
  tab-btn-on:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    padding: "10px 4px"
---

# Design System: OmniClip

## Overview

**Creative North Star: "Partitur Bertanda Pensil Konduktor"**

Aplikasi ini membaca satu jam rekaman seperti seorang konduktor membaca partitur: satu balok not per narasumber, satu huruf latihan per klip, satu balok dinamika di bawahnya. Yang terbangun bukan papan editor gelap dengan kartu kaca dan gelombang neon — itu susunan bawaan kategori dan ditolak secara sadar. Yang terbangun adalah **pelat kertas terang yang duduk di dalam panggung gelap**: `--stage` (#0B0E14) memagari layar dari tepi, `--ground` (#DDE4EC) adalah meja kerjanya, dan `--plate` (#EDF1F6) adalah kertas partiturnya. Cangkangnya gelap; pekerjaannya terang.

Empat pensil konduktor bekerja sebagai **peran fungsional, bukan hiasan**. Merah latihan menandai klip dan hanya klip. Biru isyarat dan hijau masuk menandai penutur. Stabilo kuning menandai satu-satunya hal yang sedang aktif. Tidak ada warna kelima yang "berarti sesuatu"; sisanya grafit (`--ink-2`, `--ink-3`). Karena maknanya melekat pada perannya, warna tidak pernah dipakai untuk membuat sebuah kotak tampak menarik.

Kepadatannya tinggi dan sadar diri: jari-jari 2–4px karena kertas tidak melengkung, garis 1px, angka tabular di seluruh badan, dan tepat satu momen gerak yang dikoreografi. Video bergerak hanya di dalam lubang orkestra — satu-satunya permukaan gelap yang dipakai untuk isi, bukan untuk cangkang.

**Key Characteristics:**
- Pelat terang di dalam panggung gelap; pelat tidak pernah lebih gelap dari tanahnya, di tema terang maupun gelap.
- Empat pensil berperan tetap: merah = klip, biru/hijau = penutur, stabilo = yang aktif.
- Jari-jari nyaris nol (2/3/4px); bentuknya lembar kertas, bukan pil.
- Angka tabular di seluruh aplikasi (`font-variant-numeric: tabular-nums` di `body`).
- Satu momen gerak diarang; sisanya perubahan warna ~120ms.
- Permukaan bawaan peramban (seleksi, karet, scrollbar, cincin fokus) ikut diwarnai dunia ini.

## Colors

Palet dua-kutub: panggung gelap dan pelat terang, dengan empat pensil jenuh yang muncul hanya ketika membawa arti.

### Primary
- **Merah Latihan** (`reh`): huruf latihan, batas kiri frasa klip, garis main, tombol utama, cincin `:focus-visible`, `caret-color`, `accent-color`, dan garis penanda rute aktif di rel instrumen. Ia adalah tanda "di sinilah pekerjaannya".
- **Stabilo** (`hl`) dan **Cucian Stabilo** (`hl-wash`): pita yang menandai frasa/baris yang **sedang** terpilih, latar chip aktif, latar baris indeks aktif, huruf `CLIP` pada logo, dan `::selection`. Menandai kekinian, bukan identitas.

### Secondary
- **Biru Isyarat** (`cue`): pensil penutur, warna tautan, dan huruf latihan untuk klip buatan tangan (`.reh--manual`) — yang membedakannya dari klip mesin tanpa memakai ikon atau label tambahan.
- **Hijau Masuk** (`entry`): pensil penutur pertama pada tangga suara.

### Tertiary
- **Peringatan** (`warn`) dan **Bahaya** (`danger`): status dan aksi merusak. Keduanya bukan pensil dan tidak pernah masuk tangga suara.

### Neutral
- **Panggung** (`stage`) dan **Panggung Dalam** (`stage-2`): kepala aplikasi, rel instrumen, latar viewport, lubang orkestra, dan bingkai `pit-frame` tiap thumbnail. Satu-satunya gelap yang dipakai.
- **Meja** (`ground`): latar area isi, di belakang pelat.
- **Pelat** (`plate`), **Pelat Tenggelam** (`plate-2`), **Pelat Terangkat** (`plate-3`): tiga tingkat kertas. `plate-3` adalah permukaan hover dan latar isian; `plate-2` adalah baris berselang dan keadaan nonaktif.
- **Tinta** (`ink`) / **Keterangan** (`ink-2`, 7.0:1 di atas pelat) / **Metadata** (`ink-3`, 4.6:1): tangga tiga tingkat, tidak ada tingkat keempat.
- **Garis Balok** (`rule`) dan **Garis Pinggir** (`rule-2`): garis balok, batas isian dan tombol, batas pelat, ibu jari scrollbar.

### Named Rules

**Aturan Pelat Lebih Terang.** Di tema mana pun, pelat lebih terang dari tanah di belakangnya. Tema gelap meredupkan pelatnya (`#141A24` di atas `#070A0F`); ia tidak pernah membalik hubungan itu. Uji: ambil `--plate` dan `--ground`, luminansi pelat harus lebih besar.

**Aturan Merah Bukan Suara.** Merah latihan tidak pernah dipakai untuk mengidentifikasi seorang penutur. Tangga suara berisi tepat empat pensil, berputar: hijau masuk, biru isyarat, keterangan, metadata. Memberikan merah kepada sebuah suara membuat frasa dan huruf latihannya berwarna sama di balok yang sama, dan tandanya hilang. `--warn` juga bukan pensil suara.

**Aturan Ambang Kontras.** Warna produk (warna subtitle seorang penutur) baru boleh jadi tinta antarmuka bila ia lolos ambang WCAG terhadap pelat: **4.5:1 untuk teks** (`inkSafe`) dan **3:1 untuk isian dan titik di balok**. Di bawah ambang, aplikasi jatuh ke `--ink` atau ke pensil partiturnya sendiri, dan identitas penutur pindah ke titik berwarna. Luminansi sendirian bukan ukurannya: pastel lolos uji luminansi lalu hilang di atas kertas.

**Aturan Lapisan Nama Lama.** `:root` memuat alias peninggalan dunia lama (`--bg-card`, `--text-primary`, `--text-secondary`, `--text-muted`, `--border-color`, `--accent-cyan`, `--accent-blue`, `--accent-purple`, `--radius-md`, `--shadow-card`, …) yang memetakan nama lama ke token baru supaya gaya sebaris yang belum ditulis ulang tetap benar. Itu **lapisan kompatibilitas, bukan API**. Kode baru memakai nama dunia ini (`--plate`, `--ink`, `--reh`, `--r-md`); alias lama hanya dibaca, tidak pernah ditambah.

## Typography

**Display Font:** Archivo Black (self-hosted, `ArchivoBlack-Regular.ttf`)
**Body Font:** Archivo Variable (self-hosted, `Archivo-var.ttf`, berat 100–900, lebar 62–125%), dengan `ui-sans-serif, system-ui, 'Segoe UI', sans-serif`
**Label Font:** Archivo pada `font-stretch: 80%` — lebar sempit itulah yang membuatnya terbaca sebagai tanda pensil, bukan sebagai judul kecil.

**Character:** Satu keluarga grotesk yang dipakai di dua ekstrem. Archivo Black hanya untuk judul karya, logo, dan huruf latihan — di sanalah ia bersikap seperti stempel cetak. Archivo variabel membawa sisanya, dengan berat pecahan (420 badan, 620 tombol, 680–720 keadaan aktif) supaya penekanan bisa naik tanpa mengganti ukuran.

### Hierarchy
- **Display** (Archivo Black 400, clamp 1.35–1.95rem, tinggi baris 1.08, `text-wrap: balance`): judul karya di blok judul tiap halaman. Satu per layar.
- **Headline** (Archivo 680, .84rem): judul pilihan, kepala baris di panel editor.
- **Title** (Archivo 620–720, .8–.86rem): teks tombol, chip, tautan navigasi, kepala tab.
- **Body** (Archivo 420, 15px, tinggi baris 1.5): teks berjalan dan isian. Keterangan pendukung turun ke .74–.84rem pada `--ink-2`.
- **Label** (`.mark`; Archivo 700, lebar 80%, .68rem, spasi huruf .1em, HURUF BESAR, `--ink-3`): penanda pensil di kepala pelat dan di tepi partitur.
- **Caption/Nama Balok** (Archivo 700, lebar 80%, .62rem, spasi huruf .08em, HURUF BESAR, `--ink`): nama instrumen di kolom kiri tiap balok; menyusut ke .58rem di bawah 760px.
- **Rehearsal** (Archivo Black, .72rem, spasi huruf .02em): huruf latihan A–Z lalu AA–ZZ di dalam kotak tinta pekat.

### Named Rules

**Aturan Angka Tabular.** `font-variant-numeric: tabular-nums` disetel di `body`, bukan per komponen. Semua kode waktu, durasi, dan skor sejajar secara vertikal secara bawaan. Jangan matikan.

**Aturan Dua Wajah Saja.** Hanya dua wajah dimuat sendiri: Archivo variabel dan Archivo Black. Tidak ada wajah tampilan sistem, tidak ada wajah ketiga, tidak ada monospace — kolom angka dijaga oleh angka tabular, bukan dengan mengganti keluarga huruf.

## Layout

Cangkangnya grid dua kolom: **rel instrumen 188px di kiri** (posisi tempat partitur menuliskan nama instrumen) dan kolom isi di kanan, dengan kepala aplikasi setinggi 60px membentang di atas kolom isi. Rel melekat setinggi layar (`position: sticky; height: 100dvh`); latar panggung dipasang di viewport, bukan di rel, supaya halaman panjang tidak memperlihatkan warna meja di bawah rel. Isi diberi padding `20px 22px 34px` dan dibatasi `max-width: 1320px`.

Tiap halaman dibuka dengan **blok judul karya**: judul display, keterangan kecil di bawahnya, aksi utama didorong ke kanan lewat `margin-left: auto`.

Editor memakai grid tiga kolom `250px | 1fr | 336px` dengan jarak 14px: indeks huruf latihan, papan kerja, lubang orkestra. Di bawah 1180px ia jadi dua kolom dan lubang orkestra naik ke atas dengan `order: -1` selebar penuh. Di bawah 760px semuanya menumpuk dan indeks huruf berubah jadi laci mendatar ber-scroll-snap dengan kartu 236px.

Titik potong: **1180px** (editor jadi dua kolom), **1100px / 720px** (jumlah sistem balok), **900px** (rel kiri turun jadi bilah jempol), **760px** (editor satu kolom, partitur menyempit).

Irama jarak berjalan pada langkah kecil karena kepadatannya tinggi: 4 / 6 / 8 / 10 / 14 / 18 / 22px. 8px dan 10px adalah kerja harian; 14px adalah jarak antar pelat; 18–22px hanya di sekitar blok judul dan padding halaman.

### Named Rules

**Aturan Bilah Jempol.** Di bawah 900px, navigasi tidak jadi laci melainkan turun ke bawah layar sebagai bilah jempol dengan target sentuh minimal 54px, `z-index: 30`, `padding-bottom: env(safe-area-inset-bottom)`, dan bayang ke atas. Ia menumpuk **di atas** isi, jadi tiap layar yang punya elemen berposisi absolut harus menyisakan ruang bawah sendiri.

**Aturan Enam Belas Piksel.** Di bawah 760px semua isian naik ke `font-size: 16px` dan semua tombol ke `min-height: 42px`. Angka 16 bukan pilihan estetika: di bawah itu iOS ikut men-zoom halaman saat isian difokus.

## Elevation & Depth

Sistem ini hampir datar dan mendapat kedalamannya dari **lapisan nada** (panggung → meja → pelat → pelat terangkat), bukan dari tumpukan bayang. Hanya ada dua bayang, keduanya lembut dan dua-lapis, dan keduanya berperan struktural: memisahkan kertas dari mejanya. Tidak ada bayang hover, tidak ada bayang keras beroffset, tidak ada cahaya berwarna — `--shadow-glow` sengaja dipetakan ke `none`.

### Shadow Vocabulary
- **Pelat** (`box-shadow: 0 1px 2px rgba(14,20,32,.10), 0 8px 24px -12px rgba(14,20,32,.35)`): tiap lembar kertas di atas meja. Tetap saat rehat, tidak berubah saat hover.
- **Angkat** (`box-shadow: 0 2px 4px rgba(14,20,32,.12), 0 14px 34px -14px rgba(14,20,32,.45)`): hanya untuk yang benar-benar melayang — lubang orkestra dan kotak modal.
- **Sumur panggung** (`box-shadow: inset 0 0 0 1px #ffffff12` pada `.pit-frame`): garis dalam setipis rambut yang membuat bingkai gelap terbaca sebagai sumur, bukan sebagai lubang.

### Named Rules

**Aturan Kedalaman Nada.** Kedalaman dinyatakan dengan mengganti tingkat pelat (`plate-2` → `plate` → `plate-3`) dan dengan garis 1px, bukan dengan menambah bayang. Hover menaikkan nada permukaan; ia tidak pernah menaikkan bayang.

## Shapes

Kertas tidak melengkung. Jari-jari hampir nol dan bertingkat sangat rapat: 2px untuk kendali dan isian, 3px untuk pelat dan lubang orkestra, 4px untuk modal, dan **1px** untuk huruf latihan, lencana, dan sumur gambar — nyaris siku, tepat seperti kotak yang digambar tangan di atas partitur. Satu-satunya lingkaran penuh di sistem ini adalah titik penutur 11px dan ibu jari scrollbar.

Batasnya garis 1px `--rule` atau `--rule-2` di hampir semua tempat. Dua pengecualian sengaja, keduanya meniru partitur cetak: **batas kanan 2px `--ink`** yang memisahkan kolom nama instrumen dari baloknya, dan **garis atas/bawah 2px `--hl`** yang membentuk pita stabilo. Keadaan aktif ditandai dengan garis tebal di satu sisi (kiri 3px di rel lebar, atas 3px di bilah jempol, bawah 2px pada tab), bukan dengan mengisi latar dengan warna.

## Components

### Buttons
- **Bentuk:** nyaris siku (2px), tinggi minimum 36px (42px di bawah 760px), padding `8px 14px`, isi mendatar dengan jarak 7px untuk ikon.
- **Primer:** merah latihan penuh dengan tinta putih. Hover menggelapkan sendiri lewat `color-mix(in srgb, var(--reh) 86%, #000)`.
- **Sekunder/Ghost:** pelat terangkat dengan garis `--rule` dan tinta penuh; hover turun ke `plate-2` dan batasnya menguat ke `--ink-3`.
- **Fokus:** cincin bersama seluruh aplikasi — `outline: 2px solid var(--reh)` dengan offset 2px, disetel lewat `:focus-visible` pada `:where(a, button, input, select, textarea, [tabindex])`.
- **Nonaktif:** opasitas .45, latar jatuh ke `plate-2`, tinta ke `--ink-3` — termasuk yang primer, yang kehilangan merahnya sepenuhnya.
- **Transisi:** `background/border-color/color .12s ease`. Tidak ada `transform`.

### Chips
- **Gaya:** tanda pensil di tepi partitur, bukan pil berwarna — pelat, garis `--rule`, jari-jari 2px, tinta keterangan.
- **Keadaan:** terpilih memakai tinta merah + batas merah + cucian stabilo dan berat naik ke 720; tidak terpilih hanya menguatkan batas saat hover.

### Cards / Containers
- **Pelat** adalah satu-satunya wadah: latar `--plate`, garis 1px `--rule-2`, jari-jari 3px, bayang pelat.
- **Kepala pelat** adalah baris `10px 14px` dengan garis bawah 1px dan sebuah label `.mark`; itulah cara sebuah pelat diberi nama.
- **Lubang orkestra** (`.pit`) adalah kebalikannya: panggung gelap, garis `--stage-2`, tinta `#DCE4EE`, label pada `#8493A8`, bayang angkat.

### Inputs / Fields
- **Gaya:** pelat terangkat, garis 1px `--rule`, jari-jari 2px, padding `9px 11px` (`.field`) atau `11px 14px` untuk kotak pencarian yang duduk langsung di atas pelat.
- **Fokus:** batas berubah jadi merah latihan; cincin fokus global mengurus sisanya.
- **Placeholder:** `--ink-3`.

### Navigation
- Rel instrumen: latar panggung, label `.86rem/560` pada `#93A2B8`, ikon garis 1.9 pada 17px. Hover menaikkan tinta ke `#E7EDF5` dengan lapisan `#FFFFFF08`. Aktif = putih penuh, lapisan `#FFFFFF0D`, berat 680, dan **garis kiri 3px merah latihan**.
- Di bawah 900px: bilah jempol mendatar, ikon di atas label .62rem, garis penanda pindah ke atas.

### Sistem Balok (komponen tanda tangan)

Seluruh durasi rekaman dibaca sekali pandang: satu balok per narasumber (maksimum 8), satu balok **DINAMIKA** di bawahnya, dan tiap klip duduk sebagai frasa bertanda huruf latihan pada balok penuturnya.

- **Anatomi baris:** grid `118px | 1fr` (62px di bawah 760px). Kolom nama diakhiri batas kanan 2px tinta. Balok setinggi 58px (44px di layar sempit) berisi garis-garis 1px dari `repeating-linear-gradient` setiap 9px pada opasitas .8.
- **Frasa klip:** isian `color-mix(in srgb, <pensil> 24%, transparent)` dengan batas kiri 1px pensil penuh, hover meredup lewat `filter: brightness(.94)`. Huruf latihannya duduk 11px di atas frasa; yang dekat tepi kanan berpindah titik jangkar sendiri supaya tidak terpotong. Huruf latihan terpilih membesar `scale(1.14)` dalam 180ms.
- **Membungkus jadi beberapa sistem:** `systemCountFor(width, duration)` — **satu sistem di ≥1100px**, **maksimum tiga di 720–1100px** (`ceil(durasi/2400)`), dan di bawah 720px `ceil(durasi/900)` hingga delapan, yakni satu sistem per ~15 menit. Sistem kedua dan seterusnya dipisahkan garis atas 1px. Ini menggantikan pemampatan: partitur cetak membungkus, ia tidak menyusut sampai tak terbaca.
- **Balok dinamika:** simpangan **z-skor** dari garis tengah, 320 batang setebal 1.5px — di atas garis pada `--ink-2`, di bawah pada `--ink-3`. Bukan gelombang amplitudo. Bila puncak belum dihitung, baris itu berisi kalimat, bukan grafik kosong.
- **Baris waktu:** langkah dipilih dari `[15, 30, 60, 120, 300, 600, 900, 1800]` detik menurut lebar nyata, dicetak dengan angka tabular. Barline dan nomor birama tidak digambar.

## Do's and Don'ts

### Do:
- **Do** bangun wadah baru dari `.plate` + `.plate-head` + sebuah label `.mark`, bukan dari div bergaya sebaris.
- **Do** pakai empat pensil menurut perannya: merah = klip, biru/hijau = penutur, stabilo = yang sedang aktif.
- **Do** lewatkan tiap warna produk melalui `inkSafe` (4.5:1) sebelum memakainya sebagai teks, dan melalui uji 3:1 sebelum memakainya sebagai isian atau titik di balok.
- **Do** tandai keadaan aktif dengan garis 2–3px di satu sisi dan pergeseran berat huruf, bukan dengan mengisi latar berwarna.
- **Do** pertahankan jari-jari di 1–4px; kertas tidak melengkung.
- **Do** batasi gerak pada perubahan warna/batas ~120ms, kecuali satu pita stabilo yang meluncur.
- **Do** bingkai tiap gambar bergerak dengan `.pit-frame` supaya video hanya hidup di dalam panggung.
- **Do** biarkan `body` yang memasok angka tabular.

### Don't:
- **Don't** pakai merah latihan untuk mengidentifikasi seorang penutur, dan jangan tambahkan pensil kelima ke tangga suara.
- **Don't** buat pelat lebih gelap dari tanahnya, di tema mana pun; jangan balik hubungan panggung–pelat.
- **Don't** tambahkan bayang baru. Dua yang ada sudah lengkap, dan bayang bukan penanda hover di sini.
- **Don't** pakai alias token lama (`--bg-card`, `--accent-cyan`, `--text-primary`, `--radius-md`, …) di kode baru; itu lapisan peralihan yang hanya dibaca.
- **Don't** animasikan properti tata letak (`left`, `width`, `top`, `height`). Pita stabilo dan garis main digerakkan lewat `transform` di dalam satu loop rAF.
- **Don't** ganti sistem balok yang membungkus dengan satu garis yang dimampatkan, dan jangan ganti balok dinamika jadi gelombang amplitudo — keduanya adalah susunan yang ditolak layar ini.
- **Don't** tambahkan wajah huruf ketiga atau wajah tampilan sistem.
- **Don't** pakai gelap untuk cangkang isi; satu-satunya permukaan gelap adalah panggung, rel, kepala aplikasi, dan lubang orkestra.

<!--
Yang belum terpenuhi di build ini, dicatat jujur sebagai belum-dikomitkan, bukan sebagai aturan:
- Pelat masih rata (#EDF1F6, garis 1px, satu bayang lembut). Bahan "kertas yang disorot lampu meja" — serat, tepi pelat, luruh cahaya lampu — belum diterapkan.
- Barline dan nomor birama belum digambar; baris waktu masih jam biasa.
- Balok bergaris baru dipakai sebagai perangkat di dalam editor; Studio, Klip jadi, dan Unduhan masih wadah generik.
- Watch menyisakan ~740px pelat kosong di bawah baris metanya.
- Dua string di Watch masih Inggris ("Download", "Clip Video") di antarmuka yang selebihnya Indonesia.
-->
