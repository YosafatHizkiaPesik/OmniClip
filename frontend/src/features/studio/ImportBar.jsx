import React, { useRef, useState } from 'react';
import { AlertTriangle, Link2, Loader2, Sparkles, Upload } from 'lucide-react';
import { apiPost } from '../../lib/api';

/**
 * Memasukkan video baru ke Partitur, dari tautan atau dari komputer sendiri.
 *
 * Tempatnya di sini dan bukan di halaman Cari video karena keduanya menjawab
 * pertanyaan yang berbeda. Cari video untuk "saya belum tahu mau mengklip apa";
 * ini untuk "saya sudah tahu persis videonya" — dan yang kedua tidak seharusnya
 * melewati pencarian lebih dulu. Partitur adalah daftar pekerjaan klip, jadi
 * menambah pekerjaan baru memang di sini tempatnya.
 */
export default function ImportBar({ onDone }) {
  const [tautan, setTautan] = useState('');
  // Panjang klip milik VIDEO INI, bukan milik aplikasi. Nilai di Pengaturan
  // hanya jadi titik awalnya.
  const [sibuk, setSibuk] = useState('');
  const [galat, setGalat] = useState(null);
  const [kabar, setKabar] = useState(null);
  const berkasRef = useRef(null);

  const mulaiKlip = async (videoId, judul) => {
    const res = await apiPost('/auto-clip', {
      video_id: videoId,
      max_clips: Number(localStorage.getItem('omniclip_max_clips') || 0),
      whisper_model: localStorage.getItem('omniclip_whisper_model') || 'base',
      gemini_model: localStorage.getItem('omniclip_gemini_model') || null,
    });
    setKabar(res.cached
      ? `«${judul}» sudah pernah diklip — hasilnya ada di daftar bawah.`
      : `«${judul}» masuk antrean. Kartunya muncul di bawah.`);
    onDone?.();
  };

  const kirimTautan = async (e) => {
    e.preventDefault();
    const nilai = tautan.trim();
    if (!nilai) return;
    setSibuk('tautan'); setGalat(null); setKabar(null);
    try {
      await mulaiKlip(nilai, nilai.slice(0, 40));
      setTautan('');
    } catch (err) {
      setGalat(err.message);
    } finally {
      setSibuk('');
    }
  };

  const kirimBerkas = async (e) => {
    const f = e.target.files?.[0];
    e.target.value = '';           // supaya berkas yang sama bisa dipilih lagi
    if (!f) return;
    setSibuk('berkas'); setGalat(null); setKabar(null);
    try {
      const data = new FormData();
      data.append('berkas', f);
      const hasil = await apiPost('/impor/berkas', data);
      await mulaiKlip(hasil.video_id, hasil.title);
    } catch (err) {
      setGalat(err.message);
    } finally {
      setSibuk('');
    }
  };

  return (
    <div style={{
      background: 'var(--bg-card)', border: '1px solid var(--border-color)',
      borderRadius: 'var(--radius-lg, 14px)', padding: '14px 16px', marginBottom: '18px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
        <Sparkles size={15} style={{ color: 'var(--accent-cyan)' }} />
        <strong style={{ fontSize: '0.86rem' }}>Klip video baru</strong>
      </div>
      <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '0 0 11px' }}>
        Tempel tautan YouTube, atau ambil video dari komputer ini.
      </p>

      <form onSubmit={kirimTautan}
            style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'stretch' }}>
        <div style={{ position: 'relative', flex: '1 1 260px', display: 'flex', alignItems: 'center' }}>
          <Link2 size={15} style={{ position: 'absolute', left: '11px', color: 'var(--text-muted)' }} />
          <input
            value={tautan}
            onChange={(e) => setTautan(e.target.value)}
            placeholder="https://youtube.com/watch?v=…"
            style={{
              width: '100%', padding: '9px 12px 9px 34px', fontSize: '0.83rem',
              background: 'var(--plate-3, rgba(255,255,255,0.04))',
              border: '1px solid var(--rule, var(--border-color))',
              borderRadius: 'var(--r-sm, 8px)', color: 'var(--ink)', outline: 'none',
            }}
          />
        </div>
        <button type="submit" className="btn-primary" disabled={!tautan.trim() || !!sibuk}
                style={{ fontSize: '0.82rem', whiteSpace: 'nowrap' }}>
          {sibuk === 'tautan' ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
          Potong jadi klip
        </button>
        <button type="button" className="btn-secondary" disabled={!!sibuk}
                onClick={() => berkasRef.current?.click()}
                style={{ fontSize: '0.82rem', whiteSpace: 'nowrap' }}>
          {sibuk === 'berkas' ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
          Dari komputer
        </button>
        <input ref={berkasRef} type="file" accept="video/*" hidden onChange={kirimBerkas} />
      </form>

      {sibuk === 'berkas' && (
        <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '9px 0 0' }}>
          Menyalin berkas ke penyimpanan OmniClip… video besar butuh beberapa menit.
        </p>
      )}
      {kabar && (
        <p style={{ fontSize: '0.78rem', color: 'var(--accent-cyan)', margin: '9px 0 0' }}>{kabar}</p>
      )}
      {galat && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '8px', marginTop: '9px',
          fontSize: '0.78rem', color: 'var(--danger)',
        }}>
          <AlertTriangle size={14} style={{ flexShrink: 0 }} /> {galat}
        </div>
      )}
    </div>
  );
}
