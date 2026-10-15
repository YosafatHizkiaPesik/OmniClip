import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CheckCircle2, Loader2, Scissors, X } from 'lucide-react';
import { apiPost } from '../lib/api';
import { useT } from '../lib/i18n';
import { VideoCard } from './VideoCards';

/**
 * Kisi kartu video gaya YouTube dengan kotak centang "klip banyak sekaligus".
 * Dipakai halaman Channel, Langganan, dan Riwayat (JOB-3). Klik kartu membuka
 * halaman tonton; bila ada yang dicentang, klik kartu menambah/mengurangi
 * pilihan.
 */
export default function KisiVideo({ video, vertikal = false, aksiKartu }) {
  const t = useT();
  const navigate = useNavigate();
  const [pilih, setPilih] = useState(new Set());
  const [mengantre, setMengantre] = useState(false);
  const [hasil, setHasil] = useState(null);

  const toggle = (id) => setPilih((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id); else n.add(id);
    return n;
  });

  const klipSemua = async () => {
    setMengantre(true);
    let masuk = 0; let sudah = 0; let gagal = 0;
    for (const id of pilih) {
      try {
        // eslint-disable-next-line no-await-in-loop
        const r = await apiPost('/auto-clip', {
          video_id: id,
          max_clips: Number(localStorage.getItem('omniclip_max_clips') || 0),
          whisper_model: localStorage.getItem('omniclip_whisper_model') || 'base',
          gemini_model: localStorage.getItem('omniclip_gemini_model') || null,
        });
        if (r.cached) sudah += 1; else masuk += 1;
      } catch { gagal += 1; }
    }
    setPilih(new Set());
    setMengantre(false);
    setHasil({ masuk, sudah, gagal });
  };

  return (
    <>
      <div style={{ display: 'grid', gap: '20px 16px',
                    gridTemplateColumns: `repeat(auto-fill, minmax(${vertikal ? 190 : 280}px, 1fr))` }}>
        {video.map((v) => (
          <div key={v.id} style={{ position: 'relative' }}>
            <VideoCard video={v} vertikal={vertikal} isSelected={pilih.has(v.id)}
                       onClick={() => (pilih.size ? toggle(v.id)
                         : navigate(`/watch/${v.id}`, { state: { video: v } }))} />
            <label onClick={(e) => e.stopPropagation()} title={t('kisi.pilih')}
                   style={{
                     position: 'absolute', top: 8, left: 8, zIndex: 2, display: 'flex',
                     alignItems: 'center', justifyContent: 'center', width: 26, height: 26,
                     borderRadius: 7, cursor: 'pointer',
                     background: pilih.has(v.id) ? 'var(--accent-cyan)' : 'rgba(0,0,0,0.55)',
                     border: '1px solid rgba(255,255,255,0.35)',
                   }}>
              <input type="checkbox" checked={pilih.has(v.id)} onChange={() => toggle(v.id)}
                     style={{ margin: 0, accentColor: 'var(--accent-cyan)', cursor: 'pointer' }} />
            </label>
            {aksiKartu && aksiKartu(v)}
          </div>
        ))}
      </div>

      {pilih.size > 0 && (
        <div className="bilah-aksi">
          <span style={{ fontSize: '0.8rem', fontWeight: 700 }}>{t('kisi.dipilih', { n: pilih.size })}</span>
          <button className="btn-primary" onClick={klipSemua} disabled={mengantre}
                  style={{ fontSize: '0.8rem', display: 'inline-flex', gap: 6, alignItems: 'center' }}>
            {mengantre ? <Loader2 size={14} className="animate-spin" /> : <Scissors size={14} />}
            {mengantre ? t('kisi.mengantre') : t('kisi.klip_semua')}
          </button>
          <button onClick={() => setPilih(new Set())} aria-label={t('kisi.batal')}
                  style={{ background: 'none', border: 'none', cursor: 'pointer',
                           color: 'var(--text-muted)', display: 'flex' }}>
            <X size={16} />
          </button>
        </div>
      )}
      {hasil && (
        <div className="bilah-aksi" onClick={() => setHasil(null)} style={{ cursor: 'pointer' }}>
          <CheckCircle2 size={15} style={{ color: 'var(--entry)' }} />
          {t('kisi.hasil', hasil)}
        </div>
      )}
    </>
  );
}
