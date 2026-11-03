import { describe, expect, it } from 'vitest';
import { gayaUbah } from './ubah.js';
import { jalankanModul, MODUL_DIIZINKAN } from './muatKomponen.js';
import { ukuranDokumen } from './Komposisi.jsx';
import { BAWAAN } from './motion/index.js';
import { gayaTransisi, rencanaTransisi } from './transisi.js';
import { filterWarna, matriksSuhu } from './warna.js';
import { transformEfek } from './efek.js';

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

describe('transisi (M3.5)', () => {
  const a = { id: 'a', mulai: 0, durasi: 60 };
  const b = { id: 'b', mulai: 60, durasi: 60, transisi: { jenis: 'larut', durasi: 20 } };
  it('berpusat di sambungan: yang keluar ditahan sesudah, yang masuk sebelum', () => {
    const r = rencanaTransisi([a, b]);
    expect(r.get('b')).toMatchObject({ pra: 10, pasca: 0, masuk: { jenis: 'larut', mulai: 0, d: 20 } });
    expect(r.get('a')).toMatchObject({ pra: 0, pasca: 10, keluar: { mulai: 50, d: 20 } });
  });
  it('larut: yang masuk memudar masuk di atas yang keluar', () => {
    const r = rencanaTransisi([a, b]).get('b');
    expect(gayaTransisi(r, 5).gaya.opacity).toBeCloseTo(0.25);
    expect(gayaTransisi(r, 25).gaya.opacity).toBeUndefined();
  });
  it('tanpa item sebelumnya: transisi dari latar di awal item, potong = tanpa transisi', () => {
    const r = rencanaTransisi([{ ...b, mulai: 100 }]).get('b');
    expect(r).toMatchObject({ pra: 0, masuk: { mulai: 0, d: 20 } });
    expect(rencanaTransisi([a, { ...b, transisi: { jenis: 'potong', durasi: 20 } }]).get('a').keluar).toBeNull();
  });
  it('kilat memuncak di tengah', () => {
    const r = rencanaTransisi([a, { ...b, transisi: { jenis: 'kilat', durasi: 20 } }]).get('b');
    expect(gayaTransisi(r, 10).kilat).toBe(1);
    expect(gayaTransisi(r, 2).gaya.opacity).toBe(0);
  });
});

describe('warna (M3.6)', () => {
  it('preset seperti VIDEO_FILTERS ditambah penggeser dan suhu', () => {
    expect(filterWarna({ preset: 'bw' })).toBe('grayscale(1) contrast(1.1)');
    expect(filterWarna({ kecerahan: 20, suhu: 50 }, 's1')).toBe('brightness(1.1) url(#s1)');
    expect(filterWarna({})).toBeUndefined();
    expect(matriksSuhu(0)).toBeNull();
  });
});

describe('efek (M3.8)', () => {
  it('Ken Burns membesar pelan, punch naik-tahan-turun, guncang deterministik', () => {
    expect(transformEfek({ kenburns: 'masuk' }, 0, 101)).toBeUndefined();
    expect(transformEfek({ kenburns: 'masuk' }, 100, 101)).toBe('scale(1.1500)');
    const punch = { punch: [{ t: 10, d: 20 }] };
    expect(transformEfek(punch, 5, 100)).toBeUndefined();
    expect(transformEfek(punch, 20, 100)).toBe('scale(1.1500)');
    expect(transformEfek(punch, 10, 100)).toBe('scale(1.0500)');
    expect(transformEfek({ guncang: 50 }, 7, 100)).toBe(transformEfek({ guncang: 50 }, 7, 100));
  });
  it('bilah progres memenuhi kontrak animasi bawaan', () => {
    expect(BAWAAN.ko_bilah_progres.skema.safeParse(BAWAAN.ko_bilah_progres.contohProps).success).toBe(true);
  });
});
