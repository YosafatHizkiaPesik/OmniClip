/**
 * Zona aman untuk garis bantu pratinjau (JOB-4 M1.8): bagian layar yang tidak
 * tertutup tombol dan keterangan aplikasi tempat video ditonton.
 *
 * Vertikal (TikTok, Shorts, Reels): kolom tombol di kanan, keterangan dan nama
 * akun di bawah, tab di atas. Angkanya dibulatkan dari tumpang tindih ketiga
 * aplikasi, dan sengaja sedikit lebih ketat dari yang terketat: tulisan yang
 * nyaris tertutup sama buruknya dengan yang tertutup.
 * Horizontal dan persegi: batas aman judul siaran 5% di setiap sisi.
 * Semua dalam persen kanvas.
 */
export function zonaAman(lebar, tinggi) {
  if (tinggi > lebar * 1.3) {
    return { kiri: 6, kanan: 16, atas: 10, bawah: 22 };
  }
  return { kiri: 5, kanan: 5, atas: 5, bawah: 5 };
}
