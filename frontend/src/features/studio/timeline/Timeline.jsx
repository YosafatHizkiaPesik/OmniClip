import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { ZoomIn, ZoomOut, Maximize2 } from 'lucide-react';
import WaveformCanvas from './WaveformCanvas';
import { formatTime } from '../../../utils/timeFormat';

/**
 * Timeline video sumber, bergaya editor video biasa.
 *
 * Menampilkan SELURUH video panjang, dengan blok penanda di setiap bagian yang
 * dinilai layak jadi klip. Klip yang sedang dipilih mendapat pegangan di kedua
 * ujungnya sehingga batasnya bisa digeser langsung di timeline.
 *
 * Dua keputusan yang menentukan rasanya:
 *
 * 1. TIDAK memakai scroll native. Jendela tampilan disimpan sebagai
 *    {start, end} dalam detik, dan semua anak menghitung posisinya dari situ.
 *    Dengan scroll native, zoom 20x pada podcast 75 menit berarti elemen
 *    selebar puluhan ribu piksel; di sini lebarnya selalu selebar layar.
 *
 * 2. Playhead TIDAK pernah lewat React state. Event `timeupdate` menyala ~4 Hz
 *    dan me-render ulang pohon komponen di setiap denyut adalah persis yang
 *    membuat editor terasa berat. Playhead digerakkan lewat ref di dalam loop
 *    requestAnimationFrame.
 */

// Langkah tick yang enak dibaca. Dipilih yang pertama memberi jarak >= 64 px.
const TICK_STEPS = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600];
const MIN_SPAN = 4;        // detik; batas zoom paling dalam
const HANDLE_W = 9;

function clampView(start, end, duration) {
  let span = Math.min(Math.max(end - start, MIN_SPAN), duration);
  let s = Math.max(0, Math.min(start, duration - span));
  return { start: s, end: s + span };
}

export default function Timeline({
  duration = 0,
  peaks = [],
  clips = [],
  selectedId = null,
  videoRef,
  onSeek,
  onSelectClip,
  onCommitSegment,
  busy = false,
}) {
  const trackRef = useRef(null);
  const playheadRef = useRef(null);
  const [width, setWidth] = useState(0);
  const [view, setView] = useState({ start: 0, end: duration || 1 });
  const [drag, setDrag] = useState(null);   // {clipId, segIndex, edge, start, end}

  // Video baru: kembalikan tampilan ke keseluruhan durasi.
  useEffect(() => {
    setView({ start: 0, end: Math.max(1, duration) });
  }, [duration]);

  useLayoutEffect(() => {
    const el = trackRef.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    ro.observe(el);
    setWidth(el.clientWidth);
    return () => ro.disconnect();
  }, []);

  const span = Math.max(0.001, view.end - view.start);
  const timeToPx = useCallback((t) => ((t - view.start) / span) * width, [view.start, span, width]);
  const pxToTime = useCallback((px) => view.start + (px / Math.max(1, width)) * span,
    [view.start, span, width]);

  // --- Playhead: ref + rAF, tanpa state ---------------------------------------
  useEffect(() => {
    let raf;
    const tick = () => {
      const video = videoRef?.current;
      const el = playheadRef.current;
      if (video && el && width) {
        const x = ((video.currentTime - view.start) / span) * width;
        if (x >= -2 && x <= width + 2) {
          el.style.display = 'block';
          el.style.transform = `translateX(${x}px)`;
        } else {
          el.style.display = 'none';
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [videoRef, view.start, span, width]);

  // --- Zoom & geser ------------------------------------------------------------
  const zoomAround = useCallback((anchorTime, factor) => {
    setView((v) => {
      const currentSpan = v.end - v.start;
      const nextSpan = Math.min(Math.max(currentSpan * factor, MIN_SPAN), duration || currentSpan);
      const ratio = (anchorTime - v.start) / currentSpan;
      return clampView(anchorTime - ratio * nextSpan, anchorTime - ratio * nextSpan + nextSpan, duration);
    });
  }, [duration]);

  const handleWheel = useCallback((e) => {
    if (!width || !duration) return;
    e.preventDefault();
    const rect = trackRef.current.getBoundingClientRect();
    const anchor = pxToTime(e.clientX - rect.left);
    if (e.shiftKey) {
      const shift = (e.deltaY / width) * span;
      setView((v) => clampView(v.start + shift, v.end + shift, duration));
    } else {
      zoomAround(anchor, e.deltaY > 0 ? 1.18 : 1 / 1.18);
    }
  }, [width, duration, pxToTime, span, zoomAround]);

  // `passive: false` wajib dipasang manual: React memasang listener wheel
  // sebagai passive, dan preventDefault() di dalamnya diabaikan diam-diam
  // sehingga halaman ikut ter-scroll saat pengguna zoom.
  useEffect(() => {
    const el = trackRef.current;
    if (!el) return undefined;
    el.addEventListener('wheel', handleWheel, { passive: false });
    return () => el.removeEventListener('wheel', handleWheel);
  }, [handleWheel]);

  // --- Menggeser batas klip ----------------------------------------------------
  const beginDrag = (e, clip, segIndex, edge) => {
    e.stopPropagation();
    e.preventDefault();
    if (busy) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    const seg = clip.segments[segIndex];
    setDrag({ clipId: clip.clip_id, segIndex, edge, start: seg.start, end: seg.end });
  };

  const moveDrag = (e) => {
    if (!drag) return;
    const rect = trackRef.current.getBoundingClientRect();
    const t = Math.max(0, Math.min(duration, pxToTime(e.clientX - rect.left)));
    setDrag((d) => {
      if (!d) return d;
      // Minimal 1,5 detik supaya klip tidak bisa diciutkan sampai nol.
      return d.edge === 'start'
        ? { ...d, start: Math.min(t, d.end - 1.5) }
        : { ...d, end: Math.max(t, d.start + 1.5) };
    });
  };

  const endDrag = (e) => {
    if (!drag) return;
    try { e.currentTarget.releasePointerCapture(e.pointerId); } catch { /* sudah lepas */ }
    const { clipId, segIndex, start, end } = drag;
    setDrag(null);
    onCommitSegment?.(clipId, segIndex, start, end);
  };

  // --- Tick penanda waktu ------------------------------------------------------
  const ticks = useMemo(() => {
    if (!width || !span) return [];
    const step = TICK_STEPS.find((s) => (s / span) * width >= 64) ?? TICK_STEPS.at(-1);
    const out = [];
    for (let t = Math.ceil(view.start / step) * step; t <= view.end; t += step) {
      out.push(t);
    }
    return out;
  }, [width, span, view.start, view.end]);

  const seekTo = (e) => {
    if (drag) return;
    const rect = trackRef.current.getBoundingClientRect();
    onSeek?.(Math.max(0, Math.min(duration, pxToTime(e.clientX - rect.left))));
  };

  const visibleClips = clips.filter((c) =>
    c.segments?.some((s) => s.end > view.start && s.start < view.end));

  return (
    <div style={{
      background: 'var(--bg-card)', border: '1px solid var(--border-color)',
      borderRadius: 'var(--radius-md)', overflow: 'hidden',
    }}>
      {/* Kepala: zoom */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '8px', padding: '7px 10px',
        borderBottom: '1px solid var(--border-color)', fontSize: '0.72rem',
        color: 'var(--text-secondary)',
      }}>
        <span style={{ fontWeight: 700 }}>Timeline video sumber</span>
        <span style={{ fontVariantNumeric: 'tabular-nums' }}>
          {formatTime(view.start)} – {formatTime(view.end)}
        </span>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
          scroll = zoom · shift+scroll = geser
        </span>
        <IconBtn title="Perbesar" onClick={() => zoomAround((view.start + view.end) / 2, 1 / 1.5)}>
          <ZoomIn size={14} />
        </IconBtn>
        <IconBtn title="Perkecil" onClick={() => zoomAround((view.start + view.end) / 2, 1.5)}>
          <ZoomOut size={14} />
        </IconBtn>
        <IconBtn title="Tampilkan seluruh video"
                 onClick={() => setView({ start: 0, end: Math.max(1, duration) })}>
          <Maximize2 size={14} />
        </IconBtn>
      </div>

      {/* Badan */}
      <div
        ref={trackRef}
        onPointerMove={moveDrag}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        onClick={seekTo}
        style={{ position: 'relative', userSelect: 'none', cursor: 'text', padding: '0 0 6px' }}
      >
        {/* Penggaris waktu */}
        <div style={{ position: 'relative', height: '20px', borderBottom: '1px solid var(--border-color)' }}>
          {ticks.map((t) => (
            <div key={t} style={{
              position: 'absolute', left: `${timeToPx(t)}px`, top: 0, height: '100%',
              borderLeft: '1px solid var(--border-color)', paddingLeft: '4px',
              fontSize: '0.62rem', color: 'var(--text-muted)',
              fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap', pointerEvents: 'none',
            }}>
              {formatTime(t)}
            </div>
          ))}
        </div>

        {/* Gelombang suara */}
        <div style={{ position: 'relative' }}>
          <WaveformCanvas peaks={peaks} duration={duration}
                          viewStart={view.start} viewEnd={view.end} height={54} />
        </div>

        {/* Blok klip */}
        <div style={{ position: 'relative', height: '46px', marginTop: '4px' }}>
          {visibleClips.map((clip) => {
            const isSelected = clip.clip_id === selectedId;
            return clip.segments.map((seg, segIndex) => {
              const live = drag && drag.clipId === clip.clip_id && drag.segIndex === segIndex
                ? drag : seg;
              const left = timeToPx(live.start);
              const right = timeToPx(live.end);
              if (right < -40 || left > width + 40) return null;
              return (
                <div
                  key={`${clip.clip_id}_${segIndex}`}
                  onClick={(e) => { e.stopPropagation(); onSelectClip?.(clip.clip_id); }}
                  title={`Klip #${clip.index} · ${formatTime(live.start)}`}
                  style={{
                    position: 'absolute', left: `${left}px`, width: `${Math.max(3, right - left)}px`,
                    top: 0, height: '100%', borderRadius: '5px', cursor: 'pointer',
                    background: isSelected ? 'rgba(0,242,254,0.26)' : 'rgba(0,242,254,0.10)',
                    border: isSelected ? '2px solid var(--accent-cyan)' : '1px solid rgba(0,242,254,0.4)',
                    display: 'flex', alignItems: 'center', overflow: 'hidden',
                    boxSizing: 'border-box',
                  }}
                >
                  <span style={{
                    fontSize: '0.66rem', fontWeight: 800, padding: '0 6px',
                    color: isSelected ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                    whiteSpace: 'nowrap', pointerEvents: 'none',
                  }}>
                    #{clip.index}{clip.segments.length > 1 ? `·${segIndex + 1}` : ''}
                  </span>

                  {isSelected && (
                    <>
                      <Handle side="left" onPointerDown={(e) => beginDrag(e, clip, segIndex, 'start')} />
                      <Handle side="right" onPointerDown={(e) => beginDrag(e, clip, segIndex, 'end')} />
                    </>
                  )}
                </div>
              );
            });
          })}
        </div>

        {/* Playhead */}
        <div ref={playheadRef} style={{
          position: 'absolute', top: 0, left: 0, width: '2px', height: '100%',
          background: 'var(--accent-red, #ff4d6d)', pointerEvents: 'none',
          willChange: 'transform', display: 'none', zIndex: 5,
        }} />
      </div>
    </div>
  );
}

function Handle({ side, onPointerDown }) {
  return (
    <div
      onPointerDown={onPointerDown}
      onClick={(e) => e.stopPropagation()}
      style={{
        position: 'absolute', top: 0, [side]: 0, width: `${HANDLE_W}px`, height: '100%',
        cursor: 'ew-resize', background: 'var(--accent-cyan)', opacity: 0.9,
        borderRadius: side === 'left' ? '4px 0 0 4px' : '0 4px 4px 0',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
    >
      <div style={{ width: '2px', height: '14px', background: '#00121a', borderRadius: '2px' }} />
    </div>
  );
}

function IconBtn({ children, onClick, title }) {
  return (
    <button onClick={onClick} title={title} style={{
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      width: '26px', height: '24px', borderRadius: '5px', cursor: 'pointer',
      border: '1px solid var(--border-color)', background: 'transparent',
      color: 'var(--text-secondary)',
    }}>
      {children}
    </button>
  );
}
