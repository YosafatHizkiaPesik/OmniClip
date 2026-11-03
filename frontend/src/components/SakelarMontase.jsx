import React, { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { useT } from '../lib/i18n';
import { ambilSetelan, simpanSetelan } from '../features/montase/api.js';
import { PERISTIWA_SETELAN } from '../features/montase/setelan.js';

/**
 * Sakelar "Montase (beta)" di Pengaturan (JOB-4 M1.4). Bentuknya sama dengan
 * SakelarSensor di halaman yang sama. Mematikannya hanya menyembunyikan menu;
 * proyek dan bahan tidak disentuh.
 */
export default function SakelarMontase() {
  const t = useT();
  const [aktif, setAktif] = useState(null);
  const [sibuk, setSibuk] = useState(false);

  useEffect(() => {
    let batal = false;
    ambilSetelan()
      .then((r) => { if (!batal) setAktif(r?.aktif !== false); })
      .catch(() => { if (!batal) setAktif(true); });
    return () => { batal = true; };
  }, []);

  const ubah = async (nilai) => {
    const sebelum = aktif;
    setAktif(nilai);
    setSibuk(true);
    try {
      await simpanSetelan(nilai);
      window.dispatchEvent(new Event(PERISTIWA_SETELAN));
    } catch {
      setAktif(sebelum);
    } finally {
      setSibuk(false);
    }
  };

  const menyala = aktif === true;
  return (
    <div style={{
      border: '1px solid var(--rule-2)', borderRadius: 'var(--r-sm)', padding: '11px 13px',
      background: 'var(--plate-3)',
    }}
    >
      <label style={{ display: 'flex', alignItems: 'center', gap: '9px', cursor: 'pointer' }}>
        <input
          type="checkbox"
          checked={menyala}
          disabled={aktif === null || sibuk}
          onChange={(e) => ubah(e.target.checked)}
          style={{ width: '15px', height: '15px', flex: 'none' }}
        />
        <b style={{ fontSize: '0.82rem', flex: 1 }}>{t('montase.setelan.judul')}</b>
        {sibuk && <Loader2 size={12} className="animate-spin" style={{ color: 'var(--ink-3)' }} />}
        <span style={{
          fontSize: '0.64rem', fontWeight: 800, padding: '2px 8px', borderRadius: '99px',
          flex: 'none',
          background: menyala ? 'var(--reh)' : 'var(--bg-glass)',
          color: menyala ? '#fff' : 'var(--text-muted)',
        }}
        >
          {aktif === null ? '…' : menyala ? t('umum.nyala') : t('umum.mati')}
        </span>
      </label>
      <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', margin: '6px 0 0', lineHeight: 1.55 }}>
        {t('montase.setelan.ket')}
      </p>
    </div>
  );
}
