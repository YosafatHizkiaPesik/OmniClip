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

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, options);
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw new ApiError(
      'Tidak dapat menghubungi server. Pastikan backend berjalan di port 8000.',
      { code: 'NETWORK' },
    );
  }
  if (!res.ok) throw await toApiError(res);
  if (res.status === 204) return null;
  return res.json();
}

export function apiGet(path, { signal } = {}) {
  return request(path, { signal });
}

export function apiPost(path, body, { signal } = {}) {
  return request(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body ?? {}),
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
  const res = await fetch(fileUrl(category, fileName));
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
