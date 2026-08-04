import React, { useState, useEffect, useRef } from 'react';
import { Film, HardDrive, RefreshCw, ExternalLink, Scissors, Download, Play, X, CheckCircle, Clock, Maximize2, Info } from 'lucide-react';
import { formatTime, formatDurationHuman } from '../utils/timeFormat';

// Komponen modal preview video klip
function ClipPreviewModal({ clip, onClose }) {
  const videoUrl = `http://localhost:8000${clip.web_url}`;
  const meta = clip.metadata || {};

  // Download via proxy (menghindari CORS)
  const handleDownload = async () => {
    try {
      const res = await fetch(`http://localhost:8000/api/file/edited_clips/${encodeURIComponent(clip.file_name)}`);
      if (!res.ok) throw new Error('Gagal mengambil file dari server');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = clip.file_name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      alert(`Gagal download: ${err.message}`);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          borderRadius: '20px',
          overflow: 'hidden',
          maxWidth: '460px',
          width: '100%',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 30px 60px rgba(0,0,0,0.7)',
        }}
      >
        {/* Video Player Area */}
        <div style={{
          position: 'relative',
          background: '#000',
          aspectRatio: meta.aspect_ratio === '9:16' ? '9/16' : '16/9',
          maxHeight: '500px',
          overflow: 'hidden',
        }}>
          <video
            src={videoUrl}
            controls
            autoPlay
            style={{ width: '100%', height: '100%', objectFit: 'contain' }}
          />

          {/* Close Button */}
          <button
            onClick={onClose}
            style={{
              position: 'absolute',
              top: '10px',
              right: '10px',
              width: '32px',
              height: '32px',
              borderRadius: '50%',
              background: 'rgba(0,0,0,0.7)',
              border: 'none',
              color: '#fff',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <X size={16} />
          </button>

          {/* Professional Badge */}
          {meta.subtitles && meta.subtitles.length > 0 && (
            <div style={{
              position: 'absolute',
              top: '10px',
              left: '10px',
              background: 'rgba(16, 185, 129, 0.9)',
              borderRadius: '6px',
              padding: '3px 8px',
              fontSize: '0.7rem',
              fontWeight: 800,
              color: '#fff',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}>
              <CheckCircle size={10} />
              Subtitle Burned-In
            </div>
          )}
        </div>

        {/* Info Panel */}
        <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {/* File name */}
          <div style={{ fontWeight: 700, fontSize: '0.9rem', color: '#fff', wordBreak: 'break-all' }}>
            {clip.file_name}
          </div>

          {/* Metadata Chips */}
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {meta.aspect_ratio && (
              <span style={{
                padding: '3px 8px', borderRadius: '6px', fontSize: '0.72rem', fontWeight: 700,
                background: 'rgba(0, 242, 254, 0.1)', color: 'var(--accent-cyan)', border: '1px solid rgba(0, 242, 254, 0.2)',
              }}>
                📐 {meta.aspect_ratio}
              </span>
            )}
            {meta.duration && (
              <span style={{
                padding: '3px 8px', borderRadius: '6px', fontSize: '0.72rem', fontWeight: 700,
                background: 'rgba(79, 172, 254, 0.1)', color: '#4facfe', border: '1px solid rgba(79, 172, 254, 0.2)',
              }}>
                ⏱️ {formatDurationHuman(meta.duration)}
              </span>
            )}
            {meta.start_seconds !== undefined && meta.end_seconds !== undefined && (
              <span style={{
                padding: '3px 8px', borderRadius: '6px', fontSize: '0.72rem', fontWeight: 700,
                background: 'rgba(255, 165, 0, 0.1)', color: '#ffa500', border: '1px solid rgba(255, 165, 0, 0.2)',
              }}>
                🕐 {formatTime(meta.start_seconds)} — {formatTime(meta.end_seconds)}
              </span>
            )}
            <span style={{
              padding: '3px 8px', borderRadius: '6px', fontSize: '0.72rem', fontWeight: 700,
              background: 'rgba(255, 255, 255, 0.06)', color: 'var(--text-secondary)', border: '1px solid var(--border-color)',
            }}>
              📦 {(clip.file_size / (1024 * 1024)).toFixed(2)} MB
            </span>
          </div>

          {/* Subtitles preview */}
          {meta.subtitles && meta.subtitles.length > 0 && (
            <div style={{
              background: 'rgba(0,0,0,0.3)',
              borderRadius: '8px',
              padding: '10px',
              fontSize: '0.78rem',
              color: 'var(--text-secondary)',
              maxHeight: '80px',
              overflowY: 'auto',
            }}>
              <div style={{ fontWeight: 700, color: 'var(--accent-cyan)', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Info size={12} /> {meta.subtitles.length} baris subtitle
              </div>
              {meta.subtitles.slice(0, 3).map((s, i) => (
                <div key={i} style={{ color: 'var(--text-muted)', marginTop: '2px' }}>
                  <span style={{ color: '#facc15' }}>[{formatTime(s.start)}]</span> {s.text}
                </div>
              ))}
              {meta.subtitles.length > 3 && <div style={{ color: 'var(--text-muted)' }}>...dan {meta.subtitles.length - 3} baris lagi</div>}
            </div>
          )}

          {/* Actions */}
          <button
            onClick={handleDownload}
            className="btn-primary"
            style={{ width: '100%', justifyContent: 'center' }}
          >
            <Download size={16} />
            Download Klip ke Perangkat
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ClipsTab() {
  const [data, setData] = useState({ local_clips: [], drive_clips: [] });
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('local');
  const [previewClip, setPreviewClip] = useState(null);

  const fetchClips = async () => {
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/api/clips');
      const json = await res.json();
      setData(json);
    } catch (err) {
      console.error('Error fetching clips:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchClips();
  }, []);

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Scissors size={24} style={{ color: 'var(--accent-cyan)' }} />
            Clip Studio Gallery
          </h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Hasil generate klip 9:16 profesional dengan subtitle burned-in, siap upload ke Shorts/TikTok/Reels.
          </p>
        </div>
        <button className="btn-secondary" onClick={fetchClips}>
          <RefreshCw size={16} />
          Refresh
        </button>
      </div>

      {/* Sub-tab Filter */}
      <div style={{ display: 'flex', gap: '12px', marginBottom: '20px' }}>
        <button
          className={activeTab === 'local' ? 'btn-primary' : 'btn-secondary'}
          onClick={() => setActiveTab('local')}
        >
          <Film size={16} />
          Klip Lokal ({data.local_clips.length})
        </button>
        <button
          className={activeTab === 'drive' ? 'btn-primary' : 'btn-secondary'}
          onClick={() => setActiveTab('drive')}
          style={activeTab === 'drive' ? { background: 'linear-gradient(135deg, #7f00ff, #e100ff)' } : {}}
        >
          <HardDrive size={16} />
          Google Drive ({data.drive_clips.length})
        </button>
      </div>

      {loading ? (
        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
          Memuat galeri klip...
        </div>
      ) : activeTab === 'local' ? (
        data.local_clips.length === 0 ? (
          <div style={{
            padding: '80px 20px',
            textAlign: 'center',
            background: 'var(--bg-card)',
            borderRadius: '20px',
            border: '1px dashed var(--border-color)',
          }}>
            <div style={{
              width: '72px', height: '72px', borderRadius: '50%',
              background: 'rgba(0, 242, 254, 0.08)',
              border: '2px dashed rgba(0, 242, 254, 0.2)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              margin: '0 auto 16px',
            }}>
              <Scissors size={32} style={{ color: 'var(--text-muted)' }} />
            </div>
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '8px' }}>Belum Ada Klip Dihasilkan</h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Pergi ke tab <strong>Search</strong>, pilih video, lalu klik <strong>"Clip Video (AI Studio)"</strong> untuk menghasilkan klip 9:16 profesional dengan subtitle otomatis.
            </p>
          </div>
        ) : (
          /* Grid Professional Clips */
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
            {data.local_clips.map((clip, i) => {
              const meta = clip.metadata || {};
              const hasSubtitles = meta.subtitles && meta.subtitles.length > 0;
              return (
                <div
                  key={i}
                  style={{
                    background: 'var(--bg-card)',
                    border: '1px solid var(--border-color)',
                    borderRadius: '16px',
                    overflow: 'hidden',
                    display: 'flex',
                    flexDirection: 'column',
                    cursor: 'pointer',
                    transition: 'all 0.2s ease',
                  }}
                  onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent-cyan)'; e.currentTarget.style.transform = 'translateY(-2px)'; e.currentTarget.style.boxShadow = '0 8px 24px rgba(0, 242, 254, 0.12)'; }}
                  onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--border-color)'; e.currentTarget.style.transform = 'none'; e.currentTarget.style.boxShadow = 'none'; }}
                >
                  {/* Thumbnail / Video Preview Area */}
                  <div style={{
                    position: 'relative',
                    width: '100%',
                    // Tampilkan dengan aspect ratio 9:16 jika vertikal, else 16:9
                    height: meta.aspect_ratio === '9:16' ? '320px' : '180px',
                    background: 'linear-gradient(135deg, #0d1b2e, #0a0e1a)',
                    overflow: 'hidden',
                  }}>
                    <video
                      src={`http://localhost:8000${clip.web_url}`}
                      style={{
                        width: '100%',
                        height: '100%',
                        objectFit: meta.aspect_ratio === '9:16' ? 'cover' : 'contain',
                        pointerEvents: 'none',
                      }}
                      preload="metadata"
                      muted
                    />

                    {/* Play Button Overlay */}
                    <div
                      onClick={() => setPreviewClip(clip)}
                      style={{
                        position: 'absolute',
                        inset: 0,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        background: 'rgba(0,0,0,0.4)',
                        opacity: 0,
                        transition: 'opacity 0.2s ease',
                      }}
                      onMouseEnter={e => e.currentTarget.style.opacity = '1'}
                      onMouseLeave={e => e.currentTarget.style.opacity = '0'}
                    >
                      <div style={{
                        width: '56px', height: '56px', borderRadius: '50%',
                        background: 'rgba(0, 242, 254, 0.9)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        boxShadow: '0 0 20px rgba(0, 242, 254, 0.5)',
                      }}>
                        <Play size={24} style={{ color: '#000', marginLeft: '3px' }} />
                      </div>
                    </div>

                    {/* Badges */}
                    <div style={{ position: 'absolute', top: '8px', left: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      {hasSubtitles && (
                        <span style={{
                          background: 'rgba(16, 185, 129, 0.92)',
                          borderRadius: '6px', padding: '2px 7px',
                          fontSize: '0.68rem', fontWeight: 800, color: '#fff',
                          display: 'flex', alignItems: 'center', gap: '3px',
                        }}>
                          <CheckCircle size={9} /> Subtitle
                        </span>
                      )}
                      {meta.aspect_ratio && (
                        <span style={{
                          background: 'rgba(0, 0, 0, 0.75)',
                          borderRadius: '6px', padding: '2px 7px',
                          fontSize: '0.68rem', fontWeight: 700, color: 'var(--accent-cyan)',
                        }}>
                          {meta.aspect_ratio}
                        </span>
                      )}
                    </div>

                    {/* Duration Badge */}
                    {meta.duration && (
                      <span style={{
                        position: 'absolute', bottom: '8px', right: '8px',
                        background: 'rgba(0,0,0,0.85)',
                        borderRadius: '5px', padding: '2px 7px',
                        fontSize: '0.72rem', fontWeight: 700, color: '#fff',
                      }}>
                        {formatDurationHuman(meta.duration)}
                      </span>
                    )}
                  </div>

                  {/* Info & Actions */}
                  <div style={{ padding: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {/* File Name */}
                    <div style={{ fontWeight: 700, fontSize: '0.82rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', color: '#fff' }}>
                      {clip.file_name}
                    </div>

                    {/* Timestamp Range */}
                    {meta.start_seconds !== undefined && (
                      <div style={{ fontSize: '0.73rem', color: 'var(--accent-cyan)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <Clock size={11} />
                        {formatTime(meta.start_seconds)} → {formatTime(meta.end_seconds)}
                        <span style={{ color: 'var(--text-muted)', marginLeft: '4px' }}>
                          • {(clip.file_size / (1024 * 1024)).toFixed(1)} MB
                        </span>
                      </div>
                    )}

                    {/* Action Row */}
                    <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
                      <button
                        onClick={() => setPreviewClip(clip)}
                        className="btn-secondary"
                        style={{ flex: 1, justifyContent: 'center', fontSize: '0.78rem', padding: '7px' }}
                      >
                        <Play size={13} /> Putar
                      </button>
                      <button
                        onClick={async (e) => {
                          e.stopPropagation();
                          try {
                            const res = await fetch(`http://localhost:8000/api/file/edited_clips/${encodeURIComponent(clip.file_name)}`);
                            if (!res.ok) throw new Error('Gagal');
                            const blob = await res.blob();
                            const url = window.URL.createObjectURL(blob);
                            const a = document.createElement('a');
                            a.href = url;
                            a.download = clip.file_name;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                            window.URL.revokeObjectURL(url);
                          } catch (err) {
                            alert('Gagal download: ' + err.message);
                          }
                        }}
                        className="btn-secondary"
                        style={{ flex: 1, justifyContent: 'center', fontSize: '0.78rem', padding: '7px', color: 'var(--accent-cyan)', borderColor: 'rgba(0, 242, 254, 0.3)' }}
                      >
                        <Download size={13} /> Simpan
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )
      ) : (
        /* Drive Clips */
        data.drive_clips.length === 0 ? (
          <div style={{ padding: '60px 20px', textAlign: 'center', background: 'var(--bg-card)', borderRadius: '16px', border: '1px dashed var(--border-color)' }}>
            <HardDrive size={48} style={{ color: 'var(--text-muted)', marginBottom: '12px' }} />
            <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Belum Ada Klip di Google Drive</h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
              Ekspor klip dari Studio Editor menggunakan tombol "Unggah ke Google Drive".
            </p>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '16px' }}>
            {data.drive_clips.map((item, idx) => (
              <div
                key={idx}
                style={{
                  background: 'var(--bg-card)',
                  border: '1px solid rgba(127,0,255,0.3)',
                  borderRadius: '14px',
                  padding: '16px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div style={{ padding: '10px', background: 'rgba(127,0,255,0.2)', borderRadius: '10px', color: '#e100ff' }}>
                    <HardDrive size={24} />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 700, fontSize: '0.9rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {item.file_name}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', marginTop: '2px' }}>
                      👤 {item.account_email}
                    </div>
                  </div>
                </div>

                <a
                  href={item.web_view_link}
                  target="_blank"
                  rel="noreferrer"
                  className="btn-secondary"
                  style={{ width: '100%', justifyContent: 'center', fontSize: '0.8rem', background: 'rgba(127,0,255,0.15)', borderColor: 'rgba(127,0,255,0.4)', color: '#e100ff' }}
                >
                  <ExternalLink size={14} />
                  Buka di Google Drive
                </a>
              </div>
            ))}
          </div>
        )
      )}

      {/* Preview Modal */}
      {previewClip && (
        <ClipPreviewModal
          clip={previewClip}
          onClose={() => setPreviewClip(null)}
        />
      )}
    </div>
  );
}
