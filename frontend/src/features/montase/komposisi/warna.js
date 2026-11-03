/**
 * Penyesuaian warna item video/gambar (JOB-4 M3.6).
 *
 * `item.warna = {preset, kecerahan, kontras, saturasi, suhu}`; angka -100..100,
 * 0 = tidak berubah. Preset bernama sama dengan `VIDEO_FILTERS` di
 * services/render.py (vibrant, cinematic, bw, vintage) dan meniru rantai
 * ffmpeg-nya dengan filter CSS, supaya gaya yang sama di Studio Klip dan
 * Montase terasa sama.
 *
 * Suhu (hangat/dingin) tidak ada di filter CSS biasa; dipakai matriks warna
 * SVG yang menguatkan merah dan melemahkan biru (atau sebaliknya). Matriks
 * yang sama dihitung di pratinjau dan di render, karena keduanya Chrome.
 */
export const PRESET_WARNA = {
  normal: '',
  vibrant: 'contrast(1.15) saturate(1.35) brightness(1.02)',
  cinematic: 'contrast(1.12) saturate(0.92)',
  bw: 'grayscale(1) contrast(1.1)',
  vintage: 'sepia(0.35) saturate(0.8) contrast(0.95) brightness(1.03)',
};

function angka(v) {
  const n = Number(v);
  return Number.isFinite(n) ? Math.max(-100, Math.min(100, n)) : 0;
}

/** Nilai matriks feColorMatrix untuk suhu -100 (dingin) .. 100 (hangat), atau null. */
export function matriksSuhu(suhu) {
  const s = angka(suhu) / 100;
  if (!s) return null;
  const r = 1 + 0.18 * s;
  const b = 1 - 0.18 * s;
  return `${r} 0 0 0 0  0 1 0 0 0  0 0 ${b} 0 0  0 0 0 1 0`;
}

/** String CSS `filter` untuk warna item; `idSuhu` = id filter SVG bila ada suhu. */
export function filterWarna(warna, idSuhu) {
  if (!warna) return undefined;
  const bagian = [];
  const preset = PRESET_WARNA[warna.preset];
  if (preset) bagian.push(preset);
  const k = angka(warna.kecerahan);
  const c = angka(warna.kontras);
  const s = angka(warna.saturasi);
  if (k) bagian.push(`brightness(${1 + k / 200})`);
  if (c) bagian.push(`contrast(${1 + c / 200})`);
  if (s) bagian.push(`saturate(${1 + s / 100})`);
  if (idSuhu && matriksSuhu(warna.suhu)) bagian.push(`url(#${idSuhu})`);
  return bagian.length ? bagian.join(' ') : undefined;
}
