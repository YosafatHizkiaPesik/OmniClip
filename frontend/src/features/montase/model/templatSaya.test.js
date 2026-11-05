import { describe, expect, it } from 'vitest';
import { operasiTemplat } from './templat.js';
import { ambilTemplat, operasiTemplatSaya, templatBerisi } from './templatSaya.js';
import { terapkanOperasi } from './usulan.js';

function kosong(fps = 30) {
  return {
    versi: 1, id: 'mt', nama: 'x', durasi: 1, bahan: {}, penanda: [], ekspor: {},
    kanvas: { lebar: 1080, tinggi: 1920, fps, latar: '#000' },
    lajur: [
      { id: 'V', jenis: 'video', nama: 'Video 1', item: [] }, { id: 'M', jenis: 'motion', nama: 'Animasi', item: [] },
      { id: 'T', jenis: 'teks', nama: 'Teks', item: [] }, { id: 'A', jenis: 'audio', nama: 'Suara', item: [] },
    ],
  };
}

/** Proyek jadi: kerangka Reaksi + klip video + subtitle berisi ucapan. */
function proyekJadi() {
  let { dokumen } = terapkanOperasi(kosong(), operasiTemplat(kosong(), 'reaksi', 1));
  dokumen = {
    ...dokumen,
    bahan: { b1: { jenis: 'video', durasi: 40 } },
    lajur: dokumen.lajur.map((l) => {
      if (l.id === 'V') return { ...l, item: [{ id: 'v1', jenis: 'video', bahan: 'b1', mulai: 0, durasi: 900, potong_awal: 0 }] };
      if (l.subtitle) return { ...l, item: [{ id: 's1', jenis: 'teks', teks: 'ucapan lama', mulai: 0, durasi: 30, gaya: {} }] };
      return l;
    }),
  };
  const kartu = dokumen.lajur.find((l) => l.jenis === 'motion').item[0];
  kartu.ubah = { x: 0.1, y: -0.2, skala: 0.8 };
  kartu.versi = 3;
  return dokumen;
}

describe('templat milik sendiri', () => {
  it('menyimpan kerangka saja: tanpa bahan, tanpa teks subtitle, gaya caption ikut', () => {
    const tpl = ambilTemplat(proyekJadi());
    expect(JSON.stringify(tpl)).not.toContain('b1');
    expect(JSON.stringify(tpl)).not.toContain('ucapan lama');
    expect(tpl.caption).toBe('stiker');
    expect(tpl.isi.some((i) => i.jenis === 'teks')).toBe(true);
    expect(tpl.isi.some((i) => i.jenis === 'animasi')).toBe(true);
    expect(tpl.penanda.length).toBe(2);
    expect(templatBerisi(tpl)).toBe(true);
    expect(templatBerisi(ambilTemplat(kosong()))).toBe(false);
  });

  it('dipakai di proyek 60 fps: waktu tetap dalam detik, posisi dan versi ikut', () => {
    const asal = proyekJadi();
    const tpl = { nama: 'Reaksi saya', ...ambilTemplat(asal) };
    const ops = operasiTemplatSaya(kosong(60), tpl);
    const { dokumen, dilewati } = terapkanOperasi(kosong(60), ops);
    expect(dilewati).toEqual([]);
    const motion = (d) => d.lajur.flatMap((l) => l.item).filter((i) => i.jenis === 'motion');
    expect(motion(dokumen).length).toBe(motion(asal).length);
    const label = motion(asal).find((i) => i.ubah);
    const salin = motion(dokumen).find((i) => i.komponen === label.komponen && i.ubah);
    expect(salin.ubah).toEqual(label.ubah);
    expect(salin.versi).toBe(3);
    expect(salin.mulai).toBe(label.mulai * 2);
    expect(dokumen.penanda.map((p) => p.t)).toEqual(asal.penanda.map((p) => p.t * 2));
    expect(dokumen.lajur.find((l) => l.subtitle)?.gaya_caption).toBe('stiker');
    expect(Object.keys(dokumen.bahan)).toEqual([]);
  });

  it('proyek berisi: kerangka sesudah isi yang ada', () => {
    const tpl = ambilTemplat(proyekJadi());
    const d = kosong();
    d.lajur[0].item.push({ id: 'v1', jenis: 'video', mulai: 0, durasi: 300 });
    d.durasi = 300;
    const ops = operasiTemplatSaya(d, tpl);
    expect(Math.min(...ops.filter((o) => 'mulai' in o).map((o) => o.mulai))).toBe(300);
  });
});
