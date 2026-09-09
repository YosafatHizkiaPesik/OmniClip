import React, { useEffect, useState } from 'react';
import {
  Film, Download, Trash2, RefreshCw, Loader2, AlertTriangle, Layers, X, UploadCloud,
} from 'lucide-react';
import { apiGet, apiDelete, downloadToDisk, mediaUrl } from '../lib/api';
import { formatTime } from '../utils/timeFormat';
import UploadModal from './UploadModal';

function formatBytes(bytes) {
  if (!bytes) return '';
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

function PlayerModal({ clip, onClose }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={{
        background: '#000', borderRadius: '16px', overflow: 'hidden',
        maxHeight: '86vh', position: 'relative', display: 'flex',
      }}>
        <button onClick={onClose} aria-label="Tutup" style={{
          position: 'absolute', top: '10px', right: '10px', zIndex: 2,
          background: 'rgba(0,0,0,0.6)', border: 'none', borderRadius: '50%',
          width: '32px', height: '32px', cursor: 'pointer', color: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}><X size={17} /></button>
        <video
          src={mediaUrl('edited_clips', clip.file_name)}
          controls autoPlay playsInline
          style={{ maxHeight: '86vh', maxWidth: '92vw', display: 'block' }}
        />
      </div>
    </div>
  );
}

export default function ClipsTab() {
  const [clips, setClips] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [playing, setPlaying] = useState(null);
  const [selected, setSelected] = useState(() => new Set());
  const [working, setWorking] = useState(false);
  // Terpisah dari `error`: kegagalan menghapus satu klip tidak boleh mengganti
  // seluruh daftar dengan layar error.
  const [actionError, setActionError] = useState(null);
  // Klip yang sedang dibuka jendela unggahnya. Satu per satu — tidak ada
  // bentuk jamaknya, dan itu disengaja.
  const [uploading, setUploading] = useState(null);
  // Klip mana yang sudah pernah naik ke mana, dibaca dari riwayat server.
  const [sent, setSent] = useState({});

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiGet('/clips');
      setClips(data.local_clips || []);
    } catch (err) {
      setError(err);
      setClips([]);
    } finally {
      setLoading(false);
    }
  };

  const loadUploads = async () => {
    try {
      const { uploads } = await apiGet('/uploads?limit=200');
      const map = {};
      for (const u of uploads) {
        if (u.status !== 'done') continue;
        (map[u.clip_name] ??= []).push(u);
      }
      setSent(map);
    } catch { /* riwayat kosong bukan kegagalan halaman */ }
  };

  useEffect(() => { load(); loadUploads(); }, []);

  const toggle = (name) => setSelected((prev) => {
    const next = new Set(prev);
    if (next.has(name)) next.delete(name); else next.add(name);
    return next;
  });

  const saveSelected = async () => {
    setWorking(true);
    for (const name of selected) {
      try {
        // eslint-disable-next-line no-await-in-loop
        await downloadToDisk('edited_clips', name);
      } catch { /* lanjut ke berikutnya */ }
    }
    setWorking(false);
  };

  const deleteClip = async (name) => {
    if (!window.confirm(`Hapus klip "${name}"?`)) return;
    try {
      await apiDelete(`/clips/${encodeURIComponent(name)}`);
      setSelected((prev) => { const n = new Set(prev); n.delete(name); return n; });
      load();
    } catch (err) {
      setActionError(`Gagal menghapus "${name}": ${err.message}`);
    }
  };

  return (
    <div style={{ paddingBottom: '40px' }}>
      {actionError && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap',
          padding: '11px 14px', marginBottom: '14px', fontSize: '0.83rem',
          borderRadius: 'var(--radius-md)', color: 'var(--accent-red, var(--danger))',
          background: 'color-mix(in srgb, var(--danger) 12%, transparent)', border: '1px solid color-mix(in srgb, var(--danger) 30%, transparent)',
        }}>
          <span style={{ flex: 1, minWidth: '180px' }}>{actionError}</span>
          <button className="btn-secondary" style={{ fontSize: '0.76rem', padding: '5px 11px' }}
                  onClick={() => setActionError(null)}>Tutup</button>
        </div>
      )}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap', marginBottom: '18px' }}>
        <h1 style={{ fontSize: '1.2rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '9px' }}>
          <Film size={20} style={{ color: 'var(--accent-cyan)' }} /> Klip jadi
        </h1>
        <div style={{ flex: 1 }} />
        {selected.size > 0 && (
          <button className="btn-primary" onClick={saveSelected} disabled={working} style={{ fontSize: '0.8rem' }}>
            {working ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            Simpan {selected.size} klip
          </button>
        )}
        <button className="btn-secondary" onClick={load} style={{ fontSize: '0.8rem' }}>
          <RefreshCw size={14} /> Muat ulang
        </button>
      </div>

      {loading ? (
        <div style={{ padding: '60px', textAlign: 'center' }}>
          <Loader2 size={30} className="animate-spin" style={{ color: 'var(--accent-cyan)' }} />
        </div>
      ) : error ? (
        <div style={{
          padding: '36px 20px', textAlign: 'center', background: 'var(--bg-card)',
          border: '1px solid var(--accent-red)', borderRadius: 'var(--radius-lg)',
        }}>
          <AlertTriangle size={34} style={{ color: 'var(--accent-red)', marginBottom: '10px' }} />
          <div style={{ fontWeight: 700 }}>Gagal memuat klip</div>
          <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)' }}>{error.message}</p>
        </div>
      ) : clips.length === 0 ? (
        <div style={{
          padding: '54px 20px', textAlign: 'center', background: 'var(--bg-card)',
          border: '1px dashed var(--border-color)', borderRadius: 'var(--radius-lg)',
        }}>
          <Film size={44} style={{ color: 'var(--text-muted)', marginBottom: '12px' }} />
          <h3 style={{ fontWeight: 700 }}>Belum ada klip</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Buka sebuah video di Cari video, tekan “Potong jadi klip”, lalu render klipnya di Partitur.
          </p>
        </div>
      ) : (
        <div style={{
          display: 'grid', gap: '14px',
          gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))',
        }}>
          {clips.map((clip) => {
            const meta = clip.metadata || {};
            const segCount = meta.segments?.length ?? 1;
            return (
              <div key={clip.file_name} style={{
                background: 'var(--bg-card)', border: selected.has(clip.file_name)
                  ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                borderRadius: 'var(--radius-md)', overflow: 'hidden',
                display: 'flex', flexDirection: 'column',
              }}>
                <div
                  onClick={() => setPlaying(clip)}
                  style={{
                    position: 'relative', aspectRatio: '9 / 16', background: 'var(--stage)',
                    cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}
                >
                  <video
                    src={mediaUrl('edited_clips', clip.file_name)}
                    preload="metadata" muted
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  />
                  <div style={{
                    position: 'absolute', bottom: '6px', right: '6px',
                    background: 'rgba(0,0,0,0.8)', color: '#fff', fontSize: '0.7rem',
                    fontWeight: 700, padding: '2px 6px', borderRadius: '4px',
                  }}>
                    {formatTime(meta.duration || 0)}
                  </div>
                  {segCount > 1 && (
                    <div style={{
                      position: 'absolute', top: '6px', left: '6px',
                      background: 'var(--hl-wash)', color: '#000', fontSize: '0.66rem',
                      fontWeight: 800, padding: '2px 6px', borderRadius: '4px',
                      display: 'flex', alignItems: 'center', gap: '3px',
                    }}>
                      <Layers size={10} /> {segCount}
                    </div>
                  )}
                </div>

                <div style={{ padding: '10px', display: 'flex', flexDirection: 'column', gap: '7px' }}>
                  <div style={{ fontSize: '0.76rem', fontWeight: 700, lineHeight: 1.3 }}>
                    {meta.hook_text ? meta.hook_text.slice(0, 46) : clip.file_name.slice(0, 26)}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                    {meta.aspect_ratio || '9:16'} · {formatBytes(clip.file_size)}
                  </div>
                  {/* Sudah pernah naik ke mana. Ini yang mencegah klip yang
                      sama dikirim dua kali ke kanal yang sama. */}
                  {sent[clip.file_name]?.length > 0 && (
                    <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                      {sent[clip.file_name].map((u) => (
                        <a key={u.id} href={u.remote_url} target="_blank" rel="noreferrer"
                           className="chip" style={{
                             fontSize: '.64rem', padding: '2px 7px', textDecoration: 'none',
                           }}>
                          ↗ {u.target === 'youtube' ? 'YouTube' : 'Drive'}
                        </a>
                      ))}
                    </div>
                  )}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '5px', cursor: 'pointer', fontSize: '0.72rem', flex: 1 }}>
                      <input type="checkbox" checked={selected.has(clip.file_name)}
                             onChange={() => toggle(clip.file_name)}
                             style={{ accentColor: 'var(--accent-cyan)' }} />
                      Pilih
                    </label>
                    <button onClick={() => setUploading(clip)} style={iconBtn}
                            aria-label="Unggah ke Drive atau YouTube"
                            title="Unggah ke Drive atau YouTube">
                      <UploadCloud size={14} />
                    </button>
                    <button onClick={() => downloadToDisk('edited_clips', clip.file_name)}
                            aria-label="Simpan" style={iconBtn}>
                      <Download size={14} />
                    </button>
                    <button onClick={() => deleteClip(clip.file_name)} aria-label="Hapus"
                            style={{ ...iconBtn, color: 'var(--accent-red)' }}>
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {playing && <PlayerModal clip={playing} onClose={() => setPlaying(null)} />}
      {uploading && (
        <UploadModal clip={uploading} onClose={() => setUploading(null)}
                     onDone={loadUploads} />
      )}
    </div>
  );
}

const iconBtn = {
  background: 'none', border: 'none', cursor: 'pointer',
  color: 'var(--text-secondary)', display: 'flex', padding: '3px',
};
