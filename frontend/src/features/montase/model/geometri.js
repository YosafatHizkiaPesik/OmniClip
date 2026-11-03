/**
 * Hitungan pegangan transformasi di pratinjau (JOB-4 M2.5), fungsi murni.
 *
 * Semua dalam PIKSEL KANVAS. Pegangan digambar di luar iframe
 * (editor/PeganganUbah.jsx) dan hanya mengalikan hasilnya dengan skala layar.
 *
 * Urutan transformasi sama dengan komposisi/ubah.js: titik lokal p (relatif ke
 * pusat kotak) tampil di  pusat + (x, y) + skala · R(putar) · p.
 */
import { kotakDasar } from '../komposisi/kotak.js';

const RAD = Math.PI / 180;

function putarVektor(x, y, derajat) {
  const c = Math.cos(derajat * RAD);
  const s = Math.sin(derajat * RAD);
  return { x: x * c - y * s, y: x * s + y * c };
}

/**
 * Bingkai item seperti terlihat di kanvas.
 *   tampak: bagian yang tersisa sesudah dipotong {cx, cy, w, h}
 *   penuh:  seluruh kotak sebelum dipotong {cx, cy, w, h} (untuk mode potong)
 *   putar:  sudut dalam derajat
 */
export function bingkaiItem(dokumen, item) {
  const k = kotakDasar(dokumen, item);
  const u = item.ubah ?? {};
  const skala = u.skala ?? 1;
  const putar = u.putar ?? 0;
  const p = u.potong ?? {};
  const kiri = (p.kiri || 0) / 100;
  const kanan = (p.kanan || 0) / 100;
  const atas = (p.atas || 0) / 100;
  const bawah = (p.bawah || 0) / 100;
  const cx = k.x + k.w / 2 + (u.x || 0);
  const cy = k.y + k.h / 2 + (u.y || 0);
  const geser = putarVektor((k.w * (kiri - kanan) * skala) / 2, (k.h * (atas - bawah) * skala) / 2, putar);
  return {
    putar,
    skala,
    kotak: k,
    penuh: { cx, cy, w: k.w * skala, h: k.h * skala },
    tampak: {
      cx: cx + geser.x,
      cy: cy + geser.y,
      w: k.w * (1 - kiri - kanan) * skala,
      h: k.h * (1 - atas - bawah) * skala,
    },
  };
}

/**
 * Menggeser: posisi baru dari posisi awal ditambah selisih penunjuk. Pusat
 * item menempel ke garis tengah kanvas bila jaraknya dalam `ambang`.
 * Mengembalikan {x, y, garis: {tegak, datar}} (garis bantu yang menyala).
 */
export function geser(dokumen, item, ubahAwal, dx, dy, ambang = 0) {
  const W = dokumen.kanvas.lebar;
  const H = dokumen.kanvas.tinggi;
  const k = kotakDasar(dokumen, item);
  let x = (ubahAwal?.x || 0) + dx;
  let y = (ubahAwal?.y || 0) + dy;
  const garis = { tegak: false, datar: false };
  if (ambang > 0) {
    const pusatX = k.x + k.w / 2 + x;
    const pusatY = k.y + k.h / 2 + y;
    if (Math.abs(pusatX - W / 2) <= ambang) { x += W / 2 - pusatX; garis.tegak = true; }
    if (Math.abs(pusatY - H / 2) <= ambang) { y += H / 2 - pusatY; garis.datar = true; }
  }
  return { x: Math.round(x), y: Math.round(y), garis };
}

/** Skala seragam dari pegangan sudut: sebanding jarak penunjuk ke pusat. */
export function skalaDariSudut(skalaAwal, pusat, titikAwal, titikKini) {
  const jarakAwal = Math.hypot(titikAwal.x - pusat.x, titikAwal.y - pusat.y);
  const jarakKini = Math.hypot(titikKini.x - pusat.x, titikKini.y - pusat.y);
  if (jarakAwal < 1) return skalaAwal;
  return Math.round(skalaAwal * (jarakKini / jarakAwal) * 1000) / 1000;
}

/**
 * Sudut dari pegangan putar. Menempel ke kelipatan 90 derajat bila dalam
 * `tempel` derajat (lurus kembali itu yang paling sering dicari).
 */
export function putarDari(putarAwal, pusat, titikAwal, titikKini, tempel = 4) {
  const a = Math.atan2(titikAwal.y - pusat.y, titikAwal.x - pusat.x);
  const b = Math.atan2(titikKini.y - pusat.y, titikKini.x - pusat.x);
  let sudut = putarAwal + (b - a) / RAD;
  sudut = ((((sudut + 180) % 360) + 360) % 360) - 180;
  const lurus = Math.round(sudut / 90) * 90;
  if (Math.abs(sudut - lurus) <= tempel) sudut = lurus;
  return Math.round(sudut * 10) / 10;
}

/**
 * Memotong dari satu sisi: selisih penunjuk (piksel kanvas) diterjemahkan ke
 * ruang lokal item (dibalik putar dan skalanya), lalu ke persen kotak.
 */
export function potongDariSisi(sisi, potongAwal, dx, dy, { skala = 1, putar = 0, w, h }) {
  const lokal = putarVektor(dx / skala, dy / skala, -putar);
  const p = { kiri: 0, kanan: 0, atas: 0, bawah: 0, ...potongAwal };
  if (sisi === 'kiri') p.kiri += (lokal.x / w) * 100;
  else if (sisi === 'kanan') p.kanan -= (lokal.x / w) * 100;
  else if (sisi === 'atas') p.atas += (lokal.y / h) * 100;
  else if (sisi === 'bawah') p.bawah -= (lokal.y / h) * 100;
  for (const k of Object.keys(p)) p[k] = Math.max(0, Math.round(p[k] * 10) / 10);
  return p;
}

/** Titik sudut bingkai (untuk menggambar pegangan) dalam urutan kiri-atas searah jarum jam. */
export function sudutBingkai({ cx, cy, w, h }, putar) {
  return [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([sx, sy]) => {
    const v = putarVektor((sx * w) / 2, (sy * h) / 2, putar);
    return { x: cx + v.x, y: cy + v.y };
  });
}
