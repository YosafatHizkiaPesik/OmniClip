import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Sparkles, Loader2, AlertTriangle, CheckCircle2, Trash2, Clock, Film, RefreshCw, Search,
} from 'lucide-react';
import { apiDelete, apiGet } from '../../lib/api';
import { formatTime } from '../../utils/timeFormat';

/**
 * Halaman depan Studio: setiap video yang diminta untuk diklip jadi satu kartu.
 *
 * Inilah yang membuat pengguna tidak perlu menunggui satu video sampai selesai.
 * Tekan "Clip" pada beberapa video, kembali mencari video lain, lalu buka
 * halaman ini untuk melihat mana yang sudah siap ditinjau.
 */

const POLL_MS = 2500;

const STATUS_META = {
  queued: { label: 'Menunggu antrean', color: 'var(--text-secondary)', Icon: Clock },
  running: { label: 'Sedang diproses', color: 'var(--accent-cyan)', Icon: Loader2 },
  done: { label: 'Siap ditinjau', color: 'var(--entry)', Icon: CheckCircle2 },
  failed: { label: 'Gagal', color: 'var(--accent-red, var(--danger))', Icon: AlertTriangle },
  empty: { label: 'Tidak ada klip', color: 'var(--text-muted)', Icon: AlertTriangle },
  unknown: { label: 'Belum diproses', color: 'var(--text-muted)', Icon: Clock },
};

export default function StudioHome({ onOpen, onFindVideos }) {
  const [projects, setProjects] = useState(null);
  const [error, setError] = useState(null);
  const timerRef = useRef(null);

  const load = useCallback(async () => {
    try {
      const data = await apiGet('/projects');
      setProjects(data);
      setError(null);
      return data;
    } catch (err) {
      setError(err);
      return [];
    }
  }, []);

  // Selama masih ada yang berjalan, daftar disegarkan berkala. Begitu semuanya
  // selesai, polling berhenti sendiri — tidak ada gunanya membebani server
  // untuk daftar yang tidak berubah.
  useEffect(() => {
    let alive = true;
    const tick = async () => {
      const data = await load();
      if (!alive) return;
      const busy = (data || []).some((p) => p.status === 'running' || p.status === 'queued');
      if (busy) timerRef.current = setTimeout(tick, POLL_MS);
    };
    tick();
    return () => { alive = false; clearTimeout(timerRef.current); };
  }, [load]);

  const handleDelete = async (videoId, e) => {
    e.stopPropagation();
    try {
      await apiDelete(`/projects/${videoId}`);
      setProjects((prev) => prev.filter((p) => p.video_id !== videoId));
    } catch (err) {
      setError(err);
    }
  };

  if (projects === null) {
    return (
      <div style={{ padding: '60px 20px', textAlign: 'center', color: 'var(--text-secondary)' }}>
        <Loader2 size={26} className="animate-spin" style={{ color: 'var(--accent-cyan)' }} />
        <p style={{ marginTop: '10px', fontSize: '0.85rem' }}>Memuat daftar project…</p>
      </div>
    );
  }

  return (
    <div style={{ paddingBottom: '40px' }}>
      <header style={{
        display: 'flex', alignItems: 'center', gap: '12px',
        flexWrap: 'wrap', marginBottom: '18px',
      }}>
        <div>
          <h1 style={{ fontSize: '1.3rem', fontWeight: 800, marginBottom: '3px' }}>Partitur</h1>
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: 0 }}>
            {projects.length
              ? `${projects.length} video · klik kartu untuk membuka editor`
              : 'Belum ada video yang diproses'}
          </p>
        </div>
        <div style={{ flex: 1 }} />
        <button className="btn-secondary" onClick={load} style={{ fontSize: '0.8rem' }}>
          <RefreshCw size={14} /> Segarkan
        </button>
        <button className="btn-primary" onClick={onFindVideos} style={{ fontSize: '0.8rem' }}>
          <Search size={14} /> Cari video
        </button>
      </header>

      {error && (
        <div style={{
          padding: '11px 13px', marginBottom: '14px', fontSize: '0.82rem',
          borderRadius: 'var(--radius-md)', color: 'var(--accent-red, var(--danger))',
          background: 'color-mix(in srgb, var(--danger) 12%, transparent)', border: '1px solid color-mix(in srgb, var(--danger) 30%, transparent)',
        }}>
          {error.message}
        </div>
      )}

      {!projects.length && !error && (
        <div style={{
          maxWidth: '520px', margin: '50px auto', padding: '32px 24px', textAlign: 'center',
          background: 'var(--bg-card)', border: '1px dashed var(--border-color)',
          borderRadius: 'var(--radius-lg)',
        }}>
          <Film size={38} style={{ color: 'var(--text-muted)', marginBottom: '14px' }} />
          <h3 style={{ fontWeight: 700, marginBottom: '8px' }}>Belum ada project klip</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.65 }}>
            Buka halaman Cari video, pilih videonya, lalu tekan <strong>Potong jadi klip</strong>.
            Prosesnya berjalan di latar belakang, jadi Anda bisa langsung memilih
            video berikutnya tanpa menunggu.
          </p>
          <button className="btn-primary" onClick={onFindVideos}
                  style={{ marginTop: '18px', fontSize: '0.84rem' }}>
            <Search size={15} /> Cari video
          </button>
        </div>
      )}

      <div style={{
        display: 'grid', gap: '14px',
        gridTemplateColumns: 'repeat(auto-fill, minmax(268px, 1fr))',
      }}>
        {projects.map((p) => {
          const meta = STATUS_META[p.status] ?? STATUS_META.unknown;
          const busy = p.status === 'running' || p.status === 'queued';
          const openable = p.status === 'done';
          const pct = Math.round((p.job?.progress ?? 0) * 100);

          return (
            <div
              key={p.video_id}
              onClick={() => openable && onOpen(p)}
              style={{
                background: 'var(--bg-card)', border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-lg)', overflow: 'hidden',
                cursor: openable ? 'pointer' : 'default',
                display: 'flex', flexDirection: 'column',
                opacity: p.status === 'failed' ? 0.75 : 1,
              }}
            >
              <div className="pit-frame"><div className="pit-well" style={{ aspectRatio: '16/9' }}>
                {p.thumbnail && (
                  <img src={p.thumbnail} alt="" loading="lazy"
                       style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                )}
                {p.duration ? (
                  <span style={{
                    position: 'absolute', right: '7px', bottom: '7px', padding: '2px 6px',
                    background: 'rgba(0,0,0,0.8)', borderRadius: '4px',
                    fontSize: '0.68rem', fontWeight: 700, color: '#fff',
                    fontVariantNumeric: 'tabular-nums',
                  }}>
                    {formatTime(p.duration)}
                  </span>
                ) : null}
                {p.status === 'done' && p.clip_count > 0 && (
                  <span style={{
                    position: 'absolute', left: '7px', top: '7px', padding: '3px 8px',
                    background: 'var(--hl)', borderRadius: '99px',
                    fontSize: '0.68rem', fontWeight: 800, color: '#1A1400',
                  }}>
                    {p.clip_count} klip
                  </span>
                )}
              </div></div>

              <div style={{ padding: '11px 13px', display: 'flex', flexDirection: 'column', gap: '7px', flex: 1 }}>
                <div style={{
                  fontSize: '0.84rem', fontWeight: 700, lineHeight: 1.35,
                  display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                  overflow: 'hidden',
                }}>
                  {p.title}
                </div>
                {p.channel && (
                  <div style={{ fontSize: '0.73rem', color: 'var(--text-muted)' }}>{p.channel}</div>
                )}

                <div style={{ flex: 1 }} />

                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.74rem', color: meta.color }}>
                  <meta.Icon size={13} className={p.status === 'running' ? 'animate-spin' : undefined} />
                  <span style={{ fontWeight: 700 }}>{meta.label}</span>
                  {p.engine && p.status === 'done' && (
                    <span style={{ color: 'var(--text-muted)', fontWeight: 500 }}>
                      · {p.engine === 'gemini' ? 'Gemini' : 'heuristik'}
                    </span>
                  )}
                </div>

                {busy && (
                  <>
                    <div style={{ height: '4px', borderRadius: '99px', background: 'var(--bg-glass)', overflow: 'hidden' }}>
                      <div style={{
                        width: '100%', height: '100%', background: 'var(--reh)',
                        transform: `scaleX(${pct / 100})`, transformOrigin: 'left',
                        transition: 'transform .3s cubic-bezier(.16,1,.3,1)',
                      }} />
                    </div>
                    <div style={{ fontSize: '0.71rem', color: 'var(--text-secondary)' }}>
                      {pct}% · {p.job?.message || 'Menyiapkan…'}
                    </div>
                  </>
                )}

                {p.status === 'failed' && p.job?.error && (
                  <div style={{ fontSize: '0.71rem', color: 'var(--text-muted)', lineHeight: 1.45 }}>
                    {p.job.error}
                  </div>
                )}

                <div style={{ display: 'flex', gap: '7px', marginTop: '3px' }}>
                  {openable && (
                    <button className="btn-primary" style={{ flex: 1, fontSize: '0.76rem', padding: '7px' }}
                            onClick={(e) => { e.stopPropagation(); onOpen(p); }}>
                      <Sparkles size={13} /> Buka editor
                    </button>
                  )}
                  <button
                    onClick={(e) => handleDelete(p.video_id, e)}
                    title="Hapus hasil analisis"
                    style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      width: '30px', height: '30px', borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--border-color)', background: 'transparent',
                      color: 'var(--text-muted)', cursor: 'pointer',
                    }}
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
