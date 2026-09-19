import { useEffect, useRef } from 'react';
import { apiGet } from '../lib/api';

/**
 * Memuat ulang halaman sendiri ketika build di server sudah berganti.
 *
 * Ada karena satu kelas kebingungan yang terus berulang dan selalu terlihat
 * persis seperti "perbaikannya tidak dikerjakan": peramban memegang bundel
 * lama, aplikasi berjalan dengan kode lama, dan tidak ada apa pun di layar yang
 * memberi tahu. index.html memang disajikan `no-cache`, tapi itu hanya mengatur
 * permintaan BERIKUTNYA — tab yang sudah terbuka sejak sebelum build baru tidak
 * pernah menanyakannya lagi, dan bisa bertahan berhari-hari.
 *
 * Diperiksa saat tab kembali difokuskan, bukan dengan pewaktu: saat itulah
 * orang kembali dari melakukan hal lain, dan itu satu-satunya saat memuat ulang
 * tidak mengganggu apa pun yang sedang dikerjakannya.
 */
export default function useBuildWatch() {
  const awal = useRef(null);
  const sudahMuatUlang = useRef(false);

  useEffect(() => {
    let batal = false;

    const periksa = async () => {
      if (batal || sudahMuatUlang.current) return;
      let build;
      try {
        build = (await apiGet('/build'))?.build;
      } catch {
        return;                       // backend belum siap: bukan urusan sini
      }
      if (!build) return;
      if (awal.current === null) { awal.current = build; return; }
      if (build !== awal.current) {
        sudahMuatUlang.current = true;
        // `true` sudah lama diabaikan peramban; yang benar-benar melewati cache
        // adalah memuat URL yang sama lagi setelah index.html dinyatakan basi
        // oleh header no-cache-nya sendiri.
        window.location.reload();
      }
    };

    periksa();
    const saatFokus = () => { if (document.visibilityState === 'visible') periksa(); };
    window.addEventListener('focus', saatFokus);
    document.addEventListener('visibilitychange', saatFokus);
    return () => {
      batal = true;
      window.removeEventListener('focus', saatFokus);
      document.removeEventListener('visibilitychange', saatFokus);
    };
  }, []);
}
