import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { formatTime } from '../../utils/timeFormat';
import { contrastRatio } from '../../lib/contrast';

/**
 * Sistem balok: seluruh durasi rekaman dibaca sekaligus.
 *
 * Satu balok per narasumber, satu balok dinamika di bawahnya, dan tiap klip
 * duduk sebagai frasa bertanda huruf latihan pada balok penuturnya.
 *
 * Inilah gagasan yang dimiliki layar ini: sekali pandang, bentuk seluruh
 * percakapan satu jam itu terbaca — siapa memegang giliran di menit ke berapa,
 * di mana klipnya jatuh, di mana dinamikanya memuncak. Timeline gelombang
 * tunggal yang biasa dipakai kategori ini tidak bisa menjawab pertanyaan
 * pertama sama sekali.
 *
 * Partitur MEMBUNGKUS: satu halaman memuat beberapa sistem bertumpuk, bukan
 * satu garis yang dimampatkan sampai tak terbaca. Di layar sempit sistemnya
 * dipecah per belasan menit — itu yang dilakukan partitur cetak, dan itu pula
 * yang menyelamatkan huruf latihan dari saling bertumpuk.
 *
 * Garis main dan pita stabilo digerakkan lewat ref di dalam satu loop rAF,
 * tidak pernah lewat React state: `timeupdate` menyala ~4 Hz dan me-render
 * ulang pohon komponen tiap denyut adalah persis yang membuat editor berat.
 */

const HUR = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
export const rehearsalLetter = (i) =>
  (i < 26 ? HUR[i] : HUR[Math.floor(i / 26) - 1] + HUR[i % 26]);

/** Berapa sistem yang muat, dari lebar yang benar-benar tersedia. */
function systemCountFor(width, duration) {
  if (!duration) return 1;
  if (width >= 1100) return 1;
  if (width >= 720) return Math.min(3, Math.ceil(duration / 2400));
  return Math.max(1, Math.min(8, Math.ceil(duration / 900)));   // ~15 menit
}

const TICK_STEPS = [15, 30, 60, 120, 300, 600, 900, 1800];

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
  const wrapRef = useRef(null);
  const playRefs = useRef([]);
  const bandRefs = useRef([]);
  const [width, setWidth] = useState(1200);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width));
    ro.observe(el);
    setWidth(el.getBoundingClientRect().width);
    return () => ro.disconnect();
  }, []);

  const voices = Math.max(1, Math.min(8, speakerCount || 1));
  const nSystems = systemCountFor(width, duration);
  const span = duration > 0 ? duration / nSystems : 1;

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

  const lettered = useMemo(
    () => clips.map((clip, i) => ({
      clip,
      letter: rehearsalLetter(i),
      voice: Math.min(voiceOf(clip), voices - 1),
      start: clip.segments[0].start,
      end: clip.segments[clip.segments.length - 1].end,
    })),
    [clips, voices, voiceOf],
  );

  const selected = clips.find((c) => c.clip_id === selectedId) ?? null;

  // Pita stabilo meluncur ke frasa terpilih — satu momen gerak yang diarang.
  // Digerakkan lewat transform, bukan left/width: menganimasikan geometri
  // memaksa tata letak dihitung ulang tiap bingkai.
  useEffect(() => {
    bandRefs.current.forEach((band, i) => {
      if (!band) return;
      if (!selected || !duration) { band.style.opacity = '0'; return; }
      const from = i * span;
      const s = Math.max(selected.segments[0].start, from);
      const e = Math.min(selected.segments[selected.segments.length - 1].end, from + span);
      if (e <= s) { band.style.opacity = '0'; return; }
      band.style.opacity = '1';
      band.style.transform =
        `translateX(${((s - from) / span) * 100}%) scaleX(${Math.max(0.004, (e - s) / span)})`;
    });
  }, [selected, span, duration, nSystems]);

  // Garis main hidup di sistem yang sedang dilewati; yang lain disembunyikan.
  useEffect(() => {
    let raf;
    const tick = () => {
      const v = videoRef?.current;
      if (v && duration > 0) {
        const active = Math.min(nSystems - 1, Math.floor(v.currentTime / span));
        playRefs.current.forEach((line, i) => {
          if (!line) return;
          if (i !== active) { line.style.opacity = '0'; return; }
          line.style.opacity = '1';
          line.style.transform = `translateX(${((v.currentTime - i * span) / span) * 100}%)`;
        });
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [videoRef, duration, span, nSystems]);

  /**
   * Balok dinamika: simpangan dari rata-rata, digambar dari garis tengah.
   *
   * Bukan gelombang amplitudo — itu justru timeline gelombang tunggal yang
   * ditolak layar ini, hanya dipindah ke baris bawah. Yang dibaca konduktor
   * dari partitur adalah dinamika: di mana suaranya naik di atas kebiasaan,
   * di mana ia turun. Itu z-skor, dan itulah yang dipakai mesin pemilih klip.
   */
  const dynamics = useMemo(() => {
    if (!peaks?.length) return [];
    const mean = peaks.reduce((a, b) => a + b, 0) / peaks.length;
    const sd = Math.sqrt(peaks.reduce((a, b) => a + (b - mean) ** 2, 0) / peaks.length) || 1;
    const N = 320;
    const out = [];
    const chunk = peaks.length / N;
    for (let i = 0; i < N; i += 1) {
      let sum = 0;
      let n = 0;
      for (let j = Math.floor(i * chunk); j < Math.floor((i + 1) * chunk); j += 1) {
        sum += peaks[j]; n += 1;
      }
      out.push(Math.max(-1, Math.min(1, ((sum / (n || 1)) - mean) / (sd * 2))));
    }
    return out;
  }, [peaks]);

  const seekAt = (e, sysIndex) => {
    const rect = e.currentTarget.getBoundingClientRect();
    if (!duration) return;
    const t = sysIndex * span + ((e.clientX - rect.left) / rect.width) * span;
    onSeek?.(Math.max(0, Math.min(duration, t)));
  };

  /**
   * Pensil untuk sebuah suara.
   *
   * Warna subtitle dipakai lebih dulu supaya penutur yang sama terbaca sama di
   * partitur dan di video. Tapi warna itu dipilih untuk teks di ATAS gambar —
   * orang pertama bawaannya putih — dan putih di atas pelat kertas tidak
   * terlihat sama sekali. Warna yang terlalu terang untuk kertas diganti pensil
   * partitur sendiri; identitasnya tetap terbaca, hanya bahannya yang berganti.
   */
  const pencil = useCallback((v) => {
    // Merah TIDAK ada di tangga ini: OWN-WORLD menyimpannya untuk menandai
    // klip, dan memberikannya ke sebuah suara membuat frasa dan huruf
    // latihannya berwarna sama di balok yang sama. Sisanya grafit, bukan
    // pensil kelima yang tidak disebut dunia ini.
    const own = ['var(--entry)', 'var(--cue)', 'var(--ink-2)', 'var(--ink-3)'][v % 4];
    const c = speakerColors[v];
    if (typeof c !== 'string' || !/^#[0-9a-f]{6}$/i.test(c)) return own;
    // Diukur sebagai kontras terhadap pelat, bukan luminansi sendirian:
    // pastel lolos penjagaan luminansi lalu hilang di atas kertas.
    const ratio = contrastRatio(c, '#E3E9F1');
    return ratio !== null && ratio >= 3 ? c : own;
  }, [speakerColors]);

  const step = TICK_STEPS.find((s) => span / s <= Math.max(2, Math.floor(width / 150))) ?? 1800;

  return (
    <div ref={wrapRef} className="plate stave-plate">
      {Array.from({ length: nSystems }, (_, sys) => {
        const from = sys * span;
        const ticks = [];
        for (let t = Math.ceil(from / step) * step; t < from + span; t += step) ticks.push(t);

        return (
          <div key={sys} className="stave-system">
            <div className="stave-ticks tc">
              {ticks.map((t) => (
                <span key={t} style={{ left: `${((t - from) / span) * 100}%` }}>{formatTime(t)}</span>
              ))}
            </div>

            <div className="stave-board" onClick={(e) => seekAt(e, sys)}>
              {Array.from({ length: voices }, (_, v) => (
                <div key={v} className="stave-row">
                  <div className="stave-name" data-n={v + 1}>
                    <span className="voice-dot" style={{ background: pencil(v) }} />
                    <span className="voice-name">Orang {v + 1}</span>
                  </div>
                  <div className="stave">
                    <div className="stave-lines" />
                    {lettered
                      .filter((x) => x.voice === v && x.end > from && x.start < from + span)
                      .map(({ clip, letter, start, end }) => {
                        const s = Math.max(start, from);
                        const e = Math.min(end, from + span);
                        const left = ((s - from) / span) * 100;
                        const w = Math.max(0.6, ((e - s) / span) * 100);
                        const nearEdge = left + w > 94;
                        return (
                          <div key={clip.clip_id} className="stave-phrase"
                               onClick={(ev) => { ev.stopPropagation(); onSelectClip?.(clip.clip_id); }}
                               title={`${letter} · ${formatTime(start)} · ${Math.round(end - start)} dtk`}
                               style={{
                                 left: `${left}%`, width: `${w}%`,
                                 background: `color-mix(in srgb, ${pencil(v)} 24%, transparent)`,
                                 borderLeftColor: pencil(v),
                               }}>
                            <span className={`reh${clip.source === 'manual' ? ' reh--manual' : ''}`}
                                  style={{
                                    position: 'absolute', top: '-11px',
                                    ...(nearEdge ? { right: 0 } : { left: 0 }),
                                    transformOrigin: nearEdge ? 'right bottom' : 'left bottom',
                                    transform: clip.clip_id === selectedId ? 'scale(1.14)' : 'none',
                                    transition: 'transform .18s cubic-bezier(.16,1,.3,1)',
                                  }}>{letter}</span>
                          </div>
                        );
                      })}
                  </div>
                </div>
              ))}

              <div className="stave-row stave-row--dyn">
                <div className="stave-name"><span>Dinamika</span></div>
                <div className="dyn">
                  <span className="dyn-rule" />
                  {dynamics.length
                    ? dynamics.map((z, i) => (
                      <span key={i} className="dyn-mark" style={{
                        left: `${(i / dynamics.length) * 100}%`,
                        height: `${Math.abs(z) * 46}%`,
                        top: z >= 0 ? `${50 - Math.abs(z) * 46}%` : '50%',
                        background: z >= 0 ? 'var(--ink-2)' : 'var(--ink-3)',
                      }} />
                    ))
                    : <span className="dyn-empty">Gelombang suara belum dihitung.</span>}
                </div>
              </div>

              <div className="stave-overlay">
                <div ref={(el) => { bandRefs.current[sys] = el; }}
                     className="stave-band" style={{ opacity: 0 }} />
                <div ref={(el) => { playRefs.current[sys] = el; }}
                     className="playline" style={{ opacity: 0 }} />
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
