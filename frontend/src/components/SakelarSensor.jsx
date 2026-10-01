import React, { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { apiGet, apiPost } from '../lib/api';

/**
 * Sakelar sensor kata kasar, dipakai di dua tempat.
 *
 * Satu komponen untuk panel Subtitle dan halaman Pengaturan, karena sakelarnya
 * SATU: yang diubah di Studio langsung berlaku di Pengaturan dan sebaliknya.
 * Dua komponen berarti dua tempat yang bisa menampilkan keadaan berbeda untuk
 * setelan yang sama.
 *
 * Sakelar ini menyensor TEKS yang terbakar ke video dan yang tampil di
 * pratinjau; suaranya tidak disentuh.
 */
export default function SakelarSensor({ ringkas = false }) {
  const [aktif, setAktif] = useState(null);
  const [sibuk, setSibuk] = useState(false);

  useEffect(() => {
    let batal = false;
    apiGet('/settings')
      .then((r) => { if (!batal) setAktif(r?.sensor_kata_kasar !== false); })
      .catch(() => { if (!batal) setAktif(true); });
    return () => { batal = true; };
  }, []);

  const ubah = async (nilai) => {
    const sebelum = aktif;
    setAktif(nilai);
    setSibuk(true);
    try {
      await apiPost('/settings/sensor-kata-kasar', { aktif: nilai });
    } catch {
      setAktif(sebelum);          // gagal disimpan: jangan berbohong di layar
    } finally {
      setSibuk(false);
    }
  };

  const menyala = aktif === true;
  return (
    <div style={{
      border: `1px solid ${menyala ? 'var(--rule-2)' : 'var(--rule-2)'}`,
      borderRadius: 'var(--r-sm)', padding: ringkas ? '9px 11px' : '11px 13px',
      background: 'var(--plate-3)',
    }}>
      <label style={{ display: 'flex', alignItems: 'center', gap: '9px', cursor: 'pointer' }}>
        <input type="checkbox" checked={menyala} disabled={aktif === null || sibuk}
               onChange={(e) => ubah(e.target.checked)}
               style={{ width: '15px', height: '15px', flex: 'none' }} />
        <b style={{ fontSize: '0.82rem', flex: 1 }}>Sensor kata kasar</b>
        {sibuk && <Loader2 size={12} className="animate-spin" style={{ color: 'var(--ink-3)' }} />}
        <span style={{
          fontSize: '0.64rem', fontWeight: 800, padding: '2px 8px', borderRadius: '99px',
          flex: 'none',
          background: menyala ? 'var(--reh)' : 'var(--bg-glass)',
          color: menyala ? '#fff' : 'var(--text-muted)',
        }}>
          {aktif === null ? '…' : menyala ? 'NYALA' : 'MATI'}
        </span>
      </label>
      <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', margin: '6px 0 0',
                  lineHeight: 1.55 }}>
        {menyala
          ? 'Umpatan keras ditutup satu huruf di tengahnya: "anjing" jadi "anj*ng". '
            + 'Penonton tetap membacanya, tapi mesin penyaring tidak menemukan kata '
            + 'utuhnya. Suaranya tidak disentuh.'
          : 'Teks ditampilkan apa adanya. Klip yang subtitle-nya memuat umpatan utuh '
            + 'sering diturunkan jangkauannya oleh YouTube, TikTok, dan Instagram.'}
      </p>
      {!ringkas && (
        <p style={{ fontSize: '0.7rem', color: 'var(--text-muted)', margin: '6px 0 0',
                    lineHeight: 1.5 }}>
          Umpatan ringan sengaja dibiarkan: babi, cok, cuk, anjir, bodoh, bego,
          setan, gila.
        </p>
      )}
    </div>
  );
}
