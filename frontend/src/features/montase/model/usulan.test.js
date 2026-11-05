import { describe, expect, it } from 'vitest';
import { tambahBahan } from './dokumen.js';
import { kelompokOperasi, terapkanOperasi } from './usulan.js';

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
const info = (durasi) => ({ jenis: 'video', nama: 'klip', durasi, lebar: 1080, tinggi: 1920, fps: 30, ada_suara: true });

const OPS = [
  { id: 'u1', jenis: 'animasi', kelompok: '#2', label: 'Kartu #2', alasan: 'kuat', komponen: 'ko_hitung_mundur',
    mulai: 0, durasi: 60, props: { angka: 2, judul: 'A', warna: '#FF3355' } },
  { id: 'u2', jenis: 'audio', kelompok: '#2', label: 'Narasi', alasan: 'Nomor 2', bahan: 'bn', mulai: 0,
    bahan_info: { jenis: 'audio', nama: 'n', durasi: 1.5, ada_suara: true },
    narasi: { teks: 'Nomor 2', suara: 'edge:ardi', kecepatan: 1 } },
  { id: 'u3', jenis: 'klip', kelompok: '#2', label: 'klip', alasan: 'tawa', bahan: 'b1', bahan_info: info(30),
    mulai: 60, potong_awal: 150, durasi: 300 },
  { id: 'u4', jenis: 'animasi', kelompok: '#1', label: 'Kartu #1', alasan: 'x', komponen: 'ko_hitung_mundur',
    mulai: 360, durasi: 60, props: { angka: 1, judul: 'B', warna: '#FFB800' } },
  { id: 'u5', jenis: 'klip', kelompok: '#1', label: 'klip', alasan: 'y', bahan: 'b2', bahan_info: info(10),
    mulai: 420, potong_awal: 0, durasi: 300 },
];

describe('terapkanOperasi', () => {
  it('menjalankan semua operasi dengan fungsi model dan menandai item usulan', () => {
    const { dokumen, itemUsulan, dilewati } = terapkanOperasi(kosong(), OPS);
    expect(dilewati).toEqual([]);
    expect(itemUsulan.size).toBe(5);
    const video = dokumen.lajur[0].item;
    expect(video.map((i) => [i.mulai, i.potong_awal, i.durasi, i.asal])).toEqual([
      [60, 150, 300, 'ai'], [420, 0, 300, 'ai']]);
    expect(dokumen.lajur[1].item[0].props).toEqual({ angka: 2, judul: 'A', warna: '#FF3355' });
    expect(dokumen.lajur[3].item[0].narasi.suara).toBe('edge:ardi');
    expect(dokumen.bahan.b1.durasi).toBe(30);
    expect(dokumen.durasi).toBe(720);
  });

  it('hanya yang dipilih, dan dokumen asal tidak berubah', () => {
    const awal = kosong();
    const { dokumen } = terapkanOperasi(awal, OPS, new Set(['u4', 'u5']));
    expect(dokumen.lajur[0].item).toHaveLength(1);
    expect(dokumen.lajur[1].item[0].props.angka).toBe(1);
    expect(awal.lajur[0].item).toHaveLength(0);
  });

  it('potongan dijalankan dari belakang dan beriak', () => {
    let d = tambahBahan(kosong(), { id: 'b1', jenis: 'video', durasi: 10, nama: 'v' }).dokumen;
    const id = d.lajur[0].item[0].id;
    d = tambahBahan(d, { id: 'b2', jenis: 'video', durasi: 2, nama: 'w' }).dokumen;
    const potong = [
      { id: 'p1', jenis: 'potong', item: id, dari: 30, sampai: 60 },
      { id: 'p2', jenis: 'potong', item: id, dari: 150, sampai: 180 },
    ];
    const { dokumen } = terapkanOperasi(d, potong);
    const it = dokumen.lajur[0].item;
    expect(it.map((i) => [i.mulai, i.durasi, i.potong_awal])).toEqual([
      [0, 30, 0], [30, 90, 60], [120, 120, 180], [240, 60, 0]]);
  });

  it('potongan ikut menggeser item lajur lain yang sesudahnya', () => {
    let d = tambahBahan(kosong(), { id: 'b1', jenis: 'video', durasi: 10, nama: 'v' }).dokumen;
    const id = d.lajur[0].item[0].id;
    d = terapkanOperasi(d, [
      { id: 'k1', jenis: 'animasi', komponen: 'ko_hitung_mundur', mulai: 240, durasi: 30, props: {} },
      { id: 'k0', jenis: 'animasi', komponen: 'ko_hitung_mundur', mulai: 0, durasi: 20, props: {} },
    ]).dokumen;
    const { dokumen } = terapkanOperasi(d, [{ id: 'p', jenis: 'potong', item: id, dari: 60, sampai: 120 }]);
    const anim = dokumen.lajur[1].item.map((i) => i.mulai).sort((a, b) => a - b);
    expect(anim).toEqual([0, 180]);
  });

  it('operasi yang itemnya sudah tidak ada dilewati', () => {
    const { dilewati } = terapkanOperasi(kosong(), [{ id: 'p', jenis: 'potong', item: 'hilang', dari: 0, sampai: 9 }]);
    expect(dilewati).toEqual(['p']);
  });
});

describe('kelompokOperasi', () => {
  it('per kelompok, berurutan', () => {
    expect(kelompokOperasi(OPS).map((k) => [k.kelompok, k.ops.length])).toEqual([['#2', 3], ['#1', 2]]);
  });
});
