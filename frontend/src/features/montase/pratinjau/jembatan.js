/**
 * Protokol postMessage antara editor (induk) dan iframe kotak pasir pratinjau
 * (JOB-4.md bagian 20).
 *
 * Induk -> iframe:  muat {dokumen, sumber} · putar · jeda · ke {bingkai}
 * Iframe -> induk:  siap · bingkai {bingkai} · main {main} · galat {pesan}
 *
 * Iframe beralamat `null`, jadi `targetOrigin` harus '*'. Yang menjamin pesan
 * berasal dari pihak yang benar adalah pemeriksaan `event.source` di kedua
 * sisi, bukan alamatnya.
 */
export const TANDA = 'omniclip-montase';

export function pesan(jenis, isi = {}) {
  return { ...isi, tanda: TANDA, jenis };
}

export function pesanSah(data) {
  return Boolean(data) && typeof data === 'object' && data.tanda === TANDA
    && typeof data.jenis === 'string';
}
