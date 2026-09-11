/**
 * Ragam gaya kartu judul.
 *
 * Satu daftar, dua pemakai: pratinjau menggambarnya dengan CSS, ffmpeg
 * menggambarnya lewat baris Style di berkas ASS. Keduanya diturunkan dari
 * entri yang SAMA, jadi gaya yang terlihat di layar tidak bisa berbeda dari
 * gaya yang terbakar ke dalam MP4 — kegagalan yang paling mahal di editor
 * seperti ini, karena baru ketahuan setelah render selesai.
 *
 * Angka ASS-nya ditulis dalam satuan kanvas 1920 dan diskalakan pemanggil,
 * sama seperti ukuran hurufnya, supaya satu setelan berlaku untuk kanvas
 * 1080x1920 maupun 1920x1080.
 */

/** #RRGGBB dengan alfa, untuk CSS. */
function rgba(hex, a) {
  const c = (hex || '#000000').replace('#', '');
  if (c.length !== 6) return `rgba(0,0,0,${a})`;
  const n = parseInt(c, 16);
  // eslint-disable-next-line no-bitwise
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

export const CARD_VARIANTS = [
  {
    id: 'garis',
    label: 'Garis tebal',
    note: 'Huruf putih bergaris tepi tebal. Terbaca di atas gambar apa pun — inilah yang dipakai kebanyakan klip.',
    // BorderStyle 1 = garis tepi + bayangan.
    ass: { border: 1, outline: 9, shadow: 4, back: null },
    css: (shadow, scale) => ({
      WebkitTextStroke: `${Math.max(1.5, 9 * scale * 1.6)}px ${shadow}`,
      paintOrder: 'stroke fill',
      textShadow: `0 ${Math.max(1, 4 * scale * 1.6)}px ${Math.max(2, 6 * scale * 1.6)}px ${rgba(shadow, 0.7)}`,
    }),
  },
  {
    id: 'kotak',
    label: 'Kotak isi',
    note: 'Judul duduk di dalam pelat warna. Paling tegas, dan satu-satunya yang tetap terbaca di atas gambar yang sangat ramai.',
    // BorderStyle 3 = kotak buram; BackColour yang jadi pelatnya.
    ass: { border: 3, outline: 14, shadow: 0, back: 'shadow' },
    css: (shadow, scale) => ({
      background: rgba(shadow, 0.82),
      padding: `${Math.max(3, 14 * scale * 1.4)}px ${Math.max(6, 22 * scale * 1.4)}px`,
      borderRadius: `${Math.max(2, 6 * scale * 1.4)}px`,
      boxDecorationBreak: 'clone',
      WebkitBoxDecorationBreak: 'clone',
    }),
  },
  {
    id: 'bayang',
    label: 'Bayangan jatuh',
    note: 'Tanpa garis tepi, hanya bayangan yang jatuh ke kanan bawah. Lebih tenang dan terkesan mahal.',
    ass: { border: 1, outline: 0, shadow: 11, back: null },
    css: (shadow, scale) => ({
      textShadow: `${Math.max(2, 11 * scale * 1.5)}px ${Math.max(2, 11 * scale * 1.5)}px ${Math.max(3, 10 * scale * 1.5)}px ${rgba(shadow, 0.85)}`,
    }),
  },
  {
    id: 'polos',
    label: 'Polos',
    note: 'Huruf saja, garis tepi tipis sekadar menahannya dari latar. Untuk latar yang sudah gelap dan rata.',
    ass: { border: 1, outline: 3, shadow: 2, back: null },
    css: (shadow, scale) => ({
      WebkitTextStroke: `${Math.max(0.6, 3 * scale * 1.6)}px ${shadow}`,
      paintOrder: 'stroke fill',
    }),
  },
];

export const cardVariant = (id) =>
  CARD_VARIANTS.find((v) => v.id === id) ?? CARD_VARIANTS[0];
