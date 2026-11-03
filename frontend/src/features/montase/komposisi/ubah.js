/**
 * Transformasi item (posisi, ukuran, putar, transparansi, potong) menjadi
 * gaya CSS.
 *
 * `x` dan `y` dalam piksel kanvas dari letak asal, `skala` 1 = ukuran asli,
 * `putar` dalam derajat. Satuan kanvas, bukan persen, supaya angka yang sama
 * menghasilkan letak yang sama di pratinjau yang diperkecil dan di render
 * ukuran penuh: Player menskalakan seluruh kanvas, bukan isinya satu per satu.
 *
 * `potong` = {kiri, kanan, atas, bawah} dalam persen kotak item, lewat
 * `clip-path: inset()`. Clip-path berlaku di ruang elemen itu sendiri, jadi
 * potongan ikut tergeser, terskala, dan terputar bersama itemnya, sama dengan
 * yang digambar pegangan di pratinjau (editor/PeganganUbah.jsx).
 */
import { punyaKeyframe, volumePada } from './keyframe.js';

export function gayaUbah(ubah) {
  if (!ubah) return undefined;
  const { x = 0, y = 0, skala = 1, putar = 0, opasitas = 1, potong } = ubah;
  const transform = [];
  if (x || y) transform.push(`translate(${x}px, ${y}px)`);
  if (skala !== 1) transform.push(`scale(${skala})`);
  if (putar) transform.push(`rotate(${putar}deg)`);
  const gaya = {
    transform: transform.length ? transform.join(' ') : undefined,
    opacity: opasitas === 1 ? undefined : opasitas,
  };
  if (potong && (potong.kiri || potong.kanan || potong.atas || potong.bawah)) {
    const p = (v) => `${Number(v) || 0}%`;
    gaya.clipPath = `inset(${p(potong.atas)} ${p(potong.kanan)} ${p(potong.bawah)} ${p(potong.kiri)})`;
  }
  return gaya;
}

/**
 * Pengali volume untuk lembut masuk/keluar (fade), linear. `f` = bingkai
 * sejak item mulai, `durasi` = panjang item. Bila jumlah keduanya melebihi
 * panjang item, keduanya dipendekkan sebanding supaya tetap bertemu di
 * tengah, bukan saling menimpa.
 */
export function pengaliFade(f, durasi, masuk = 0, keluar = 0) {
  let a = Math.max(0, masuk || 0);
  let b = Math.max(0, keluar || 0);
  if (a + b > durasi && a + b > 0) {
    const k = durasi / (a + b);
    a *= k;
    b *= k;
  }
  let v = 1;
  if (a > 0 && f < a) v = Math.min(v, f / a);
  if (b > 0 && f > durasi - b) v = Math.min(v, (durasi - f) / b);
  return Math.max(0, Math.min(1, v));
}

/**
 * Prop `volume` Remotion: angka tetap bila tanpa fade dan tanpa keyframe
 * volume, fungsi per bingkai bila ada salah satunya (M2.7, M3.7).
 */
export function volumeItem(item, lajur) {
  const lj = lajur?.volume ?? 1;
  const adaFade = item.fade_masuk > 0 || item.fade_keluar > 0;
  if (!adaFade && !punyaKeyframe(item, 'volume')) return (item.volume ?? 1) * lj;
  return (f) => volumePada(item, f) * lj * pengaliFade(f, item.durasi, item.fade_masuk, item.fade_keluar);
}
