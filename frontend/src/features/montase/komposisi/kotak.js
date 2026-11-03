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

// Lebar rata-rata huruf per font bawaan, pecahan dari ukuran (diukur kasar
// pada "MOMEN TERBAIK"). Hanya untuk besar bingkai pegangan.
const LEBAR_FONT = {
  'Bebas Neue': 0.42, Anton: 0.46, Teko: 0.4, 'Fjalla One': 0.5, Oswald: 0.5,
  'Archivo Black': 0.68, Bungee: 0.72, 'Luckiest Guy': 0.62, 'Lilita One': 0.56,
  'Playfair Display': 0.58,
};

/** Tinggi baris teks per jenis latar: stabilo butuh jarak supaya pelatnya tidak bertumpuk. */
export function tinggiBaris(latar) {
  return latar === 'sorot' ? 1.3 : TINGGI_BARIS;
}

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
    const g = item.gaya ?? {};
    const ukuran = g.ukuran ?? 96;
    const latar = g.latar ?? 'tanpa';
    const padX = latar === 'tanpa' || latar === 'pita' ? 0 : (g.pad_x ?? 0.42) * ukuran;
    const padY = latar === 'tanpa' ? 0 : (g.pad_y ?? (latar === 'pita' ? 0.3 : 0.22)) * ukuran;
    const ruang = Math.max(1, W - 2 * TEPI_TEKS.datar - 2 * padX);
    const baris = String(item.teks ?? '').split('\n');
    const lebarHuruf = ukuran * (LEBAR_FONT[g.font] ?? LEBAR_HURUF) * (g.kapital ? 1.12 : 1);
    let terlebar = 0;
    let jumlah = 0;
    for (const b of baris) {
      const lebar = Math.max(1, b.length) * lebarHuruf;
      terlebar = Math.max(terlebar, Math.min(lebar, ruang));
      jumlah += Math.max(1, Math.ceil(lebar / ruang));
    }
    const w = latar === 'pita' ? W : terlebar + 2 * padX;
    const h = jumlah * ukuran * tinggiBaris(latar) + 2 * padY;
    const letak = g.letak ?? 'tengah';
    let y = (H - h) / 2;
    if (letak === 'atas') y = TEPI_TEKS.tegak;
    else if (letak === 'bawah') y = H - TEPI_TEKS.tegak - h;
    const rata = g.perataan ?? 'tengah';
    let x = (W - w) / 2;
    if (latar !== 'pita' && rata === 'kiri') x = TEPI_TEKS.datar;
    else if (latar !== 'pita' && rata === 'kanan') x = W - TEPI_TEKS.datar - w;
    return { x, y, w, h };
  }
  return penuh;
}
