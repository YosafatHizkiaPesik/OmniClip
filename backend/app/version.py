"""
Nomor versi OmniClip. Satu sumber, dibaca semua yang membutuhkannya.

Sebelum berkas ini ada, versinya ditulis di tiga tempat dan sudah tidak
sepakat: "3.2" dua kali di backend, "3.1" di halaman Pengaturan. Selama tidak
ada yang membacanya, itu hanya kelalaian kecil. Begitu ada sistem pembaruan, ia
jadi cacat: pembaruan bekerja dengan membandingkan "versi saya" terhadap "versi
terbaru", dan pertanyaan pertama itu harus punya tepat satu jawaban.

Penomoran dimulai ulang dari 1.0.0 saat OmniClip jadi aplikasi yang dibagikan.
Angka 3.x yang lama tidak pernah dirilis ke siapa pun, jadi ia tidak menandai
apa-apa yang bisa dibandingkan.

Menaikkan versi: ubah di SINI saja, lalu beri tag git yang sama persis
(v1.0.1). Alur build menolak tag yang tidak cocok dengan berkas ini — rilis
yang isinya mengaku versi lama akan membuat setiap aplikasi menawarkan
pembaruan yang sama berulang-ulang, selamanya.

ANGKA MANA YANG DINAIKKAN:

  - angka TENGAH bila ada yang baru bisa dilakukan pengguna — gaya judul baru,
    rak pustaka baru, pembatas bingkai yang bisa diseret;
  - angka TERAKHIR bila hanya memperbaiki yang sudah ada.

Aturan ini ditulis 26 September 2026 sesudah pemiliknya bertanya kenapa versi
sesudah 1.0.9 adalah 1.0.10 dan bukan 1.1. Pertanyaannya tepat: rilis itu
membawa sepuluh gaya judul bergerak, tiga rak pustaka, dan pembatas bingkai
game yang bisa diseret — semuanya hal baru, bukan perbaikan. Menaikkan angka
terakhir saja mengecilkan isinya, dan orang yang melihat "1.0.8 -> 1.0.10"
mengira ada dua perbaikan kecil.

Pembandingnya numerik (lihat `sebagai_tuple`), jadi 1.0.10 memang lebih besar
daripada 1.0.9 dan tidak ada yang rusak. Yang salah hanya penamaannya.
"""

__version__ = "1.1.0"


def sebagai_tuple(v: str) -> tuple[int, ...]:
    """
    "1.0.2" -> (1, 0, 2), supaya perbandingannya numerik.

    Membandingkan sebagai teks keliru pada kasus yang pasti terjadi: "1.0.10"
    lebih kecil daripada "1.0.9" menurut abjad.
    """
    bagian = []
    for potong in v.strip().lstrip("vV").split("."):
        angka = ""
        for c in potong:
            if not c.isdigit():
                break
            angka += c
        bagian.append(int(angka) if angka else 0)
    return tuple(bagian) or (0,)
