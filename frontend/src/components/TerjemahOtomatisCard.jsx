import React, { useEffect, useState } from 'react';
import { Languages } from 'lucide-react';
import { apiGet, apiPost } from '../lib/api';

/**
 * Terjemahan otomatis untuk video berbahasa asing.
 *
 * Anime Jepang atau video Inggris: subtitle ASLINYA tetap tampil — pemiliknya
 * menilai itu lebih menarik — dan terjemahannya dipasang di bawahnya sebagai
 * subtitle kedua, langsung saat video dianalisis.
 */
export default function TerjemahOtomatisCard({ card, sectionTitle, helpText }) {
  const [bahasa, setBahasa] = useState(null);
  const [daftar, setDaftar] = useState([]);
  const [simpan, setSimpan] = useState(null);

  useEffect(() => {
    apiGet('/settings/terjemah-otomatis').then((r) => setBahasa(r.bahasa ?? '')).catch(() => setBahasa(''));
    apiGet('/settings/languages').then((r) => setDaftar(r.common ?? [])).catch(() => {});
  }, []);

  const pilih = async (v) => {
    setBahasa(v);
    try {
      await apiPost('/settings/terjemah-otomatis', { bahasa: v });
      setSimpan('Tersimpan.');
      setTimeout(() => setSimpan(null), 2000);
    } catch (e) {
      setSimpan(e.message);
    }
  };

  const pilihan = daftar.length ? daftar : [{ code: 'id', label: 'Indonesia' }, { code: 'en', label: 'Inggris' }];
  return (
    <div style={card}>
      <div style={sectionTitle}>
        <Languages size={18} style={{ color: 'var(--reh)' }} />
        Terjemahan otomatis
      </div>
      <p style={helpText}>
        Video yang bahasanya berbeda — misalnya anime berbahasa Jepang — langsung
        diberi subtitle terjemahan di bawah subtitle aslinya saat dianalisis. Tanpa
        kunci Gemini pun tetap jalan (lewat Google Terjemahan).
      </p>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginTop: '10px', flexWrap: 'wrap' }}>
        <select value={bahasa ?? ''} disabled={bahasa === null} onChange={(e) => pilih(e.target.value)}
                style={{ padding: '7px 10px', fontSize: '0.8rem', fontFamily: 'inherit',
                         borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)',
                         background: 'transparent', color: 'var(--ink)' }}>
          <option value="">Mati — hanya subtitle asli</option>
          {pilihan.map((b) => <option key={b.code} value={b.code}>Terjemahkan ke {b.label}</option>)}
        </select>
        {simpan && <span style={helpText}>{simpan}</span>}
      </div>
    </div>
  );
}
