import React from 'react';
import { Play } from 'lucide-react';
import { formatTime } from '../utils/timeFormat';

/**
 * Kartu video yang dipakai bersama oleh feed dan daftar rekomendasi.
 *
 * Sebelumnya semuanya tinggal di dalam SearchTab, sehingga halaman tonton dan
 * halaman feed tidak bisa dipisah menjadi dua rute tanpa menyalin kodenya.
 */

/**
 * Umur video, dari tanggal unggah sungguhan.
 *
 * Mengembalikan string kosong bila tanggalnya belum diketahui — dan itu
 * disengaja. Hasil pencarian YouTube tidak membawa tanggal unggah sama sekali;
 * tanggalnya menyusul beberapa detik kemudian dari panggilan terpisah. Selama
 * belum datang, kartunya tidak menuliskan apa pun. Menuliskan "baru" atau hari
 * ini sebagai nilai bawaan akan membuat video tujuh tahun lalu terlihat seperti
 * unggahan kemarin.
 */
export function formatAge(uploadDate) {
  if (!uploadDate || !/^\d{8}$/.test(String(uploadDate))) return '';
  const t = String(uploadDate);
  const then = new Date(+t.slice(0, 4), +t.slice(4, 6) - 1, +t.slice(6, 8));
  const days = Math.floor((Date.now() - then.getTime()) / 86400000);
  if (!Number.isFinite(days) || days < 0) return '';
  if (days < 1) return 'hari ini';
  if (days < 7) return `${days} hari lalu`;
  if (days < 30) return `${Math.floor(days / 7)} minggu lalu`;
  if (days < 365) return `${Math.floor(days / 30)} bulan lalu`;
  const years = Math.floor(days / 365);
  return `${years} tahun lalu`;
}

export function formatViews(views) {
  if (!views) return '';
  if (views >= 1_000_000) return `${(views / 1_000_000).toFixed(1)}Jt`;
  if (views >= 1_000) return `${(views / 1_000).toFixed(0)}Rb`;
  return `${views}`;
}

// Avatar Channel
export function ChannelAvatar({ name, size = 36 }) {
  const initials = name ? name.slice(0, 2).toUpperCase() : '?';
  const colors = ['var(--reh)', '#4facfe', '#7f00ff', 'var(--danger)', 'var(--entry)', '#f59e0b'];
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
export function VideoCard({ video, isSelected, onClick }) {
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
      <div className="pit-frame">
        <div className="pit-well" style={{ paddingTop: '56.25%' }}>
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
            background: 'var(--hl-wash)',
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
      </div>

      {/* Info */}
      <div style={{ display: 'flex', gap: '10px', padding: '10px 2px 4px' }}>
        <ChannelAvatar name={video.channel} size={36} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: '0.87rem', fontWeight: 660, lineHeight: 1.35, color: 'var(--ink)',
            display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
          }}>{video.title}</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--ink-2)', marginTop: '3px' }}>
            {video.channel}
          </div>
          <div style={{ fontSize: '0.72rem', color: 'var(--ink-3)', marginTop: '1px', display: 'flex', gap: '6px' }}>
            {/* Durasi TIDAK diulang di sini: lencana di pojok gambar sudah
                menyebutkannya, dan menuliskannya dua kali dengan format berbeda
                ("56:42" dan "56 mnt 42 dtk") membuat keduanya terbaca seperti
                dua angka yang berbeda. */}
            {video.views > 0 && <span>{formatViews(video.views)} tayangan</span>}
            {formatAge(video.upload_date) && <span>• {formatAge(video.upload_date)}</span>}
          </div>
        </div>
      </div>
    </div>
  );
}

// Horizontal small card for related/sidebar
export function RelatedVideoCard({ video, onClick }) {
  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', gap: '10px', cursor: 'pointer', padding: '6px',
        borderRadius: '8px', transition: 'background 0.15s',
      }}
      onMouseEnter={e => e.currentTarget.style.background = 'var(--plate-2)'}
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
          fontSize: '0.82rem', fontWeight: 660, lineHeight: 1.3, color: 'var(--ink)',
          display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
        }}>{video.title}</div>
        <div style={{ fontSize: '0.72rem', color: 'var(--ink-2)', marginTop: '4px' }}>{video.channel}</div>
        {video.views > 0 && <div style={{ fontSize: '0.68rem', color: 'var(--ink-3)' }}>{formatViews(video.views)} views</div>}
      </div>
    </div>
  );
}

