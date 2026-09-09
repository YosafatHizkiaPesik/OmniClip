import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Search, Loader2, Video, RefreshCw } from 'lucide-react';
import { apiGet } from '../lib/api';
import { VideoCard } from '../components/VideoCards';

// Tahun sengaja tidak dicantumkan: menempelkan "2024" ke setiap kueri menyaring
// hasil ke tahun yang sudah lewat.
// Emoji dibuang: ia bukan sistem ikon, dan sebelas emoji dari sebelas keluarga
// gambar yang berbeda membuat baris ini terbaca sebagai tempelan, bukan kendali.
const CATEGORIES = [
  { label: 'Trending', query: 'trending viral indonesia' },
  { label: 'Podcast', query: 'podcast indonesia terbaru' },
  { label: 'Wawancara', query: 'wawancara eksklusif indonesia' },
  { label: 'Edukasi', query: 'edukasi menarik indonesia' },
  { label: 'Gaming', query: 'gaming highlights indonesia' },
  { label: 'Musik', query: 'musik viral indonesia' },
  { label: 'Tech', query: 'teknologi AI indonesia' },
  { label: 'Finance', query: 'investasi tips keuangan indonesia' },
  { label: 'Komedi', query: 'komedi lucu indonesia' },
  { label: 'Kuliner', query: 'kuliner makanan enak indonesia' },
  { label: 'Travel', query: 'travel wisata indonesia' },
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
  // Dinaikkan oleh tombol Segarkan. Beranda tanpa kata kunci mengambil kueri
  // acak dari server, jadi menaikkan angka ini benar-benar mengganti isinya.
  const [nonce, setNonce] = useState(0);
  const [sort, setSort] = useState('relevan');
  // Tanggal unggah datang MENYUSUL, dari panggilan terpisah: hasil pencarian
  // YouTube tidak membawanya sama sekali, dan mengambilnya berarti membuka tiap
  // videonya. Kartunya tampil dulu, tanggalnya mengisi belakangan.
  const [dates, setDates] = useState({});

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
      ? `/search?q=${encodeURIComponent(q)}&limit=20&sort=${sort}`
      : `/trending?limit=20&refresh=${nonce}`);
  }, [q, nonce, sort, load]);

  useEffect(() => {
    const ids = feed.map((v) => v.id).filter(Boolean);
    if (!ids.length) return undefined;
    let cancelled = false;
    apiGet(`/upload-dates?ids=${ids.join(',')}`)
      .then((res) => { if (!cancelled) setDates((prev) => ({ ...prev, ...res })); })
      // Tanggal yang tidak datang bukan kegagalan halaman: kartunya cukup
      // tidak menuliskan tanggal apa pun.
      .catch(() => {});
    return () => { cancelled = true; };
  }, [feed]);

  const submit = (e) => {
    e.preventDefault();
    const value = draft.trim();
    setParams(value ? { q: value } : {}, { replace: false });
  };

  const activeCategory = CATEGORIES.findIndex((c) => c.query === q);

  // Urutan dikerjakan YouTube, bukan diurutkan ulang di sini: tanpa tanggal
  // unggah di hasil pencarian, "terbaru" mustahil dijawab dari data yang ada.
  const SORTS = [
    ['relevan', 'Paling relevan'],
    ['terbaru', 'Terbaru'],
    ['terpopuler', 'Tayangan terbanyak'],
    ['rating', 'Paling disukai'],
  ];

  return (
    <div className="page">
      <div className="work-block">
        <div style={{ minWidth: 0, flex: '1 1 260px' }}>
          <h1 className="work-title">Cari video</h1>
          <div className="sub">
            Tempel tautan YouTube, atau telusuri untuk mencari bahan.
          </div>
        </div>
        {!q && (
          <div className="actions">
            <button className="btn-secondary" disabled={loading}
                    onClick={() => setNonce((n) => n + 1)}>
              <RefreshCw size={14} className={loading ? 'animate-spin' : undefined} />
              Segarkan
            </button>
          </div>
        )}
      </div>

      <form onSubmit={submit} className="search-container">
        <div className="search-input-wrapper">
          <input
            type="text"
            className="search-input"
            placeholder="Tempel tautan YouTube, atau ketik kata kunci"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          <button type="submit" className="btn-primary" disabled={loading}
                  style={{ minWidth: '104px' }}>
            {loading ? <Loader2 size={16} className="animate-spin" /> : <Search size={16} />}
            Cari
          </button>
        </div>
      </form>

      <div style={{
        display: 'flex', gap: '8px', overflowX: 'auto',
        paddingBottom: '8px', marginBottom: '20px', scrollbarWidth: 'none',
      }}>
        {CATEGORIES.map((cat, i) => (
          <button
            key={cat.label}
            onClick={() => setParams({ q: cat.query })}
            className={`chip${activeCategory === i ? ' is-on' : ''}`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {/* Urutan hanya berlaku untuk pencarian: beranda tanpa kata kunci sudah
          mengambil kueri acak tiap muat, dan mengurutkannya tidak berarti. */}
      {q && (
        <div style={{
          display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center',
          marginBottom: '18px',
        }}>
          <span className="mark" style={{ color: 'var(--ink-3)' }}>Urutkan</span>
          {SORTS.map(([id, label]) => (
            <button key={id} onClick={() => setSort(id)}
                    className={`chip${sort === id ? ' is-on' : ''}`}>
              {label}
            </button>
          ))}
        </div>
      )}

      {loading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '20px' }}>
          {[...Array(12)].map((_, i) => (
            <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ width: '100%', paddingTop: '56.25%', background: 'var(--plate-2)', borderRadius: 'var(--r-sm)', animation: 'pulse 1.5s ease-in-out infinite' }} />
              <div style={{ height: '14px', background: 'var(--plate-2)', borderRadius: 'var(--r-sm)', width: '90%', animation: 'pulse 1.5s ease-in-out infinite' }} />
              <div style={{ height: '12px', background: 'var(--plate-2)', borderRadius: 'var(--r-sm)', width: '60%', animation: 'pulse 1.5s ease-in-out infinite' }} />
            </div>
          ))}
        </div>
      ) : error ? (
        <div style={{
          padding: '46px 24px', textAlign: 'center', background: 'var(--bg-card)',
          borderRadius: 'var(--r-md)', border: '1px solid color-mix(in srgb, var(--danger) 40%, transparent)',
        }}>
          <Video size={38} style={{ color: 'var(--danger)', marginBottom: '12px' }} />
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
                  onClick={() => setNonce((n) => n + 1)}>
            Coba lagi
          </button>
        </div>
      ) : feed.length === 0 ? (
        <div style={{ padding: '60px 20px', textAlign: 'center', background: 'var(--bg-card)', borderRadius: 'var(--r-md)', border: '1px dashed var(--border-color)' }}>
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
              video={{ ...video, ...(dates[video.id] ?? {}) }}
              onClick={() => navigate(`/watch/${video.id}`, { state: { video } })}
            />
          ))}
        </div>
      )}
    </div>
  );
}
