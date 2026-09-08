import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Play, Pause, RotateCcw } from 'lucide-react';

const RATIO_BOX = {
  '9:16': { width: 300, aspect: '9 / 16' },
  '1:1': { width: 380, aspect: '1 / 1' },
  '4:5': { width: 340, aspect: '4 / 5' },
  '16:9': { width: 520, aspect: '16 / 9' },
};

/**
 * Pemutar pratinjau klip.
 *
 * Klip bisa terdiri dari beberapa segmen dari bagian video yang berbeda, jadi
 * pemutar melompat sendiri ke segmen berikutnya saat segmen berjalan habis —
 * inilah yang membuat gabungan menit 10 + menit 50 bisa ditonton utuh sebelum
 * dirender.
 */
export default function ClipPreview({
  src, clip, aspectRatio = '9:16', style,
  // Timeline perlu membaca posisi pemutaran untuk menggambar playhead, jadi
  // elemen <video> dibagi lewat ref dari luar.
  videoRef: externalRef,
  // Saat pengguna menjelajahi timeline video panjang, pemutar tidak boleh
  // menarik posisinya kembali ke dalam batas klip.
  constrained = true,
}) {
  const innerRef = useRef(null);
  const videoRef = externalRef ?? innerRef;
  const [segIndex, setSegIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [clipTime, setClipTime] = useState(0);

  const segments = clip?.segments ?? [];
  const offsets = useMemo(() => {
    let acc = 0;
    return segments.map((s) => {
      const o = acc;
      acc += Math.max(0, s.end - s.start);
      return o;
    });
  }, [segments]);
  const totalDuration = useMemo(
    () => segments.reduce((a, s) => a + Math.max(0, s.end - s.start), 0),
    [segments],
  );

  // Kembali ke awal saat klip atau batasnya berubah.
  useEffect(() => {
    setSegIndex(0);
    setClipTime(0);
    const v = videoRef.current;
    if (v && segments[0]) {
      v.currentTime = segments[0].start;
    }
  }, [clip?.clip_id, segments[0]?.start, segments.length]);

  const handleTimeUpdate = () => {
    const v = videoRef.current;
    const seg = segments[segIndex];
    if (!v || !seg) return;
    if (!constrained) return;   // mode jelajah: biarkan video berjalan bebas

    if (v.currentTime >= seg.end - 0.03) {
      const next = segIndex + 1;
      if (next < segments.length) {
        setSegIndex(next);
        v.currentTime = segments[next].start;
      } else {
        v.pause();
        setPlaying(false);
        setSegIndex(0);
        v.currentTime = segments[0].start;
        setClipTime(0);
      }
      return;
    }
    if (v.currentTime < seg.start - 0.5) v.currentTime = seg.start;
    setClipTime((offsets[segIndex] ?? 0) + (v.currentTime - seg.start));
  };

  const toggle = () => {
    const v = videoRef.current;
    if (!v) return;
    if (playing) {
      v.pause();
    } else {
      const seg = segments[segIndex];
      if (seg && (v.currentTime < seg.start || v.currentTime > seg.end)) {
        v.currentTime = seg.start;
      }
      v.play();
    }
  };

  const restart = () => {
    const v = videoRef.current;
    if (!v || !segments[0]) return;
    setSegIndex(0);
    v.currentTime = segments[0].start;
    setClipTime(0);
    v.play();
  };

  // Baris subtitle yang aktif pada posisi klip saat ini. Dalam mode jelajah
  // tidak ada baris yang ditampilkan: waktunya relatif terhadap klip, bukan
  // terhadap video sumber, jadi menampilkannya justru menyesatkan.
  const activeLine = useMemo(() => {
    if (!constrained) return null;
    const lines = clip?.subtitles ?? [];
    return lines.find((l) => clipTime >= l.start && clipTime <= l.end) ?? null;
  }, [clip?.subtitles, clipTime, constrained]);

  const activeWordIndex = useMemo(() => {
    if (!activeLine?.words?.length) return -1;
    return activeLine.words.findIndex((w) => clipTime >= w.s && clipTime <= w.e);
  }, [activeLine, clipTime]);

  const box = RATIO_BOX[aspectRatio] ?? RATIO_BOX['9:16'];
  const showHook = constrained && clipTime < 3.5 && (clip?.hook_text || '').trim();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
      <div
        style={{
          position: 'relative',
          width: '100%',
          maxWidth: `${box.width}px`,
          aspectRatio: box.aspect,
          background: '#000',
          borderRadius: '14px',
          overflow: 'hidden',
          boxShadow: 'var(--shadow-card)',
        }}
      >
        {src ? (
          <video
            ref={videoRef}
            src={src}
            onTimeUpdate={handleTimeUpdate}
            onPlay={() => setPlaying(true)}
            onPause={() => setPlaying(false)}
            playsInline
            style={{ width: '100%', height: '100%', objectFit: 'contain', background: '#000' }}
          />
        ) : (
          <div style={{
            width: '100%', height: '100%', display: 'flex', alignItems: 'center',
            justifyContent: 'center', color: 'var(--text-muted)', fontSize: '0.8rem',
            textAlign: 'center', padding: '20px',
          }}>
            Video sumber belum tersedia untuk pratinjau.
          </div>
        )}

        {/* Hook — tampilan ini mencerminkan apa yang benar-benar dibakar ke video */}
        {showHook && (
          <div style={{
            position: 'absolute', top: '7%', left: '6%', right: '6%',
            textAlign: 'center', color: '#00E5FF', fontWeight: 900,
            fontSize: 'clamp(0.85rem, 4.2vw, 1.15rem)', lineHeight: 1.15,
            textTransform: 'uppercase', letterSpacing: '0.01em',
            background: 'rgba(0,0,0,0.7)', padding: '8px 10px', borderRadius: '8px',
            pointerEvents: 'none',
          }}>
            {clip.hook_text}
          </div>
        )}

        {/* Karaoke */}
        {activeLine && (
          <div style={{
            position: 'absolute', left: '5%', right: '5%',
            bottom: style?.position === 'top' ? undefined : '14%',
            top: style?.position === 'top' ? '18%' : undefined,
            textAlign: 'center', pointerEvents: 'none',
            fontWeight: 900, lineHeight: 1.2,
            fontSize: `clamp(0.9rem, ${(style?.size ?? 96) / 22}vw, 1.5rem)`,
            textShadow: '0 2px 0 #000, 2px 0 0 #000, -2px 0 0 #000, 0 -2px 0 #000, 0 3px 8px rgba(0,0,0,0.9)',
            textTransform: style?.uppercase === false ? 'none' : 'uppercase',
          }}>
            {(activeLine.words?.length ? activeLine.words : [{ w: activeLine.text }]).map((w, i) => (
              <span key={i} style={{
                color: i === activeWordIndex ? (style?.highlight ?? '#FFE500') : (style?.primary ?? '#FFFFFF'),
                marginRight: '0.28em',
                display: 'inline-block',
                transform: i === activeWordIndex ? 'scale(1.08)' : 'none',
                transition: 'transform 90ms ease',
              }}>{w.w}</span>
            ))}
          </div>
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.8rem' }}>
        <button className="btn-secondary" onClick={toggle} disabled={!src}
                style={{ padding: '6px 14px' }}>
          {playing ? <Pause size={14} /> : <Play size={14} />}
          {playing ? 'Jeda' : 'Putar'}
        </button>
        <button className="btn-secondary" onClick={restart} disabled={!src}
                style={{ padding: '6px 12px' }} aria-label="Ulang dari awal">
          <RotateCcw size={14} />
        </button>
        <span style={{ color: 'var(--text-secondary)', fontVariantNumeric: 'tabular-nums' }}>
          {constrained ? (
            <>
              {clipTime.toFixed(1)}s / {totalDuration.toFixed(1)}s
              {segments.length > 1 && ` · potongan ${segIndex + 1}/${segments.length}`}
            </>
          ) : 'Mode jelajah video sumber'}
        </span>
      </div>
    </div>
  );
}
