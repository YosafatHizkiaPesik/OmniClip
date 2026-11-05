/**
 * Kisi preset caption subtitle (JOB-5 P1). Contoh tiap preset digambar dengan
 * CSS biasa di halaman editor (bukan di kotak pasir), jadi hanya perkiraan
 * rupa: warna, pelat, garis, dan cara kata aktif disorot. Wujud sebenarnya
 * terlihat di pratinjau begitu diterapkan.
 */
import React from 'react';
import { useT } from '../../../lib/i18n';
import { PRESET_CAPTION } from '../model/presetCaption.js';

function Contoh({ g }) {
  const kalimat = ['KATA', 'AKTIF'];
  const huruf = {
    fontFamily: `"${g.font}", sans-serif`, fontWeight: 800, color: g.warna, fontSize: '.78rem',
    textTransform: g.kapital ? 'uppercase' : 'none',
    // Garis digambar di luar huruf (paint-order), setipis yang masih terlihat di ukuran sekecil ini.
    WebkitTextStroke: g.garis ? `${Math.min(2, g.garis / 3)}px ${g.warna_garis}` : undefined,
    paintOrder: 'stroke fill',
    textShadow: g.kabur ? `0 0 6px ${g.warna_garis}` : (g.bayang ? '2px 2px 0 rgba(0,0,0,.6)' : undefined),
  };
  const pelat = g.latar === 'pelat' || g.latar === 'sorot' || g.latar === 'pita'
    ? { background: g.warna_latar, opacity: 1, borderRadius: g.latar === 'pita' ? 0 : 6, padding: '2px 6px' } : {};
  const aktif = !g.warna_sorot ? {} : g.sorot === 'kotak'
    ? { background: g.warna_sorot, borderRadius: 4, padding: '0 3px' }
    : { color: g.warna_sorot, display: 'inline-block', transform: g.sorot === 'besar' ? 'scale(1.15)' : undefined };
  return (
    <span className="montase-caption-contoh" style={{ ...huruf, ...pelat }}>
      {kalimat[0]} <span style={aktif}>{kalimat[1]}</span>
    </span>
  );
}

export default function KisiCaption({ aktif, onPilih, disabled }) {
  const t = useT();
  return (
    <div className="montase-kisi-caption" role="group" aria-label={t('montase.caption.judul')}>
      {PRESET_CAPTION.map((p) => (
        <button key={p.id} type="button" className={`montase-caption-pilihan ${aktif === p.id ? 'aktif' : ''}`}
                onClick={() => onPilih(p.id)} disabled={disabled} aria-pressed={aktif === p.id}
                title={t(`montase.caption.${p.id}`)}
        >
          <Contoh g={p.gaya} />
          <small>{t(`montase.caption.${p.id}`)}</small>
        </button>
      ))}
    </div>
  );
}
