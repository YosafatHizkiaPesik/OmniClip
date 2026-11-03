import { describe, expect, it } from 'vitest';
import {
  bersihkanUbah, cariItem, hapusItem, tambahBahan, tambahTeks, ubahItem,
} from './dokumen.js';
import {
  bekukan, belah, bisaHapusLajur, gandakan, hapusBanyak, hapusBeriak, hapusLajur, pangkasKanan,
  pangkasKiri, pasangSubtitle, pindahItem, rapatkan, salin, semuaItem, sisipkan, tambahLajur, tambahPenanda, tempel,
  tempelKe, titikMagnet, titikSisip, ubahKecepatan, ubahLajur, ubahTransform,
} from './suntingan.js';
import { batal, buatRiwayat, catat, ulang, BATAS_LANGKAH } from './riwayat.js';

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
const video = (id, durasi = 4) => ({ id, jenis: 'video', nama: id, durasi, ada_suara: true });
function dua() {
  let d = tambahBahan(kosong(), video('bh_a')).dokumen;   // i1: 0-120
  d = tambahBahan(d, video('bh_b')).dokumen;               // i2: 120-240
  return d;
}
const item = (d, id) => cariItem(d, id).item;

describe('belah', () => {
  it('membelah di garis putar dan menggeser potong_awal bagian kanan', () => {
    const { dokumen, itemBaru } = belah(dua(), 'i1', 50);
    expect(item(dokumen, 'i1')).toMatchObject({ mulai: 0, durasi: 50 });
    expect(item(dokumen, itemBaru)).toMatchObject({ mulai: 50, durasi: 70, potong_awal: 50 });
  });
  it('tidak membelah di tepi atau di lajur terkunci', () => {
    expect(belah(dua(), 'i1', 0).itemBaru).toBeNull();
    const d = ubahLajur(dua(), 'L1', { kunci: true });
    expect(belah(d, 'i1', 50).dokumen).toBe(d);
  });
  it('memperhitungkan kecepatan', () => {
    let d = dua();
    d = { ...d, lajur: d.lajur.map((l) => ({ ...l, item: l.item.map((i) => ({ ...i, kecepatan: 2 })) })) };
    const { dokumen, itemBaru } = belah(d, 'i1', 30);
    expect(item(dokumen, itemBaru).potong_awal).toBe(60);
  });
});

describe('pangkas', () => {
  it('kiri menggeser awal dan potong_awal, tidak melewati awal bahan', () => {
    let d = pangkasKiri(dua(), 'i1', 30);
    expect(item(d, 'i1')).toMatchObject({ mulai: 30, durasi: 90, potong_awal: 30 });
    d = pangkasKiri(d, 'i1', -100);
    expect(item(d, 'i1')).toMatchObject({ mulai: 0, durasi: 120, potong_awal: 0 });
  });
  it('kanan tidak melewati panjang bahan, minimal satu bingkai', () => {
    expect(item(pangkasKanan(dua(), 'i1', 999), 'i1').durasi).toBe(120);
    expect(item(pangkasKanan(dua(), 'i1', 60), 'i1').durasi).toBe(60);
    expect(item(pangkasKanan(dua(), 'i1', -5), 'i1').durasi).toBe(1);
  });
  it('teks boleh dipanjangkan bebas', () => {
    const { dokumen, itemId } = tambahTeks(kosong());
    expect(item(pangkasKanan(dokumen, itemId, 900), itemId).durasi).toBe(900);
  });
});

describe('pindah, hapus beriak, salin, gandakan', () => {
  it('pindahItem tidak kurang dari nol dan pindah ke lajur sejenis saja', () => {
    let d = pindahItem(dua(), ['i2'], -500);
    expect(item(d, 'i2').mulai).toBe(0);
    d = tambahLajur(d, 'video').dokumen;
    const lajurBaru = d.lajur.find((l) => l.nama === 'Video 2').id;
    d = pindahItem(d, ['i2'], 10, lajurBaru);
    expect(cariItem(d, 'i2').lajur.id).toBe(lajurBaru);
    expect(pindahItem(d, ['i2'], 0, 'L4')).toBe(d);
  });
  it('hapusBeriak merapatkan sesudahnya', () => {
    const d = hapusBeriak(dua(), 'i1');
    expect(item(d, 'i2').mulai).toBe(0);
    expect(Object.keys(d.bahan)).toEqual(['bh_b']);
  });
  it('salin lalu tempel di garis putar menjaga jarak, id baru', () => {
    const papan = salin(dua(), ['i1', 'i2']);
    const { dokumen, itemBaru } = tempel(dua(), papan, 300);
    expect(itemBaru).toHaveLength(2);
    expect(itemBaru.map((id) => item(dokumen, id).mulai)).toEqual([300, 420]);
  });
  it('gandakan menaruh salinan sesudah item terakhir', () => {
    const { dokumen, itemBaru } = gandakan(dua(), ['i2']);
    expect(item(dokumen, itemBaru[0]).mulai).toBe(240);
    expect(dokumen.durasi).toBe(360);
  });
  it('hapusBanyak membuang bahan yatim', () => {
    expect(Object.keys(hapusBanyak(dua(), ['i1', 'i2']).bahan)).toEqual([]);
  });
});

describe('sisip (seret klip ke atas klip lain)', () => {
  function lima() {
    let d = kosong();
    for (const n of [1, 2, 3, 4, 5]) d = tambahBahan(d, video(`bh_${n}`, 6)).dokumen;
    return d;   // i1..i5, masing-masing 180 bingkai, rapat
  }
  const urutan = (d) => d.lajur[0].item.slice().sort((a, b) => a.mulai - b.mulai)
    .map((i) => `${i.id}@${i.mulai}`).join(' ');
  it('klip terakhir ke awal: jadi pertama, sisanya bergeser', () => {
    const d = lima();
    const di = titikSisip(d, 'i5', 'L1', 10, 40);
    expect(di).toBe(0);
    expect(urutan(sisipkan(d, 'i5', 'L1', di))).toBe('i5@0 i1@180 i2@360 i3@540 i4@720');
  });
  it('klip pertama ke paruh kanan klip kedua: tukar tempat', () => {
    const d = lima();
    const di = titikSisip(d, 'i1', 'L1', 200, 300);
    expect(di).toBe(360);
    expect(urutan(sisipkan(d, 'i1', 'L1', di))).toBe('i2@0 i1@180 i3@360 i4@540 i5@720');
  });
  it('tidak menimpa apa pun: bukan sisipan', () => {
    expect(titikSisip(lima(), 'i5', 'L1', 900, 950)).toBeNull();
  });
});

describe('rapatkan', () => {
  it('celah sesudah kecepatan 2x hilang, urutan tetap', () => {
    let d = ubahKecepatan(dua(), 'i1', 2);       // i1: 0-60, i2: 120-240
    d = rapatkan(d, 'L1');
    expect(item(d, 'i2').mulai).toBe(60);
    expect(d.durasi).toBe(180);
    expect(rapatkan(d, 'L1')).toBe(d);
  });
});

describe('subtitle', () => {
  const potongan = [
    { mulai: 0, durasi: 30, teks: 'halo semua', kata: [{ w: 'halo', t: 0, d: 10 }, { w: 'semua', t: 12, d: 10 }] },
    { mulai: 30, durasi: 20, teks: 'apa kabar', kata: [] },
  ];
  it('lajur subtitle baru di atas lajur teks, item bertanda AI', () => {
    const { dokumen, lajurId } = pasangSubtitle(dua(), potongan, { alasan: 'dari ucapan' });
    const l = dokumen.lajur.find((x) => x.id === lajurId);
    expect(l).toMatchObject({ jenis: 'teks', nama: 'Subtitle', subtitle: true });
    expect(dokumen.lajur.map((x) => x.id).indexOf(lajurId)).toBe(dokumen.lajur.findIndex((x) => x.id === 'L3') + 1);
    expect(l.item[0]).toMatchObject({ teks: 'halo semua', asal: 'ai', alasan: 'dari ucapan' });
  });
  it('dijalankan ulang mengganti isi, tidak menumpuk', () => {
    const a = pasangSubtitle(dua(), potongan);
    const b = pasangSubtitle(a.dokumen, potongan.slice(0, 1));
    expect(b.lajurId).toBe(a.lajurId);
    expect(b.dokumen.lajur.find((x) => x.id === b.lajurId).item).toHaveLength(1);
    expect(b.dokumen.lajur).toHaveLength(a.dokumen.lajur.length);
  });
});

describe('bekukan', () => {
  it('menahan satu bingkai dan menggeser sisanya', () => {
    const { dokumen, itemBaru } = bekukan(dua(), 'i1', 60, 30);
    const beku = item(dokumen, itemBaru);
    expect(beku).toMatchObject({ mulai: 60, durasi: 30, beku: true, volume: 0 });
    expect(item(dokumen, 'i2').mulai).toBe(150);
    expect(dokumen.durasi).toBe(270);
  });
});

describe('lajur', () => {
  it('lajur video baru tepat di atas video terakhir', () => {
    const { dokumen } = tambahLajur(kosong(), 'video');
    expect(dokumen.lajur.map((l) => l.nama)).toEqual(['Video 1', 'Video 2', 'Animasi', 'Teks', 'Suara']);
  });
  it('hanya lajur kosong yang bukan satu-satunya yang bisa dihapus', () => {
    let d = dua();
    expect(bisaHapusLajur(d, 'L1')).toBe(false);
    const { dokumen, lajurId } = tambahLajur(d, 'audio');
    d = hapusLajur(dokumen, lajurId);
    expect(d.lajur).toHaveLength(4);
    expect(hapusLajur(d, 'L4')).toBe(d);
  });
});

describe('magnet dan penanda', () => {
  it('menempel ke ujung item, garis putar, dan penanda dalam ambang', () => {
    const d = tambahPenanda(dua(), 200, '#4');
    const titik = titikMagnet(d, { garis: 77, kecuali: ['i2'] });
    expect(titik).toEqual([0, 77, 120, 200]);
    expect(tempelKe(195, titik, 8)).toBe(200);
    expect(tempelKe(160, titik, 8)).toBe(160);
  });
});

describe('kecepatan dan transformasi', () => {
  it('2x memendekkan item setengahnya, 0,5x memanjangkan sampai sisa bahan', () => {
    let d = ubahKecepatan(dua(), 'i1', 2);
    expect(item(d, 'i1')).toMatchObject({ kecepatan: 2, durasi: 60 });
    d = ubahKecepatan(d, 'i1', 0.5);
    expect(item(d, 'i1')).toMatchObject({ kecepatan: 0.5, durasi: 240 });
    expect(item(d, 'i2').mulai).toBe(120);
  });
  it('ubahTransform menggabung sebagian dan menjepit', () => {
    let d = ubahTransform(dua(), 'i1', { x: 10, skala: 99 });
    d = ubahTransform(d, 'i1', { potong: { kiri: 60 } });
    d = ubahTransform(d, 'i1', { potong: { kanan: 60 } });
    expect(item(d, 'i1').ubah).toEqual({ x: 10, skala: 20, potong: { kiri: 60, kanan: 35, atas: 0, bawah: 0 } });
  });
  it('bersihkanUbah membuang kolom asing dan potongan nol', () => {
    expect(bersihkanUbah({ x: 'a', y: 3, aneh: 1, potong: { kiri: 0 } })).toEqual({ y: 3 });
  });
  it('ubahItem dan hapusItem menolak lajur terkunci, fade dibulatkan', () => {
    const d = ubahLajur(dua(), 'L1', { kunci: true });
    expect(ubahItem(d, 'i1', { volume: 0 })).toBe(d);
    expect(hapusItem(d, 'i1')).toBe(d);
    expect(semuaItem(d)).toEqual([]);
    expect(item(ubahItem(dua(), 'i1', { fade_masuk: 7.6, isi: 'aneh' }), 'i1'))
      .toMatchObject({ fade_masuk: 8, isi: 'contain' });
  });
  it('tambahBahan bisa di bingkai dan lajur tertentu', () => {
    let d = tambahLajur(dua(), 'video').dokumen;
    const lajurId = d.lajur[1].id;
    const hasil = tambahBahan(d, video('bh_c'), { mulai: 33, lajurId });
    d = hasil.dokumen;
    expect(cariItem(d, hasil.itemId).lajur.id).toBe(lajurId);
    expect(item(d, hasil.itemId).mulai).toBe(33);
  });
});

describe('riwayat', () => {
  it('batal dan ulang', () => {
    let r = buatRiwayat('a');
    r = catat(r, 'b');
    r = catat(r, 'c');
    r = batal(r);
    expect(r.kini).toBe('b');
    r = ulang(r);
    expect(r.kini).toBe('c');
    r = batal(batal(r));
    expect(batal(r)).toBe(r);
  });
  it('ketikan beruntun digabung jadi satu langkah', () => {
    let r = buatRiwayat('');
    r = catat(r, 'h', { gabung: 'teks:i1', waktu: 0 });
    r = catat(r, 'ha', { gabung: 'teks:i1', waktu: 100 });
    r = catat(r, 'hai', { gabung: 'teks:i1', waktu: 200 });
    expect(batal(r).kini).toBe('');
  });
  it('satu seretan satu langkah walau berhenti lama', () => {
    let r = buatRiwayat(0);
    r = catat(r, 1, { gabung: 'seret:1', waktu: 0, jendela: Infinity });
    r = catat(r, 2, { gabung: 'seret:1', waktu: 60000, jendela: Infinity });
    expect(batal(r).kini).toBe(0);
  });
  it('seretan yang kembali ke awal tidak meninggalkan langkah', () => {
    const awal = { a: 1 };
    let r = catat(buatRiwayat('x'), awal);
    r = catat(r, { a: 2 }, { gabung: 'seret:2', waktu: 0, jendela: Infinity });
    r = catat(r, awal, { gabung: 'seret:2', waktu: 10, jendela: Infinity });
    expect(r.kini).toBe(awal);
    expect(r.lalu).toEqual(['x']);
  });
  it('dibatasi seratus langkah', () => {
    let r = buatRiwayat(0);
    for (let i = 1; i <= 150; i += 1) r = catat(r, i);
    expect(r.lalu).toHaveLength(BATAS_LANGKAH);
  });
});
