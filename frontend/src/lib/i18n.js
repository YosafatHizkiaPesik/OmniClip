/**
 * Terjemahan antarmuka (JOB-3 J3-1).
 *
 * Kamus per bahasa ada di `src/locales/<kode>.js`, berupa objek datar
 * `{ 'nav.beranda': 'Beranda', ... }`. Menambah bahasa = menambah satu berkas
 * kamus dan satu baris di `BAHASA`. Kunci yang belum diterjemahkan jatuh ke
 * bahasa Indonesia (bahasa sumber), lalu ke kuncinya sendiri, jadi teks yang
 * terlewat terlihat, bukan kosong.
 *
 * Bawaan sementara Indonesia, bukan bahasa peramban: selama terjemahan UI
 * belum menyeluruh (JOB-3 Fase C), mengikuti peramban berbahasa Inggris
 * menghasilkan layar setengah Inggris setengah Indonesia.
 */
import { createElement, Fragment, useSyncExternalStore } from 'react';
import id from '../locales/id';
import en from '../locales/en';

const KAMUS = { id, en };
export const BAHASA = [
  { kode: 'id', nama: 'Bahasa Indonesia' },
  { kode: 'en', nama: 'English' },
];
const KUNCI = 'omniclip.bahasa';
const BAWAAN = 'id';

function awal() {
  try {
    const s = localStorage.getItem(KUNCI);
    if (s && KAMUS[s]) return s;
  } catch { /* penyimpanan peramban tidak tersedia */ }
  return BAWAAN;
}

let kini = awal();
const pendengar = new Set();
if (typeof document !== 'undefined') document.documentElement.lang = kini;

export function bahasa() {
  return kini;
}

export function setBahasa(kode) {
  if (!KAMUS[kode] || kode === kini) return;
  kini = kode;
  try { localStorage.setItem(KUNCI, kode); } catch { /* abaikan */ }
  if (typeof document !== 'undefined') document.documentElement.lang = kode;
  pendengar.forEach((f) => f());
}

/** Teks untuk `kunci`, dengan `{nama}` diganti dari `isi`. */
export function t(kunci, isi) {
  let s = KAMUS[kini]?.[kunci] ?? KAMUS.id[kunci] ?? kunci;
  if (isi) {
    for (const [k, v] of Object.entries(isi)) s = s.split(`{${k}}`).join(String(v));
  }
  return s;
}

function langganan(f) {
  pendengar.add(f);
  return () => pendengar.delete(f);
}

/** Hook: komponen dirender ulang saat bahasa berganti. Mengembalikan `t`. */
export function useT() {
  useSyncExternalStore(langganan, bahasa, bahasa);
  return t;
}

/** Kode lokal Intl untuk bahasa pilihan: tanggal dan angka ikut bahasanya. */
export function lokal() {
  return kini === 'id' ? 'id-ID' : 'en-US';
}

/** Angka utuh dengan pemisah ribuan sesuai bahasa: 12.345 / 12,345. */
export function angka(n) {
  return Number(n || 0).toLocaleString(lokal());
}

/** Format angka ringkas sesuai bahasa: 1,2 jt / 1.2M. */
export function angkaRingkas(n) {
  if (n == null || Number.isNaN(Number(n))) return '';
  try {
    return new Intl.NumberFormat(lokal(),
      { notation: 'compact', maximumFractionDigits: 1 }).format(Number(n));
  } catch {
    return String(n);
  }
}

/**
 * Teks kamus dengan `**tebal**` dirender sebagai <b>. Supaya satu kalimat
 * yang punya kata tebal di tengahnya tetap satu kunci kamus, dan susunan
 * kalimat tiap bahasa bebas mengikuti tata bahasanya sendiri.
 */
export function tebal(teks) {
  const bagian = String(teks).split(/\*\*(.+?)\*\*/g);
  if (bagian.length === 1) return teks;
  return createElement(Fragment, null,
    ...bagian.map((b, i) => (i % 2 ? createElement('b', { key: i }, b) : b)));
}
