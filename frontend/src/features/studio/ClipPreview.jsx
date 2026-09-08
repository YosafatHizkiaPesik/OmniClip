import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Play, Pause, RotateCcw, Loader2 } from 'lucide-react';

const RATIO_BOX = {
  '9:16': { width: 300, aspect: '9 / 16' },
  '1:1': { width: 380, aspect: '1 / 1' },
  '4:5': { width: 340, aspect: '4 / 5' },
  '16:9': { width: 520, aspect: '16 / 9' },
};

/**
 * Pemutar pratinjau klip.
 *
 * Dua tugasnya:
 *
 * 1. Klip bisa terdiri dari beberapa segmen dari bagian video yang berbeda,
 *    jadi pemutar melompat sendiri ke segmen berikutnya saat segmen berjalan
 *    habis — inilah yang membuat gabungan menit 10 + menit 50 bisa ditonton
 *    utuh sebelum dirender.
 *
 * 2. Menampilkan BINGKAI yang sebenarnya, bukan frame 16:9 apa adanya.
 *    Sebelumnya pratinjau memperlihatkan video sumber utuh, sehingga tidak ada
 *    cara melihat bagaimana smart reframe membingkai pembicara selain dengan
 *    merender dulu. Sekarang crop-nya digerakkan di sini memakai rencana yang
 *    sama persis yang nanti dikirim ke ffmpeg.
 */
export default function ClipPreview({
  src, clip, aspectRatio = '9:16', style,
  videoRef: externalRef,
  constrained = true,
  frameMode = 'smart',
  reframe = null,          // {available, crop_w, source_w, keyframes:[[t,x]]}
  reframeLoading = false,
}) {
  const innerRef = useRef(null);
  const videoRef = externalRef ?? innerRef;
  const bgRef = useRef(null);
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

  useEffect(() => {
    setSegIndex(0);
    setClipTime(0);
    const v = videoRef.current;
    if (v && segments[0]) v.currentTime = segments[0].start;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clip?.clip_id, segments[0]?.start, segments.length]);

  const useReframe = frameMode === 'smart' && reframe?.available && constrained;
  const useCenter = frameMode === 'center';
  const useBlur = !useReframe && !useCenter;

  /**
   * Posisi crop pada waktu klip tertentu.
   *
   * Keyframe hanya ditulis saat nilainya berubah, jadi pencarian di sini
   * mengambil perintah terakhir yang berlaku — persis cara `sendcmd` ffmpeg
   * menafsirkannya, sehingga pratinjau dan hasil render tidak berbeda.
   */
  const cropXAt = useMemo(() => {
    const kf = reframe?.keyframes;
    if (!kf?.length) return null;
    return (t) => {
      let lo = 0;
      let hi = kf.length - 1;
      if (t <= kf[0][0]) return kf[0][1];
      while (lo < hi) {
        const mid = Math.ceil((lo + hi) / 2);
        if (kf[mid][0] <= t) lo = mid;
        else hi = mid - 1;
      }
      return kf[lo][1];
    };
  }, [reframe]);

  // Loop rAF: menggerakkan crop lewat ref (tanpa state) dan menyegarkan waktu
  // klip pada ~20 Hz. `timeupdate` hanya menyala 4 Hz — terlalu kasar untuk
  // sorotan karaoke per kata, dan jauh terlalu kasar untuk gerakan kamera.
  useEffect(() => {
    let raf;
    let lastPushed = -1;
    const tick = () => {
      const v = videoRef.current;
      if (v) {
        const seg = segments[segIndex];
        const t = constrained && seg
          ? (offsets[segIndex] ?? 0) + (v.currentTime - seg.start)
          : v.currentTime;

        if (useReframe && cropXAt) {
          const x = cropXAt(Math.max(0, t));
          v.style.transform = `translateX(${(-x / reframe.source_w) * 100}%)`;
        }
        if (bgRef.current && Math.abs(bgRef.current.currentTime - v.currentTime) > 0.25) {
          bgRef.current.currentTime = v.currentTime;
        }
        if (Math.abs(t - lastPushed) > 0.05) {
          lastPushed = t;
          setClipTime(t);
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [videoRef, segments, segIndex, offsets, constrained, useReframe, cropXAt, reframe]);

  const handleTimeUpdate = () => {
    const v = videoRef.current;
    const seg = segments[segIndex];
    if (!v || !seg) return;
    if (!constrained) return;

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
      }
      return;
    }
    if (v.currentTime < seg.start - 0.5) v.currentTime = seg.start;
  };

  const toggle = () => {
    const v = videoRef.current;
    if (!v) return;
    if (playing) {
      v.pause();
      bgRef.current?.pause();
    } else {
      const seg = segments[segIndex];
      if (constrained && seg && (v.currentTime < seg.start || v.currentTime > seg.end)) {
        v.currentTime = seg.start;
      }
      v.play();
      bgRef.current?.play().catch(() => { /* latar kabur boleh gagal diam-diam */ });
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
  const showHook = constrained && clipTime < 3.5 && (clip?.hook_text || '').trim()
    && style?.showHook !== false;

  // Geometri crop. Lebar video dilebihkan sebesar rasio sumber terhadap crop,
  // lalu digeser; hasilnya jendela crop persis mengisi kotak pratinjau.
  const zoom = reframe?.source_w && reframe?.crop_w
    ? (reframe.source_w / reframe.crop_w) * 100 : 100;

  const videoStyle = useReframe
    ? {
      position: 'absolute', top: 0, left: 0, height: '100%', width: `${zoom}%`,
      objectFit: 'cover', willChange: 'transform', background: '#000',
    }
    : useCenter
      ? {
        position: 'absolute', top: 0, left: '50%', height: '100%', width: 'auto',
        transform: 'translateX(-50%)', background: '#000',
      }
      : {
        position: 'absolute', top: 0, left: 0, width: '100%', height: '100%',
        objectFit: 'contain', background: 'transparent',
      };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
      <div style={{
        position: 'relative', width: '100%', maxWidth: `${box.width}px`,
        aspectRatio: box.aspect, background: '#000', borderRadius: '14px',
        overflow: 'hidden', boxShadow: 'var(--shadow-card)',
      }}>
        {src ? (
          <>
            {/* Latar kabur — mencerminkan bilah kabur pada hasil render */}
            {useBlur && (
              <video
                ref={bgRef}
                src={src}
                muted
                playsInline
                aria-hidden="true"
                style={{
                  position: 'absolute', inset: 0, width: '100%', height: '100%',
                  objectFit: 'cover', filter: 'blur(18px)', transform: 'scale(1.12)',
                }}
              />
            )}
            <video
              ref={videoRef}
              src={src}
              onTimeUpdate={handleTimeUpdate}
              onPlay={() => setPlaying(true)}
              onPause={() => setPlaying(false)}
              playsInline
              style={videoStyle}
            />
          </>
        ) : (
          <div style={{
            width: '100%', height: '100%', display: 'flex', alignItems: 'center',
            justifyContent: 'center', color: 'var(--text-muted)', fontSize: '0.8rem',
            textAlign: 'center', padding: '20px',
          }}>
            Video sumber belum tersedia untuk pratinjau.
          </div>
        )}

        {/* Penanda mode bingkai */}
        {constrained && (
          <div style={{
            position: 'absolute', left: '8px', top: '8px', padding: '3px 8px',
            borderRadius: '99px', fontSize: '0.62rem', fontWeight: 800,
            background: 'rgba(0,0,0,0.72)', color: useReframe ? '#00E5FF' : '#cbd5e1',
            display: 'flex', alignItems: 'center', gap: '5px', pointerEvents: 'none',
          }}>
            {reframeLoading && <Loader2 size={10} className="animate-spin" />}
            {reframeLoading ? 'Melacak wajah…'
              : useReframe ? `Ikut wajah ${Math.round((reframe.face_coverage ?? 0) * 100)}%`
                : useCenter ? 'Potong tengah' : 'Bilah kabur'}
          </div>
        )}

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

        {activeLine && (
          <CaptionOverlay line={activeLine} activeWordIndex={activeWordIndex}
                          style={style} clipTime={clipTime} />
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

/** Subtitle di pratinjau, mencerminkan gaya yang akan dibakar ke video. */
function CaptionOverlay({ line, activeWordIndex, style, clipTime }) {
  const words = line.words?.length ? line.words : [{ w: line.text }];
  const anim = style?.animation ?? 'karaoke_pop';
  const uppercase = style?.uppercase !== false;

  // Warna per pembicara: baris yang ditandai pembicara kedua memakai warna
  // sendiri, sehingga percakapan dua orang bisa dibedakan sekilas.
  const speakerColor = line.speaker === 1
    ? (style?.speaker2 ?? '#7CFFB2')
    : (style?.primary ?? '#FFFFFF');

  const age = clipTime - line.start;
  const entry = anim === 'none' ? {} : lineEntryStyle(anim, age);

  return (
    <div style={{
      position: 'absolute', left: '5%', right: '5%',
      bottom: style?.position === 'top' ? undefined : '14%',
      top: style?.position === 'top' ? '18%' : undefined,
      textAlign: 'center', pointerEvents: 'none',
      fontWeight: 900, lineHeight: 1.2,
      fontSize: `clamp(0.9rem, ${(style?.size ?? 96) / 22}vw, 1.5rem)`,
      textShadow: '0 2px 0 #000, 2px 0 0 #000, -2px 0 0 #000, 0 -2px 0 #000, 0 3px 8px rgba(0,0,0,0.9)',
      textTransform: uppercase ? 'uppercase' : 'none',
      ...entry,
    }}>
      {words.map((w, i) => {
        const active = i === activeWordIndex;
        return (
          <span key={i} style={{
            color: active ? (style?.highlight ?? '#FFE500') : speakerColor,
            marginRight: '0.28em',
            display: 'inline-block',
            transform: active && anim === 'karaoke_pop' ? 'scale(1.09)' : 'none',
            transition: 'transform 90ms ease, color 60ms linear',
          }}>{w.w}</span>
        );
      })}
    </div>
  );
}

/** Animasi masuk per baris. Durasinya sengaja pendek supaya tidak mengganggu. */
function lineEntryStyle(anim, age) {
  const d = 0.26;
  if (age < 0 || age > d) return {};
  const p = Math.min(1, Math.max(0, age / d));
  const ease = 1 - (1 - p) * (1 - p);
  if (anim === 'fade') return { opacity: ease };
  if (anim === 'slide_up') {
    return { opacity: ease, transform: `translateY(${(1 - ease) * 18}px)` };
  }
  if (anim === 'pop_in') {
    return { opacity: ease, transform: `scale(${0.86 + 0.14 * ease})` };
  }
  return {};
}
