import React, { useState, useEffect, useRef } from 'react';
import { Search, Download, Scissors, Play, ArrowLeft, CheckCircle2, Sparkles, Loader2, Video, TrendingUp, Flame, Music, Gamepad2, Cpu, Globe, Eye, Clock } from 'lucide-react';
import { formatTime, formatDurationHuman } from '../utils/timeFormat';
import { apiGet, apiPost, downloadToDisk } from '../lib/api';
import { useJobRunner } from '../hooks/useJob';
import JobProgress from './JobProgress';

// Tahun sengaja tidak dicantumkan: menempelkan "2024" ke setiap kueri menyaring
// hasil ke tahun yang sudah lewat, dan chip pertama dulu sama persis dengan
// chip "Trending".
const CATEGORY_SHORTCUTS = [
  { label: '🔥 Trending', query: 'trending viral indonesia' },
  { label: '🎙️ Podcast', query: 'podcast indonesia terbaru' },
  { label: '🎤 Wawancara', query: 'wawancara eksklusif indonesia' },
  { label: '📚 Edukasi', query: 'edukasi menarik indonesia' },
  { label: '🎮 Gaming', query: 'gaming highlights indonesia' },
  { label: '🎵 Musik', query: 'musik viral indonesia' },
  { label: '💻 Tech', query: 'teknologi AI indonesia' },
  { label: '💰 Finance', query: 'investasi tips keuangan indonesia' },
  { label: '😂 Komedi', query: 'komedi lucu indonesia' },
  { label: '🍜 Kuliner', query: 'kuliner makanan enak indonesia' },
  { label: '✈️ Travel', query: 'travel wisata indonesia' },
];

// Format view count YouTube-style
function formatViews(views) {
  if (!views) return '';
  if (views >= 1_000_000) return `${(views / 1_000_000).toFixed(1)}Jt`;
  if (views >= 1_000) return `${(views / 1_000).toFixed(0)}Rb`;
  return `${views}`;
}

// Avatar Channel
function ChannelAvatar({ name, size = 36 }) {
  const initials = name ? name.slice(0, 2).toUpperCase() : '?';
  const colors = ['#00f2fe', '#4facfe', '#7f00ff', '#ff0844', '#10b981', '#f59e0b'];
  const colorIdx = name ? name.charCodeAt(0) % colors.length : 0;
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%',
      background: `linear-gradient(135deg, ${colors[colorIdx]}, ${colors[(colorIdx + 2) % colors.length]})`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontWeight: 800, fontSize: size * 0.38, color: '#000',
      flexShrink: 0,
    }}>{initials}</div>
  );
}

// Video Card — mirip YouTube
function VideoCard({ video, isSelected, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        gap: 0,
        borderRadius: '12px',
        overflow: 'hidden',
        transition: 'transform 0.15s ease',
        background: 'transparent',
      }}
      onMouseEnter={e => e.currentTarget.style.transform = 'translateY(-2px)'}
      onMouseLeave={e => e.currentTarget.style.transform = 'none'}
    >
      {/* Thumbnail */}
      <div style={{ position: 'relative', width: '100%', paddingTop: '56.25%', background: '#0d1b2e', borderRadius: '10px', overflow: 'hidden' }}>
        <img
          src={video.thumbnail}
          alt={video.title}
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
          loading="lazy"
        />
        {/* Duration badge */}
        {video.duration > 0 && (
          <span style={{
            position: 'absolute', bottom: '6px', right: '6px',
            background: 'rgba(0,0,0,0.85)', color: '#fff',
            fontSize: '0.72rem', fontWeight: 700, padding: '1px 5px', borderRadius: '4px',
          }}>{formatTime(video.duration)}</span>
        )}
        {/* Play overlay */}
        {isSelected && (
          <div style={{
            position: 'absolute', inset: 0,
            background: 'rgba(0, 242, 254, 0.15)',
            border: '2px solid var(--accent-cyan)',
            borderRadius: '10px',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <div style={{
              width: '40px', height: '40px', borderRadius: '50%',
              background: 'var(--accent-cyan)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <Play size={18} style={{ color: '#000', marginLeft: '2px' }} />
            </div>
          </div>
        )}
      </div>

      {/* Info */}
      <div style={{ display: 'flex', gap: '10px', padding: '10px 2px 4px' }}>
        <ChannelAvatar name={video.channel} size={36} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: '0.87rem', fontWeight: 600, lineHeight: 1.35, color: '#fff',
            display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
          }}>{video.title}</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '3px' }}>
            {video.channel}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '1px', display: 'flex', gap: '6px' }}>
            {video.views > 0 && <span>{formatViews(video.views)} views</span>}
            {video.duration > 0 && <span>• {formatDurationHuman(video.duration)}</span>}
          </div>
        </div>
      </div>
    </div>
  );
}

// Horizontal small card for related/sidebar
function RelatedVideoCard({ video, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', gap: '10px', cursor: 'pointer', padding: '6px',
        borderRadius: '8px', transition: 'background 0.15s',
      }}
      onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
    >
      <div style={{ position: 'relative', flexShrink: 0, width: '160px', height: '90px', borderRadius: '8px', overflow: 'hidden', background: '#0d1b2e' }}>
        <img src={video.thumbnail} alt={video.title} style={{ width: '100%', height: '100%', objectFit: 'cover' }} loading="lazy" />
        {video.duration > 0 && (
          <span style={{
            position: 'absolute', bottom: '4px', right: '4px',
            background: 'rgba(0,0,0,0.85)', color: '#fff',
            fontSize: '0.68rem', fontWeight: 700, padding: '1px 4px', borderRadius: '3px',
          }}>{formatTime(video.duration)}</span>
        )}
      </div>
      <div style={{ flex: 1, minWidth: 0, paddingTop: '2px' }}>
        <div style={{
          fontSize: '0.82rem', fontWeight: 600, lineHeight: 1.3, color: '#fff',
          display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
        }}>{video.title}</div>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '4px' }}>{video.channel}</div>
        {video.views > 0 && <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>{formatViews(video.views)} views</div>}
      </div>
    </div>
  );
}

export default function SearchTab({ onOpenStudio }) {
  const [query, setQuery] = useState('');
  const [feed, setFeed] = useState([]);           // Main grid feed (trending/search results)
  const [relatedVideos, setRelatedVideos] = useState([]); // Related videos (sidebar)
  const [feedLoading, setFeedLoading] = useState(true);
  const [relatedLoading, setRelatedLoading] = useState(false);
  const [activeCategory, setActiveCategory] = useState(0);
  const [selectedVideo, setSelectedVideo] = useState(null);

  // Download modal state
  const [showDownloadModal, setShowDownloadModal] = useState(false);
  const [selectedResolution, setSelectedResolution] = useState('720p');
  const downloadJob = useJobRunner();
  const downloadResult = downloadJob.result;

  // Pengklipan berjalan sebagai job di latar belakang. Halaman ini tidak
  // berpindah ke Studio: pengguna bisa langsung mengantre video berikutnya.
  const [analyzingClip, setAnalyzingClip] = useState(false);
  const [clipPending, setClipPending] = useState(null);  // konfirmasi video panjang
  const [clipNotice, setClipNotice] = useState(null);    // {kind, text}
  // Kegagalan pencarian harus terlihat. Sebelumnya `catch { setFeed([]) }`
  // membuat rate limit YouTube tampak persis seperti "tidak ada hasil".
  const [feedError, setFeedError] = useState(null);
  // Model transkripsi. 'base' cepat tapi sering salah pada percakapan Indonesia
  // yang cepat; 'small' jauh lebih akurat dengan biaya ~5x waktu proses.
  const [whisperModel, setWhisperModel] = useState('base');
  // Panjang klip yang dicari. Batas atas inilah yang menentukan apakah sebuah
  // pembahasan tertangkap utuh atau hanya pembukaannya.
  const [clipLength, setClipLength] = useState('medium');

  // Load trending on mount (YouTube homepage style)
  useEffect(() => {
    loadTrending();
  }, []);

  /** Satu jalur untuk semua pengisian feed, lengkap dengan error yang terlihat. */
  const fillFeed = async (path) => {
    setFeedLoading(true);
    setFeedError(null);
    try {
      const data = await apiGet(path);
      setFeed(Array.isArray(data) ? data : []);
    } catch (err) {
      setFeed([]);
      setFeedError(err);
    } finally {
      setFeedLoading(false);
    }
  };

  const loadTrending = () => fillFeed('/trending?limit=20');

  const loadCategory = (catQuery, catIndex) => {
    setActiveCategory(catIndex);
    setSelectedVideo(null);
    return fillFeed(`/search?q=${encodeURIComponent(catQuery)}&limit=20`);
  };

  const handleSearchSubmit = (e) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;
    setSelectedVideo(null);
    setActiveCategory(-1);
    return fillFeed(`/search?q=${encodeURIComponent(query.trim())}&limit=20`);
  };

  // When user selects a video → load related videos from a related query
  const handleSelectVideo = async (video) => {
    setSelectedVideo(video);
    setRelatedLoading(true);
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
    try {
      // Search for related videos based on channel + title keywords
      const relatedQuery = `${video.channel} ${video.title.split(' ').slice(0, 4).join(' ')}`;
      const data = await apiGet(`/search?q=${encodeURIComponent(relatedQuery)}&limit=15`);
      // Exclude the current video
      const filtered = (Array.isArray(data) ? data : []).filter(v => v.id !== video.id);
      setRelatedVideos(filtered.slice(0, 12));
    } catch {
      setRelatedVideos([]);
    } finally {
      setRelatedLoading(false);
    }
  };

  // Unduhan berjalan sebagai job di backend: progresnya nyata, bisa dibatalkan,
  // dan tetap berjalan meski modal ditutup.
  const handleDownloadSubmit = async () => {
    if (!selectedVideo) return;
    try {
      await downloadJob.run('/download', {
        url: selectedVideo.id || selectedVideo.url,
        resolution: selectedResolution,
      });
    } catch {
      /* error sudah tersimpan di downloadJob.error dan ditampilkan di modal */
    }
  };

  const handleProxyDownload = async (fileName) => {
    try {
      await downloadToDisk('local_downloads', fileName);
    } catch (err) {
      setClipNotice({ kind: 'error', text: `Gagal menyimpan file: ${err.message}` });
    }
  };

  /** Mengantre pekerjaan klip tanpa memindahkan halaman. */
  const startClipJob = async (video) => {
    setClipPending(null);
    setAnalyzingClip(true);
    try {
      const res = await apiPost('/auto-clip', {
        video_id: video.id, max_clips: 8,
        whisper_model: whisperModel, clip_length: clipLength,
        // Model dipilih di Settings; kosong berarti biarkan server memutuskan.
        gemini_model: localStorage.getItem('omniclip_gemini_model') || null,
      });
      setClipNotice({
        kind: res.cached ? 'cached' : 'queued',
        text: res.cached
          ? 'Video ini sudah pernah diklip. Hasilnya menunggu di Clip Studio.'
          : 'Diantrekan. Prosesnya berjalan di latar belakang — Anda bisa langsung memilih video lain.',
      });
    } catch (err) {
      setClipNotice({ kind: 'error', text: err.message });
    } finally {
      setAnalyzingClip(false);
    }
  };

  const handleTriggerClip = async () => {
    if (!selectedVideo || analyzingClip) return;
    setClipNotice(null);
    setAnalyzingClip(true);
    try {
      const info = await apiGet(`/video-info?url=${encodeURIComponent(selectedVideo.id)}`);
      const minutes = (info.duration || 0) / 60;
      // Video panjang tanpa subtitle harus disalin ucapannya di CPU. Pengguna
      // berhak tahu perkiraan waktunya sebelum pekerjaan itu dimulai.
      if (!info.has_captions && minutes > 12) {
        setClipPending({ video: selectedVideo, minutes, estimate: Math.ceil(minutes * 0.3) });
        setAnalyzingClip(false);
        return;
      }
      await startClipJob(selectedVideo);
    } catch (err) {
      setClipNotice({ kind: 'error', text: err.message });
      setAnalyzingClip(false);
    }
  };

  // ===== RENDER PLAYER + SIDEBAR VIEW (when video selected) =====
  if (selectedVideo) {
    return (
      <div style={{ display: 'flex', gap: '24px', maxWidth: '100%' }}>
        {/* LEFT: Player + Info */}
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Search Bar (stays visible) */}
          <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '10px', marginBottom: '16px' }}>
            <div style={{ flex: 1, position: 'relative', display: 'flex', alignItems: 'center' }}>
              <Search size={18} style={{ position: 'absolute', left: '14px', color: 'var(--text-muted)' }} />
              <input
                className="search-input"
                style={{ paddingLeft: '44px' }}
                placeholder="Cari video YouTube..."
                value={query}
                onChange={e => setQuery(e.target.value)}
              />
            </div>
            <button type="submit" className="btn-primary" style={{ padding: '0 18px' }}>
              <Search size={16} /> Cari
            </button>
            <button type="button" className="btn-secondary" onClick={() => setSelectedVideo(null)} style={{ padding: '0 14px' }}>
              <ArrowLeft size={16} /> Feed
            </button>
          </form>

          {/* YouTube Embed Player (Privacy-Enhanced, Clean Console) */}
          <div style={{ background: '#000', borderRadius: '14px', overflow: 'hidden', position: 'relative' }}>
            <iframe
              key={selectedVideo.id}
              src={`https://www.youtube-nocookie.com/embed/${selectedVideo.id}?autoplay=1&rel=0&enablejsapi=1&origin=${window.location.origin}`}
              title={selectedVideo.title}
              style={{ width: '100%', height: '420px', border: 'none', display: 'block' }}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              referrerPolicy="strict-origin-when-cross-origin"
            />
          </div>

          {/* Video Info */}
          <div style={{ padding: '14px 0' }}>
            <h2 style={{ fontSize: '1.15rem', fontWeight: 700, lineHeight: 1.4, marginBottom: '8px' }}>
              {selectedVideo.title}
            </h2>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <ChannelAvatar name={selectedVideo.channel} size={32} />
                <div>
                  <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>{selectedVideo.channel}</div>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', display: 'flex', gap: '8px' }}>
                    {selectedVideo.views > 0 && <span><Eye size={10} style={{ verticalAlign: 'middle' }} /> {formatViews(selectedVideo.views)} views</span>}
                    {selectedVideo.duration > 0 && <span><Clock size={10} style={{ verticalAlign: 'middle' }} /> {formatDurationHuman(selectedVideo.duration)}</span>}
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700 }}>
                    Panjang klip
                  </span>
                  <div style={{ display: 'flex', gap: '3px' }}>
                    {[
                      ['short', 'Pendek', '15–40 detik'],
                      ['medium', 'Sedang', '20–60 detik'],
                      ['long', 'Panjang', '35–110 detik, pembahasan utuh'],
                    ].map(([v, t, hint]) => (
                      <button key={v} onClick={() => setClipLength(v)} title={hint}
                              style={{
                                padding: '5px 10px', fontSize: '0.73rem', fontWeight: 700,
                                cursor: 'pointer', borderRadius: 'var(--radius-sm)',
                                border: clipLength === v ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                                background: clipLength === v ? 'rgba(0,242,254,0.12)' : 'transparent',
                                color: clipLength === v ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                              }}>{t}</button>
                    ))}
                  </div>
                </div>
                <button
                  onClick={() => { downloadJob.reset(); setShowDownloadModal(true); }}
                  className="btn-secondary"
                  style={{ background: 'rgba(79, 172, 254, 0.12)', borderColor: 'rgba(79, 172, 254, 0.35)', color: '#4facfe', fontSize: '0.85rem' }}
                >
                  <Download size={16} /> Download
                </button>
                <button
                  onClick={handleTriggerClip}
                  disabled={analyzingClip}
                  className="btn-primary"
                  style={{ background: 'linear-gradient(135deg, #ff0844, #ff4e50)', color: '#fff', fontSize: '0.85rem' }}
                >
                  {analyzingClip
                    ? <><Loader2 size={16} className="animate-spin" /> Mengantre…</>
                    : <><Scissors size={16} /><Sparkles size={14} /> Clip Video</>}
                </button>
              </div>
            </div>

            {/* Konfirmasi untuk video panjang tanpa subtitle */}
            {clipPending && (
              <div style={{
                marginTop: '14px', padding: '14px 16px',
                background: 'var(--bg-card)', border: '1px solid var(--border-color)',
                borderRadius: 'var(--radius-md)',
              }}>
                <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start', marginBottom: '10px' }}>
                  <Clock size={18} style={{ color: 'var(--accent-cyan)', flexShrink: 0, marginTop: '2px' }} />
                  <div>
                    <div style={{ fontSize: '0.92rem', fontWeight: 800, marginBottom: '4px' }}>
                      Video ini tidak punya subtitle di YouTube
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
                      Durasinya {Math.round(clipPending.minutes)} menit, jadi ucapannya harus
                      disalin dulu di komputer ini — perkiraan{' '}
                      <strong style={{ color: 'var(--accent-cyan)' }}>± {clipPending.estimate} menit</strong>.
                      Prosesnya berjalan di latar belakang, jadi Anda tetap bisa menonton
                      dan mengantre video lain sementara menunggu.
                    </div>
                  </div>
                </div>
                <div style={{ marginBottom: '12px' }}>
                  <div style={{
                    fontSize: '0.72rem', fontWeight: 800, color: 'var(--text-secondary)',
                    marginBottom: '7px', letterSpacing: '0.02em',
                  }}>
                    KETELITIAN TRANSKRIP
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                    {[
                      { id: 'base', title: 'Cepat', detail: `± ${clipPending.estimate} menit`,
                        note: 'Cukup untuk bicara jelas dan pelan.' },
                      { id: 'small', title: 'Akurat', detail: `± ${clipPending.estimate * 5} menit`,
                        note: 'Jauh lebih baik untuk percakapan cepat dan bahasa gaul.' },
                    ].map((opt) => (
                      <button key={opt.id} onClick={() => setWhisperModel(opt.id)} style={{
                        textAlign: 'left', padding: '9px 11px', cursor: 'pointer',
                        borderRadius: 'var(--radius-sm)',
                        border: whisperModel === opt.id
                          ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                        background: whisperModel === opt.id ? 'rgba(0,242,254,0.08)' : 'transparent',
                      }}>
                        <div style={{
                          fontSize: '0.82rem', fontWeight: 800,
                          color: whisperModel === opt.id ? 'var(--accent-cyan)' : 'var(--text-primary)',
                        }}>
                          {opt.title} <span style={{ fontWeight: 600, color: 'var(--text-muted)' }}>{opt.detail}</span>
                        </div>
                        <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', lineHeight: 1.4, marginTop: '2px' }}>
                          {opt.note}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <button className="btn-primary" style={{ fontSize: '0.82rem' }}
                          onClick={() => startClipJob(clipPending.video)}>
                    <Sparkles size={14} /> Lanjutkan
                  </button>
                  <button className="btn-secondary" style={{ fontSize: '0.82rem' }}
                          onClick={() => setClipPending(null)}>
                    Batal
                  </button>
                </div>
              </div>
            )}

            {/* Hasil pengantrean */}
            {clipNotice && (
              <div style={{
                marginTop: '14px', padding: '12px 15px', borderRadius: 'var(--radius-md)',
                display: 'flex', alignItems: 'center', gap: '11px', flexWrap: 'wrap',
                background: clipNotice.kind === 'error' ? 'rgba(255,77,109,0.1)' : 'rgba(0,242,254,0.08)',
                border: `1px solid ${clipNotice.kind === 'error' ? 'rgba(255,77,109,0.3)' : 'rgba(0,242,254,0.3)'}`,
              }}>
                {clipNotice.kind === 'error'
                  ? <Loader2 size={16} style={{ color: 'var(--accent-red, #ff4d6d)' }} />
                  : <CheckCircle2 size={16} style={{ color: 'var(--accent-cyan)' }} />}
                <span style={{ fontSize: '0.83rem', flex: 1, minWidth: '200px' }}>{clipNotice.text}</span>
                {clipNotice.kind !== 'error' && (
                  <button className="btn-primary" style={{ fontSize: '0.78rem', padding: '6px 12px' }}
                          onClick={onOpenStudio}>
                    <Scissors size={13} /> Buka Clip Studio
                  </button>
                )}
                <button className="btn-secondary" style={{ fontSize: '0.78rem', padding: '6px 12px' }}
                        onClick={() => setClipNotice(null)}>
                  Tutup
                </button>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT: Related Videos Sidebar */}
        <div style={{ width: '360px', flexShrink: 0, display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <div style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--text-secondary)', marginBottom: '8px', paddingLeft: '4px' }}>
            Video Berikutnya
          </div>
          {relatedLoading ? (
            <div style={{ padding: '40px', textAlign: 'center' }}>
              <Loader2 size={24} className="animate-spin" style={{ color: 'var(--accent-cyan)' }} />
            </div>
          ) : relatedVideos.length === 0 ? (
            <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              Tidak ada video terkait ditemukan.
            </div>
          ) : (
            relatedVideos.map(v => (
              <RelatedVideoCard key={v.id} video={v} onClick={() => handleSelectVideo(v)} />
            ))
          )}
        </div>

        {/* Download Modal */}
        {showDownloadModal && (
          <div className="modal-overlay">
            <div className="modal-box" style={{ maxWidth: '420px' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 700, borderBottom: '1px solid var(--border-color)', paddingBottom: '10px' }}>
                📥 Download: <span style={{ color: 'var(--accent-cyan)', fontSize: '0.9rem' }}>{selectedVideo.title.slice(0, 50)}...</span>
              </h3>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
                {['360p', '480p', '720p', '1080p', 'Audio MP3'].map(res => (
                  <button key={res} onClick={() => setSelectedResolution(res)} style={{
                    padding: '10px 6px', borderRadius: '8px', fontWeight: 700, cursor: 'pointer', fontSize: '0.82rem',
                    border: selectedResolution === res ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                    background: selectedResolution === res ? 'rgba(0,242,254,0.12)' : 'rgba(30,41,59,0.5)',
                    color: selectedResolution === res ? 'var(--accent-cyan)' : 'var(--text-primary)',
                    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px',
                  }}>
                    {res}
                    {selectedResolution === res && <CheckCircle2 size={13} />}
                  </button>
                ))}
              </div>
              {(downloadJob.job || downloadJob.error) && (
                <div style={{ padding: '12px', background: 'var(--bg-glass)', border: '1px solid var(--border-color)', borderRadius: '10px' }}>
                  <JobProgress job={downloadJob.job} error={downloadJob.error} onCancel={downloadJob.cancel} />

                  {downloadResult && (
                    <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {downloadResult.note && (
                        <div style={{ fontSize: '0.76rem', color: 'var(--text-secondary)' }}>{downloadResult.note}</div>
                      )}
                      <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                        {downloadResult.width}×{downloadResult.height} · {(downloadResult.file_size / 1048576).toFixed(1)} MB
                      </div>
                      <button
                        onClick={() => handleProxyDownload(downloadResult.file_name)}
                        className="btn-primary"
                        style={{ background: '#10b981', color: '#fff', fontSize: '0.78rem', padding: '6px 12px', alignSelf: 'flex-start' }}
                      >
                        <Download size={13} /> Simpan ke Perangkat
                      </button>
                    </div>
                  )}
                </div>
              )}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                <button className="btn-secondary" onClick={() => setShowDownloadModal(false)}>Tutup</button>
                <button className="btn-primary" onClick={handleDownloadSubmit} disabled={downloadJob.active}>
                  {downloadJob.active
                    ? <><Loader2 size={15} className="animate-spin" /> Mengunduh…</>
                    : <><Download size={15} /> Unduh via Server</>}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ===== HOMEPAGE / FEED VIEW =====
  return (
    <div className="search-tab">
      {/* Search Bar */}
      <form onSubmit={handleSearchSubmit} className="search-container">
        <div className="search-input-wrapper">
          <Search size={20} />
          <input
            type="text"
            className="search-input"
            placeholder="Cari video YouTube atau tempelkan URL..."
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
        </div>
        <button type="submit" className="btn-primary" disabled={feedLoading}>
          {feedLoading ? <Loader2 size={18} className="animate-spin" /> : <Search size={18} />}
          Cari
        </button>
      </form>

      {/* Category Chips (YouTube-style filter bar) */}
      <div style={{ display: 'flex', gap: '8px', overflowX: 'auto', paddingBottom: '8px', marginBottom: '20px', scrollbarWidth: 'none' }}>
        {CATEGORY_SHORTCUTS.map((cat, i) => (
          <button
            key={cat.label}
            onClick={() => loadCategory(cat.query, i)}
            style={{
              flexShrink: 0,
              padding: '6px 14px',
              borderRadius: '20px',
              border: 'none',
              background: activeCategory === i ? '#fff' : 'rgba(255,255,255,0.1)',
              color: activeCategory === i ? '#000' : 'var(--text-primary)',
              fontWeight: 600,
              fontSize: '0.82rem',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              transition: 'all 0.15s ease',
            }}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Video Grid */}
      {feedLoading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '20px' }}>
          {[...Array(12)].map((_, i) => (
            <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ width: '100%', paddingTop: '56.25%', background: 'rgba(255,255,255,0.05)', borderRadius: '10px', animation: 'pulse 1.5s ease-in-out infinite' }} />
              <div style={{ height: '14px', background: 'rgba(255,255,255,0.05)', borderRadius: '6px', width: '90%', animation: 'pulse 1.5s ease-in-out infinite' }} />
              <div style={{ height: '12px', background: 'rgba(255,255,255,0.05)', borderRadius: '6px', width: '60%', animation: 'pulse 1.5s ease-in-out infinite' }} />
            </div>
          ))}
        </div>
      ) : feedError ? (
        <div style={{
          padding: '46px 24px', textAlign: 'center', background: 'var(--bg-card)',
          borderRadius: '16px', border: '1px solid rgba(255,77,109,0.35)',
        }}>
          <Video size={38} style={{ color: 'var(--accent-red, #ff4d6d)', marginBottom: '12px' }} />
          <h3 style={{ fontWeight: 700, marginBottom: '6px' }}>Pencarian gagal</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6, maxWidth: '440px', margin: '0 auto' }}>
            {feedError.message}
          </p>
          {feedError.code === 'YTDLP_RATE_LIMIT' && (
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '10px', lineHeight: 1.6 }}>
              YouTube sedang membatasi permintaan dari komputer ini. Tunggu beberapa
              menit, atau pasang berkas cookies di halaman Settings.
            </p>
          )}
          <button className="btn-secondary" style={{ marginTop: '16px', fontSize: '0.83rem' }}
                  onClick={() => (activeCategory >= 0
                    ? loadCategory(CATEGORY_SHORTCUTS[activeCategory].query, activeCategory)
                    : handleSearchSubmit())}>
            Coba lagi
          </button>
        </div>
      ) : feed.length === 0 ? (
        <div style={{ padding: '60px 20px', textAlign: 'center', background: 'var(--bg-card)', borderRadius: '16px', border: '1px dashed var(--border-color)' }}>
          <Video size={40} style={{ color: 'var(--text-muted)', marginBottom: '12px' }} />
          <h3 style={{ fontWeight: 700 }}>Tidak ada video ditemukan</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>Coba kata kunci yang berbeda.</p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '20px 16px' }}>
          {feed.map(video => (
            <VideoCard
              key={video.id}
              video={video}
              isSelected={selectedVideo?.id === video.id}
              onClick={() => handleSelectVideo(video)}
            />
          ))}
        </div>
      )}
    </div>
  );
}
