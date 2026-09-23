/**
 * Satu-satunya tempat frontend berbicara dengan backend.
 *
 * Sebelumnya `http://localhost:8000` di-hardcode di 32 tempat pada 7 file,
 * sehingga mengganti port atau men-deploy backend berarti find-and-replace.
 * Sekarang semua lewat BASE relatif yang di-proxy oleh Vite (lihat vite.config.js).
 */

const BASE = import.meta.env.VITE_API_BASE ?? '/api';

export class ApiError extends Error {
  constructor(message, { status, code } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

/** Menerjemahkan respons gagal jadi ApiError berpesan Indonesia. */
async function toApiError(res) {
  let code;
  let message;
  try {
    const body = await res.json();
    // Backend memakai {code, message}; HTTPException FastAPI memakai {detail}.
    code = body.code;
    message = body.message ?? body.detail;
    if (message && typeof message !== 'string') message = JSON.stringify(message);
  } catch {
    /* respons bukan JSON */
  }
  if (!message) {
    message =
      res.status === 404
        ? 'Data tidak ditemukan.'
        : res.status === 429
          ? 'Terlalu banyak permintaan. Coba lagi sebentar lagi.'
          : res.status >= 500
            ? 'Server sedang bermasalah. Cek apakah backend berjalan.'
            : `Permintaan gagal (${res.status}).`;
  }
  return new ApiError(message, { status: res.status, code });
}

// --- Profil aktif -----------------------------------------------------------
//
// Disimpan per peramban dan dikirim di SETIAP permintaan sebagai header, bukan
// disetel sekali di server: dua tab (atau laptop dan HP) boleh bekerja di
// profil yang berbeda tanpa saling menimpa. Lihat backend services/profil.py.
const PROFIL_KEY = 'omniclip.profil';

export function profilAktif() {
  try {
    const n = parseInt(localStorage.getItem(PROFIL_KEY) || '1', 10);
    return Number.isFinite(n) && n > 0 ? n : 1;
  } catch {
    return 1;
  }
}

/** Pindah profil: seluruh halaman dimuat ulang supaya tidak ada data profil lama yang tertinggal di layar. */
export function pilihProfil(id) {
  try { localStorage.setItem(PROFIL_KEY, String(id)); } catch { /* mode privat */ }
  window.location.reload();
}

/** Kategori media folder klip profil aktif: /api/media/klip_<id>/<berkas>. */
export function kategoriKlip() {
  return `klip_${profilAktif()}`;
}

async function request(path, options = {}) {
  let res;
  options = { ...options,
              headers: { ...(options.headers || {}), 'X-Omniclip-Profil': String(profilAktif()) } };
  try {
    // credentials same-origin: cookie sesi ikut terkirim. Ini bawaan fetch
    // modern, ditulis eksplisit karena gerbang masuk bergantung padanya.
    res = await fetch(`${BASE}${path}`, { credentials: 'same-origin', ...options });
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw new ApiError(
      'Tidak dapat menghubungi server. Pastikan backend berjalan di port 8000.',
      { code: 'NETWORK' },
    );
  }
  if (res.status === 401) {
    // Sesi berakhir di tengah pemakaian — cookie kedaluwarsa, atau kata sandi
    // diganti dari perangkat lain. Tanpa pemberitahuan ini, gejalanya adalah
    // setiap tombol berhenti bekerja tanpa alasan yang terlihat.
    window.dispatchEvent(new CustomEvent('omniclip:auth-required'));
  }
  if (!res.ok) throw await toApiError(res);
  if (res.status === 204) return null;
  return res.json();
}

export function apiGet(path, { signal } = {}) {
  return request(path, { signal });
}

/**
 * `raw: true` mengirim body sebagai teks apa adanya.
 *
 * Dipakai untuk memasang berkas OAuth client: isinya adalah JSON milik Google,
 * dan membungkusnya lagi ke dalam JSON hanya menambah satu lapis escape yang
 * harus dibuka lagi di server.
 */
export function apiPost(path, body, { signal, raw = false } = {}) {
  // FormData dikirim apa adanya, TANPA Content-Type dari kita.
  //
  // Unggahan multipart butuh sebuah `boundary` di header, dan satu-satunya
  // yang tahu nilainya adalah peramban — ia menyusunnya sendiri saat melihat
  // FormData. Menuliskan Content-Type sendiri menghapus boundary itu, dan
  // server menolak seluruh unggahan dengan galat yang tidak menyebut sebabnya.
  if (typeof FormData !== 'undefined' && body instanceof FormData) {
    return request(path, { method: 'POST', body, signal });
  }
  return request(path, {
    method: 'POST',
    headers: { 'Content-Type': raw ? 'text/plain' : 'application/json' },
    body: raw ? String(body) : JSON.stringify(body ?? {}),
    signal,
  });
}

export function apiPut(path, body, { signal } = {}) {
  return request(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
    signal,
  });
}

/**
 * Mengirim FormData sambil melaporkan kemajuannya (0-1).
 *
 * `fetch` tidak bisa memberi tahu berapa yang sudah terkirim, dan video
 * impor berukuran ratusan megabita: tanpa angka, beberapa menit mengirim
 * tidak bisa dibedakan dari macet.
 */
export function apiUnggah(path, formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${BASE}${path}`);
    xhr.withCredentials = true;
    xhr.setRequestHeader('X-Omniclip-Profil', String(profilAktif()));
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) onProgress(e.loaded / e.total);
    };
    xhr.onload = () => {
      let body = null;
      try { body = JSON.parse(xhr.responseText); } catch { /* bukan JSON */ }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body);
      else {
        reject(new ApiError(body?.message ?? body?.detail
          ?? `Pengiriman gagal (${xhr.status}).`, { status: xhr.status, code: body?.code }));
      }
    };
    xhr.onerror = () => reject(new ApiError(
      'Pengiriman terputus. Pastikan backend berjalan.', { code: 'NETWORK' }));
    xhr.send(formData);
  });
}

export function apiPatch(path, body, { signal } = {}) {
  return request(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
    signal,
  });
}

export function apiDelete(path, { signal } = {}) {
  return request(path, { method: 'DELETE', signal });
}

/** URL pemutaran inline (mendukung seeking lewat HTTP Range). */
export function mediaUrl(category, fileName) {
  return `${BASE}/media/${category}/${encodeURIComponent(fileName)}`;
}

/** URL unduh paksa (Content-Disposition: attachment). */
export function fileUrl(category, fileName) {
  return `${BASE}/file/${category}/${encodeURIComponent(fileName)}`;
}

/**
 * Mengunduh file lewat backend agar tidak kena CORS, lalu menyimpannya.
 * Rutinitas ini sebelumnya disalin-tempel di 4 komponen.
 */
export async function downloadToDisk(category, fileName) {
  const res = await fetch(fileUrl(category, fileName), { credentials: 'same-origin' });
  if (!res.ok) throw await toApiError(res);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** URL embed YouTube dengan origin yang benar (bukan port yang di-hardcode). */
export function youtubeEmbedUrl(videoId, { start, end, autoplay = 0 } = {}) {
  const params = new URLSearchParams({
    origin: window.location.origin,
    autoplay: String(autoplay),
    rel: '0',
    modestbranding: '1',
  });
  if (start != null) params.set('start', String(Math.floor(start)));
  if (end != null) params.set('end', String(Math.ceil(end)));
  return `https://www.youtube-nocookie.com/embed/${videoId}?${params}`;
}
