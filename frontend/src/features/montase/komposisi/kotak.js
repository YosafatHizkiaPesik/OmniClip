/**
 * Kotak dasar setiap item di kanvas (piksel kanvas), SEBELUM transformasi.
 *
 * Dipakai di dua tempat yang harus sepakat persis:
 *   - komposisi: item video/gambar digambar di kotak ini, lalu `ubah`
 *     (geser, skala, putar, potong) diterapkan dengan titik pusat kotak;
 *   - pegangan di pratinjau (editor/PeganganUbah.jsx): bingkai pilihan dan
 *     pegangannya digambar dari kotak yang sama.
 *
 * Video dan gambar "muat" (contain) menempati persegi panjang sesuai rasio
 * bahannya di tengah kanvas, bukan seluruh kanvas. Dengan begitu potongan
 * (crop) dalam persen berarti persen GAMBARNYA, bukan persen kanvas yang
 * kebetulan kosong di atas dan bawah video mendatar. Bila ukuran bahan tidak
 * diketahui, kotaknya seluruh kanvas (sama dengan perilaku Tahap 1).
 *
 * Kotak teks hanya PERKIRAAN (lebar huruf tebal ~0,56 em): ukuran teks
 * sebenarnya baru diketahui setelah digambar di dalam iframe, dan iframe
 * tidak boleh dipercaya untuk mengukur. Perkiraan ini hanya menentukan besar
 * bingkai pegangan; letak teks sendiri tetap dihitung peramban.
 */
export const LEBAR_HURUF = 0.56;
export const TINGGI_BARIS = 1.1;
export const TEPI_TEKS = { datar: 60, tegak: 160 };

export function kotakDasar(dokumen, item) {
  const W = dokumen?.kanvas?.lebar ?? 1080;
  const H = dokumen?.kanvas?.tinggi ?? 1920;
  const penuh = { x: 0, y: 0, w: W, h: H };
  if (item.jenis === 'video' || item.jenis === 'gambar') {
    const b = dokumen?.bahan?.[item.bahan];
    if (item.isi === 'cover' || !(b?.lebar > 0) || !(b?.tinggi > 0)) return penuh;
    const s = Math.min(W / b.lebar, H / b.tinggi);
    const w = b.lebar * s;
    const h = b.tinggi * s;
    return { x: (W - w) / 2, y: (H - h) / 2, w, h };
  }
  if (item.jenis === 'teks') {
    const ukuran = item.gaya?.ukuran ?? 96;
    const ruang = Math.max(1, W - 2 * TEPI_TEKS.datar);
    const baris = String(item.teks ?? '').split('\n');
    const lebarHuruf = ukuran * LEBAR_HURUF;
    let terlebar = 0;
    let jumlah = 0;
    for (const b of baris) {
      const lebar = Math.max(1, b.length) * lebarHuruf;
      terlebar = Math.max(terlebar, Math.min(lebar, ruang));
      jumlah += Math.max(1, Math.ceil(lebar / ruang));
    }
    const w = terlebar;
    const h = jumlah * ukuran * TINGGI_BARIS;
    const letak = item.gaya?.letak ?? 'tengah';
    let y = (H - h) / 2;
    if (letak === 'atas') y = TEPI_TEKS.tegak;
    else if (letak === 'bawah') y = H - TEPI_TEKS.tegak - h;
    return { x: (W - w) / 2, y, w, h };
  }
  return penuh;
}
