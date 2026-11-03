/**
 * Panggilan API Montase (JOB-4 bagian 18). Satu tempat, supaya alamatnya tidak
 * tersebar di komponen.
 */
import { apiDelete, apiGet, apiPost, apiPut, apiUnggah } from '../../lib/api';

export const ambilSetelan = () => apiGet('/montase/setelan');
export const simpanSetelan = (aktif) => apiPost('/montase/setelan', { aktif });

export const daftarProyek = () => apiGet('/montase/proyek').then((r) => r.proyek ?? []);
export const buatProyek = (isi) => apiPost('/montase/proyek', isi);
export const ambilProyek = (id) => apiGet(`/montase/proyek/${encodeURIComponent(id)}`);
export const simpanProyek = (id, dokumen, revisi) =>
  apiPut(`/montase/proyek/${encodeURIComponent(id)}`, { dokumen, revisi });
export const hapusProyek = (id) => apiDelete(`/montase/proyek/${encodeURIComponent(id)}`);
export const gandakanProyek = (id) =>
  apiPost(`/montase/proyek/${encodeURIComponent(id)}/gandakan`);
export const eksporProyek = (id) =>
  apiPost(`/montase/proyek/${encodeURIComponent(id)}/ekspor`);

export const daftarBahan = () => apiGet('/montase/bahan').then((r) => r.bahan ?? []);
export const sumberBahan = (asal) =>
  apiGet(`/montase/bahan/sumber?asal=${encodeURIComponent(asal)}`).then((r) => r.sumber ?? []);
export const rujukBahan = (asal, rujukan) => apiPost('/montase/bahan/rujuk', { asal, rujukan });
export const hapusBahan = (id) => apiDelete(`/montase/bahan/${encodeURIComponent(id)}`);
export function imporBahan(berkas, onProgress) {
  const data = new FormData();
  data.append('berkas', berkas);
  return apiUnggah('/montase/bahan/impor', data, onProgress);
}

export const ambilToken = () => apiGet('/montase/token').then((r) => r.token);

/**
 * Alamat bertoken untuk bahan. Dipakai iframe kotak pasir dan `<img>`, yang
 * keduanya tidak membawa sesi maupun header profil: tokennya yang membawa.
 */
export function alamatBahan(token, bahanId, { sunting = false, turunan = null } = {}) {
  const dasar = `/api/montase/t/${token}/bahan/${encodeURIComponent(bahanId)}`;
  if (turunan) return `${dasar}/${turunan}`;
  return sunting ? `${dasar}?sunting=1` : dasar;
}

/** `sumber` untuk Komposisi: setiap bahan di dokumen -> alamat salinan suntingnya. */
export function sumberPratinjau(dokumen, token) {
  const bahan = {};
  if (token) {
    for (const id of Object.keys(dokumen?.bahan ?? {})) {
      bahan[id] = alamatBahan(token, id, { sunting: true });
    }
  }
  return { bahan, komponen: {} };
}
