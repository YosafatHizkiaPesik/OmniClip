import { describe, expect, it } from 'vitest';
import { kotakDasar } from '../komposisi/kotak.js';
import { gayaUbah, pengaliFade, volumeItem } from '../komposisi/ubah.js';
import {
  bingkaiItem, geser, potongDariSisi, putarDari, skalaDariSudut,
} from './geometri.js';

const dok = {
  kanvas: { lebar: 1080, tinggi: 1920, fps: 30 },
  bahan: { bh_datar: { jenis: 'video', lebar: 1920, tinggi: 1080 } },
};
const video = (ubah, isi = 'contain') => ({ id: 'i1', jenis: 'video', bahan: 'bh_datar', isi, ubah });

describe('kotakDasar', () => {
  it('video mendatar "muat" di kanvas tegak: selebar kanvas, di tengah', () => {
    expect(kotakDasar(dok, video())).toEqual({ x: 0, y: 656.25, w: 1080, h: 607.5 });
  });
  it('"penuh" dan bahan tanpa ukuran memakai seluruh kanvas', () => {
    expect(kotakDasar(dok, video(undefined, 'cover'))).toEqual({ x: 0, y: 0, w: 1080, h: 1920 });
    expect(kotakDasar(dok, { jenis: 'video', bahan: 'bh_lain' }).w).toBe(1080);
  });
  it('teks di atas mulai dari tepi atas, satu baris setinggi ukuran huruf x 1,1', () => {
    const k = kotakDasar(dok, { jenis: 'teks', teks: 'Halo', gaya: { ukuran: 100, letak: 'atas' } });
    expect(k.y).toBe(160);
    expect(k.h).toBeCloseTo(110);
    expect(k.w).toBeCloseTo(224);
  });
});

describe('bingkaiItem', () => {
  it('potong kiri 10% menggeser pusat tampak ke kanan sebesar 5% lebar', () => {
    const b = bingkaiItem(dok, video({ potong: { kiri: 10 } }));
    expect(b.tampak.cx).toBeCloseTo(540 + 54);
    expect(b.tampak.w).toBeCloseTo(972);
  });
  it('skala dan putar ikut menggeser pusat potongan', () => {
    const b = bingkaiItem(dok, video({ skala: 2, putar: 90, potong: { kiri: 10 } }));
    // Geser lokal (+54, 0) x skala 2, diputar 90 derajat -> (0, +108).
    expect(b.tampak.cx).toBeCloseTo(540);
    expect(b.tampak.cy).toBeCloseTo(960 + 108);
  });
});

describe('pegangan', () => {
  it('geser menempel ke garis tengah dalam ambang', () => {
    const g = geser(dok, video(), { x: 0, y: 0 }, 6, 300, 10);
    expect(g).toMatchObject({ x: 0, y: 300, garis: { tegak: true, datar: false } });
  });
  it('skala sebanding jarak ke pusat', () => {
    expect(skalaDariSudut(1, { x: 0, y: 0 }, { x: 100, y: 0 }, { x: 150, y: 0 })).toBe(1.5);
  });
  it('putar seperempat lingkaran, menempel ke 90', () => {
    expect(putarDari(0, { x: 0, y: 0 }, { x: 0, y: -100 }, { x: 102, y: 2 })).toBe(90);
    expect(putarDari(170, { x: 0, y: 0 }, { x: 100, y: 0 }, { x: 0, y: 100 })).toBe(-100);
  });
  it('potong sisi kanan pada item terputar 180 derajat memakai arah lokal', () => {
    const p = potongDariSisi('kanan', {}, 100, 0, { skala: 1, putar: 180, w: 1000, h: 500 });
    expect(p.kanan).toBe(10);
  });
});

describe('ubah dan fade', () => {
  it('potong menjadi clip-path inset atas kanan bawah kiri', () => {
    expect(gayaUbah({ potong: { kiri: 10, kanan: 0, atas: 5, bawah: 0 } }).clipPath)
      .toBe('inset(5% 0% 0% 10%)');
  });
  it('fade masuk dan keluar linear, dipendekkan bila melebihi item', () => {
    expect(pengaliFade(0, 100, 10, 10)).toBe(0);
    expect(pengaliFade(5, 100, 10, 10)).toBe(0.5);
    expect(pengaliFade(50, 100, 10, 10)).toBe(1);
    expect(pengaliFade(95, 100, 10, 10)).toBe(0.5);
    expect(pengaliFade(50, 100, 100, 100)).toBe(1);
  });
  it('volume tetap berupa angka bila tanpa fade', () => {
    expect(volumeItem({ volume: 0.5 }, { volume: 2 })).toBe(1);
    expect(typeof volumeItem({ volume: 1, fade_masuk: 10, durasi: 60 })).toBe('function');
  });
});
