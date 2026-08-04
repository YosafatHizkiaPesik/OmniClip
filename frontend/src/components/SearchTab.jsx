import React, { useState, useEffect, useRef } from 'react';
import { Search, Download, Scissors, Play, ArrowLeft, CheckCircle2, Sparkles, Loader2, Video, TrendingUp, Flame, Music, Gamepad2, Cpu, Globe, Eye, Clock } from 'lucide-react';
import { formatTime, formatDurationHuman } from '../utils/timeFormat';

const CATEGORY_SHORTCUTS = [
  { label: 'Semua', query: 'trending viral indonesia 2024' },
  { label: '🔥 Trending', query: 'trending viral indonesia 2024' },
  { label: '🎙️ Podcast', query: 'podcast viral indonesia 2024' },
  { label: '🎮 Gaming', query: 'gaming highlights indonesia 2024' },
  { label: '🎵 Musik', query: 'musik viral indonesia 2024' },
  { label: '💻 Tech', query: 'teknologi AI indonesia 2024' },
  { label: '💰 Finance', query: 'investasi tips keuangan indonesia 2024' },
  { label: '😂 Komedi', query: 'komedi lucu indonesia 2024' },
  { label: '🍜 Kuliner', query: 'kuliner makanan enak indonesia 2024' },
  { label: '✈️ Travel', query: 'travel wisata indonesia 2024' },
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

export default function SearchTab({ onOpenClipEditor }) {
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
  const [downloading, setDownloading] = useState(false);
  const [downloadResult, setDownloadResult] = useState(null);

  // AI clip analyze
  const [analyzingClip, setAnalyzingClip] = useState(false);

  // Load trending on mount (YouTube homepage style)
  useEffect(() => {
    loadTrending();
  }, []);

  const loadTrending = async () => {
    setFeedLoading(true);
    try {
      const res = await fetch('http://localhost:8000/api/trending?limit=20');
      const data = await res.json();
      setFeed(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Trending error:', err);
      setFeed([]);
    } finally {
      setFeedLoading(false);
    }
  };

  const loadCategory = async (catQuery, catIndex) => {
    setActiveCategory(catIndex);
    setFeedLoading(true);
    setSelectedVideo(null);
    try {
      const res = await fetch(`http://localhost:8000/api/search?q=${encodeURIComponent(catQuery)}&limit=20`);
      const data = await res.json();
      setFeed(Array.isArray(data) ? data : []);
    } catch (err) {
      setFeed([]);
    } finally {
      setFeedLoading(false);
    }
  };

  const handleSearchSubmit = async (e) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;
    setFeedLoading(true);
    setSelectedVideo(null);
    setActiveCategory(-1);
    try {
      const res = await fetch(`http://localhost:8000/api/search?q=${encodeURIComponent(query.trim())}&limit=20`);
      const data = await res.json();
      setFeed(Array.isArray(data) ? data : []);
    } catch {
      setFeed([]);
    } finally {
      setFeedLoading(false);
    }
  };

  // When user selects a video → load related videos from a related query
  const handleSelectVideo = async (video) => {
    setSelectedVideo(video);
    setRelatedLoading(true);
    setDownloadResult(null);
    // Scroll to top
    window.scrollTo({ top: 0, behavior: 'smooth' });
    try {
      // Search for related videos based on channel + title keywords
      const relatedQuery = `${video.channel} ${video.title.split(' ').slice(0, 4).join(' ')}`;
      const res = await fetch(`http://localhost:8000/api/search?q=${encodeURIComponent(relatedQuery)}&limit=15`);
      const data = await res.json();
      // Exclude the current video
      const filtered = (Array.isArray(data) ? data : []).filter(v => v.id !== video.id);
      setRelatedVideos(filtered.slice(0, 12));
    } catch {
      setRelatedVideos([]);
    } finally {
      setRelatedLoading(false);
    }
  };

  const handleDownloadSubmit = async () => {
    if (!selectedVideo) return;
    setDownloading(true);
    setDownloadResult(null);
    try {
      const res = await fetch('http://localhost:8000/api/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: selectedVideo.url, resolution: selectedResolution })
      });
      const data = await res.json();
      if (res.ok) {
        setDownloadResult(data);
      } else {
        alert(data.detail || 'Pengunduhan gagal. Coba resolusi lain.');
      }
    } catch {
      alert('Gagal terhubung ke backend. Pastikan server berjalan.');
    } finally {
      setDownloading(false);
    }
  };

  const handleProxyDownload = async (fileName) => {
    try {
      const res = await fetch(`http://localhost:8000/api/file/local_downloads/${encodeURIComponent(fileName)}`);
      if (!res.ok) throw new Error('File tidak ditemukan');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = fileName;
      document.body.appendChild(a); a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) { alert(`Gagal download: ${err.message}`); }
  };

  const handleTriggerClip = () => {
    if (!selectedVideo) return;
    // Immediately open Studio Editor (aiData=null triggers smooth loading screen in StudioEditor)
    onOpenClipEditor(selectedVideo, null);
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
              src={`https://www.youtube-nocookie.com/embed/${selectedVideo.id}?autoplay=1&rel=0&enablejsapi=1&origin=http://localhost:5173`}
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
              <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
                <button
                  onClick={() => { setDownloadResult(null); setShowDownloadModal(true); }}
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
                    ? <><Loader2 size={16} className="animate-spin" /> Gemini menganalisis...</>
                    : <><Scissors size={16} /><Sparkles size={14} /> AI Clip Studio</>}
                </button>
              </div>
            </div>
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
              {downloadResult && (
                <div style={{ padding: '10px', background: 'rgba(16,185,129,0.15)', border: '1px solid #10b981', borderRadius: '8px', fontSize: '0.82rem', color: '#10b981' }}>
                  <div style={{ fontWeight: 700, marginBottom: '6px' }}>✅ {downloadResult.file_name}</div>
                  <button onClick={() => handleProxyDownload(downloadResult.file_name)} className="btn-primary" style={{ background: '#10b981', color: '#fff', fontSize: '0.78rem', padding: '5px 12px' }}>
                    <Download size={13} /> Simpan ke Perangkat
                  </button>
                </div>
              )}
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                <button className="btn-secondary" onClick={() => setShowDownloadModal(false)}>Tutup</button>
                <button className="btn-primary" onClick={handleDownloadSubmit} disabled={downloading}>
                  {downloading ? <><Loader2 size={15} className="animate-spin" /> Mengunduh...</> : <><Download size={15} /> Unduh via Server</>}
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
      ) : feed.length === 0 ? (
        <div style={{ padding: '60px 20px', textAlign: 'center', background: 'var(--bg-card)', borderRadius: '16px', border: '1px dashed var(--border-color)' }}>
          <Video size={40} style={{ color: 'var(--text-muted)', marginBottom: '12px' }} />
          <h3 style={{ fontWeight: 700 }}>Tidak ada video ditemukan</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>Coba kata kunci yang berbeda atau periksa koneksi internet.</p>
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
