import { describe, expect, it } from 'vitest';
import { gayaUbah } from './ubah.js';
import { jalankanModul, MODUL_DIIZINKAN } from './muatKomponen.js';
import { ukuranDokumen } from './Komposisi.jsx';
import { BAWAAN } from './motion/index.js';

describe('gayaUbah', () => {
  it('tanpa ubah tidak menambah gaya apa pun', () => {
    expect(gayaUbah(undefined)).toBeUndefined();
    expect(gayaUbah({})).toEqual({ transform: undefined, opacity: undefined });
  });
  it('posisi dalam piksel kanvas, urutan geser lalu skala lalu putar', () => {
    expect(gayaUbah({ x: 10, y: -20, skala: 1.5, putar: 30, opasitas: 0.5 })).toEqual({
      transform: 'translate(10px, -20px) scale(1.5) rotate(30deg)',
      opacity: 0.5,
    });
  });
});

describe('ukuranDokumen', () => {
  it('bawaan Shorts 30 fps', () => {
    expect(ukuranDokumen(null)).toEqual({ lebar: 1080, tinggi: 1920, fps: 30, durasi: 1 });
  });
  it('durasi dibulatkan ke bingkai utuh, minimal satu', () => {
    const u = ukuranDokumen({ kanvas: { lebar: 1920, tinggi: 1080, fps: 60 }, durasi: 299.6 });
    expect(u).toEqual({ lebar: 1920, tinggi: 1080, fps: 60, durasi: 300 });
    expect(ukuranDokumen({ durasi: 0 }).durasi).toBe(1);
  });
});

describe('jalankanModul (komponen buatan AI)', () => {
  it('memberi React dan Remotion yang sama dengan komposisi', () => {
    const m = jalankanModul(
      'const r = require("react"); const rm = require("remotion");'
      + ' exports.sama = r; exports.remotion = rm; exports.default = function A() { return null; };',
    );
    expect(m.sama).toBe(MODUL_DIIZINKAN.react);
    expect(m.remotion).toBe(MODUL_DIIZINKAN.remotion);
    expect(typeof m.default).toBe('function');
  });
  it('impor di luar kontrak gagal saat dimuat', () => {
    expect(() => jalankanModul('require("fs")')).toThrow(/tidak diizinkan/);
    expect(() => jalankanModul('require("constructor")')).toThrow(/tidak diizinkan/);
  });
});

describe('animasi bawaan', () => {
  it('setiap animasi bawaan memenuhi kontrak bagian 21', () => {
    for (const [id, modul] of Object.entries(BAWAAN)) {
      expect(id).toMatch(/^ko_[a-z0-9_]+$/);
      expect(typeof modul.default).toBe('function');
      expect(modul.skema.safeParse(modul.contohProps).success).toBe(true);
      expect(Number.isInteger(modul.durasiBawaan)).toBe(true);
      expect(typeof modul.kategori).toBe('string');
    }
  });
});
