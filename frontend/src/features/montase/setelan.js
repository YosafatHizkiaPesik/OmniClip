/**
 * Sakelar "Montase (beta)" (JOB-4 M1.4): satu nilai di server, dibaca menu
 * dan halaman Pengaturan. Perubahan dari Pengaturan diumumkan lewat peristiwa
 * jendela supaya menu ikut berubah tanpa memuat ulang halaman.
 */
import { useEffect, useState } from 'react';
import { ambilSetelan } from './api.js';

export const PERISTIWA_SETELAN = 'omniclip:montase';

export function useMontaseAktif() {
  // Bawaan TAMPIL: menu yang muncul sedetik kemudian lebih mengganggu daripada
  // menu yang hilang sedetik kemudian pada sedikit orang yang mematikannya.
  const [aktif, setAktif] = useState(true);
  useEffect(() => {
    let hidup = true;
    const muat = () => ambilSetelan()
      .then((r) => { if (hidup) setAktif(r?.aktif !== false); })
      .catch(() => {});
    muat();
    window.addEventListener(PERISTIWA_SETELAN, muat);
    return () => { hidup = false; window.removeEventListener(PERISTIWA_SETELAN, muat); };
  }, []);
  return aktif;
}
