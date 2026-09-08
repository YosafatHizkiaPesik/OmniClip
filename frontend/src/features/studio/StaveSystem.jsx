import React, { useCallback, useEffect, useMemo, useRef } from 'react';
import { formatTime } from '../../utils/timeFormat';

/**
 * Sistem balok: seluruh durasi video dibaca sekaligus.
 *
 * Satu balok per narasumber, satu balok energi bicara di bawahnya, dan tiap
 * klip duduk sebagai frasa bertanda huruf latihan pada balok penuturnya.
 *
 * Inilah gagasan yang dimiliki layar ini: sekali pandang, bentuk seluruh
 * percakapan satu jam itu terbaca — siapa memegang giliran di menit ke berapa,
 * di mana klipnya jatuh, dan di mana energinya memuncak. Timeline gelombang
 * tunggal yang biasa dipakai kategori ini tidak bisa menjawab pertanyaan
 * pertama sama sekali.
 *
 * Playhead dan pita stabilo digerakkan lewat ref di dalam loop rAF, tidak
 * pernah lewat React state: `timeupdate` menyala ~4 Hz dan me-render ulang
 * pohon komponen tiap denyut adalah persis yang membuat editor terasa berat.
 */

const HUR = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
export const rehearsalLetter = (i) =>
  (i < 26 ? HUR[i] : HUR[Math.floor(i / 26) - 1] + HUR[i % 26]);

/** Berapa tick waktu yang muat, dengan jarak enak dibaca. */
const TICK_STEPS = [30, 60, 120, 300, 600, 900, 1800, 3600];
function pickStep(duration, width) {
  const want = Math.max(2, Math.floor(width / 110));
  return TICK_STEPS.find((s) => duration / s <= want) ?? 3600;
}

export default function StaveSystem({
  duration = 0,
  peaks = [],
  clips = [],
  selectedId = null,
  speakerCount = 2,
  speakerColors = [],
  videoRef,
  onSeek,
  onSelectClip,
}) {
  const boardRef = useRef(null);
  const playRef = useRef(null);
  const bandRef = useRef(null);
  const widthRef = useRef(900);

  const pct = useCallback((t) => (duration > 0 ? (t / duration) * 100 : 0), [duration]);

  useEffect(() => {
    const el = boardRef.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(([e]) => { widthRef.current = e.contentRect.width; });
    ro.observe(el);
    widthRef.current = el.getBoundingClientRect().width;
    return () => ro.disconnect();
  }, []);

  // Garis main mengikuti video tiap frame, tanpa menyentuh state.
  useEffect(() => {
    let raf;
    const tick = () => {
      const v = videoRef?.current;
      if (v && playRef.current && duration > 0) {
        playRef.current.style.left = `${(v.currentTime / duration) * 100}%`;
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [videoRef, duration]);

  /** Penutur mana yang paling banyak bicara di sebuah klip. */
  const voiceOf = useCallback((clip) => {
    const lines = clip.subtitles ?? [];
    if (!lines.length) return 0;
    const tally = {};
    for (const l of lines) {
      const s = l.speaker || 0;
      tally[s] = (tally[s] || 0) + 1;
    }
    return Number(Object.entries(tally).sort((a, b) => b[1] - a[1])[0][0]);
  }, []);

  const voices = Math.max(1, Math.min(8, speakerCount || 1));
  const rows = useMemo(() => {
    const byVoice = Array.from({ length: voices }, () => []);
    clips.forEach((clip, i) => {
      const v = Math.min(voiceOf(clip), voices - 1);
      byVoice[v].push({ clip, letter: rehearsalLetter(i) });
    });
    return byVoice;
  }, [clips, voices, voiceOf]);

  const selected = clips.find((c) => c.clip_id === selectedId) ?? null;

  // Pita stabilo meluncur ke frasa terpilih — satu momen gerak yang diarang,
  // bukan efek yang ditaburkan ke setiap elemen.
  useEffect(() => {
    const band = bandRef.current;
    if (!band) return;
    if (!selected) { band.style.opacity = '0'; return; }
    const s = selected.segments[0].start;
    const e = selected.segments[selected.segments.length - 1].end;
    band.style.opacity = '1';
    band.style.left = `${pct(s)}%`;
    band.style.width = `${Math.max(0.35, pct(e - s))}%`;
  }, [selected, pct]);

  const seekAt = (e) => {
    const rect = boardRef.current?.getBoundingClientRect();
    if (!rect || !duration) return;
    onSeek?.(Math.max(0, Math.min(duration, ((e.clientX - rect.left) / rect.width) * duration)));
  };

  const step = pickStep(duration || 1, widthRef.current);
  const ticks = [];
  for (let t = 0; t <= duration; t += step) ticks.push(t);

  // Balok energi digambar dari puncak gelombang yang sama dengan timeline lama,
  // dipadatkan jadi batang tipis supaya terbaca sebagai dinamika, bukan lagu.
  const energy = useMemo(() => {
    if (!peaks?.length) return [];
    const N = 220;
    const out = [];
    const chunk = peaks.length / N;
    for (let i = 0; i < N; i += 1) {
      let m = 0;
      for (let j = Math.floor(i * chunk); j < Math.floor((i + 1) * chunk); j += 1) {
        if (peaks[j] > m) m = peaks[j];
      }
      out.push(m / 255);
    }
    return out;
  }, [peaks]);

  return (
    <div className="plate" style={{ padding: '12px 0 8px', marginBottom: '16px' }}>
      {/* nomor birama */}
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        padding: '0 14px 8px calc(var(--stave-name) + 12px)', color: 'var(--ink-3)', fontSize: '.68rem',
      }} className="tc">
        {ticks.map((t) => <span key={t}>{formatTime(t)}</span>)}
      </div>

      <div ref={boardRef} onClick={seekAt}
           style={{ position: 'relative', cursor: 'crosshair' }}>
        {rows.map((phrases, v) => (
          <div key={v} style={{ display: 'grid', gridTemplateColumns: 'var(--stave-name) minmax(0,1fr)' }}>
            <div style={{
              padding: '0 12px', borderRight: '2px solid var(--ink)',
              display: 'flex', flexDirection: 'column', justifyContent: 'center',
            }}>
              <span className="mark" style={{ color: 'var(--ink)' }}>Orang {v + 1}</span>
              <span className="tc" style={{ fontSize: '.66rem', color: 'var(--ink-3)' }}>
                {phrases.length} huruf
              </span>
            </div>
            <div className="stave" style={{ position: 'relative' }}>
              <div className="stave-lines" />
              {phrases.map(({ clip, letter }) => {
                const s = clip.segments[0].start;
                const e = clip.segments[clip.segments.length - 1].end;
                const on = clip.clip_id === selectedId;
                return (
                  <div key={clip.clip_id}
                       className={`stave-phrase${v % 2 ? ' stave-phrase--cue' : ''}`}
                       onClick={(ev) => { ev.stopPropagation(); onSelectClip?.(clip.clip_id); }}
                       title={`${letter} · ${formatTime(s)} · ${Math.round(e - s)} dtk`}
                       style={{ left: `${pct(s)}%`, width: `${Math.max(0.3, pct(e - s))}%` }}>
                    {/* Huruf di ujung kanan digantung dari tepi kanan frasa,
                        kalau tidak ia terpotong bingkai pada klip menit terakhir. */}
                    <span className={`reh${clip.source === 'manual' ? ' reh--manual' : ''}`}
                          style={{
                            position: 'absolute', top: '-11px',
                            ...(pct(s) > 90 ? { right: 0 } : { left: 0 }),
                            transform: on ? 'scale(1.12)' : 'none',
                            transformOrigin: pct(s) > 90 ? 'right bottom' : 'left bottom',
                            transition: 'transform .18s cubic-bezier(.16,1,.3,1)',
                          }}>{letter}</span>
                  </div>
                );
              })}
            </div>
          </div>
        ))}

        {/* balok energi */}
        <div style={{ display: 'grid', gridTemplateColumns: 'var(--stave-name) minmax(0,1fr)' }}>
          <div style={{
            padding: '0 12px', borderRight: '2px solid var(--ink)',
            display: 'flex', flexDirection: 'column', justifyContent: 'center',
          }}>
            <span className="mark" style={{ color: 'var(--ink)' }}>Energi</span>
            <span className="tc" style={{ fontSize: '.66rem', color: 'var(--ink-3)' }}>
              puncak RMS
            </span>
          </div>
          <div style={{
            height: '34px', display: 'flex', alignItems: 'flex-end', gap: '1px',
            padding: '0 14px 6px 0',
          }}>
            {energy.length
              ? energy.map((h, i) => (
                <span key={i} style={{
                  flex: 1, height: `${Math.max(6, h * 100)}%`,
                  background: 'var(--ink-3)', opacity: .55, borderRadius: '.5px',
                }} />
              ))
              : <span style={{ color: 'var(--ink-3)', fontSize: '.72rem', alignSelf: 'center' }}>
                  Gelombang suara belum dihitung.
                </span>}
          </div>
        </div>

        {/* stabilo + garis main, keduanya di atas seluruh sistem */}
        <div style={{ position: 'absolute', inset: '0 14px 0 var(--stave-name)', pointerEvents: 'none' }}>
          <div ref={bandRef} className="stave-band" style={{ opacity: 0 }} />
          <div ref={playRef} className="playline" style={{ left: 0 }} />
        </div>
      </div>
    </div>
  );
}
