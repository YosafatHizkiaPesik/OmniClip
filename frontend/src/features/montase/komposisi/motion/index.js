/**
 * Pustaka animasi bawaan (JOB-4 M4.2). Kunci = id komponen di dokumen proyek
 * (`komponen`). Animasi bawaan ikut kode aplikasi dan tidak butuh AI maupun
 * kompilasi. Semuanya ditulis mengikuti kontrak yang sama dengan animasi
 * buatan AI (bagian 21), jadi sekaligus menjadi contoh di prompt AI.
 */
import * as AjakanLangganan from './AjakanLangganan.jsx';
import * as AngkaNaik from './AngkaNaik.jsx';
import * as BilahPeringkat from './BilahPeringkat.jsx';
import * as BilahProgres from './BilahProgres.jsx';
import * as GarisKejut from './GarisKejut.jsx';
import * as HitungMundur from './HitungMundur.jsx';
import * as JudulKinetik from './JudulKinetik.jsx';
import * as LabelNama from './LabelNama.jsx';
import * as LedakanEmoji from './LedakanEmoji.jsx';
import * as LingkaranPanah from './LingkaranPanah.jsx';
import * as TransisiKilat from './TransisiKilat.jsx';

export const BAWAAN = Object.freeze({
  ko_hitung_mundur: HitungMundur,
  ko_judul_kinetik: JudulKinetik,
  ko_label_nama: LabelNama,
  ko_ledakan_emoji: LedakanEmoji,
  ko_garis_kejut: GarisKejut,
  ko_lingkaran_panah: LingkaranPanah,
  ko_ajakan_langganan: AjakanLangganan,
  ko_bilah_peringkat: BilahPeringkat,
  ko_angka_naik: AngkaNaik,
  ko_transisi_kilat: TransisiKilat,
  ko_bilah_progres: BilahProgres,
});
