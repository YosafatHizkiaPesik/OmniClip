import { describe, expect, it } from 'vitest';
import { gabung, hitungOrisinalitas } from './orisinalitas.js';

const F = 30;
function dok(item) {
  const lajur = [
    { id: 'V', jenis: 'video', item: [] },
    { id: 'M', jenis: 'motion', item: [] },
    { id: 'T', jenis: 'teks', item: [] },
    { id: 'S', jenis: 'teks', subtitle: true, item: [] },
    { id: 'A', jenis: 'audio', item: [] },
  ];
  const ke = { video: 'V', motion: 'M', teks: 'T', sub: 'S', audio: 'A' };
  for (const [l, it] of item) lajur.find((x) => x.id === ke[l]).item.push(it);
  const durasi = Math.max(...item.map(([, i]) => i.mulai + i.durasi));
  return { kanvas: { fps: F }, durasi, bahan: {}, lajur };
}
const v = (mulai, detik, bahan = 'bLain') => ['video', { id: `v${mulai}`, jenis: 'video', bahan, mulai: mulai * F, durasi: detik * F }];
const asal = new Map([['bLain', 'klip_jadi'], ['bSendiri', 'impor'], ['bTts', 'tts'], ['bRekam', 'rekam']]);

describe('hitungOrisinalitas', () => {
  it('potongan polos video orang lain: kurang, wajib narasi, satu celah panjang', () => {
    const h = hitungOrisinalitas(dok([v(0, 40)]), asal);
    expect(h.tingkat).toBe('kurang');
    expect(h.cukup).toBe(false);
    expect(h.persen).toBe(0);
    expect(h.celah).toHaveLength(1);
    expect(h.saran.map((s) => s.kunci)).toEqual(['wajib_narasi', 'celah', 'dominan_lain']);
  });

  it('susunan Top N: narasi di kartu sebelum klip bukan celah, tapi klip panjang tetap celah', () => {
    const h = hitungOrisinalitas(dok([
      ['motion', { id: 'k1', jenis: 'motion', mulai: 0, durasi: 3 * F }],
      ['audio', { id: 'n1', jenis: 'audio', bahan: 'bTts', narasi: { teks: 'Nomor 2' }, mulai: 0, durasi: 3 * F }],
      v(3, 10),
      ['motion', { id: 'k2', jenis: 'motion', mulai: 13 * F, durasi: 3 * F }],
      ['audio', { id: 'n2', jenis: 'audio', bahan: 'bTts', narasi: { teks: 'Nomor 1' }, mulai: 13 * F, durasi: 3 * F }],
      v(16, 30),
    ]), asal);
    expect(h.cukup).toBe(true);
    // Klip 1 (10 dtk) tertutup pengantar 3 dtk; klip 2: 19..46 = 27 dtk tanpa apa pun.
    expect(h.celah.map((c) => c.detik)).toEqual([27]);
    expect(h.saran.map((s) => s.kunci)).toContain('suara_sendiri');
    expect(h.tingkat).toBe('sedang');
  });

  it('rekaman sendiri dan teks sepanjang video: baik; subtitle tidak dihitung', () => {
    const h = hitungOrisinalitas(dok([
      v(0, 20),
      ['audio', { id: 'r', jenis: 'audio', bahan: 'bRekam', mulai: 0, durasi: 20 * F }],
      ['sub', { id: 's', jenis: 'teks', mulai: 0, durasi: 20 * F }],
    ]), asal);
    expect(h.tingkat).toBe('baik');
    expect(h.persen).toBe(100);
    expect(h.detik.tambahan).toBe(0);
    expect(h.saran).toEqual([]);
  });

  it('narasi yang sudah direkam (teleprompter) dihitung suara sendiri walau bahannya belum dikenal', () => {
    const h = hitungOrisinalitas(dok([
      v(0, 10),
      ['audio', { id: 'n', jenis: 'audio', bahan: 'bBaru', narasi: { teks: 'x', direkam: true }, mulai: 0, durasi: 3 * F }],
    ]), asal);
    expect(h.detik.sendiri).toBe(3);
    expect(h.saran.map((s) => s.kunci)).not.toContain('suara_sendiri');
  });

  it('bahan milik sendiri saja selalu cukup', () => {
    const h = hitungOrisinalitas(dok([v(0, 60, 'bSendiri')]), asal);
    expect([h.cukup, h.adaLain, h.celah.length, h.tingkat]).toEqual([true, false, 0, 'baik']);
  });
});

describe('gabung', () => {
  it('rentang bertumpuk disatukan', () => {
    expect(gabung([[5, 9], [0, 3], [2, 6]])).toEqual([[0, 9]]);
  });
});
