/**
 * Operasi dokumen proyek Montase sebagai FUNGSI MURNI (JOB-4 M2.1, dimulai di
 * Tahap 1): masuk dokumen, keluar dokumen baru, tidak ada yang diubah di
 * tempat. Fungsi yang sama dipakai tangan manusia di editor dan, di Tahap 5,
 * daftar operasi buatan asisten AI.
 *
 * Semua waktu dalam BINGKAI (bilangan bulat), sama dengan skema server
 * (backend/app/montase/skema.py). `durasi` dokumen dihitung ulang dari ujung
 * item terakhir, sama dengan aturan server.
 */

export const JENIS_LAJUR_ITEM = {
  video: 'video', gambar: 'video', audio: 'audio', teks: 'teks', motion: 'motion',
};
export const DETIK_GAMBAR = 5;
export const DETIK_TEKS = 3;
/**
 * Gaya teks baru: huruf putih Montserrat bergaris hitam, terbaca di atas
 * gambar apa pun tanpa pelat. Tema lain dipilih di panel Properti (M3.1).
 */
/** Gaya subtitle otomatis: huruf besar bergaris di bawah, kata yang diucapkan disorot kuning. */
export const GAYA_SUBTITLE = {
  font: 'Montserrat', ukuran: 76, warna: '#ffffff', kapital: true, letak: 'bawah',
  perataan: 'tengah', latar: 'tanpa', warna_latar: '#000000', alfa_latar: 1,
  garis: 7, warna_garis: '#000000', bayang: 0, kabur: 0, gerak: 'muncul', warna_sorot: '#FFE500',
};
export const GAYA_TEKS_BAWAAN = {
  font: 'Montserrat', ukuran: 96, warna: '#ffffff', kapital: false, letak: 'tengah',
  perataan: 'tengah', latar: 'tanpa', warna_latar: '#000000', alfa_latar: 1,
  garis: 5, warna_garis: '#000000', bayang: 0, kabur: 0, gerak: 'pop',
};

function salin(dokumen) {
  return {
    ...dokumen,
    bahan: { ...dokumen.bahan },
    lajur: dokumen.lajur.map((l) => ({ ...l, item: l.item.map((i) => ({ ...i })) })),
  };
}

/** Ujung item terakhir di semua lajur, minimal satu bingkai. */
export function durasiIsi(dokumen) {
  let ujung = 1;
  for (const l of dokumen.lajur) {
    for (const i of l.item) ujung = Math.max(ujung, i.mulai + i.durasi);
  }
  return ujung;
}

function rapikan(dokumen) {
  return { ...dokumen, durasi: durasiIsi(dokumen) };
}

/** Id item baru yang belum dipakai di dokumen ini. */
export function idBaru(dokumen, awalan = 'i') {
  const dipakai = new Set(dokumen.lajur.flatMap((l) => l.item.map((i) => i.id)));
  let n = dipakai.size + 1;
  while (dipakai.has(`${awalan}${n}`)) n += 1;
  return `${awalan}${n}`;
}

export function cariItem(dokumen, itemId) {
  for (const lajur of dokumen.lajur) {
    const item = lajur.item.find((i) => i.id === itemId);
    if (item) return { lajur, item };
  }
  return null;
}

export function lajurUntuk(dokumen, jenisItem) {
  const jenisLajur = JENIS_LAJUR_ITEM[jenisItem];
  return dokumen.lajur.find((l) => l.jenis === jenisLajur) ?? null;
}

export function ujungLajur(lajur) {
  return lajur.item.reduce((m, i) => Math.max(m, i.mulai + i.durasi), 0);
}

/**
 * Lajur tujuan: `lajurId` bila diberikan, cocok jenisnya, dan tidak terkunci;
 * selain itu lajur pertama yang cocok dan tidak terkunci, lalu lajur pertama
 * yang cocok (lajur terkunci tetap lebih baik daripada galat).
 */
function lajurTujuan(dokumen, jenisItem, lajurId) {
  const jenisLajur = JENIS_LAJUR_ITEM[jenisItem];
  const cocok = dokumen.lajur.filter((l) => l.jenis === jenisLajur);
  return cocok.find((l) => l.id === lajurId && !l.kunci)
    ?? cocok.find((l) => !l.kunci) ?? cocok[0] ?? null;
}

function sisipkan(dokumen, jenisItem, item, lajurId = null) {
  const target = lajurTujuan(dokumen, jenisItem, lajurId);
  if (!target) throw new Error(`Tidak ada lajur untuk item ${jenisItem}`);
  const baru = salin(dokumen);
  baru.lajur = baru.lajur.map((l) => (l.id === target.id ? { ...l, item: [...l.item, item] } : l));
  return rapikan(baru);
}

/**
 * Menaruh bahan di ujung lajurnya (video/gambar ke lajur gambar, audio ke lajur
 * suara), berurutan seperti CapCut. Metadata bahannya ikut dicatat di
 * `dokumen.bahan` supaya dokumen bisa dibaca tanpa basis data.
 */
export function tambahBahan(dokumen, bahan, { mulai = null, lajurId = null } = {}) {
  const fps = dokumen.kanvas.fps;
  const lajur = lajurTujuan(dokumen, bahan.jenis, lajurId);
  if (!lajur) throw new Error(`Tidak ada lajur untuk bahan ${bahan.jenis}`);
  const detik = bahan.jenis === 'gambar' ? DETIK_GAMBAR : Math.max(1 / fps, bahan.durasi || 1);
  const id = idBaru(dokumen);
  const item = {
    id,
    jenis: bahan.jenis,
    bahan: bahan.id,
    mulai: mulai === null ? ujungLajur(lajur) : Math.max(0, Math.round(mulai)),
    durasi: Math.max(1, Math.round(detik * fps)),
    potong_awal: 0,
    kecepatan: 1,
    volume: 1,
    asal: 'tangan',
  };
  if (bahan.jenis !== 'audio') item.isi = 'contain';
  const hasil = sisipkan(dokumen, bahan.jenis, item, lajur.id);
  hasil.bahan = {
    ...hasil.bahan,
    [bahan.id]: {
      jenis: bahan.jenis,
      nama: bahan.nama ?? '',
      durasi: bahan.durasi ?? null,
      lebar: bahan.lebar ?? null,
      tinggi: bahan.tinggi ?? null,
      fps: bahan.fps ?? null,
      ada_suara: Boolean(bahan.ada_suara),
    },
  };
  return { dokumen: hasil, itemId: id };
}

export function tambahTeks(dokumen, { mulai = 0, teks = 'Teks', lajurId = null } = {}) {
  const id = idBaru(dokumen);
  const item = {
    id, jenis: 'teks', mulai: Math.max(0, Math.round(mulai)),
    durasi: Math.round(DETIK_TEKS * dokumen.kanvas.fps), teks,
    gaya: { ...GAYA_TEKS_BAWAAN }, asal: 'tangan',
  };
  return { dokumen: sisipkan(dokumen, 'teks', item, lajurId), itemId: id };
}

export function tambahMotion(dokumen, { komponen, modul, mulai = 0, lajurId = null }) {
  const id = idBaru(dokumen);
  const item = {
    id, jenis: 'motion', komponen, versi: 1, mulai: Math.max(0, Math.round(mulai)),
    durasi: modul?.durasiBawaan ?? Math.round(2 * dokumen.kanvas.fps),
    props: { ...modul?.contohProps }, asal: 'tangan',
  };
  return { dokumen: sisipkan(dokumen, 'motion', item, lajurId), itemId: id };
}

/** Bahan yang tidak dipakai item mana pun dibuang dari `dokumen.bahan`. */
function buangBahanYatim(dokumen) {
  const dipakai = new Set(dokumen.lajur.flatMap((l) => l.item.map((i) => i.bahan).filter(Boolean)));
  const bahan = Object.fromEntries(Object.entries(dokumen.bahan).filter(([id]) => dipakai.has(id)));
  return { ...dokumen, bahan };
}

export function hapusItem(dokumen, itemId) {
  const hit = cariItem(dokumen, itemId);
  if (!hit || hit.lajur.kunci) return dokumen;
  const baru = salin(dokumen);
  baru.lajur = baru.lajur.map((l) => ({ ...l, item: l.item.filter((i) => i.id !== itemId) }));
  return rapikan(buangBahanYatim(baru));
}

// Rentang yang sama dengan skema server (backend/app/montase/skema.py).
const BATAS = {
  mulai: [0, Infinity], durasi: [1, Infinity], potong_awal: [0, Infinity],
  kecepatan: [0.25, 4], volume: [0, 2], fade_masuk: [0, Infinity], fade_keluar: [0, Infinity],
};
const BULAT = new Set(['mulai', 'durasi', 'potong_awal', 'fade_masuk', 'fade_keluar']);

export const BATAS_UBAH = {
  x: [-20000, 20000], y: [-20000, 20000], skala: [0.01, 20], putar: [-3600, 3600],
  opasitas: [0, 1],
};
/** Potongan (crop) dalam persen per sisi; dua sisi berhadapan menyisakan >= 5%. */
export const SISA_POTONG = 5;

function jepit(v, [bawah, atas]) {
  return Math.min(atas, Math.max(bawah, v));
}

/**
 * Transformasi item yang sudah dibersihkan: angka di luar rentang dijepit,
 * kolom tak dikenal dibuang, dan potongan yang menghabiskan gambar dikecilkan.
 */
export function bersihkanUbah(ubah) {
  const hasil = {};
  for (const [k, batas] of Object.entries(BATAS_UBAH)) {
    const v = Number(ubah?.[k]);
    if (ubah && k in ubah && Number.isFinite(v)) hasil[k] = jepit(v, batas);
  }
  const p = ubah?.potong;
  if (p && typeof p === 'object') {
    const sisi = {};
    for (const k of ['kiri', 'kanan', 'atas', 'bawah']) {
      const v = Number(p[k]);
      sisi[k] = Number.isFinite(v) ? jepit(v, [0, 100 - SISA_POTONG]) : 0;
    }
    for (const [a, b] of [['kiri', 'kanan'], ['atas', 'bawah']]) {
      const lebih = sisi[a] + sisi[b] - (100 - SISA_POTONG);
      if (lebih > 0) sisi[b] = Math.max(0, sisi[b] - lebih);
    }
    if (Object.values(sisi).some((v) => v > 0)) hasil.potong = sisi;
  }
  return hasil;
}

/** Mengubah kolom item; angka dijepit ke rentang yang sama dengan skema server. */
export function ubahItem(dokumen, itemId, perubahan) {
  const hit = cariItem(dokumen, itemId);
  if (!hit || hit.lajur.kunci) return dokumen;
  const bersih = { ...perubahan };
  for (const [k, [bawah, atas]] of Object.entries(BATAS)) {
    if (k in bersih) {
      let v = Number(bersih[k]);
      if (!Number.isFinite(v)) { delete bersih[k]; continue; }
      if (BULAT.has(k)) v = Math.round(v);
      bersih[k] = Math.min(atas, Math.max(bawah, v));
    }
  }
  if ('ubah' in bersih) bersih.ubah = bersihkanUbah(bersih.ubah);
  if ('isi' in bersih && !['contain', 'cover'].includes(bersih.isi)) delete bersih.isi;
  const baru = salin(dokumen);
  baru.lajur = baru.lajur.map((l) => ({
    ...l, item: l.item.map((i) => (i.id === itemId ? { ...i, ...bersih } : i)),
  }));
  return rapikan(baru);
}

/**
 * Menukar item dengan tetangganya di lajur yang sama (arah -1 / +1). Lajur
 * disusun ulang berurutan mulai dari awal item paling depan, jadi tidak ada
 * celah maupun tumpukan sesudahnya.
 */
export function pindahUrutan(dokumen, itemId, arah) {
  const hit = cariItem(dokumen, itemId);
  if (!hit) return dokumen;
  const urut = [...hit.lajur.item].sort((a, b) => a.mulai - b.mulai);
  const i = urut.findIndex((x) => x.id === itemId);
  const j = i + arah;
  if (j < 0 || j >= urut.length) return dokumen;
  [urut[i], urut[j]] = [urut[j], urut[i]];
  let posisi = Math.min(...hit.lajur.item.map((x) => x.mulai));
  const tersusun = urut.map((x) => {
    const y = { ...x, mulai: posisi };
    posisi += x.durasi;
    return y;
  });
  const baru = salin(dokumen);
  baru.lajur = baru.lajur.map((l) => (l.id === hit.lajur.id ? { ...l, item: tersusun } : l));
  return rapikan(baru);
}

export function ubahProyek(dokumen, perubahan) {
  const baru = { ...dokumen, ...perubahan };
  if (perubahan.kanvas) baru.kanvas = { ...dokumen.kanvas, ...perubahan.kanvas };
  return rapikan(baru);
}
