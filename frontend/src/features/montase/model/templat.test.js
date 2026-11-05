import { describe, expect, it } from 'vitest';
import { BAWAAN } from '../komposisi/motion/index.js';
import { TEMPLAT, operasiTemplat } from './templat.js';
import { terapkanOperasi } from './usulan.js';
import { PRESET_CAPTION } from './presetCaption.js';

function kosong() {
  return {
    versi: 1, id: 'mt', nama: 'x', durasi: 1, bahan: {}, penanda: [], ekspor: {},
    kanvas: { lebar: 1080, tinggi: 1920, fps: 30, latar: '#000' },
    lajur: [
      { id: 'V', jenis: 'video', nama: 'Video 1', item: [] }, { id: 'M', jenis: 'motion', nama: 'Animasi', item: [] },
      { id: 'T', jenis: 'teks', nama: 'Teks', item: [] }, { id: 'A', jenis: 'audio', nama: 'Suara', item: [] },
    ],
  };
}

describe('templat video', () => {
  for (const tpl of TEMPLAT) {
    for (const v of [0, 1, 2]) {
      it(`${tpl.id} variasi ${v}: props animasi sah, caption dikenal, diterapkan tanpa dilewati`, () => {
        const ops = operasiTemplat(kosong(), tpl.id, v);
        expect(ops.length).toBeGreaterThan(2);
        for (const o of ops.filter((x) => x.jenis === 'animasi')) {
          const modul = BAWAAN[o.komponen];
          expect(modul, o.komponen).toBeTruthy();
          const hasil = modul.skema.safeParse(o.props);
          expect(hasil.success, `${o.komponen}: ${JSON.stringify(hasil.error?.issues ?? [])}`).toBe(true);
        }
        const caption = ops.find((o) => o.jenis === 'lajur_caption').preset;
        expect(PRESET_CAPTION.some((p) => p.id === caption)).toBe(true);
        const { dokumen, dilewati } = terapkanOperasi(kosong(), ops);
        expect(dilewati).toEqual([]);
        expect(dokumen.penanda.length).toBeGreaterThan(0);
        expect(dokumen.lajur.find((l) => l.subtitle)?.gaya_caption).toBe(caption);
      });
    }
  }

  it('variasi berbeda menghasilkan warna/caption berbeda', () => {
    const a = operasiTemplat(kosong(), 'top_n', 0);
    const b = operasiTemplat(kosong(), 'top_n', 1);
    expect(a.find((o) => o.jenis === 'lajur_caption').preset).not.toBe(b.find((o) => o.jenis === 'lajur_caption').preset);
  });

  it('proyek berisi: kerangka sesudah isi yang ada', () => {
    const d = kosong();
    d.lajur[0].item.push({ id: 'v1', jenis: 'video', mulai: 0, durasi: 300 });
    d.durasi = 300;
    const ops = operasiTemplat(d, 'reaksi', 0);
    expect(Math.min(...ops.filter((o) => 'mulai' in o).map((o) => o.mulai))).toBe(300);
  });
});
