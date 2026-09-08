import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Search, Loader2, Video } from 'lucide-react';
import { apiGet } from '../lib/api';
import { VideoCard } from '../components/VideoCards';

// Tahun sengaja tidak dicantumkan: menempelkan "2024" ke setiap kueri menyaring
// hasil ke tahun yang sudah lewat.
const CATEGORIES = [
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

/**
 * Feed pencarian.
 *
 * Kata kunci disimpan di URL (`/?q=...`), bukan hanya di state komponen.
 * Dengan begitu tombol back browser mengembalikan pencarian sebelumnya, dan
 * sebuah hasil pencarian bisa dibagikan atau di-bookmark.
 */
export default function Home() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const q = params.get('q') ?? '';
  const [draft, setDraft] = useState(q);
  const [feed, setFeed] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => { setDraft(q); }, [q]);

  const load = useCallback(async (path) => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiGet(path);
      setFeed(Array.isArray(data) ? data : []);
    } catch (err) {
      // Kegagalan harus terlihat: `catch { setFeed([]) }` membuat rate limit
      // YouTube tampak persis seperti "tidak ada hasil".
      setFeed([]);
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(q
      ? `/search?q=${encodeURIComponent(q)}&limit=20`
      : '/trending?limit=20');
  }, [q, load]);

  const submit = (e) => {
    e.preventDefault();
    const value = draft.trim();
    setParams(value ? { q: value } : {}, { replace: false });
  };

  const activeCategory = CATEGORIES.findIndex((c) => c.query === q);

  return (
    <div className="search-tab">
      <form onSubmit={submit} className="search-container">
        <div className="search-input-wrapper">
          <Search size={20} />
          <input
            type="text"
            className="search-input"
            placeholder="Cari video YouTube atau tempelkan URL..."
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
        </div>
        <button type="submit" className="btn-primary" disabled={loading}>
          {loading ? <Loader2 size={18} className="animate-spin" /> : <Search size={18} />}
          Cari
        </button>
      </form>

      <div style={{
        display: 'flex', gap: '8px', overflowX: 'auto',
        paddingBottom: '8px', marginBottom: '20px', scrollbarWidth: 'none',
      }}>
        {CATEGORIES.map((cat, i) => (
          <button
            key={cat.label}
            onClick={() => setParams({ q: cat.query })}
            style={{
              flexShrink: 0, padding: '6px 14px', borderRadius: '20px', border: 'none',
              background: activeCategory === i ? '#fff' : 'rgba(255,255,255,0.1)',
              color: activeCategory === i ? '#000' : 'var(--text-primary)',
              fontWeight: 600, fontSize: '0.82rem', cursor: 'pointer', whiteSpace: 'nowrap',
            }}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '20px' }}>
          {[...Array(12)].map((_, i) => (
            <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ width: '100%', paddingTop: '56.25%', background: 'rgba(255,255,255,0.05)', borderRadius: '10px', animation: 'pulse 1.5s ease-in-out infinite' }} />
              <div style={{ height: '14px', background: 'rgba(255,255,255,0.05)', borderRadius: '6px', width: '90%', animation: 'pulse 1.5s ease-in-out infinite' }} />
              <div style={{ height: '12px', background: 'rgba(255,255,255,0.05)', borderRadius: '6px', width: '60%', animation: 'pulse 1.5s ease-in-out infinite' }} />
            </div>
          ))}
        </div>
      ) : error ? (
        <div style={{
          padding: '46px 24px', textAlign: 'center', background: 'var(--bg-card)',
          borderRadius: '16px', border: '1px solid rgba(255,77,109,0.35)',
        }}>
          <Video size={38} style={{ color: 'var(--accent-red, #ff4d6d)', marginBottom: '12px' }} />
          <h3 style={{ fontWeight: 700, marginBottom: '6px' }}>Pencarian gagal</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6, maxWidth: '440px', margin: '0 auto' }}>
            {error.message}
          </p>
          {error.code === 'YTDLP_RATE_LIMIT' && (
            <p style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginTop: '10px', lineHeight: 1.6 }}>
              YouTube sedang membatasi permintaan dari komputer ini. Tunggu beberapa
              menit, atau pasang berkas cookies di halaman Settings.
            </p>
          )}
          <button className="btn-secondary" style={{ marginTop: '16px', fontSize: '0.83rem' }}
                  onClick={() => load(q ? `/search?q=${encodeURIComponent(q)}&limit=20` : '/trending?limit=20')}>
            Coba lagi
          </button>
        </div>
      ) : feed.length === 0 ? (
        <div style={{ padding: '60px 20px', textAlign: 'center', background: 'var(--bg-card)', borderRadius: '16px', border: '1px dashed var(--border-color)' }}>
          <Video size={40} style={{ color: 'var(--text-muted)', marginBottom: '12px' }} />
          <h3 style={{ fontWeight: 700 }}>Tidak ada video ditemukan</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Coba kata kunci yang berbeda.
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '20px 16px' }}>
          {feed.map((video) => (
            <VideoCard
              key={video.id}
              video={video}
              onClick={() => navigate(`/watch/${video.id}`, { state: { video } })}
            />
          ))}
        </div>
      )}
    </div>
  );
}
