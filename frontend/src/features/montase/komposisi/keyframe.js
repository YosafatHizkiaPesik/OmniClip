/**
 * Keyframe (JOB-4 M3.7): nilai sifat item yang berubah sepanjang waktu.
 *
 * Bentuk di dokumen:
 *   item.keyframe = { x: [{t, v, kurva}], y: [...], skala: [...], putar: [...],
 *                     opasitas: [...], volume: [...] }
 * `t` dalam bingkai RELATIF ke awal item (jadi menggeser item tidak perlu
 * menggeser keyframe-nya), `v` nilainya dalam satuan yang sama dengan
 * `item.ubah`/`item.volume`, `kurva` = cara MENUJU keyframe ini dari yang
 * sebelumnya: linear, masuk, keluar, masuk-keluar, pegas.
 *
 * Sifat yang punya keyframe mengabaikan nilai dasarnya (`ubah.x`, `volume`),
 * sama dengan CapCut: begitu ada keyframe, nilainya ditentukan keyframe.
 *
 * Dipakai komposisi (menggambar) dan editor (panel, pegangan, linimasa),
 * jadi satu-satunya tempat yang menghitung nilai antara.
 */
import { Easing } from 'remotion';

export const SIFAT_KEYFRAME = ['x', 'y', 'skala', 'putar', 'opasitas', 'volume'];
export const KURVA = ['linear', 'masuk', 'keluar', 'masuk-keluar', 'pegas'];

const PELANDAI = {
  linear: (p) => p,
  masuk: Easing.in(Easing.cubic),
  keluar: Easing.out(Easing.cubic),
  'masuk-keluar': Easing.inOut(Easing.cubic),
  // Melewati sasaran sedikit lalu kembali: "pegas" di CapCut.
  pegas: Easing.out(Easing.back(1.7)),
};

/** Nilai satu daftar keyframe pada bingkai relatif `f`; `bawaan` bila kosong. */
export function nilaiPada(daftar, f, bawaan) {
  if (!Array.isArray(daftar) || !daftar.length) return bawaan;
  if (f <= daftar[0].t) return daftar[0].v;
  const akhir = daftar[daftar.length - 1];
  if (f >= akhir.t) return akhir.v;
  for (let i = 0; i < daftar.length - 1; i += 1) {
    const a = daftar[i];
    const b = daftar[i + 1];
    if (f >= a.t && f <= b.t) {
      const p = b.t === a.t ? 1 : (f - a.t) / (b.t - a.t);
      const q = (PELANDAI[b.kurva] ?? PELANDAI.linear)(p);
      return a.v + (b.v - a.v) * q;
    }
  }
  return akhir.v;
}

export function punyaKeyframe(item, sifat) {
  return Array.isArray(item?.keyframe?.[sifat]) && item.keyframe[sifat].length > 0;
}

/** `item.ubah` pada bingkai relatif `f`, dengan keyframe diterapkan. */
export function ubahPada(item, f) {
  const kf = item?.keyframe;
  if (!kf) return item?.ubah;
  const dasar = item.ubah ?? {};
  const hasil = { ...dasar };
  let ada = false;
  for (const s of ['x', 'y', 'skala', 'putar', 'opasitas']) {
    if (punyaKeyframe(item, s)) {
      const bawaan = s === 'skala' || s === 'opasitas' ? 1 : 0;
      hasil[s] = nilaiPada(kf[s], f, dasar[s] ?? bawaan);
      ada = true;
    }
  }
  return ada ? hasil : item.ubah;
}

/** Volume item pada bingkai relatif `f` (tanpa fade dan volume lajur). */
export function volumePada(item, f) {
  return punyaKeyframe(item, 'volume') ? nilaiPada(item.keyframe.volume, f, item.volume ?? 1) : (item.volume ?? 1);
}

/** Semua bingkai relatif yang punya keyframe (sifat apa pun), urut, untuk wajik di linimasa. */
export function bingkaiKeyframe(item) {
  const t = new Set();
  for (const s of SIFAT_KEYFRAME) for (const k of item?.keyframe?.[s] ?? []) t.add(k.t);
  return [...t].sort((a, b) => a - b);
}
