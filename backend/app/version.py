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

  Naik SATU PER SATU di angka terakhir: 1.2.1, 1.2.2, 1.2.3, ... sampai 1.2.9.
  Angka tengah baru naik sesudah angka terakhir habis, jadi setelah 1.2.9
  barulah 1.3.0.

  Besar kecilnya isi rilis TIDAK menentukan. Rilis yang membawa fitur baru dan
  rilis yang hanya memperbaiki sama-sama menaikkan satu angka terakhir.

Aturan ini ditegaskan pemiliknya 29 September 2026, mengoreksi aturan
sebelumnya yang ditulis di sini 26 September: "mengapa versi lompat ke 1.3
bukan ke 1.2.3 dan seterusnya hingga 1.2.9 barulah setelah itu 1.3.0".

Teguran pertamanya (26 September, kenapa sesudah 1.0.9 datang 1.0.10 dan bukan
1.1) saya tafsirkan sebagai "angka tengah untuk fitur baru". Itu keliru: yang
ia persoalkan adalah angka terakhir yang melewati sembilan, bukan besarnya isi
rilis. 1.3.0 sudah telanjur terbit sebelum koreksi ini, jadi hitungan
berikutnya berjalan dari sana: 1.3.1, 1.3.2, dan seterusnya.

Pembandingnya numerik (lihat `sebagai_tuple`), jadi 1.0.10 memang lebih besar
daripada 1.0.9 dan tidak ada yang rusak. Yang salah hanya penamaannya.
"""

__version__ = "1.3.3"


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
