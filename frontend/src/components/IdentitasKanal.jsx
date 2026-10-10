import React, { useEffect, useRef, useState } from 'react';
import { apiGet, apiPut } from '../lib/api';

/**
 * Identitas kanal: outro teks, intro, dan outro berkas (JOB-2 F2-5).
 *
 * Bagian yang SELALU sama di kanal ini dan tidak ada di kanal lain, supaya
 * penonton mengenali klipnya. Disimpan di setelan akun yang aktif (kelompok
 * `merek`), menyimpan sendiri sesudah berhenti mengubah.
 *
 * Berkas intro/outro dipilih dari pustaka Sisipan (impor dulu di Studio, tab
 * Sisipan). Intro dibatasi 3 detik oleh server: di video pendek, detik
 * pertama yang menentukan orang bertahan atau pergi.
 */
export default function IdentitasKanal({ style, bantu }) {
  const [nilai, setNilai] = useState(null);
  const [aset, setAset] = useState([]);
  const awal = useRef('');

  useEffect(() => {
    let batal = false;
    apiGet('/profil/setelan')
      .then((r) => {
        if (batal) return;
        const m = { outro_teks: '', intro: '', outro: '', ...(r?.setelan?.merek || {}) };
        awal.current = JSON.stringify(m);
        setNilai(m);
      })
      .catch(() => { if (!batal) setNilai({ outro_teks: '', intro: '', outro: '' }); });
    apiGet('/aset')
      .then((r) => { if (!batal) setAset((r.aset || []).filter((a) => ['video', 'gambar'].includes(a.jenis))); })
      .catch(() => {});
    return () => { batal = true; };
  }, []);

  useEffect(() => {
    if (!nilai) return undefined;
    const cap = JSON.stringify(nilai);
    if (cap === awal.current) return undefined;
    const t = setTimeout(() => {
      apiPut('/profil/setelan', { kelompok: 'merek', nilai })
        .then(() => { awal.current = cap; })
        .catch(() => {});
    }, 800);
    return () => clearTimeout(t);
  }, [nilai]);

  if (!nilai) return null;
  const ubah = (patch) => setNilai((n) => ({ ...n, ...patch }));
  const pilihan = (id) => (
    <select value={nilai[id] || ''} onChange={(e) => ubah({ [id]: e.target.value })}
            style={{ ...style, padding: '5px 8px' }}>
      <option value="">Tanpa {id}</option>
      {aset.map((a) => (
        <option key={a.id} value={a.id}>
          {a.nama} ({a.jenis}{a.durasi ? `, ${Number(a.durasi).toFixed(1)} dtk` : ''})
        </option>
      ))}
    </select>
  );

  return (
    <>
      <div style={{ ...bantu, marginTop: '12px', marginBottom: '4px' }}>
        Penutup setiap klip, tampil di atas bingkai terakhir (kosongkan bila tidak perlu):
      </div>
      <input value={nilai.outro_teks || ''} maxLength={160}
             placeholder="Contoh: Ikuti @namakanal untuk klip lainnya"
             onChange={(e) => ubah({ outro_teks: e.target.value })}
             style={{ ...style, width: '100%' }} />
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '8px', alignItems: 'center' }}>
        <span style={bantu}>Intro (maks. 3 detik):</span> {pilihan('intro')}
        <span style={bantu}>Outro:</span> {pilihan('outro')}
      </div>
      {!aset.length && (
        <div style={{ ...bantu, marginTop: '4px' }}>
          Untuk intro/outro berupa video atau logo, impor berkasnya dulu di Studio, tab Sisipan.
        </div>
      )}
    </>
  );
}
