/**
 * Operasi linimasa Tahap 2 (JOB-4 M2.1-M2.7), semuanya fungsi murni seperti
 * model/dokumen.js. Waktu dalam bingkai.
 *
 * Aturan yang dijaga di sini, bukan di komponen:
 *   - item di lajur TERKUNCI tidak bisa diubah (fungsi mengembalikan dokumen
 *     yang sama, jadi tidak ada langkah kosong di riwayat batal);
 *   - item bahan tidak bisa dipanjangkan melewati bahannya, dan tidak bisa
 *     dipangkas ke kiri melewati awal bahannya;
 *   - pindah lajur hanya ke lajur yang jenisnya cocok (video/gambar ke lajur
 *     gambar, teks ke teks, dan seterusnya).
 */
import {
  BATAS_UBAH, bersihkanUbah, cariItem, durasiIsi, GAYA_SUBTITLE, idBaru, JENIS_LAJUR_ITEM,
  tambahBahan, ubahItem,
} from './dokumen.js';
import { KURVA, nilaiPada, punyaKeyframe, SIFAT_KEYFRAME } from '../komposisi/keyframe.js';
import { presetCaption } from './presetCaption.js';

const MEDIA = new Set(['video', 'audio']);

function rapikan(dokumen) {
  return { ...dokumen, durasi: durasiIsi(dokumen) };
}

function petaItem(dokumen, fn) {
  return rapikan({
    ...dokumen,
    lajur: dokumen.lajur.map((l) => ({ ...l, item: l.item.map((i) => fn(i, l) ?? i) })),
  });
}

function terkunci(dokumen, itemId) {
  return Boolean(cariItem(dokumen, itemId)?.lajur.kunci);
}

/** Panjang bahan item media dalam bingkai linimasa yang tersisa dari potong_awal. */
export function sisaBahan(dokumen, item) {
  if (!MEDIA.has(item.jenis)) return Infinity;
  const detik = dokumen.bahan[item.bahan]?.durasi;
  if (!detik) return Infinity;
  const fps = dokumen.kanvas.fps;
  return Math.floor((detik * fps - (item.potong_awal || 0)) / (item.kecepatan || 1));
}

/** Membelah item di bingkai `di` (mutlak). Mengembalikan {dokumen, itemBaru}. */
export function belah(dokumen, itemId, di) {
  const hit = cariItem(dokumen, itemId);
  if (!hit || hit.lajur.kunci) return { dokumen, itemBaru: null };
  const { item, lajur } = hit;
  const potong = Math.round(di) - item.mulai;
  if (potong <= 0 || potong >= item.durasi) return { dokumen, itemBaru: null };
  const itemBaru = idBaru(dokumen);
  const kanan = {
    ...item,
    id: itemBaru,
    mulai: item.mulai + potong,
    durasi: item.durasi - potong,
  };
  if (item.keyframe) kanan.keyframe = geserKeyframe(item.keyframe, potong);
  if (MEDIA.has(item.jenis)) {
    kanan.potong_awal = (item.potong_awal || 0) + Math.round(potong * (item.kecepatan || 1));
  }
  const baru = {
    ...dokumen,
    lajur: dokumen.lajur.map((l) => (l.id !== lajur.id ? l : {
      ...l,
      item: l.item.flatMap((i) => (i.id === itemId ? [{ ...i, durasi: potong }, kanan] : [i])),
    })),
  };
  return { dokumen: rapikan(baru), itemBaru };
}

/** Menggeser ujung kiri item ke `mulaiBaru`; ujung kanan tetap. */
export function pangkasKiri(dokumen, itemId, mulaiBaru) {
  const hit = cariItem(dokumen, itemId);
  if (!hit || hit.lajur.kunci) return dokumen;
  const { item } = hit;
  const ujung = item.mulai + item.durasi;
  let mulai = Math.min(Math.round(mulaiBaru), ujung - 1);
  mulai = Math.max(0, mulai);
  if (MEDIA.has(item.jenis)) {
    const k = item.kecepatan || 1;
    // Tidak bisa mundur melewati awal bahan.
    const palingKiri = item.mulai - Math.floor((item.potong_awal || 0) / k);
    mulai = Math.max(mulai, palingKiri);
  }
  const delta = mulai - item.mulai;
  if (delta === 0) return dokumen;
  return petaItem(dokumen, (i) => (i.id !== itemId ? null : {
    ...i,
    mulai,
    durasi: ujung - mulai,
    ...(i.keyframe ? { keyframe: geserKeyframe(i.keyframe, delta) } : {}),
    ...(MEDIA.has(i.jenis)
      ? { potong_awal: Math.max(0, (i.potong_awal || 0) + Math.round(delta * (i.kecepatan || 1))) }
      : {}),
  }));
}

/** Menggeser ujung kanan item ke `ujungBaru`; ujung kiri tetap. */
export function pangkasKanan(dokumen, itemId, ujungBaru) {
  const hit = cariItem(dokumen, itemId);
  if (!hit || hit.lajur.kunci) return dokumen;
  const { item } = hit;
  let durasi = Math.max(1, Math.round(ujungBaru) - item.mulai);
  durasi = Math.min(durasi, sisaBahan(dokumen, item));
  if (durasi === item.durasi) return dokumen;
  return petaItem(dokumen, (i) => (i.id !== itemId ? null : { ...i, durasi }));
}

/** Lajur tujuan yang sah untuk item, atau null. */
function lajurCocok(dokumen, item, lajurId) {
  const l = dokumen.lajur.find((x) => x.id === lajurId);
  if (!l || l.kunci || l.jenis !== JENIS_LAJUR_ITEM[item.jenis]) return null;
  return l;
}

/**
 * Menggeser item sebanyak `delta` bingkai (tidak kurang dari 0). Bila
 * `lajurTujuan` diberikan dan hanya satu item yang digeser, item pindah ke
 * lajur itu bila jenisnya cocok.
 */
export function pindahItem(dokumen, itemIds, delta, lajurTujuan = null) {
  const ids = new Set(itemIds.filter((id) => !terkunci(dokumen, id)));
  if (!ids.size) return dokumen;
  const geser = Math.max(Math.round(delta), -Math.min(
    ...[...ids].map((id) => cariItem(dokumen, id).item.mulai),
  ));
  let tujuan = null;
  if (lajurTujuan && ids.size === 1) {
    const { item, lajur } = cariItem(dokumen, [...ids][0]);
    tujuan = lajur.id !== lajurTujuan ? lajurCocok(dokumen, item, lajurTujuan) : null;
  }
  if (geser === 0 && !tujuan) return dokumen;
  const dipindah = [];
  let lajur = dokumen.lajur.map((l) => ({
    ...l,
    item: l.item.flatMap((i) => {
      if (!ids.has(i.id)) return [i];
      const baru = { ...i, mulai: i.mulai + geser };
      if (tujuan) { dipindah.push(baru); return []; }
      return [baru];
    }),
  }));
  if (tujuan) {
    lajur = lajur.map((l) => (l.id === tujuan.id ? { ...l, item: [...l.item, ...dipindah] } : l));
  }
  return rapikan({ ...dokumen, lajur });
}

/**
 * Mengganti kecepatan tanpa mengubah potongan bahan yang dipakai: 10 detik
 * bahan pada 2x menjadi 5 detik di linimasa (sama dengan CapCut). Durasi baru
 * tetap dijepit ke sisa bahan.
 */
export function ubahKecepatan(dokumen, itemId, kecepatan) {
  const hit = cariItem(dokumen, itemId);
  if (!hit || hit.lajur.kunci || !MEDIA.has(hit.item.jenis) || hit.item.beku) return dokumen;
  const k = Math.min(4, Math.max(0.25, Number(kecepatan) || 1));
  const lama = hit.item.kecepatan || 1;
  if (k === lama) return dokumen;
  const baru = { ...hit.item, kecepatan: k };
  baru.durasi = Math.max(1, Math.min(Math.round((hit.item.durasi * lama) / k), sisaBahan(dokumen, baru)));
  return petaItem(dokumen, (i) => (i.id === itemId ? baru : null));
}

/** Menggabungkan sebagian transformasi (x, y, skala, putar, opasitas, potong). */
export function ubahTransform(dokumen, itemId, sebagian) {
  const hit = cariItem(dokumen, itemId);
  if (!hit || hit.lajur.kunci) return dokumen;
  const lama = hit.item.ubah ?? {};
  const gabung = { ...lama, ...sebagian };
  if (sebagian.potong) gabung.potong = { ...lama.potong, ...sebagian.potong };
  const ubah = bersihkanUbah(gabung);
  return petaItem(dokumen, (i) => (i.id === itemId ? { ...i, ubah } : null));
}

/** Id semua item yang tidak terkunci, untuk Ctrl+A. */
export function semuaItem(dokumen) {
  return dokumen.lajur.filter((l) => !l.kunci).flatMap((l) => l.item.map((i) => i.id));
}

/**
 * Titik sisip saat satu item diseret menimpa item lain di lajur tujuan.
 *
 * CapCut tidak membiarkan dua item bertumpuk di satu lajur; menyeret klip ke
 * atas klip lain berarti "taruh di sini" dan sisanya bergeser. Fungsi ini
 * mencari item yang tertimpa (yang berada di bawah penunjuk `f`, atau yang
 * paling banyak tertimpa) lalu mengembalikan tepi kirinya bila penunjuk di
 * paruh kiri item itu, tepi kanannya bila di paruh kanan. Null bila tidak
 * ada yang tertimpa (seretan bebas biasa).
 */
export function titikSisip(dokumen, itemId, lajurId, mulaiBaru, f) {
  const hit = cariItem(dokumen, itemId);
  const lajur = dokumen.lajur.find((l) => l.id === lajurId);
  if (!hit || !lajur) return null;
  const akhir = mulaiBaru + hit.item.durasi;
  const kena = lajur.item.filter((i) => i.id !== itemId && i.mulai < akhir && i.mulai + i.durasi > mulaiBaru);
  if (!kena.length) return null;
  const tumpang = (i) => Math.min(akhir, i.mulai + i.durasi) - Math.max(mulaiBaru, i.mulai);
  const b = kena.find((i) => f >= i.mulai && f < i.mulai + i.durasi)
    ?? kena.reduce((x, y) => (tumpang(y) > tumpang(x) ? y : x));
  return f < b.mulai + b.durasi / 2 ? b.mulai : b.mulai + b.durasi;
}

/**
 * Menyisipkan item di bingkai `di` lajur `lajurId`: item dicabut dari
 * tempatnya (yang sesudahnya di lajur asal merapat), lalu item di lajur
 * tujuan mulai `di` bergeser ke kanan sepanjang item. Untuk deretan klip yang
 * rapat, hasilnya persis menukar urutan. `di` dalam koordinat SEBELUM item
 * dicabut.
 */
export function sisipkan(dokumen, itemId, lajurId, di) {
  const hit = cariItem(dokumen, itemId);
  if (!hit || hit.lajur.kunci) return dokumen;
  const { item } = hit;
  const tujuan = lajurId === hit.lajur.id ? hit.lajur : lajurCocok(dokumen, item, lajurId);
  if (!tujuan) return dokumen;
  const dur = item.durasi;
  const ujungAsal = item.mulai + dur;
  let titik = Math.max(0, Math.round(di));
  if (tujuan.id === hit.lajur.id && titik >= ujungAsal) titik -= dur;
  const lajur = dokumen.lajur.map((l) => {
    let isi = l.item;
    if (l.id === hit.lajur.id) {
      isi = isi.filter((i) => i.id !== itemId)
        .map((i) => (i.mulai >= ujungAsal ? { ...i, mulai: i.mulai - dur } : i));
    }
    if (l.id === tujuan.id) {
      isi = [...isi.map((i) => (i.mulai >= titik ? { ...i, mulai: i.mulai + dur } : i)), { ...item, mulai: titik }];
    }
    return isi === l.item ? l : { ...l, item: isi };
  });
  return rapikan({ ...dokumen, lajur });
}

/**
 * Merapatkan celah di satu lajur: item disusun berurutan tanpa jeda, mulai
 * dari letak item pertamanya. Celah muncul sesudah mengubah kecepatan atau
 * memangkas klip di tengah deretan; CapCut menyebutnya "hapus celah".
 */
export function rapatkan(dokumen, lajurId) {
  const lajur = dokumen.lajur.find((l) => l.id === lajurId);
  if (!lajur || lajur.kunci || lajur.item.length < 2) return dokumen;
  const urut = [...lajur.item].sort((a, b) => a.mulai - b.mulai);
  let posisi = urut[0].mulai;
  const baru = new Map();
  for (const i of urut) {
    if (i.mulai !== posisi) baru.set(i.id, posisi);
    posisi += i.durasi;
  }
  if (!baru.size) return dokumen;
  return rapikan({
    ...dokumen,
    lajur: dokumen.lajur.map((l) => (l.id !== lajurId ? l : {
      ...l, item: l.item.map((i) => (baru.has(i.id) ? { ...i, mulai: baru.get(i.id) } : i)),
    })),
  });
}

/** Menghapus item dan merapatkan item sesudahnya di lajur yang sama. */
export function hapusBeriak(dokumen, itemId) {
  const hit = cariItem(dokumen, itemId);
  if (!hit || hit.lajur.kunci) return dokumen;
  const { item, lajur } = hit;
  const baru = {
    ...dokumen,
    lajur: dokumen.lajur.map((l) => (l.id !== lajur.id ? l : {
      ...l,
      item: l.item.filter((i) => i.id !== itemId).map((i) => (
        i.mulai >= item.mulai + item.durasi ? { ...i, mulai: i.mulai - item.durasi } : i)),
    })),
  };
  return buangBahanYatim(rapikan(baru));
}

function buangBahanYatim(dokumen) {
  const dipakai = new Set(dokumen.lajur.flatMap((l) => l.item.map((i) => i.bahan).filter(Boolean)));
  return { ...dokumen, bahan: Object.fromEntries(Object.entries(dokumen.bahan).filter(([id]) => dipakai.has(id))) };
}

export function hapusBanyak(dokumen, itemIds) {
  const ids = new Set(itemIds.filter((id) => !terkunci(dokumen, id)));
  if (!ids.size) return dokumen;
  return buangBahanYatim(rapikan({
    ...dokumen,
    lajur: dokumen.lajur.map((l) => ({ ...l, item: l.item.filter((i) => !ids.has(i.id)) })),
  }));
}

/** Isi papan klip: salinan item beserta metadata bahannya dan lajur asalnya. */
export function salin(dokumen, itemIds) {
  const item = [];
  for (const id of itemIds) {
    const hit = cariItem(dokumen, id);
    if (hit) item.push({ ...hit.item, _lajur: hit.lajur.id });
  }
  const bahan = {};
  for (const i of item) if (i.bahan && dokumen.bahan[i.bahan]) bahan[i.bahan] = dokumen.bahan[i.bahan];
  return item.length ? { item, bahan } : null;
}

/**
 * Menempelkan isi papan klip mulai bingkai `di`, jarak antar item dijaga.
 * Item masuk lajur asalnya bila masih ada dan tidak terkunci, selain itu
 * lajur pertama yang jenisnya cocok. Mengembalikan {dokumen, itemBaru: [...]}.
 */
export function tempel(dokumen, papan, di) {
  if (!papan?.item?.length) return { dokumen, itemBaru: [] };
  const awal = Math.min(...papan.item.map((i) => i.mulai));
  let hasil = { ...dokumen, bahan: { ...dokumen.bahan, ...papan.bahan } };
  const itemBaru = [];
  for (const asli of papan.item) {
    const { _lajur, ...isi } = asli;
    const id = idBaru(hasil);
    const baru = { ...isi, id, mulai: Math.max(0, Math.round(di) + (asli.mulai - awal)) };
    const tujuan = lajurCocok(hasil, baru, _lajur)
      ?? hasil.lajur.find((l) => !l.kunci && l.jenis === JENIS_LAJUR_ITEM[baru.jenis]);
    if (!tujuan) continue;
    hasil = {
      ...hasil,
      lajur: hasil.lajur.map((l) => (l.id === tujuan.id ? { ...l, item: [...l.item, baru] } : l)),
    };
    itemBaru.push(id);
  }
  return { dokumen: rapikan(hasil), itemBaru };
}

/** Gandakan: tempel salinan tepat sesudah ujung item terakhir yang dipilih. */
export function gandakan(dokumen, itemIds) {
  const papan = salin(dokumen, itemIds);
  if (!papan) return { dokumen, itemBaru: [] };
  const ujung = Math.max(...papan.item.map((i) => i.mulai + i.durasi));
  return tempel(dokumen, papan, ujung);
}

/**
 * Bekukan bingkai: item media dibelah di `di`, lalu bingkai itu ditahan
 * selama `durasiBeku`, dan item sesudahnya di lajur yang sama bergeser.
 */
export function bekukan(dokumen, itemId, di, durasiBeku) {
  const hit = cariItem(dokumen, itemId);
  if (!hit || hit.lajur.kunci || hit.item.jenis !== 'video') return { dokumen, itemBaru: null };
  const lajurId = hit.lajur.id;
  const titik = Math.round(di);
  let d = dokumen;
  if (titik > hit.item.mulai && titik < hit.item.mulai + hit.item.durasi) {
    d = belah(d, itemId, titik).dokumen;
  }
  const kiri = cariItem(d, itemId).item;
  const potongBeku = (kiri.potong_awal || 0) + Math.round((titik - kiri.mulai) * (kiri.kecepatan || 1));
  const id = idBaru(d);
  const beku = {
    ...kiri, id, mulai: titik, durasi: Math.max(1, Math.round(durasiBeku)),
    potong_awal: Math.max(0, potongBeku - 1), beku: true, volume: 0,
  };
  d = {
    ...d,
    lajur: d.lajur.map((l) => (l.id !== lajurId ? l : {
      ...l,
      item: [...l.item.map((i) => (i.mulai >= titik ? { ...i, mulai: i.mulai + beku.durasi } : i)), beku],
    })),
  };
  return { dokumen: rapikan(d), itemBaru: id };
}

// --- lajur ----------------------------------------------------------------

const NAMA_LAJUR = { video: 'Video', teks: 'Teks', motion: 'Animasi', audio: 'Suara' };

/**
 * Lajur baru diletakkan sesudah lajur terakhir sejenisnya, jadi lajur video
 * kedua tergambar DI ATAS video pertama (lapisan seperti CapCut), dan lajur
 * suara tetap di bawah.
 */
export function tambahLajur(dokumen, jenis) {
  const dipakai = new Set(dokumen.lajur.map((l) => l.id));
  let n = dokumen.lajur.length + 1;
  while (dipakai.has(`L${n}`)) n += 1;
  const sejenis = dokumen.lajur.filter((l) => l.jenis === jenis).length;
  const lajur = { id: `L${n}`, jenis, nama: `${NAMA_LAJUR[jenis]} ${sejenis + 1}`, item: [] };
  const terakhir = dokumen.lajur.map((l) => l.jenis).lastIndexOf(jenis);
  const posisi = terakhir >= 0 ? terakhir + 1 : dokumen.lajur.length;
  const daftar = [...dokumen.lajur];
  daftar.splice(posisi, 0, lajur);
  return { dokumen: { ...dokumen, lajur: daftar }, lajurId: lajur.id };
}

const KOLOM_LAJUR = new Set(['nama', 'kunci', 'bisu', 'sembunyi', 'volume']);

export function ubahLajur(dokumen, lajurId, perubahan) {
  const bersih = Object.fromEntries(Object.entries(perubahan).filter(([k]) => KOLOM_LAJUR.has(k)));
  if ('volume' in bersih) bersih.volume = Math.min(2, Math.max(0, Number(bersih.volume) || 0));
  if ('nama' in bersih) bersih.nama = String(bersih.nama).slice(0, 60);
  return { ...dokumen, lajur: dokumen.lajur.map((l) => (l.id === lajurId ? { ...l, ...bersih } : l)) };
}

/** Lajur hanya bisa dihapus bila kosong dan bukan satu-satunya dari jenisnya. */
export function bisaHapusLajur(dokumen, lajurId) {
  const l = dokumen.lajur.find((x) => x.id === lajurId);
  if (!l || l.item.length) return false;
  return dokumen.lajur.filter((x) => x.jenis === l.jenis).length > 1;
}

export function hapusLajur(dokumen, lajurId) {
  if (!bisaHapusLajur(dokumen, lajurId)) return dokumen;
  return { ...dokumen, lajur: dokumen.lajur.filter((l) => l.id !== lajurId) };
}

// --- penanda dan magnet ------------------------------------------------------

export function tambahPenanda(dokumen, di, label = '') {
  const t = Math.max(0, Math.round(di));
  if ((dokumen.penanda ?? []).some((p) => p.t === t)) return dokumen;
  const penanda = [...(dokumen.penanda ?? []), { t, label: String(label).slice(0, 40) }]
    .sort((a, b) => a.t - b.t);
  return { ...dokumen, penanda };
}

export function ubahPenanda(dokumen, t, label) {
  return {
    ...dokumen,
    penanda: (dokumen.penanda ?? []).map((p) => (p.t === t ? { ...p, label: String(label).slice(0, 40) } : p)),
  };
}

export function hapusPenanda(dokumen, t) {
  return { ...dokumen, penanda: (dokumen.penanda ?? []).filter((p) => p.t !== t) };
}

/** Titik tempel magnet: awal, garis putar, ujung item lain, dan penanda. */
export function titikMagnet(dokumen, { garis = null, kecuali = [] } = {}) {
  const lewati = new Set(kecuali);
  const titik = new Set([0]);
  if (garis !== null) titik.add(Math.round(garis));
  for (const l of dokumen.lajur) {
    for (const i of l.item) {
      if (lewati.has(i.id)) continue;
      titik.add(i.mulai);
      titik.add(i.mulai + i.durasi);
    }
  }
  for (const p of dokumen.penanda ?? []) titik.add(p.t);
  return [...titik].sort((a, b) => a - b);
}

/** Bingkai terdekat dalam `ambang`, atau `nilai` sendiri bila tidak ada. */
export function tempelKe(nilai, titik, ambang) {
  let terbaik = nilai;
  let jarak = ambang + 1;
  for (const t of titik) {
    const j = Math.abs(t - nilai);
    if (j <= ambang && j < jarak) { terbaik = t; jarak = j; }
  }
  return terbaik;
}


// --- subtitle otomatis (M3.2) ------------------------------------------------

/**
 * Menaruh potongan subtitle (hasil pekerjaan `montase_subtitle`) di lajur
 * teks bertanda `subtitle`. Lajur subtitle yang sudah ada dan tidak terkunci
 * DIGANTI isinya (menjalankan ulang tidak menumpuk); bila belum ada, lajur
 * baru dibuat di atas lajur teks lain. Setiap item bertanda `asal: 'ai'`
 * beserta alasannya dan bisa dihapus sendiri. Mengembalikan {dokumen, lajurId}.
 */
export function pasangSubtitle(dokumen, potongan, { nama = 'Subtitle', alasan = '' } = {}) {
  let d = dokumen;
  let lajur = d.lajur.find((l) => l.subtitle && !l.kunci);
  if (!lajur) {
    const hasil = tambahLajur(d, 'teks');
    d = ubahLajur(hasil.dokumen, hasil.lajurId, { nama });
    d = { ...d, lajur: d.lajur.map((l) => (l.id === hasil.lajurId ? { ...l, subtitle: true } : l)) };
    lajur = d.lajur.find((l) => l.id === hasil.lajurId);
  }
  const dipakai = new Set(d.lajur.filter((l) => l.id !== lajur.id).flatMap((l) => l.item.map((i) => i.id)));
  // Subtitle yang dibuat ulang memakai preset caption lajurnya (JOB-5 P1).
  const gaya = presetCaption(lajur.gaya_caption)?.gaya ?? GAYA_SUBTITLE;
  let n = 1;
  const item = [];
  for (const p of potongan) {
    while (dipakai.has(`s${n}`)) n += 1;
    const id = `s${n}`;
    dipakai.add(id);
    item.push({
      id, jenis: 'teks', mulai: Math.max(0, Math.round(p.mulai)), durasi: Math.max(1, Math.round(p.durasi)),
      teks: String(p.teks).slice(0, 500), kata: p.kata, gaya: { ...gaya }, asal: 'ai', alasan,
    });
  }
  const lajurId = lajur.id;
  return {
    dokumen: rapikan({ ...d, lajur: d.lajur.map((l) => (l.id === lajurId ? { ...l, item } : l)) }),
    lajurId,
  };
}


// --- narasi dan rekaman (M3.3) -----------------------------------------------

function metaBahan(bahan) {
  return {
    jenis: bahan.jenis, nama: bahan.nama ?? '', durasi: bahan.durasi ?? null,
    lebar: bahan.lebar ?? null, tinggi: bahan.tinggi ?? null, fps: bahan.fps ?? null,
    ada_suara: Boolean(bahan.ada_suara),
  };
}

/**
 * Menaruh bahan suara (narasi, rekaman) di bingkai `mulai`, di lajur audio
 * pertama yang tidak terkunci dan KOSONG di rentang itu; bila semuanya terisi,
 * lajur audio baru dibuat (seperti CapCut: suara baru tidak menimpa musik).
 * `narasi` = {teks, suara, kecepatan} disimpan di item supaya bisa dibuat ulang.
 */
export function taruhSuara(dokumen, bahan, { mulai = 0, narasi = null } = {}) {
  const fps = dokumen.kanvas.fps;
  const awal = Math.max(0, Math.round(mulai));
  const panjang = Math.max(1, Math.round((bahan.durasi || 1) * fps));
  const kosong = (l) => !l.kunci && l.jenis === 'audio'
    && !l.item.some((i) => i.mulai < awal + panjang && i.mulai + i.durasi > awal);
  let d = dokumen;
  let lajur = d.lajur.find(kosong);
  if (!lajur) {
    const baru = tambahLajur(d, 'audio');
    d = baru.dokumen;
    lajur = d.lajur.find((l) => l.id === baru.lajurId);
  }
  const hasil = tambahBahan(d, bahan, { mulai: awal, lajurId: lajur.id });
  if (!narasi) return hasil;
  return {
    dokumen: petaItem(hasil.dokumen, (i) => (i.id === hasil.itemId ? { ...i, narasi } : null)),
    itemId: hasil.itemId,
  };
}

/**
 * Mengganti bahan item (narasi yang teksnya diubah): item tetap di tempatnya,
 * panjangnya mengikuti suara baru, bahan lama dibuang bila tidak dipakai lagi.
 */
export function gantiBahanItem(dokumen, itemId, bahan, tambahan = {}) {
  const hit = cariItem(dokumen, itemId);
  if (!hit || hit.lajur.kunci) return dokumen;
  const fps = dokumen.kanvas.fps;
  const d = {
    ...dokumen,
    bahan: { ...dokumen.bahan, [bahan.id]: metaBahan(bahan) },
  };
  const hasil = petaItem(d, (i) => (i.id !== itemId ? null : {
    ...i, ...tambahan, bahan: bahan.id, potong_awal: 0,
    durasi: Math.max(1, Math.round(((bahan.durasi || 1) * fps) / (i.kecepatan || 1))),
  }));
  return buangBahanYatim(hasil);
}


// --- keyframe (M3.7) ----------------------------------------------------------

const BAWAAN_SIFAT = { x: 0, y: 0, skala: 1, putar: 0, opasitas: 1, volume: 1 };
const BATAS_SIFAT = { ...BATAS_UBAH, volume: [0, 2] };

/**
 * Keyframe relatif ke awal item, jadi saat awal item bergeser `delta`
 * bingkai (belah, pangkas kiri), semua `t` dikurangi `delta`. Keyframe yang
 * jatuh sebelum 0 TIDAK dibuang: nilai antara tetap dihitung dari pasangan
 * yang mengapitnya, jadi gerakannya tidak meloncat di titik potong.
 */
export function geserKeyframe(keyframe, delta) {
  const hasil = {};
  for (const [s, daftar] of Object.entries(keyframe ?? {})) {
    hasil[s] = (daftar ?? []).map((k) => ({ ...k, t: k.t - delta }));
  }
  return hasil;
}

function nilaiDasar(item, sifat) {
  return sifat === 'volume' ? (item.volume ?? 1) : (item.ubah?.[sifat] ?? BAWAAN_SIFAT[sifat]);
}

/** Nilai sifat item pada bingkai relatif `f` (keyframe bila ada, selain itu nilai dasar). */
export function nilaiSifat(item, sifat, f) {
  return punyaKeyframe(item, sifat) ? nilaiPada(item.keyframe[sifat], f, nilaiDasar(item, sifat)) : nilaiDasar(item, sifat);
}

function jepitSifat(sifat, v) {
  const [bawah, atas] = BATAS_SIFAT[sifat];
  return Math.min(atas, Math.max(bawah, Number(v)));
}

function gantiKeyframe(dokumen, itemId, fn) {
  const hit = cariItem(dokumen, itemId);
  if (!hit || hit.lajur.kunci) return dokumen;
  const keyframe = fn({ ...hit.item.keyframe }, hit.item);
  if (!keyframe) return dokumen;
  for (const s of Object.keys(keyframe)) if (!keyframe[s]?.length) delete keyframe[s];
  return petaItem(dokumen, (i) => {
    if (i.id !== itemId) return null;
    const { keyframe: _lama, ...sisa } = i;
    return Object.keys(keyframe).length ? { ...sisa, keyframe } : sisa;
  });
}

/** Menaruh (atau mengganti) keyframe `sifat` di bingkai relatif `f`. */
export function aturKeyframe(dokumen, itemId, sifat, f, nilai, kurva = null) {
  if (!SIFAT_KEYFRAME.includes(sifat) || !Number.isFinite(Number(nilai))) return dokumen;
  const t = Math.round(f);
  return gantiKeyframe(dokumen, itemId, (kf) => {
    const lama = kf[sifat] ?? [];
    const ada = lama.find((k) => k.t === t);
    const k = { t, v: jepitSifat(sifat, nilai), kurva: kurva ?? ada?.kurva ?? 'linear' };
    kf[sifat] = [...lama.filter((x) => x.t !== t), k].sort((a, b) => a.t - b.t);
    return kf;
  });
}

/**
 * Wajik di panel: ada keyframe di `f` -> dihapus; belum -> ditambah dengan
 * nilai saat ini (jadi menambah keyframe tidak mengubah rupa). Keyframe
 * terakhir yang dihapus meninggalkan nilainya sebagai nilai dasar.
 */
export function tombolKeyframe(dokumen, itemId, sifat, f) {
  const hit = cariItem(dokumen, itemId);
  if (!hit || hit.lajur.kunci) return dokumen;
  const t = Math.round(f);
  const daftar = hit.item.keyframe?.[sifat] ?? [];
  const ada = daftar.find((k) => k.t === t);
  if (!ada) return aturKeyframe(dokumen, itemId, sifat, t, nilaiSifat(hit.item, sifat, t));
  let d = gantiKeyframe(dokumen, itemId, (kf) => ({ ...kf, [sifat]: daftar.filter((k) => k.t !== t) }));
  if (daftar.length === 1) d = aturNilaiDasar(d, itemId, sifat, ada.v);
  return d;
}

function aturNilaiDasar(dokumen, itemId, sifat, v) {
  if (sifat === 'volume') return ubahItem(dokumen, itemId, { volume: v });
  return ubahTransform(dokumen, itemId, { [sifat]: v });
}

/** Kurva semua keyframe yang ada tepat di bingkai relatif `f`. */
export function kurvaKeyframe(dokumen, itemId, f, kurva) {
  if (!KURVA.includes(kurva)) return dokumen;
  const t = Math.round(f);
  return gantiKeyframe(dokumen, itemId, (kf) => {
    let ada = false;
    for (const s of Object.keys(kf)) {
      kf[s] = kf[s].map((k) => {
        if (k.t !== t) return k;
        ada = true;
        return { ...k, kurva };
      });
    }
    return ada ? kf : null;
  });
}

/**
 * Mengubah sifat dari panel atau pegangan di bingkai relatif `f`: sifat yang
 * sudah punya keyframe ditulis sebagai keyframe di `f`, yang belum mengubah
 * nilai dasarnya. Sama dengan CapCut, dan pegangan tidak perlu tahu bedanya.
 */
export function ubahSifatDiBingkai(dokumen, itemId, sebagian, f) {
  const hit = cariItem(dokumen, itemId);
  if (!hit || hit.lajur.kunci) return dokumen;
  let d = dokumen;
  const dasar = {};
  for (const [s, v] of Object.entries(sebagian)) {
    if (SIFAT_KEYFRAME.includes(s) && punyaKeyframe(hit.item, s)) d = aturKeyframe(d, itemId, s, f, v);
    else dasar[s] = v;
  }
  const { volume, ...transform } = dasar;
  if (volume !== undefined) d = ubahItem(d, itemId, { volume });
  if (Object.keys(transform).length) d = ubahTransform(d, itemId, transform);
  return d;
}

/** Kembalikan letak, ukuran, putar, transparansi, dan potong; keyframe volume tetap. */
export function aturUlangTransform(dokumen, itemId) {
  const hit = cariItem(dokumen, itemId);
  if (!hit || hit.lajur.kunci) return dokumen;
  return petaItem(dokumen, (i) => {
    if (i.id !== itemId) return null;
    const { ubah: _u, keyframe, ...sisa } = i;
    const tetap = keyframe?.volume?.length ? { volume: keyframe.volume } : null;
    return tetap ? { ...sisa, keyframe: tetap } : sisa;
  });
}

// --- perendam musik (M3.4) ----------------------------------------------------

/**
 * Rentang ucapan di linimasa (bingkai mutlak): item lajur subtitle (kata yang
 * benar-benar diucapkan) dan item audio di lajur audio LAIN yang tidak bisu
 * (narasi, rekaman). Suara klip video tanpa subtitle tidak dihitung: tanpa
 * tahu di mana orang berbicara, merendam musik sepanjang video bukan
 * perendaman, hanya musik yang lebih pelan.
 */
export function rentangUcapan(dokumen, kecualiLajurId) {
  const r = [];
  for (const l of dokumen.lajur) {
    if (l.id === kecualiLajurId || l.bisu) continue;
    if (l.subtitle || l.jenis === 'audio') for (const i of l.item) r.push([i.mulai, i.mulai + i.durasi]);
  }
  return r.sort((a, b) => a[0] - b[0]);
}

function gabungRentang(rentang, jeda) {
  const hasil = [];
  for (const [a, b] of rentang) {
    const akhir = hasil[hasil.length - 1];
    if (akhir && a - akhir[1] <= jeda) akhir[1] = Math.max(akhir[1], b);
    else hasil.push([a, b]);
  }
  return hasil;
}

/**
 * Perendam otomatis: volume item di lajur musik turun ke `turun` x volumenya
 * selama ada ucapan, dengan lembut `lembut` detik di kedua sisi. Hasilnya
 * keyframe volume biasa (wajik di linimasa, bisa diubah satu per satu), dan
 * menjalankannya lagi mengganti keyframe volume yang lama.
 */
export function rendamMusik(dokumen, lajurId, { turun = 0.25, lembut = 0.3 } = {}) {
  const lajur = dokumen.lajur.find((l) => l.id === lajurId);
  if (!lajur || lajur.kunci || lajur.jenis !== 'audio') return dokumen;
  const fps = dokumen.kanvas.fps;
  const l = Math.max(1, Math.round(lembut * fps));
  const ucapan = gabungRentang(rentangUcapan(dokumen, lajurId), Math.round(0.5 * fps));
  const rendah = Math.min(1, Math.max(0, turun));
  return petaItem(dokumen, (i, lj) => {
    if (lj.id !== lajurId) return null;
    const v0 = i.volume ?? 1;
    const kunci = [];
    for (const [a, b] of ucapan) {
      if (b <= i.mulai || a >= i.mulai + i.durasi) continue;
      const ra = a - i.mulai;
      const rb = b - i.mulai;
      kunci.push({ t: ra - l, v: v0 }, { t: ra, v: v0 * rendah }, { t: rb, v: v0 * rendah }, { t: rb + l, v: v0 });
    }
    const { keyframe = {}, ...sisa } = i;
    const { volume: _lama, ...lain } = keyframe;
    if (!kunci.length) return Object.keys(lain).length ? { ...sisa, keyframe: lain } : sisa;
    // Ucapan yang berdekatan: keyframe naik dan turun yang bertumpuk dirapikan,
    // nilai yang lebih rendah menang supaya musik tidak naik sesaat di antaranya.
    const per = new Map();
    for (const k of kunci) {
      const ada = per.get(k.t);
      if (ada === undefined || k.v < ada) per.set(k.t, k.v);
    }
    const urut = [...per.entries()].sort((a, b) => a[0] - b[0])
      .map(([t, v]) => ({ t, v: Math.round(v * 1000) / 1000, kurva: 'masuk-keluar' }));
    return { ...sisa, keyframe: { ...lain, volume: urut } };
  });
}

// --- efek dan stiker (M3.8) ---------------------------------------------------

/** Punch-in di bingkai relatif `f` selama `d` bingkai; punch di bingkai yang sama diganti. */
export function tambahPunch(dokumen, itemId, f, d) {
  const hit = cariItem(dokumen, itemId);
  if (!hit || hit.lajur.kunci || !['video', 'gambar'].includes(hit.item.jenis)) return dokumen;
  const t = Math.max(0, Math.min(hit.item.durasi - 1, Math.round(f)));
  const lama = (hit.item.efek?.punch ?? []).filter((p) => p.t !== t);
  const punch = [...lama, { t, d: Math.max(1, Math.min(Math.round(d), hit.item.durasi - t)), kuat: 0.15 }]
    .sort((a, b) => a.t - b.t);
  return ubahItem(dokumen, itemId, { efek: { ...hit.item.efek, punch } });
}

export function hapusPunch(dokumen, itemId, t) {
  const hit = cariItem(dokumen, itemId);
  if (!hit) return dokumen;
  const punch = (hit.item.efek?.punch ?? []).filter((p) => p.t !== t);
  return ubahItem(dokumen, itemId, { efek: { ...hit.item.efek, punch } });
}

/** Stiker emoji: item teks besar tanpa garis, muncul dengan "pop". */
export function tambahStiker(dokumen, { mulai = 0, emoji = '🔥' } = {}) {
  const fps = dokumen.kanvas.fps;
  const lajur = dokumen.lajur.find((l) => l.jenis === 'teks' && !l.kunci && !l.subtitle)
    ?? dokumen.lajur.find((l) => l.jenis === 'teks' && !l.kunci);
  if (!lajur) return { dokumen, itemId: null };
  const id = idBaru(dokumen);
  const item = {
    id, jenis: 'teks', mulai: Math.max(0, Math.round(mulai)), durasi: Math.round(2 * fps), teks: emoji,
    stiker: true, asal: 'tangan',
    gaya: { ukuran: 240, warna: '#ffffff', letak: 'tengah', perataan: 'tengah', latar: 'tanpa', garis: 0, bayang: 0, kabur: 0, gerak: 'pop' },
  };
  return {
    dokumen: rapikan({ ...dokumen, lajur: dokumen.lajur.map((l) => (l.id === lajur.id ? { ...l, item: [...l.item, item] } : l)) }),
    itemId: id,
  };
}

// --- reaksi kamera (JOB-5 O5) --------------------------------------------------

/**
 * Rekaman reaksi kamera sebagai gambar-dalam-gambar di bingkai `mulai`: di
 * lajur video SELAIN lajur utama yang kosong di rentang itu (atau lajur video
 * baru), diperkecil ke sudut kanan bawah, di atas zona subtitle (22% bawah
 * kanvas tegak). Ukurannya kira-kira 42% lebar kanvas tegak, 30% kanvas datar.
 */
export function tambahReaksi(dokumen, bahan, mulai) {
  const fps = dokumen.kanvas.fps;
  const awal = Math.max(0, Math.round(mulai));
  const panjang = Math.max(1, Math.round((bahan.durasi || 1) * fps));
  const video = dokumen.lajur.filter((l) => l.jenis === 'video');
  const kosong = video.slice(1).find((l) => !l.kunci
    && !l.item.some((i) => i.mulai < awal + panjang && i.mulai + i.durasi > awal));
  let d = dokumen;
  let lajurId = kosong?.id;
  if (!lajurId) {
    const baru = tambahLajur(d, 'video');
    d = baru.dokumen;
    lajurId = baru.lajurId;
  }
  const hasil = tambahBahan(d, { ...bahan, jenis: 'video' }, { mulai: awal, lajurId });
  const W = dokumen.kanvas.lebar;
  const H = dokumen.kanvas.tinggi;
  const bw = bahan.lebar || 16;
  const bh = bahan.tinggi || 9;
  const s0 = Math.min(W / bw, H / bh);
  const kotakW = bw * s0;
  const kotakH = bh * s0;
  const tegak = H > W;
  const skala = ((tegak ? 0.42 : 0.3) * W) / kotakW;
  const w = kotakW * skala;
  const h = kotakH * skala;
  const tepi = 0.04 * W;
  const bawah = tegak ? 0.72 * H : H - tepi;
  const ubah = {
    skala: Math.round(skala * 1000) / 1000,
    x: Math.round(W - tepi - w / 2 - W / 2),
    y: Math.round(bawah - h / 2 - H / 2),
  };
  return {
    dokumen: ubahItem(hasil.dokumen, hasil.itemId, { ubah, nama: bahan.nama || undefined }),
    itemId: hasil.itemId,
    lajurId,
  };
}
