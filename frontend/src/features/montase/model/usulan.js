/**
 * Usulan asisten (JOB-4 M5.1-M5.5): daftar OPERASI dari server dijalankan
 * dengan fungsi model yang sama dengan tangan manusia. Asisten tidak pernah
 * menulis dokumen proyek; editor memakai `terapkanOperasi` untuk pratinjau
 * usulan (item baru bergaris putus) dan, bila diterima, sekali lagi pada
 * dokumen sungguhan sebagai SATU langkah batal.
 *
 * Jenis operasi (waktu dalam bingkai):
 *   klip     {bahan, bahan_info, mulai, potong_awal, durasi}
 *   animasi  {komponen, props, mulai, durasi}
 *   teks     {teks, mulai, durasi}
 *   audio    {bahan, bahan_info, mulai, narasi?}
 *   potong   {item, dari, sampai}          buang rentang (jeda, kata isian)
 *   ubah     {item, ubah?, keyframe?}      bingkai ulang (posisi, skala)
 * Semua operasi punya {id, kelompok, label, alasan}.
 */
import {
  cariItem, durasiIsi, tambahBahan, tambahMotion, tambahTeks, ubahItem,
} from './dokumen.js';
import { belah, hapusBeriak, taruhSuara } from './suntingan.js';

function tandaiAi(dokumen, itemId, op, tambahan = {}) {
  return ubahItem(dokumen, itemId, { asal: 'ai', alasan: (op.alasan || '').slice(0, 500), ...tambahan });
}

/**
 * Potongan jeda menggeser juga item di lajur LAIN yang mulai sesudah
 * potongannya (kartu, narasi, teks), supaya tetap menempel pada klipnya.
 * `hapusBeriak` sendiri hanya meriak di lajurnya; di Top 5 hasil asisten itu
 * membuat kartu #1 menimpa awal klip #1 sesudah jeda klip #5 dibuang.
 */
function geserLajurLain(dokumen, lajurId, sampai, delta) {
  const baru = {
    ...dokumen,
    lajur: dokumen.lajur.map((l) => (l.id === lajurId || l.kunci ? l : {
      ...l, item: l.item.map((i) => (i.mulai >= sampai ? { ...i, mulai: Math.max(0, i.mulai - delta) } : i)),
    })),
  };
  return { ...baru, durasi: durasiIsi(baru) };
}

function jalankanSatu(d, op) {
  switch (op.jenis) {
    case 'klip': {
      const h = tambahBahan(d, { ...op.bahan_info, id: op.bahan, jenis: op.bahan_info?.jenis || 'video' },
        { mulai: op.mulai });
      return { dokumen: tandaiAi(h.dokumen, h.itemId, op, { potong_awal: op.potong_awal || 0, durasi: op.durasi }),
        itemId: h.itemId };
    }
    case 'animasi': {
      const h = tambahMotion(d, { komponen: op.komponen, modul: { contohProps: op.props ?? {}, durasiBawaan: op.durasi },
        mulai: op.mulai });
      return { dokumen: tandaiAi(h.dokumen, h.itemId, op), itemId: h.itemId };
    }
    case 'teks': {
      const h = tambahTeks(d, { mulai: op.mulai, teks: op.teks });
      return { dokumen: tandaiAi(h.dokumen, h.itemId, op, { durasi: op.durasi }), itemId: h.itemId };
    }
    case 'audio': {
      const h = taruhSuara(d, { ...op.bahan_info, id: op.bahan, jenis: 'audio' },
        { mulai: op.mulai, narasi: op.narasi ?? null });
      return { dokumen: tandaiAi(h.dokumen, h.itemId, op), itemId: h.itemId };
    }
    case 'ubah': {
      if (!cariItem(d, op.item)) return { dokumen: d, itemId: null };
      const perubahan = {};
      if (op.ubah) perubahan.ubah = op.ubah;
      if (op.keyframe) perubahan.keyframe = op.keyframe;
      return { dokumen: ubahItem(d, op.item, perubahan), itemId: op.item };
    }
    case 'potong': {
      const hit = cariItem(d, op.item);
      if (!hit) return { dokumen: d, itemId: null };
      const { item } = hit;
      const dari = Math.max(item.mulai, Math.round(op.dari));
      const sampai = Math.min(item.mulai + item.durasi, Math.round(op.sampai));
      if (sampai - dari < 1) return { dokumen: d, itemId: null };
      let x = d;
      let tengah = item.id;
      if (sampai < item.mulai + item.durasi) x = belah(x, item.id, sampai).dokumen;
      if (dari > item.mulai) {
        const b = belah(x, item.id, dari);
        x = b.dokumen;
        tengah = b.itemBaru;
      }
      if (!tengah) return { dokumen: d, itemId: null };
      const beriak = hapusBeriak(x, tengah);
      return { dokumen: geserLajurLain(beriak, hit.lajur.id, sampai, sampai - dari), itemId: null };
    }
    default:
      return { dokumen: d, itemId: null };
  }
}

/**
 * Menjalankan operasi terpilih (`pilih`: Set id, atau null = semua).
 * Mengembalikan {dokumen, itemUsulan: Map itemId -> opId, dilewati: [opId]}.
 *
 * Potongan dijalankan paling akhir dan dari belakang ke depan per item,
 * supaya potongan yang satu tidak menggeser letak potongan lain.
 */
export function terapkanOperasi(dokumen, operasi, pilih = null) {
  const dipilih = operasi.filter((op) => !pilih || pilih.has(op.id));
  const potong = dipilih.filter((op) => op.jenis === 'potong').sort((a, b) => b.dari - a.dari);
  const lain = dipilih.filter((op) => op.jenis !== 'potong');
  let d = dokumen;
  const itemUsulan = new Map();
  const dilewati = [];
  for (const op of [...lain, ...potong]) {
    let h;
    try {
      h = jalankanSatu(d, op);
    } catch {
      h = { dokumen: d, itemId: null };
    }
    if (h.dokumen === d && op.jenis !== 'ubah') dilewati.push(op.id);
    d = h.dokumen;
    if (h.itemId) itemUsulan.set(h.itemId, op.id);
  }
  return { dokumen: d, itemUsulan, dilewati };
}

/** Operasi dikelompokkan per `kelompok`, urutannya seperti datang dari server. */
export function kelompokOperasi(operasi) {
  const peta = new Map();
  for (const op of operasi) {
    const k = op.kelompok ?? '';
    if (!peta.has(k)) peta.set(k, []);
    peta.get(k).push(op);
  }
  return [...peta.entries()].map(([kelompok, ops]) => ({ kelompok, ops }));
}
