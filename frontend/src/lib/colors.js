import { useCallback, useEffect, useState } from 'react';

/**
 * Warna teks: rekomendasi, riwayat, dan favorit.
 *
 * Palet bawaan sengaja bukan roda warna penuh. Subtitle klip dibaca di atas
 * gambar yang terus berubah, jadi yang berhasil hanyalah warna dengan
 * luminansi tinggi; warna gelap akan hilang ditelan garis luar hitamnya
 * sendiri. Daftar di bawah semuanya lolos syarat itu — pemilih warna bebas
 * tetap ada untuk yang tahu persis apa yang dia mau.
 */

export const FAV_KEY = 'omniclip_color_favs';
export const RECENT_KEY = 'omniclip_color_recent';

/** Palet lengkap, dikelompokkan supaya bisa dipindai cepat. */
export const COLOR_GROUPS = [
  {
    name: 'Netral',
    colors: ['#FFFFFF', '#F5F1E6', '#D8DEE9', '#B9C6D6', '#1A1A1A'],
  },
  {
    name: 'Hangat',
    colors: ['#FFE500', '#FFD166', '#FF9F1C', '#FF7A45', '#FF4D6D', '#FF2E63'],
  },
  {
    name: 'Sejuk',
    colors: ['#00E5FF', '#5BC8FF', '#4D7CFF', '#7C5CFF', '#B39DFF', '#00F5D4'],
  },
  {
    name: 'Segar',
    colors: ['#7CFF6B', '#7CFFB2', '#B8FF3A', '#39FF88', '#FFB3C7', '#FF8FE5'],
  },
];

export const ALL_COLORS = COLOR_GROUPS.flatMap((g) => g.colors);

/**
 * Pasangan warna teks + kata aktif yang sudah terbukti terbaca.
 *
 * Dipisahkan dari palet satuan karena yang menentukan kesan sebuah subtitle
 * adalah KONTRAS antara warna dasar dan warna sorotnya, bukan salah satunya.
 */
export const COLOR_PAIRS = [
  { id: 'klasik', name: 'Klasik', primary: '#FFFFFF', highlight: '#FFE500' },
  { id: 'neon', name: 'Neon', primary: '#FFFFFF', highlight: '#00E5FF' },
  { id: 'permen', name: 'Permen', primary: '#FFFFFF', highlight: '#FF4D6D' },
  { id: 'limau', name: 'Limau', primary: '#FFFFFF', highlight: '#B8FF3A' },
  { id: 'senja', name: 'Senja', primary: '#FFD166', highlight: '#FF7A45' },
  { id: 'mint', name: 'Mint', primary: '#F5F1E6', highlight: '#00F5D4' },
  { id: 'ungu', name: 'Ultraviolet', primary: '#FFFFFF', highlight: '#B39DFF' },
  { id: 'esbiru', name: 'Es biru', primary: '#D8DEE9', highlight: '#5BC8FF' },
];

export function normalizeHex(input) {
  const raw = String(input || '').trim().replace(/^#/, '');
  if (/^[0-9a-fA-F]{3}$/.test(raw)) {
    return `#${raw.split('').map((c) => c + c).join('')}`.toUpperCase();
  }
  if (/^[0-9a-fA-F]{6}$/.test(raw)) return `#${raw}`.toUpperCase();
  return null;
}

function read(key) {
  try {
    const v = JSON.parse(localStorage.getItem(key) || '[]');
    return Array.isArray(v) ? v.filter((c) => normalizeHex(c)) : [];
  } catch {
    return [];
  }
}

function write(key, list) {
  try {
    localStorage.setItem(key, JSON.stringify(list));
  } catch { /* mode privat: fitur ini boleh hilang tanpa merusak apa pun */ }
}

/** Warna favorit pengguna, bertahan antar sesi. */
export function useFavoriteColors() {
  const [favs, setFavs] = useState(() => read(FAV_KEY));

  // Dua panel warna bisa terbuka sekaligus; peristiwa ini menjaga keduanya
  // menampilkan daftar favorit yang sama tanpa mengangkat state ke atas.
  useEffect(() => {
    const sync = () => setFavs(read(FAV_KEY));
    window.addEventListener('omniclip:colors', sync);
    return () => window.removeEventListener('omniclip:colors', sync);
  }, []);

  const toggle = useCallback((color) => {
    const hex = normalizeHex(color);
    if (!hex) return;
    const next = read(FAV_KEY).includes(hex)
      ? read(FAV_KEY).filter((c) => c !== hex)
      : [hex, ...read(FAV_KEY)].slice(0, 18);
    write(FAV_KEY, next);
    setFavs(next);
    window.dispatchEvent(new Event('omniclip:colors'));
  }, []);

  return [favs, toggle];
}

/** Warna yang baru saja dipakai — terisi sendiri, tanpa perlu ditandai. */
export function useRecentColors() {
  const [recent, setRecent] = useState(() => read(RECENT_KEY));

  useEffect(() => {
    const sync = () => setRecent(read(RECENT_KEY));
    window.addEventListener('omniclip:colors', sync);
    return () => window.removeEventListener('omniclip:colors', sync);
  }, []);

  const remember = useCallback((color) => {
    const hex = normalizeHex(color);
    if (!hex) return;
    const next = [hex, ...read(RECENT_KEY).filter((c) => c !== hex)].slice(0, 12);
    write(RECENT_KEY, next);
    setRecent(next);
    window.dispatchEvent(new Event('omniclip:colors'));
  }, []);

  return [recent, remember];
}
