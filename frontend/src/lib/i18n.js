/**
 * Terjemahan antarmuka (JOB-3 J3-1).
 *
 * Kamus per bahasa ada di `src/locales/<kode>.js`, berupa objek datar
 * `{ 'nav.beranda': 'Beranda', ... }`. Menambah bahasa = menambah satu berkas
 * kamus dan satu baris di `BAHASA`. Kunci yang belum diterjemahkan jatuh ke
 * bahasa Indonesia (bahasa sumber), lalu ke kuncinya sendiri, jadi teks yang
 * terlewat terlihat, bukan kosong.
 *
 * Bawaan mengikuti bahasa peramban (sejak Fase C selesai, 16 Oktober 2026):
 * peramban berbahasa Indonesia mendapat Indonesia, selain itu English. Pilihan
 * yang pernah dibuat sendiri disimpan dan selalu menang.
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

function dariPeramban() {
  try {
    for (const l of navigator.languages || [navigator.language]) {
      const k = String(l || '').slice(0, 2).toLowerCase();
      if (KAMUS[k]) return k;
    }
    return 'en';
  } catch {
    return BAWAAN;
  }
}

function awal() {
  try {
    const s = localStorage.getItem(KUNCI);
    if (s && KAMUS[s]) return s;
  } catch { /* penyimpanan peramban tidak tersedia */ }
  return dariPeramban();
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

/*
 * Negara konten (diminta pemilik 15 Oktober 2026: pengguna OmniClip belum
 * tentu orang Indonesia). Dipakai untuk daftar populer YouTube di Beranda dan
 * topik.
 *
 * Bawaannya IKUT BAHASA ANTARMUKA, bukan negara peramban. Dilaporkan pemilik
 * 16 Oktober 2026: di mode English topiknya berbahasa Inggris, tapi sesudah
 * ganti ke Indonesia isinya tetap sama, karena Firefox-nya en-US dan negara
 * diambil dari situ. Bahasa Indonesia = Indonesia; English = negara peramban
 * bila perambannya berbahasa Inggris (en-GB -> GB), selain itu Amerika
 * Serikat. Pilihan di Pengaturan > Tampilan dan bahasa mengalahkan semuanya;
 * "Otomatis" menghapusnya.
 */
const KUNCI_WILAYAH = 'omniclip.wilayah';
export const NEGARA = [
  'ID', 'US', 'GB', 'IN', 'MY', 'SG', 'PH', 'AU', 'CA', 'DE', 'FR', 'ES', 'IT',
  'NL', 'BR', 'MX', 'JP', 'KR', 'TH', 'VN', 'TR', 'SA', 'AE', 'NG', 'ZA',
];
const NEGARA_INGGRIS = new Set(['US', 'GB', 'AU', 'CA', 'IN', 'NZ', 'IE', 'SG', 'PH', 'ZA', 'NG']);

/** Negara yang dipilih sendiri di Pengaturan, atau '' (otomatis). */
export function wilayahPilihan() {
  try {
    const s = localStorage.getItem(KUNCI_WILAYAH);
    if (s && /^[A-Z]{2}$/.test(s)) return s;
  } catch { /* abaikan */ }
  return '';
}

export function wilayahOtomatis(kode = kini) {
  if (kode === 'id') return 'ID';
  try {
    for (const l of navigator.languages || [navigator.language]) {
      const m = /^en-([A-Za-z]{2})$/.exec(l || '');
      if (m && NEGARA_INGGRIS.has(m[1].toUpperCase())) return m[1].toUpperCase();
    }
  } catch { /* tidak ada navigator */ }
  return 'US';
}

export function wilayah() {
  return wilayahPilihan() || wilayahOtomatis();
}

/** '' = otomatis (ikut bahasa). */
export function setWilayah(kode) {
  try {
    if (kode) localStorage.setItem(KUNCI_WILAYAH, kode);
    else localStorage.removeItem(KUNCI_WILAYAH);
  } catch { /* abaikan */ }
  pendengar.forEach((f) => f());
}

/** Nama negara dalam bahasa antarmuka: "Indonesia", "Amerika Serikat". */
export function namaNegara(kode) {
  try {
    return new Intl.DisplayNames([lokal()], { type: 'region' }).of(kode) || kode;
  } catch {
    return kode;
  }
}
