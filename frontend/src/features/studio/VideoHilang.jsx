import React, { useEffect, useState } from 'react';
import { AlertTriangle, Download, Loader2 } from 'lucide-react';
import { apiGet, apiPost } from '../../lib/api';

/**
 * Video sumber tidak ada lagi di penyimpanan, padahal klipnya masih ada.
 *
 * Tanpa ini Studio hanya menampilkan dua kotak hitam dan tombol putar yang
 * tidak berbuat apa-apa — terlapor pada video MrBeast yang berkasnya terhapus.
 * Klip, subtitle, dan suntingannya tersimpan terpisah dari berkas videonya,
 * jadi yang hilang cuma videonya, dan itu bisa diambil lagi dari YouTube.
 */
export default function VideoHilang({ videoId, onPulih }) {
  const [jalur, setJalur] = useState([]);
  const [audio, setAudio] = useState('');          // '' = suara asli
  const [kerja, setKerja] = useState(null);        // {progress, message}
  const [galat, setGalat] = useState(null);

  useEffect(() => {
    let batal = false;
    apiGet(`/video-info?url=${encodeURIComponent(videoId)}`)
      .then((info) => { if (!batal) setJalur(info?.audio_tracks ?? []); })
      .catch(() => {});
    return () => { batal = true; };
  }, [videoId]);

  const unduh = async () => {
    setGalat(null);
    setKerja({ progress: 0, message: 'Mengantre…' });
    try {
      const { job_id: jobId } = await apiPost('/download', {
        url: videoId, audio_lang: audio || null,
      });
      for (;;) {
        // eslint-disable-next-line no-await-in-loop
        const job = await apiGet(`/jobs/${jobId}`);
        setKerja({ progress: job.progress ?? 0, message: job.message || 'Mengunduh…' });
        if (job.status === 'done') break;
        if (job.status === 'failed' || job.status === 'cancelled') {
          throw new Error(job.error || 'Unduhan gagal.');
        }
        // eslint-disable-next-line no-await-in-loop
        await new Promise((r) => setTimeout(r, 1200));
      }
      await onPulih?.();
    } catch (err) {
      setGalat(err.message);
    } finally {
      setKerja(null);
    }
  };

  return (
    <div className="plate studio-note" style={{ borderLeftColor: 'var(--warn)', fontSize: '.8rem' }}>
      <div style={{ display: 'flex', gap: '9px', alignItems: 'flex-start' }}>
        <AlertTriangle size={15} style={{ color: 'var(--warn)', flexShrink: 0, marginTop: '2px' }} />
        <div style={{ flex: 1, lineHeight: 1.55 }}>
          <b>Berkas video sumber tidak ada di penyimpanan komputer ini.</b>{' '}
          Klip, subtitle, dan suntingan Anda aman, yang hilang hanya videonya,
          dan itu bisa diunduh lagi dari YouTube.
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap',
                        marginTop: '8px' }}>
            {jalur.length > 1 && (
              <select value={audio} onChange={(e) => setAudio(e.target.value)} disabled={!!kerja}
                      style={{ padding: '5px 8px', fontSize: '0.78rem', borderRadius: '6px',
                               background: 'transparent', color: 'var(--ink)',
                               border: '1px solid var(--border-color)' }}>
                {jalur.map((j) => (
                  <option key={j.lang} value={j.asli ? '' : j.lang}>
                    Suara {j.nama}{j.asli ? ' (asli)' : ''}
                  </option>
                ))}
              </select>
            )}
            <button className="btn-primary" onClick={unduh} disabled={!!kerja}
                    style={{ fontSize: '.78rem' }}>
              {kerja ? <Loader2 size={13} className="animate-spin" /> : <Download size={13} />}
              {kerja ? `Mengunduh ${Math.round((kerja.progress ?? 0) * 100)}%` : 'Unduh ulang video'}
            </button>
          </div>
          {kerja && (
            <>
              <div style={{ height: '5px', marginTop: '8px', borderRadius: '99px',
                            background: 'var(--bg-glass)', overflow: 'hidden',
                            border: '1px solid var(--border-color)' }}>
                <div style={{ width: `${Math.max(2, Math.round((kerja.progress ?? 0) * 100))}%`,
                              height: '100%', background: 'var(--reh)', transition: 'width .5s' }} />
              </div>
              <div style={{ marginTop: '4px', color: 'var(--ink-2)' }}>{kerja.message}</div>
            </>
          )}
          {galat && <div style={{ marginTop: '6px', color: 'var(--danger)' }}>{galat}</div>}
        </div>
      </div>
    </div>
  );
}
