import React, { useEffect, useState } from 'react';
import { AudioLines } from 'lucide-react';
import { apiGet, apiPost } from '../lib/api';

import { useT } from '../lib/i18n';
const PILIHAN = [
  {
    id: 'mati', label: 'suara.mati', nota: 'suara.mati_ket',
  },
  {
    id: 'seimbang', label: 'suara.seimbang', nota: 'suara.seimbang_ket',
  },
  {
    id: 'bersih', label: 'suara.bersih', nota: 'suara.bersih_ket',
  },
];

/** Perapian suara saat render. Berlaku untuk semua render berikutnya. */
export default function SuaraCard({ card, sectionTitle, helpText }) {
  const t = useT();
  const [nilai, setNilai] = useState(null);
  const [kabar, setKabar] = useState(null);

  useEffect(() => {
    apiGet('/settings').then((r) => setNilai(r.render_suara || 'seimbang'))
      .catch(() => setNilai('seimbang'));
  }, []);

  const pilih = async (v) => {
    const sebelumnya = nilai;
    setNilai(v);
    try {
      await apiPost('/settings/suara', { nilai: v });
      setKabar(t('umum.tersimpan_render'));
      setTimeout(() => setKabar(null), 2500);
    } catch (e) {
      setNilai(sebelumnya);
      setKabar(e.message);
    }
  };

  return (
    <div style={card}>
      <div style={sectionTitle}>
        <AudioLines size={18} style={{ color: 'var(--reh)' }} />
        {t('suara.judul')}
      </div>
      <p className="bantu" style={helpText}>
        {t('suara.ket')}
      </p>
      <div style={{ marginTop: '10px' }}>
        {PILIHAN.map((p) => (
          <label key={p.id} style={{
            display: 'flex', gap: '9px', alignItems: 'flex-start', cursor: 'pointer',
            padding: '8px 0', borderTop: '1px solid var(--border-color)',
          }}>
            <input type="radio" name="suara" checked={nilai === p.id}
                   onChange={() => pilih(p.id)} disabled={nilai === null}
                   style={{ marginTop: '3px', accentColor: 'var(--reh)' }} />
            <span>
              <span style={{ fontSize: '0.79rem', fontWeight: 700 }}>{t(p.label)}</span>
              <span style={{ ...helpText, display: 'block', marginTop: '2px' }}>{t(p.nota)}</span>
            </span>
          </label>
        ))}
      </div>
      {kabar && <p style={{ ...helpText, marginTop: '8px' }}>{kabar}</p>}
    </div>
  );
}
