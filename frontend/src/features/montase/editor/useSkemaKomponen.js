/**
 * Skema props item animasi terpilih (JOB-4 M4.5): animasi bawaan dihitung di
 * sini, komponen AI diminta dari iframe kotak pasir (kode AI tidak pernah
 * berjalan di editor). Disimpan per `id@versi` untuk satu sesi.
 */
import { useEffect, useState } from 'react';
import { BAWAAN } from '../komposisi/index.js';
import { contohAman, skemaJson } from '../komposisi/skemaJson.js';
import { alamatKodeKomponen } from '../api.js';

const simpanan = new Map();

export default function useSkemaKomponen(item, pratinjau, token) {
  const kunci = item?.jenis === 'motion' ? `${item.komponen}@${item.versi ?? 1}` : null;
  const [, setVersi] = useState(0);
  useEffect(() => {
    if (!kunci || simpanan.has(kunci)) return undefined;
    const bawaan = BAWAAN[item.komponen];
    if (bawaan) {
      simpanan.set(kunci, { skema: skemaJson(bawaan), contoh: contohAman(bawaan), galat: null });
      setVersi((v) => v + 1);
      return undefined;
    }
    if (!token || !pratinjau.current?.mintaSkema) return undefined;
    let hidup = true;
    simpanan.set(kunci, null);
    pratinjau.current.mintaSkema(kunci, alamatKodeKomponen(token, item.komponen, item.versi ?? 1))
      .then((h) => {
        if (h.galat) simpanan.delete(kunci);
        else simpanan.set(kunci, h);
        if (hidup) setVersi((v) => v + 1);
      });
    return () => { hidup = false; };
  }, [kunci, item?.komponen, item?.versi, pratinjau, token]);
  return kunci ? simpanan.get(kunci) ?? null : null;
}
