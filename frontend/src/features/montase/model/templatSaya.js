/**
 * Templat milik sendiri (JOB-5 P4): kerangka proyek yang sudah jadi disimpan
 * untuk dipakai lagi di proyek lain, seperti templat bawaan (model/templat.js).
 *
 * Yang disimpan hanya KERANGKA: item teks (beserta gaya, posisi), item
 * animasi (komponen, versi, props), penanda, dan preset caption lajur
 * subtitle. Bahan video, gambar, dan suara TIDAK ikut: isinya beda di tiap
 * video, dan menyalinnya hanya menghasilkan video yang sama dua kali (pola
 * konten tidak autentik yang diperingatkan O3). Teks subtitle juga dibuang
 * karena itu ucapan video lama; gaya caption-nya yang dibawa.
 *
 * Waktu disimpan dalam DETIK supaya templat dari proyek 30 fps tetap pas di
 * proyek 60 fps. Keyframe memakai bingkai, jadi hanya dibawa bila fps sama.
 */
import { durasiIsi } from './dokumen.js';
import { operasiTemplat } from './templat.js';

export const TEMPLAT_SAYA_MAKS_ITEM = 200;

const salinBila = (i, kunci) => Object.fromEntries(kunci.filter((k) => i[k] != null).map((k) => [k, i[k]]));

/** Kerangka `dokumen` sebagai data templat (murni, bisa dikirim ke server). */
export function ambilTemplat(dokumen) {
  const fps = dokumen.kanvas.fps;
  const d = (bingkai) => Math.round((bingkai / fps) * 1000) / 1000;
  const isi = [];
  let caption = null;
  for (const l of dokumen.lajur) {
    if (l.subtitle) {
      caption = caption ?? l.gaya_caption ?? null;
      continue;
    }
    for (const i of l.item) {
      if (i.jenis === 'teks') {
        isi.push({ jenis: 'teks', teks: i.teks, mulai: d(i.mulai), durasi: d(i.durasi), gaya: i.gaya,
          ...salinBila(i, ['ubah', 'keyframe']) });
      } else if (i.jenis === 'motion') {
        isi.push({ jenis: 'animasi', komponen: i.komponen, versi: i.versi ?? 1, props: i.props ?? {},
          mulai: d(i.mulai), durasi: d(i.durasi), ...salinBila(i, ['ubah', 'keyframe']) });
      }
    }
  }
  isi.sort((a, b) => a.mulai - b.mulai);
  return {
    kanvas: { lebar: dokumen.kanvas.lebar, tinggi: dokumen.kanvas.tinggi, fps },
    detik: d(durasiIsi(dokumen)),
    caption,
    isi: isi.slice(0, TEMPLAT_SAYA_MAKS_ITEM),
    penanda: (dokumen.penanda ?? []).map((p) => ({ t: d(p.t), label: p.label || '' })),
  };
}

/** Templat ini punya isi yang bisa dipakai (tidak kosong)? */
export function templatBerisi(tpl) {
  return Boolean(tpl && (tpl.isi?.length || tpl.penanda?.length || tpl.caption));
}

/**
 * Operasi usulan dari templat milik sendiri, diletakkan SESUDAH isi proyek
 * yang sudah ada (sama dengan templat bawaan). `teks(kunci)` menerjemahkan
 * alasan (t dari useT).
 */
export function operasiTemplatSaya(dokumen, tpl, teks = (k) => k) {
  if (!templatBerisi(tpl)) return [];
  const fps = dokumen.kanvas.fps;
  const f = (detik) => Math.max(0, Math.round((detik || 0) * fps));
  const isiAda = durasiIsi(dokumen);
  const awal = isiAda > 1 ? isiAda : 0;
  const fpsSama = tpl.kanvas?.fps === fps;
  const ops = [];
  const op = (isi) => ops.push({ id: `s${ops.length + 1}`, kelompok: tpl.nama || teks('templat_saya'),
    alasan: teks('alasan_saya'), ...isi });
  if (tpl.caption) op({ jenis: 'lajur_caption', label: teks('caption'), preset: tpl.caption });
  for (const i of tpl.isi ?? []) {
    const umum = { mulai: awal + f(i.mulai), durasi: Math.max(1, f(i.durasi)) };
    if (i.ubah) umum.ubah = i.ubah;
    if (i.keyframe && fpsSama) umum.keyframe = i.keyframe;
    if (i.jenis === 'teks') {
      op({ jenis: 'teks', label: String(i.teks ?? '').slice(0, 40), teks: i.teks ?? '', gaya: i.gaya, ...umum });
    } else if (i.jenis === 'animasi' && i.komponen) {
      op({ jenis: 'animasi', label: i.komponen, komponen: i.komponen, versi: i.versi ?? 1, props: i.props ?? {}, ...umum });
    }
  }
  for (const p of tpl.penanda ?? []) op({ jenis: 'penanda', label: p.label, t: awal + f(p.t) });
  return ops;
}

/** Awalan nilai pilihan untuk templat milik sendiri ("saya:<id>"). */
export const AWALAN_SAYA = 'saya:';

/**
 * Operasi dari nilai pilihan PilihTemplat: id templat bawaan, atau
 * "saya:<id>" yang dicari di `milik` (daftar dari server).
 */
export function operasiPilihan(dokumen, nilai, variasi, milik, teks) {
  if (!nilai) return [];
  if (nilai.startsWith(AWALAN_SAYA)) {
    const tpl = (milik ?? []).find((x) => x.id === nilai.slice(AWALAN_SAYA.length));
    return tpl ? operasiTemplatSaya(dokumen, tpl, teks) : [];
  }
  return operasiTemplat(dokumen, nilai, variasi, teks);
}
