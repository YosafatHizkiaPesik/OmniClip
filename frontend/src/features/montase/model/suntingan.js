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
  bersihkanUbah, cariItem, durasiIsi, idBaru, JENIS_LAJUR_ITEM,
} from './dokumen.js';

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
