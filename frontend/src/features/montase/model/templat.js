/**
 * Templat video bawaan (JOB-5 P3).
 *
 * Templat = kerangka video sebagai OPERASI USULAN (model/usulan.js): kartu dan
 * animasi, judul, label nama, bilah progres, ajakan berlangganan, gaya
 * caption, dan PENANDA bernama di tempat klip harus ditaruh. Diterima atau
 * ditolak seperti usulan asisten; tidak ada yang menulis dokumen langsung.
 *
 * Setiap templat punya tiga VARIASI (warna, gaya caption, animasi pembuka).
 * Kebijakan konten tidak autentik YouTube menilai pola kanal; templat yang
 * dipakai persis sama di setiap video adalah pola itu, dan pemeriksa
 * kemiripan (O3) akan memperingatkannya. Variasi membuat titik awal berbeda
 * tanpa harus menyusun dari nol.
 *
 * Bila proyek sudah berisi, kerangka diletakkan SESUDAH isi yang ada.
 */
import { durasiIsi } from './dokumen.js';

const WARNA = [
  ['#FF3355', '#FFB800', '#22C55E', '#3B82F6', '#A855F7'],
  ['#00E5FF', '#7C3AED', '#F472B6', '#FACC15', '#34D399'],
  ['#F97316', '#EF4444', '#EAB308', '#84CC16', '#06B6D4'],
];
const CAPTION = {
  top_n: ['pantul', 'kotak_ungu', 'tebal_bayang'],
  reaksi: ['kotak_ungu', 'stiker', 'sorot_kuning'],
  podcast: ['sorot_kuning', 'kotak_hijau', 'sinema'],
  edukasi: ['sinema', 'minimal', 'berita'],
  sebelum_sesudah: ['minimal', 'neon', 'tebal_bayang'],
};

export const TEMPLAT = [
  { id: 'top_n', detik: 50 },
  { id: 'reaksi', detik: 45 },
  { id: 'podcast', detik: 60 },
  { id: 'edukasi', detik: 45 },
  { id: 'sebelum_sesudah', detik: 20 },
];

/**
 * Operasi kerangka untuk templat `id`, variasi 0..2. `teks(kunci, isi)`
 * menerjemahkan teks contoh (t dari useT), supaya model tetap murni.
 */
export function operasiTemplat(dokumen, id, variasi = 0, teks = (k) => k) {
  const tpl = TEMPLAT.find((x) => x.id === id);
  if (!tpl) return [];
  const fps = dokumen.kanvas.fps;
  const v = ((variasi % 3) + 3) % 3;
  const warna = WARNA[v];
  const f = (detik) => Math.round(detik * fps);
  const awal = durasiIsi(dokumen) > 1 ? durasiIsi(dokumen) : 0;
  const ops = [];
  const op = (isi) => ops.push({ id: `t${ops.length + 1}`, kelompok: teks(`nama_${id}`), alasan: teks(`alasan_${isi.jenis}`), ...isi });
  const judulAtas = (isi, dari, lama) => op({
    jenis: 'teks', label: isi, teks: isi, mulai: awal + f(dari), durasi: f(lama),
    gaya: { letak: 'atas', ukuran: 92, kapital: true, latar: 'pelat', warna_latar: warna[0], warna: '#ffffff', gerak: 'pop' },
  });
  const penanda = (dari, label) => op({ jenis: 'penanda', label, t: awal + f(dari) });
  const ajakan = (dari) => op({
    jenis: 'animasi', label: teks('ajakan'), komponen: 'ko_ajakan_langganan', mulai: awal + f(dari), durasi: f(3),
    props: { kanal: teks('kanal'), tombol: 'SUBSCRIBE', sudah: 'SUBSCRIBED', warna: warna[0].toUpperCase() },
  });
  op({ jenis: 'lajur_caption', label: teks('caption'), preset: CAPTION[id][v] });

  if (id === 'top_n') {
    const n = 5;
    for (let k = n; k >= 1; k -= 1) {
      const t0 = (n - k) * 10;
      op({
        jenis: 'animasi', label: `#${k}`, komponen: v === 2 ? 'ko_judul_kinetik' : 'ko_hitung_mundur',
        mulai: awal + f(t0), durasi: f(2),
        props: v === 2 ? { teks: `#${k} ${teks('judul_momen')}`, warna: '#FFFFFF', sorot: warna[k - 1], ukuran: 120, jeda: 6 }
          : { angka: k, judul: teks('judul_momen'), warna: warna[k - 1] },
      });
      penanda(t0 + 2, teks('slot_klip', { n: k }));
    }
    // Satu bilah per bagian supaya segmen yang menyala mengikuti nomor yang sedang tampil.
    for (let k = n; k >= 1; k -= 1) {
      op({ jenis: 'animasi', label: `${teks('bilah_peringkat')} #${k}`, komponen: 'ko_bilah_peringkat',
        mulai: awal + f((n - k) * 10), durasi: f(10), props: { jumlah: n, aktif: k, warna: warna[0], atas: 7 } });
    }
    ajakan(n * 10 - 3);
  } else if (id === 'reaksi') {
    judulAtas(teks('judul_reaksi'), 0, 3);
    penanda(0, teks('slot_tanggapi'));
    penanda(3, teks('slot_reaksi'));
    op({ jenis: 'animasi', label: teks('label_nama'), komponen: 'ko_label_nama', mulai: awal + f(3.5), durasi: f(4),
      props: { nama: teks('nama_anda'), peran: teks('peran_reaksi'), warna: warna[1], bawah: 26 } });
    ajakan(tpl.detik - 3);
  } else if (id === 'podcast') {
    judulAtas(teks('judul_podcast'), 0, 3);
    penanda(0, teks('slot_podcast'));
    op({ jenis: 'animasi', label: teks('label_nama'), komponen: 'ko_label_nama', mulai: awal + f(1), durasi: f(4),
      props: { nama: teks('nama_tamu'), peran: teks('peran_tamu'), warna: warna[2], bawah: 26 } });
    op({ jenis: 'animasi', label: teks('bilah_progres'), komponen: 'ko_bilah_progres', mulai: awal, durasi: f(tpl.detik),
      props: { warna: warna[0], latar: '#000000', tebal: 14, letak: 'atas' } });
    ajakan(tpl.detik - 3);
  } else if (id === 'edukasi') {
    judulAtas(teks('judul_edukasi'), 0, 3);
    penanda(0, teks('slot_edukasi'));
    op({ jenis: 'animasi', label: teks('angka'), komponen: 'ko_angka_naik', mulai: awal + f(12), durasi: f(3),
      props: { angka: 1000, label: teks('keterangan_angka'), warna: warna[1], pemisah: '.' } });
    penanda(12, teks('slot_fakta'));
    ajakan(tpl.detik - 3);
  } else if (id === 'sebelum_sesudah') {
    judulAtas(teks('sebelum'), 0, 9.5);
    penanda(0, teks('slot_sebelum'));
    op({ jenis: 'animasi', label: teks('kilat'), komponen: 'ko_transisi_kilat', mulai: awal + f(9.5), durasi: f(1),
      props: { warna: '#FFFFFF', guncang: 30 } });
    judulAtas(teks('sesudah'), 10, 10);
    penanda(10, teks('slot_sesudah'));
  }
  return ops;
}
