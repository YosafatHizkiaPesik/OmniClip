/**
 * Uji geometri bingkai — fungsi murni di `frames.js`.
 *
 * KENAPA BERKAS INI ADA
 *
 * Sampai 2 Oktober 2026 proyek ini tidak punya penjalan uji JavaScript sama
 * sekali. Tiga puluh ribu baris frontend "diuji" dengan cara membaca berkasnya
 * sebagai TEKS dari uji Python — lima belas berkas uji, empat puluh satu
 * pencocokan string. Cara itu bisa memastikan sebuah baris ADA; ia tidak bisa
 * memastikan baris itu menghitung hal yang benar.
 *
 * Dua bug nyata lolos karena itu, keduanya ditemukan pemiliknya dari tangkapan
 * layar, bukan dari uji:
 *
 *   - `frames.find(f => f.id === frameId)` dengan dua bingkai tanpa id:
 *     `undefined === undefined` cocok untuk dua-duanya, jadi menyeret satu
 *     kotak memindahkan keduanya.
 *   - `kotakReaksi` di sini menyimpang dari `kotak_reaksi` di backend, jadi
 *     pratinjau Studio dan hasil render menghitung potongan yang berbeda.
 *
 * Yang diuji di sini SENGAJA hanya fungsi murni: tidak ada DOM, tidak ada
 * React, tidak ada jaringan. Di situlah geometrinya tinggal, dan geometri yang
 * salah adalah bentuk kegagalan yang paling sering terlihat di layar.
 */

import { describe, expect, it } from 'vitest';

import {
  berIdLengkap,
  clipTimeFor,
  coverPercent,
  kotakReaksi,
  newFrameId,
  rasioKeluaran,
  sourceTimeFor,
  susunGaming,
} from './frames';

// Bingkai sumber 1920x1080, kanvas keluaran 9:16.
const SRC_ASPEK = 1920 / 1080;
const OUT_ASPEK = 1080 / 1920;

/** Rasio piksel bidang wajah selebar kanvas, setinggi `tinggi` persen. */
const rasioBidangWajah = (tinggi) => (1080 * 100) / (1920 * tinggi);

describe('kotakReaksi: potongan bidang wajah', () => {
  // Panel-panel ini bentuk nyata yang terukur pada klip LaperGang pemiliknya.
  const PANEL = [
    { nama: 'kecil di pojok', x: 2, y: 4, w: 22, h: 24 },
    { nama: 'tegak', x: 6.3, y: 20.3, w: 16.4, h: 31.0 },
    { nama: 'besar', x: 0, y: 31.8, w: 42.0, h: 45.4 },
    { nama: 'sangat tegak', x: 2, y: 10, w: 6, h: 70 },
  ];

  it.each(PANEL)('tidak pernah keluar panel $nama', (panel) => {
    const r = kotakReaksi(panel, null, rasioBidangWajah(40), SRC_ASPEK);
    expect(r.x).toBeGreaterThanOrEqual(panel.x - 0.05);
    expect(r.y).toBeGreaterThanOrEqual(panel.y - 0.05);
    expect(r.x + r.w).toBeLessThanOrEqual(panel.x + panel.w + 0.05);
    expect(r.y + r.h).toBeLessThanOrEqual(panel.y + panel.h + 0.05);
  });

  it.each(PANEL)('sebesar yang bentuknya izinkan di panel $nama', (panel) => {
    // Aturan pemiliknya, 1 Oktober 2026: "tidak boleh lebih bahkan hingga
    // memotong sampai ke dalam bingkai game, tapi jika bingkai hanya kurang
    // atau lebih kecil sedikit dari kotak facecam maka tidak masalah". Jadi
    // satu sisi harus pas dengan sisi panelnya — bukan mengecil di keduanya.
    const r = kotakReaksi(panel, null, rasioBidangWajah(40), SRC_ASPEK);
    const pasLebar = Math.abs(r.w - panel.w) <= 0.05;
    const pasTinggi = Math.abs(r.h - panel.h) <= 0.05;
    expect(pasLebar || pasTinggi).toBe(true);
  });

  it('tetap di dalam panel walau kepalanya di tepi', () => {
    // Kepala menempel di tepi kanan panel. Aturan lama melebarkan potongan
    // sampai memuat kepala berikut ruangnya, dan di sini itu berarti menjulur
    // keluar panel — yang isinya gambar permainan.
    const panel = { x: 6.3, y: 20.3, w: 16.4, h: 31.0 };
    const muka = [19.0, 24.0, 22.4, 31.0];
    const r = kotakReaksi(panel, muka, rasioBidangWajah(40), SRC_ASPEK);
    expect(r.x + r.w).toBeLessThanOrEqual(panel.x + panel.w + 0.05);
    expect(r.x).toBeGreaterThanOrEqual(panel.x - 0.05);
  });

  it('jatuh di kepala, bukan di tengah panel', () => {
    // Panel 6x70 dengan kepala di y 14-24: potongan selebar 6% hanya setinggi
    // beberapa persen, jadi memuat kepalanya utuh memang mustahil. Yang bisa
    // dituntut adalah ia jatuh DI kepala — bukan di tengah panel, yang pada
    // panel setinggi 70% berarti dada dan perut.
    const panel = { x: 2, y: 10, w: 6, h: 70 };
    const muka = [3, 14, 7, 24];
    const r = kotakReaksi(panel, muka, rasioBidangWajah(40), SRC_ASPEK);
    const pusat = r.y + r.h / 2;
    expect(pusat).toBeGreaterThanOrEqual(muka[1]);
    expect(pusat).toBeLessThanOrEqual(muka[3]);
  });
});

describe('susunGaming: susunan dua bidang', () => {
  const PANEL = { x: 2, y: 4, w: 22, h: 24 };
  const dasar = {
    frames: [
      { id: 'permainan', label: 'Permainan', src: { x: 0, y: 0, w: 100, h: 100 },
        dst: { x: 0, y: 30, w: 100, h: 70 } },
      { id: 'reaksi', label: 'Reaksi', src: { ...PANEL },
        dst: { x: 0, y: 0, w: 100, h: 30 } },
    ],
    reaksi: [{ t: 0, kotak: { ...PANEL } }],
  };
  const susun = (wajah) => susunGaming(dasar, {
    wajah, permainan: 'isi', srcAspek: SRC_ASPEK, outAspek: OUT_ASPEK,
  });

  it('bidang wajah selebar kanvas', () => {
    const d = susun(30).frames[1].dst;
    expect(d.x).toBe(0);
    expect(d.w).toBe(100);
  });

  it('dua bidang menutup tinggi kanvas tanpa celah', () => {
    const f = susun(30).frames;
    expect(f[0].dst.h + f[1].dst.h).toBeCloseTo(100, 6);
  });

  it('tinggi bidang wajah dijepit 15-75', () => {
    expect(susun(5).frames[1].dst.h).toBe(15);
    expect(susun(90).frames[1].dst.h).toBe(75);
  });

  it('potongan reaksi tidak keluar panel pada tinggi mana pun', () => {
    for (const wajah of [15, 20, 30, 40, 55, 75]) {
      const s = susun(wajah).frames[1].src;
      expect(s.x).toBeGreaterThanOrEqual(PANEL.x - 0.05);
      expect(s.y).toBeGreaterThanOrEqual(PANEL.y - 0.05);
      expect(s.x + s.w).toBeLessThanOrEqual(PANEL.x + PANEL.w + 0.05);
      expect(s.y + s.h).toBeLessThanOrEqual(PANEL.y + PANEL.h + 0.05);
    }
  });
});

describe('berIdLengkap: id bingkai', () => {
  it('susunan yang sudah benar dikembalikan apa adanya', () => {
    const l = { frames: [{ id: 'a' }, { id: 'b' }] };
    expect(berIdLengkap(l)).toBe(l);
  });

  it('id yang hilang diisi', () => {
    const hasil = berIdLengkap({ frames: [{}, {}] });
    const id = hasil.frames.map((f) => f.id);
    expect(id.every(Boolean)).toBe(true);
    expect(new Set(id).size).toBe(2);
  });

  it('id yang KEMBAR diperbaiki', () => {
    // `find(f => f.id === frameId)` memberi kotak yang salah di sini, sama
    // buruknya dengan id yang hilang.
    const hasil = berIdLengkap({ frames: [{ id: 'x' }, { id: 'x' }] });
    expect(new Set(hasil.frames.map((f) => f.id)).size).toBe(2);
  });

  it('susunan kosong tidak membuatnya melempar', () => {
    expect(berIdLengkap(null)).toBe(null);
    expect(berIdLengkap({ frames: [] })).toEqual({ frames: [] });
  });

  it('newFrameId tidak pernah memberi dua id yang sama', () => {
    const n = new Set(Array.from({ length: 500 }, newFrameId));
    expect(n.size).toBe(500);
  });
});

describe('coverPercent: geometri "cover"', () => {
  it('sumber sebentuk bidangnya tidak dipotong', () => {
    // Kotak 16:9 di bidang 16:9: tidak ada yang perlu dipangkas.
    const g = coverPercent({ x: 0, y: 0, w: 100, h: 100 },
      { x: 0, y: 0, w: 100, h: 100 }, 16 / 9, 16 / 9);
    expect(g.width).toBeCloseTo(100, 6);
    expect(g.height).toBeCloseTo(100, 6);
  });

  it('sumber lebih lebar dipangkas kiri-kanan, bukan atas-bawah', () => {
    const g = coverPercent({ x: 0, y: 0, w: 100, h: 100 },
      { x: 0, y: 0, w: 100, h: 100 }, 16 / 9, 9 / 16);
    expect(g.height).toBeCloseTo(100, 6);
    expect(g.width).toBeGreaterThan(100);
  });

  it('kotak tak sah menjawab null, bukan melempar', () => {
    const sah = { x: 0, y: 0, w: 10, h: 10 };
    expect(coverPercent({ ...sah, w: 0 }, sah, 1, 1)).toBe(null);
    expect(coverPercent(sah, { ...sah, h: 0 }, 1, 1)).toBe(null);
    expect(coverPercent(sah, sah, 0, 1)).toBe(null);
  });
});

describe('waktu klip dan waktu sumber', () => {
  const SEG = [{ start: 10, end: 20 }, { start: 100, end: 105 }];

  it('bolak-balik kembali ke angka yang sama', () => {
    for (const t of [0, 1.5, 9.999, 10, 12, 14.9]) {
      expect(clipTimeFor(SEG, sourceTimeFor(SEG, t))).toBeCloseTo(t, 6);
    }
  });

  it('potongan kedua menyambung tanpa lompatan', () => {
    expect(sourceTimeFor(SEG, 10)).toBeCloseTo(100, 6);
    expect(clipTimeFor(SEG, 100)).toBeCloseTo(10, 6);
  });

  it('tanpa potongan, waktunya dipakai apa adanya', () => {
    expect(clipTimeFor(null, 7)).toBe(7);
    expect(sourceTimeFor([], 7)).toBe(7);
  });
});

describe('rasioKeluaran', () => {
  it('rasio yang dikenal', () => {
    expect(rasioKeluaran('9:16')).toBeCloseTo(1080 / 1920, 6);
    expect(rasioKeluaran('16:9')).toBeCloseTo(1920 / 1080, 6);
    expect(rasioKeluaran('1:1')).toBeCloseTo(1, 6);
  });

  it('rasio asing jatuh ke 9:16, bukan NaN', () => {
    expect(rasioKeluaran('entah')).toBeCloseTo(1080 / 1920, 6);
  });
});
