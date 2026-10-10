import React, { useState } from 'react';
import { Loader2, ZoomIn, Trash2, Plus, Crosshair } from 'lucide-react';
import { apiPost } from '../../lib/api';
import { formatTime } from '../../utils/timeFormat';

/**
 * Punch-in zoom (JOB-2 F2-1): gambar membesar sekejap di momen yang keras,
 * seperti editor manusia memperbesar bidikan saat orang tertawa atau
 * berteriak. Titiknya USULAN dari kekerasan suara klip; bisa dihapus, digeser
 * ke posisi pemutar, atau ditambah sendiri. Hanya gambarnya yang membesar,
 * subtitle dan tulisan tidak.
 */
export default function PunchPanel({ clip, videoId, waktuSekarang = 0, onChange, onSeek }) {
  const [sibuk, setSibuk] = useState(false);
  const [galat, setGalat] = useState('');
  const [catatan, setCatatan] = useState('');
  if (!clip) return null;
  const titik = clip.punch_in ?? [];
  const ubah = (i, patch) => onChange(titik.map((p, j) => (j === i ? { ...p, ...patch } : p)));

  const cari = async () => {
    setSibuk(true); setGalat(''); setCatatan('');
    try {
      const r = await apiPost('/clip-punch-in', {
        video_id: videoId,
        segments: (clip.segments || []).map((s) => ({ start: s.start, end: s.end })),
      }, { timeout: 120000 });
      const baru = r.titik || [];
      onChange(baru);
      setCatatan(baru.length ? `${baru.length} momen ditemukan.`
        : 'Tidak ada lonjakan suara yang cukup jelas di klip ini.');
    } catch (e) {
      setGalat(e.message || 'Gagal mencari momen.');
    } finally { setSibuk(false); }
  };

  return (
    <div style={{ borderTop: '1px solid var(--line)', marginTop: '14px', paddingTop: '12px',
                  display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <b style={{ fontSize: '.84rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
        <ZoomIn size={14} /> Punch-in
      </b>
      <span style={{ fontSize: '.74rem', color: 'var(--ink-3)', lineHeight: 1.5 }}>
        Gambar membesar sekejap saat suaranya melonjak (tawa, teriakan, penekanan). Subtitle dan
        tulisan tidak ikut membesar.
      </span>
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
        <button className="btn-secondary" onClick={cari} disabled={sibuk}>
          {sibuk ? <Loader2 size={13} className="animate-spin" /> : <ZoomIn size={13} />}
          {sibuk ? 'Mendengarkan klip…' : 'Cari momen otomatis'}
        </button>
        <button className="btn-secondary"
                onClick={() => onChange([...titik, { t: Math.round(waktuSekarang * 100) / 100,
                                                      dur: 1, skala: 1.15, asal: 'pengguna' }]
                  .sort((a, b) => a.t - b.t))}>
          <Plus size={13} /> Di posisi pemutar ({formatTime(waktuSekarang)})
        </button>
      </div>
      {galat && <div style={{ fontSize: '.74rem', color: 'var(--danger)' }}>{galat}</div>}
      {catatan && <div style={{ fontSize: '.74rem', color: 'var(--ink-3)' }}>{catatan}</div>}
      {titik.map((p, i) => (
        <div key={`${p.t}-${i}`} style={{ display: 'flex', gap: '6px', alignItems: 'center',
                                         fontSize: '.76rem', flexWrap: 'wrap' }}>
          <button className="btn-secondary" style={{ padding: '2px 7px', fontSize: '.74rem' }}
                  onClick={() => onSeek?.(p.t)} title="Lihat di pemutar">
            {formatTime(p.t)}
          </button>
          <select className="field" value={String(p.skala ?? 1.15)}
                  style={{ width: 'auto', padding: '2px 6px', fontSize: '.74rem' }}
                  onChange={(e) => ubah(i, { skala: Number(e.target.value) })}>
            <option value="1.1">Halus</option>
            <option value="1.15">Sedang</option>
            <option value="1.25">Kuat</option>
          </select>
          <select className="field" value={String(p.dur ?? 1)}
                  style={{ width: 'auto', padding: '2px 6px', fontSize: '.74rem' }}
                  onChange={(e) => ubah(i, { dur: Number(e.target.value) })}>
            <option value="0.6">0,6 dtk</option>
            <option value="1">1 dtk</option>
            <option value="2">2 dtk</option>
          </select>
          <button className="btn-secondary" style={{ padding: '2px 6px' }} title="Pindah ke posisi pemutar"
                  onClick={() => ubah(i, { t: Math.round(waktuSekarang * 100) / 100, asal: 'pengguna' })}>
            <Crosshair size={12} />
          </button>
          <button className="btn-secondary" style={{ padding: '2px 6px' }} title="Hapus"
                  onClick={() => onChange(titik.filter((_, j) => j !== i))}>
            <Trash2 size={12} />
          </button>
          {p.alasan && <span style={{ color: 'var(--ink-3)' }}>{p.alasan}</span>}
        </div>
      ))}
    </div>
  );
}
