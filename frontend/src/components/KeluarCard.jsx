import React, { useState } from 'react';
import { AlertTriangle, Loader2, Power } from 'lucide-react';
import { apiPost } from '../lib/api';

import { useT } from '../lib/i18n';
/**
 * Mematikan OmniClip dari halamannya sendiri.
 *
 * Ada sejak jendela konsol disembunyikan di Windows. Selama konsolnya terlihat,
 * "tutup jendela itu" adalah jawaban yang jelas; tanpa konsol, satu-satunya
 * cara lain adalah Task Manager — dan pengguna yang harus membuka Task Manager
 * untuk menutup aplikasinya akan menyimpulkan aplikasinya rusak.
 */
export default function KeluarCard({ card, sectionTitle, helpText }) {
  const t = useT();
  const [sibuk, setSibuk] = useState(false);
  const [mati, setMati] = useState(false);
  const [galat, setGalat] = useState(null);

  const keluar = async () => {
    if (!window.confirm(
      t('keluar.yakin'))) return;
    setSibuk(true);
    setGalat(null);
    try {
      await apiPost('/settings/mati', {});
      setMati(true);
    } catch (e) {
      setGalat(e.message);
      setSibuk(false);
    }
  };

  if (mati) {
    return (
      <div style={card}>
        <div style={sectionTitle}>
          <Power size={18} style={{ color: 'var(--entry)' }} />
          {t('keluar.berhenti')}
        </div>
        <p className="bantu" style={helpText}>
          {t('keluar.berhenti_ket')}
        </p>
      </div>
    );
  }

  return (
    <div style={card}>
      <div style={sectionTitle}>
        <Power size={18} style={{ color: 'var(--reh)' }} />
        {t('keluar.judul')}
      </div>
      <p className="bantu" style={helpText}>
        {t('keluar.ket')}
      </p>
      <button className="btn-secondary" onClick={keluar} disabled={sibuk}
              style={{ marginTop: '12px', display: 'inline-flex', gap: '7px',
                       alignItems: 'center', color: 'var(--danger)' }}>
        {sibuk ? <Loader2 size={15} className="animate-spin" /> : <Power size={15} />}
        {t('keluar.matikan')}
      </button>
      {galat && (
        <div style={{ ...helpText, marginTop: '10px', color: 'var(--accent-red)',
                      display: 'flex', alignItems: 'center', gap: '7px' }}>
          <AlertTriangle size={15} />{galat}
        </div>
      )}
    </div>
  );
}
