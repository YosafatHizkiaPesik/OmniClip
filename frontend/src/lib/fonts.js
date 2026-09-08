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

/** Rantai fallback untuk CSS: font display dulu, lalu sans-serif sistem. */
export function fontStack(family) {
  return `'${family || 'Montserrat'}', 'Segoe UI', system-ui, sans-serif`;
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
