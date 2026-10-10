import React, { useEffect, useRef, useState } from 'react';
import { apiGet, apiPut } from '../lib/api';

/**
 * Gaya komentar kanal ini, untuk draf komentar AI di Studio (JOB-2 F1-2).
 *
 * Satu kalimat bebas: cara pemilik kanal biasa bicara ke penontonnya. Tanpa
 * ini drafnya tetap ditulis, tapi dengan gaya umum, dan gaya umum yang sama
 * di semua klip adalah tanda produksi massal yang sedang dihindari.
 *
 * Disimpan di setelan akun yang AKTIF (kelompok `komentar`), menyimpan sendiri
 * sesudah berhenti mengetik, seperti isian lain di halaman ini.
 */
export default function GayaKomentar({ style, bantu }) {
  const [gaya, setGaya] = useState(null);
  const awal = useRef(null);

  useEffect(() => {
    let batal = false;
    apiGet('/profil/setelan')
      .then((r) => {
        if (batal) return;
        const g = r?.setelan?.komentar?.gaya || '';
        awal.current = g;
        setGaya(g);
      })
      .catch(() => { if (!batal) setGaya(''); });
    return () => { batal = true; };
  }, []);

  useEffect(() => {
    if (gaya === null || gaya === awal.current) return undefined;
    const t = setTimeout(() => {
      apiPut('/profil/setelan', { kelompok: 'komentar', nilai: { gaya } })
        .then(() => { awal.current = gaya; })
        .catch(() => {});
    }, 800);
    return () => clearTimeout(t);
  }, [gaya]);

  if (gaya === null) return null;
  return (
    <>
      <div style={{ ...bantu, marginTop: '12px', marginBottom: '4px' }}>
        Gaya komentar Anda, dipakai saat AI menyusun draf komentar di Studio:
      </div>
      <input value={gaya} maxLength={300}
             placeholder='Contoh: santai, pakai "gue", suka nanya balik ke penonton'
             onChange={(e) => setGaya(e.target.value)}
             style={{ ...style, width: '100%' }} />
    </>
  );
}
