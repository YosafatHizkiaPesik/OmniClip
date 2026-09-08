# Font yang dibundel

Semua font di direktori ini berasal dari proyek Google Fonts dan boleh
didistribusikan ulang bersama aplikasi.

| Berkas | Keluarga | Lisensi |
|---|---|---|
| Anton-Regular.ttf | Anton | SIL Open Font License 1.1 |
| ArchivoBlack-Regular.ttf | Archivo Black | SIL Open Font License 1.1 |
| BebasNeue-Regular.ttf | Bebas Neue | SIL Open Font License 1.1 |
| Bungee-Regular.ttf | Bungee | SIL Open Font License 1.1 |
| FjallaOne-Regular.ttf | Fjalla One | SIL Open Font License 1.1 |
| LilitaOne-Regular.ttf | Lilita One | SIL Open Font License 1.1 |
| LuckiestGuy-Regular.ttf | Luckiest Guy | Apache License 2.0 |
| Montserrat-ExtraBold.ttf | Montserrat | SIL Open Font License 1.1 |
| Oswald-Bold.ttf | Oswald | SIL Open Font License 1.1 |
| PlayfairDisplay-Black.ttf | Playfair Display | SIL Open Font License 1.1 |
| Poppins-ExtraBold.ttf | Poppins | SIL Open Font License 1.1 |
| Rubik-ExtraBold.ttf | Rubik | SIL Open Font License 1.1 |
| Teko-Bold.ttf | Teko | SIL Open Font License 1.1 |

## Perubahan terhadap berkas aslinya

Berkas Teko, Rubik, dan Playfair Display hanya tersedia sebagai font variabel di
hulu, sedangkan libass hanya memakai instance bawaan sebuah font variabel — jadi
ketiganya di-*instance* ke satu berat tetap (Teko 700, Rubik 800, Playfair
Display 900) memakai `fontTools.varLib.instancer`.

Seluruh berkas juga diseragamkan tabel namanya: nama keluarga utama (name ID 1)
diisi nama keluarga polos, dan tiap berkas ditandai bergaya Bold. libass
mencocokkan font lewat name ID 1; tanpa penyeragaman ini, permintaan
"Montserrat" tidak cocok dengan berkas yang menamai dirinya "Montserrat
ExtraBold" dan hasilnya jatuh diam-diam ke font sistem.

Kedua perubahan itu tidak mengubah bentuk hurufnya. Lisensi aslinya tetap
berlaku; teks lengkapnya ada di repositori google/fonts pada direktori masing-
masing font.
