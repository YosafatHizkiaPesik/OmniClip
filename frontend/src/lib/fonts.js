import { apiGet } from './api';

/**
 * Font display yang dibundel bersama backend.
 *
 * Daftarnya datang dari server, bukan ditulis ulang di sini, karena nama
 * keluarganya harus sama persis dengan yang dicari libass saat merender. Ketika
 * daftar ini hidup terpisah sebagai teks di frontend, mengganti font tidak
 * mengubah apa pun di pratinjau — bedanya baru terlihat setelah render selesai,
 * dan hanya kalau nama keluarganya kebetulan cocok.
 */
let cache = null;
let pending = null;

const FALLBACK = [
  { family: 'Montserrat', label: 'Montserrat', note: 'tebal & bulat, gaya CapCut' },
];

/**
 * Rantai fallback untuk CSS: font display dulu, lalu font aksara, lalu
 * sans-serif sistem.
 *
 * Font display yang dibundel semuanya hanya memuat huruf Latin, jadi tanpa
 * mata rantai tengah ini pratinjau video Jepang memakai font apa pun yang
 * kebetulan ada di komputernya — dan bentuknya berbeda dari hasil render.
 * Noto disebut lebih dulu karena itu yang dipakai libass; nama-nama
 * sesudahnya adalah font bawaan Windows, macOS, dan Linux.
 */
const AKSARA = [
  'Noto Sans JP', 'Noto Sans KR', 'Noto Sans SC', 'Noto Sans Arabic',
  'Yu Gothic', 'Hiragino Sans', 'Meiryo',
  'Malgun Gothic', 'Apple SD Gothic Neo',
  'Microsoft YaHei', 'PingFang SC',
].map((f) => `'${f}'`).join(', ');

export function fontStack(family) {
  return `'${family || 'Montserrat'}', ${AKSARA}, 'Segoe UI', system-ui, sans-serif`;
}

export function cachedFonts() {
  return cache ?? FALLBACK;
}

export function loadFonts() {
  if (cache) return Promise.resolve(cache);
  if (pending) return pending;

  pending = apiGet('/fonts')
    .then((res) => {
      const fonts = res.fonts?.length ? res.fonts : FALLBACK;
      injectFaces(fonts);
      cache = fonts;
      return fonts;
    })
    .catch(() => {
      cache = FALLBACK;
      return FALLBACK;
    })
    .finally(() => { pending = null; });

  return pending;
}

/**
 * Memasang @font-face sekali untuk seluruh aplikasi.
 *
 * `font-weight: 100 900` disengaja: berkasnya sudah ditandai bergaya Bold di
 * sisi backend, jadi berapa pun berat yang diminta CSS harus memakai berkas
 * yang sama — bukan menyuruh browser menebalkannya sendiri, yang membuat
 * pratinjau lebih gemuk daripada hasil rendernya.
 */
function injectFaces(fonts) {
  if (document.getElementById('omniclip-fonts')) return;
  const el = document.createElement('style');
  el.id = 'omniclip-fonts';
  el.textContent = fonts
    .filter((f) => f.url)
    .map((f) => `@font-face{font-family:'${f.family}';`
      + `src:url('${f.url}') format('truetype');`
      + 'font-weight:100 900;font-style:normal;font-display:swap}')
    .join('\n');
  document.head.appendChild(el);
}
