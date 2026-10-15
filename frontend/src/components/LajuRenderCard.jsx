import React, { useEffect, useState } from 'react';
import { Gauge } from 'lucide-react';
import { apiGet, apiPost } from '../lib/api';

import { useT } from '../lib/i18n';
const PILIHAN = [
  {
    id: 'sumber', label: 'fps.sumber', nota: 'fps.sumber_ket',
  },
  {
    id: '30', label: 'fps.30', nota: 'fps.30_ket',
  },
];

/**
 * Laju bingkai hasil render.
 *
 * Sampai 5 Oktober 2026 selalu 30, dipatok di tiga tempat terpisah. Alasannya
 * masuk akal — sumber 60 fps membawa dua kali bingkai yang dibutuhkan melewati
 * setiap filter, lalu separuhnya dibuang begitu sampai ke pengode — tapi yang
 * hilang tidak ikut dihitung.
 *
 * Dilaporkan pemiliknya sesudah mengunggah beberapa video: "kualitasnya jelek
 * meskipun sudah ada tulisan SD dan HD". Terukur pada klip jadinya: 1080x1920
 * dan 13,7 Mbps — resolusi dan bitrate justru baik — tapi 30 fps dari sumber
 * 60 fps.
 */
export default function LajuRenderCard({ card, sectionTitle, helpText }) {
  const t = useT();
  const [nilai, setNilai] = useState(null);
  const [kabar, setKabar] = useState(null);

  useEffect(() => {
    apiGet('/settings').then((r) => setNilai(r.render_fps || 'sumber'))
      .catch(() => setNilai('sumber'));
  }, []);

  const pilih = async (v) => {
    const sebelumnya = nilai;
    setNilai(v);
    try {
      await apiPost('/settings/render-fps', { nilai: v });
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
        <Gauge size={18} style={{ color: 'var(--reh)' }} />
        {t('fps.judul')}
      </div>
      <p className="bantu" style={helpText}>
        {t('fps.ket')}
      </p>
      <div style={{ marginTop: '10px' }}>
        {PILIHAN.map((p) => (
          <label key={p.id} style={{
            display: 'flex', gap: '9px', alignItems: 'flex-start', cursor: 'pointer',
            padding: '8px 0', borderTop: '1px solid var(--border-color)',
          }}>
            <input type="radio" name="laju-render" checked={nilai === p.id}
                   onChange={() => pilih(p.id)} disabled={nilai === null}
                   style={{ marginTop: '3px', accentColor: 'var(--reh)' }} />
            <span>
              <span style={{ fontSize: '0.79rem', fontWeight: 700 }}>{t(p.label)}</span>
              <span style={{ ...helpText, display: 'block', marginTop: '2px' }}>{t(p.nota)}</span>
            </span>
          </label>
        ))}
      </div>
      {kabar && (
        <div style={{ ...helpText, marginTop: '8px', color: 'var(--entry)' }}>{kabar}</div>
      )}
    </div>
  );
}
