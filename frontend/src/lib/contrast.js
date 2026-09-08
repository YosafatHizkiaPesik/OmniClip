/**
 * Apakah sebuah warna cukup terbaca di atas pelat kertas.
 *
 * Penjaga pertama saya memakai LUMINANSI saja dengan ambang 0,72. Itu meloloskan
 * warna pastel: #FFB3C7 — warna subtitle bawaan orang ketiga — duduk di 0,58,
 * lolos penjagaan, lalu tampil di atas pelat #E3E9F1 dengan rasio 1,3:1. Praktis
 * tidak terbaca, dan itu terjadi tepat pada baris lirik.
 *
 * Yang menentukan keterbacaan bukan seberapa terang sebuah warna, melainkan
 * seberapa jauh ia dari latarnya. Jadi yang diukur di sini rasio kontras
 * sungguhan (WCAG), bukan luminansinya sendirian.
 */
const PLATE = { light: '#E3E9F1', dark: '#101620' };

function channel(v) {
  const c = v / 255;
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

export function luminance(hex) {
  const m = /^#([0-9a-f]{6})$/i.exec(String(hex).trim());
  if (!m) return null;
  const [r, g, b] = [0, 2, 4].map((i) => channel(parseInt(m[1].slice(i, i + 2), 16)));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

export function contrastRatio(a, b) {
  const la = luminance(a);
  const lb = luminance(b);
  if (la === null || lb === null) return null;
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

/** Warna teks yang aman: yang diminta bila lolos, kalau tidak tinta pelat. */
export function inkSafe(hex, { min = 4.5, fallback = 'var(--ink)' } = {}) {
  // Uji asap merender komponen ke string di Node, tempat `document` tidak ada.
  // Pelat terang adalah asumsi yang benar di sana: itu tema bawaannya.
  const theme = typeof document !== 'undefined'
    && document.documentElement?.getAttribute('data-theme') === 'dark'
    ? 'dark' : 'light';
  const ratio = contrastRatio(hex, PLATE[theme]);
  return ratio !== null && ratio >= min ? hex : fallback;
}
