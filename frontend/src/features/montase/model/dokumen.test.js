import { describe, expect, it } from 'vitest';
import {
  cariItem, durasiIsi, hapusItem, pindahUrutan, tambahBahan, tambahMotion, tambahTeks, ubahItem,
  ubahProyek,
} from './dokumen.js';

function kosong() {
  return {
    versi: 1, id: 'mt_a', nama: 'Uji', durasi: 1, bahan: {}, penanda: [], ekspor: {},
    kanvas: { lebar: 1080, tinggi: 1920, fps: 30, latar: '#000000' },
    lajur: [
      { id: 'L1', jenis: 'video', nama: 'Video 1', item: [] },
      { id: 'L2', jenis: 'motion', nama: 'Animasi', item: [] },
      { id: 'L3', jenis: 'teks', nama: 'Teks', item: [] },
      { id: 'L4', jenis: 'audio', nama: 'Suara', item: [] },
    ],
  };
}
const video = (id, durasi) => ({ id, jenis: 'video', nama: id, durasi, lebar: 1080, tinggi: 1920, ada_suara: true });

describe('tambahBahan', () => {
  it('menaruh tiga video berurutan di lajur gambar dan mencatat bahannya', () => {
    let d = kosong();
    for (const [id, det] of [['bh_a', 2], ['bh_b', 1.5], ['bh_c', 3]]) d = tambahBahan(d, video(id, det)).dokumen;
    const item = d.lajur[0].item;
    expect(item.map((i) => [i.mulai, i.durasi])).toEqual([[0, 60], [60, 45], [105, 90]]);
    expect(Object.keys(d.bahan)).toEqual(['bh_a', 'bh_b', 'bh_c']);
    expect(d.durasi).toBe(195);
  });
  it('audio ke lajur suara, gambar lima detik', () => {
    let d = tambahBahan(kosong(), { id: 'bh_m', jenis: 'audio', durasi: 10 }).dokumen;
    d = tambahBahan(d, { id: 'bh_g', jenis: 'gambar' }).dokumen;
    expect(d.lajur[3].item[0].durasi).toBe(300);
    expect(d.lajur[0].item[0].durasi).toBe(150);
    expect(d.lajur[3].item[0].isi).toBeUndefined();
  });
  it('tidak mengubah dokumen asal', () => {
    const asal = kosong();
    tambahBahan(asal, video('bh_a', 2));
    expect(asal.lajur[0].item).toEqual([]);
    expect(asal.bahan).toEqual({});
  });
});

describe('teks dan animasi', () => {
  it('teks di garis putar, tiga detik', () => {
    const { dokumen, itemId } = tambahTeks(kosong(), { mulai: 45.4 });
    expect(cariItem(dokumen, itemId).item).toMatchObject({ mulai: 45, durasi: 90, jenis: 'teks' });
  });
  it('animasi memakai durasi dan props contoh modulnya', () => {
    const modul = { durasiBawaan: 60, contohProps: { angka: 5 } };
    const { dokumen, itemId } = tambahMotion(kosong(), { komponen: 'ko_hitung_mundur', modul, mulai: 10 });
    expect(cariItem(dokumen, itemId).item).toMatchObject({ durasi: 60, props: { angka: 5 }, versi: 1 });
  });
});

describe('ubah, hapus, pindah', () => {
  const tiga = () => ['bh_a', 'bh_b', 'bh_c'].reduce((d, id) => tambahBahan(d, video(id, 1)).dokumen, kosong());

  it('ubahItem menjepit angka ke rentang skema server', () => {
    const d = ubahItem(tiga(), 'i1', { kecepatan: 9, volume: -1, durasi: 0.4, mulai: 12.6 });
    expect(cariItem(d, 'i1').item).toMatchObject({ kecepatan: 4, volume: 0, durasi: 1, mulai: 13 });
  });
  it('hapusItem membuang bahan yang tidak dipakai lagi', () => {
    const d = hapusItem(tiga(), 'i2');
    expect(d.lajur[0].item.map((i) => i.id)).toEqual(['i1', 'i3']);
    expect(Object.keys(d.bahan)).toEqual(['bh_a', 'bh_c']);
  });
  it('pindahUrutan menukar dan menyusun ulang tanpa celah', () => {
    let d = ubahItem(tiga(), 'i1', { durasi: 10 });
    d = { ...d, lajur: d.lajur.map((l) => (l.id === 'L1'
      ? { ...l, item: l.item.map((i, n) => ({ ...i, mulai: [0, 10, 40][n] })) } : l)) };
    d = pindahUrutan(d, 'i3', -1);
    const urut = [...d.lajur[0].item].sort((a, b) => a.mulai - b.mulai);
    expect(urut.map((i) => [i.id, i.mulai])).toEqual([['i1', 0], ['i3', 10], ['i2', 40]]);
    expect(pindahUrutan(d, 'i1', -1)).toBe(d);
  });
  it('durasi dokumen mengikuti ujung item terakhir', () => {
    expect(durasiIsi(kosong())).toBe(1);
    expect(ubahProyek(tiga(), { nama: 'Baru' })).toMatchObject({ nama: 'Baru', durasi: 90 });
  });
});
