import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Play, Pause, RotateCcw, Loader2, Move } from 'lucide-react';
import { fontStack } from '../../lib/fonts';

const RATIO_BOX = {
  '9:16': { width: 300, aspect: '9 / 16' },
  '1:1': { width: 380, aspect: '1 / 1' },
  '4:5': { width: 340, aspect: '4 / 5' },
  '16:9': { width: 520, aspect: '16 / 9' },
};

// Ukuran dan margin subtitle disimpan dalam satuan kanvas setinggi 1920 —
// satuan yang sama yang dipakai render, yang menyekalakan gaya ke tinggi kanvas
// sebenarnya. Karena Fontsize pada ASS relatif terhadap PlayResY, pecahan
// nilai/1920 berlaku untuk SEMUA rasio, jadi pratinjau bisa memakai satu rumus.
const CANVAS_H = 1920;

/**
 * Pemutar pratinjau klip.
 *
 * Tiga tugasnya:
 *
 * 1. Klip bisa terdiri dari beberapa segmen dari bagian video yang berbeda,
 *    jadi pemutar melompat sendiri ke segmen berikutnya saat segmen berjalan
 *    habis — inilah yang membuat gabungan menit 10 + menit 50 bisa ditonton
 *    utuh sebelum dirender.
 *
 * 2. Menampilkan BINGKAI yang sebenarnya, bukan frame 16:9 apa adanya, memakai
 *    rencana crop yang sama persis yang nanti dikirim ke ffmpeg.
 *
 * 3. Menampilkan subtitle pada ukuran dan posisi yang sebanding dengan hasil
 *    akhirnya, dan membiarkannya digeser serta diubah ukurannya langsung di
 *    atas gambar.
 */
export default function ClipPreview({
  src, clip, aspectRatio = '9:16', style,
  videoRef: externalRef,
  constrained = true,
  frameMode = 'smart',
  reframe = null,          // {available, crop_w, source_w, keyframes:[[t,x]]}
  reframeLoading = false,
  onStyleChange = null,    // menggeser/mengubah ukuran subtitle di atas gambar
}) {
  const innerRef = useRef(null);
  const videoRef = externalRef ?? innerRef;
  const bgRef = useRef(null);
  const boxRef = useRef(null);
  const [segIndex, setSegIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [clipTime, setClipTime] = useState(0);
  const [boxH, setBoxH] = useState(0);
  const [dragging, setDragging] = useState(null);   // 'move' | 'size' | null

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

  // Tinggi kotak diukur, bukan ditebak, supaya ukuran teks pratinjau benar-benar
  // sebanding dengan hasil render pada rasio apa pun.
  useLayoutEffect(() => {
    const el = boxRef.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(([entry]) => setBoxH(entry.contentRect.height));
    ro.observe(el);
    setBoxH(el.getBoundingClientRect().height);
    return () => ro.disconnect();
  }, [aspectRatio, frameMode]);

  const useReframe = frameMode === 'smart' && reframe?.available && constrained;
  const useCenter = frameMode === 'center';
  const useOriginal = frameMode === 'original';
  const useBlur = !useReframe && !useCenter && !useOriginal;

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

  // Sisa geseran dari mode ikut-wajah HARUS dihapus saat mode bingkai berganti.
  // Tanpa ini, `translateX` terakhir yang ditulis loop rAF tetap menempel di
  // elemen video, dan bilah kabur tampil dengan videonya melenceng ke kiri —
  // persis bug "kadang tampilannya begini" yang sulit ditiru karena hanya
  // muncul setelah sempat memakai mode ikut-wajah.
  useEffect(() => {
    if (!useReframe && videoRef.current) videoRef.current.style.transform = '';
  }, [useReframe, videoRef, aspectRatio, frameMode]);

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

  const lines = clip?.subtitles ?? [];
  const activeLine = useMemo(() => {
    if (!constrained) return null;
    return lines.find((l) => clipTime >= l.start && clipTime <= l.end) ?? null;
  }, [lines, clipTime, constrained]);

  // Saat dijeda dan tidak ada baris yang sedang diucapkan, baris pertama
  // ditampilkan redup. Tanpa ini, mengatur posisi dan ukuran teks hanya bisa
  // dilakukan pada detik-detik acak ketika kebetulan ada yang bicara.
  //
  // Hanya saat dijeda: memunculkannya di sela-sela ucapan selama pemutaran akan
  // membuat baris pertama berkedip terus di tempat yang salah.
  const ghostLine = !activeLine && constrained && !playing ? lines[0] ?? null : null;
  const shownLine = activeLine ?? ghostLine;

  const activeWordIndex = useMemo(() => {
    if (!activeLine?.words?.length) return -1;
    return activeLine.words.findIndex((w) => clipTime >= w.s && clipTime <= w.e);
  }, [activeLine, clipTime]);

  /**
   * Menggeser dan mengubah ukuran subtitle langsung di atas gambar.
   *
   * Nilainya ditulis dalam satuan kanvas 1920 supaya apa yang terlihat di sini
   * benar-benar nilai yang dikirim ke ffmpeg — bukan angka pratinjau yang nanti
   * diterjemahkan lagi.
   */
  const startDrag = useCallback((mode) => (e) => {
    if (!onStyleChange || !boxH) return;
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.setPointerCapture?.(e.pointerId);
    setDragging(mode);

    const y0 = e.clientY;
    const startMargin = style?.margin_v ?? 300;
    const startSize = style?.size ?? 96;
    const anchorTop = style?.position === 'top';
    const perPx = CANVAS_H / boxH;      // piksel layar -> satuan kanvas

    const onMove = (ev) => {
      const dy = (ev.clientY - y0) * perPx;
      if (mode === 'move') {
        // Jangkar bawah: menyeret ke bawah berarti margin mengecil.
        const next = anchorTop ? startMargin + dy : startMargin - dy;
        onStyleChange({ margin_v: Math.round(Math.max(40, Math.min(1500, next))) });
      } else {
        onStyleChange({ size: Math.round(Math.max(44, Math.min(190, startSize - dy))) });
      }
    };
    const onUp = () => {
      setDragging(null);
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  }, [onStyleChange, boxH, style?.margin_v, style?.size, style?.position]);

  // Bingkai orisinal mengabaikan pilihan rasio: kotaknya harus mengikuti bentuk
  // video sumber, bukan 9:16, atau pratinjaunya berbohong soal hasil akhir.
  const box = useOriginal
    ? RATIO_BOX['16:9']
    : (RATIO_BOX[aspectRatio] ?? RATIO_BOX['9:16']);
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
    : useOriginal
      ? {
        position: 'absolute', inset: 0, width: '100%', height: '100%',
        objectFit: 'contain', background: '#000',
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
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px', width: '100%' }}>
      <div ref={boxRef} style={{
        position: 'relative', width: '100%', maxWidth: `${box.width}px`,
        aspectRatio: box.aspect, background: '#000', borderRadius: '14px',
        overflow: 'hidden', boxShadow: 'var(--shadow-card)',
        touchAction: dragging ? 'none' : 'auto',
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
                : useOriginal ? 'Bingkai orisinal'
                  : useCenter ? 'Potong tengah' : 'Bilah kabur'}
          </div>
        )}

        {dragging && (
          <div style={{
            position: 'absolute', right: '8px', top: '8px', padding: '3px 8px',
            borderRadius: '99px', fontSize: '0.62rem', fontWeight: 800,
            background: 'rgba(0,0,0,0.8)', color: '#00E5FF', pointerEvents: 'none',
            fontVariantNumeric: 'tabular-nums',
          }}>
            {dragging === 'move'
              ? `Jarak ${style?.margin_v ?? 300}`
              : `Ukuran ${style?.size ?? 96}`}
          </div>
        )}

        {showHook && (
          <div style={{
            position: 'absolute', top: '7%', left: '6%', right: '6%',
            textAlign: 'center', color: '#00E5FF', fontWeight: 900,
            fontFamily: fontStack(style?.font),
            fontSize: 'clamp(0.85rem, 4.2vw, 1.15rem)', lineHeight: 1.15,
            textTransform: 'uppercase', letterSpacing: '0.01em',
            background: 'rgba(0,0,0,0.7)', padding: '8px 10px', borderRadius: '8px',
            pointerEvents: 'none',
          }}>
            {clip.hook_text}
          </div>
        )}

        {shownLine && boxH > 0 && (
          <CaptionOverlay line={shownLine} activeWordIndex={activeWordIndex}
                          style={style} clipTime={clipTime} boxH={boxH}
                          ghost={!activeLine}
                          draggable={Boolean(onStyleChange)}
                          dragging={dragging}
                          onMoveStart={startDrag('move')}
                          onSizeStart={startDrag('size')} />
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

      {onStyleChange && shownLine && (
        <p style={{
          fontSize: '0.68rem', color: 'var(--text-muted)', margin: 0,
          display: 'flex', alignItems: 'center', gap: '5px', textAlign: 'center',
        }}>
          <Move size={11} /> Seret subtitle untuk memindahkannya, tarik bulatan
          di kanan untuk mengubah ukurannya.
        </p>
      )}
    </div>
  );
}

/**
 * Subtitle di pratinjau, mencerminkan gaya yang akan dibakar ke video.
 *
 * Ukuran, jarak dari tepi, dan tebal garis luar semuanya dihitung dari satuan
 * kanvas 1920 yang sama dengan file ASS, jadi yang terlihat di sini benar-benar
 * proporsi hasil akhirnya — bukan perkiraan berbasis lebar layar.
 */
function CaptionOverlay({
  line, activeWordIndex, style, clipTime, boxH, ghost,
  draggable, dragging, onMoveStart, onSizeStart,
}) {
  const words = line.words?.length ? line.words : [{ w: line.text }];
  const anim = style?.animation ?? 'karaoke_pop';
  const uppercase = style?.uppercase !== false;
  const scale = boxH / CANVAS_H;

  // Warna per penutur. Penutur pertama memakai warna teks utama, sehingga video
  // satu narasumber tampil persis seperti sebelum fitur ini ada.
  const palette = style?.speaker_colors ?? ['#7CFFB2', '#FFB3C7', '#B39DFF'];
  const sp = line.speaker || 0;
  const speakerColor = sp >= 1 && sp <= palette.length
    ? palette[sp - 1]
    : (style?.primary ?? '#FFFFFF');

  const age = clipTime - line.start;
  const entry = ghost || anim === 'none' ? {} : lineEntryStyle(anim, age);

  const fontPx = Math.max(9, (style?.size ?? 96) * scale);
  const marginPx = (style?.margin_v ?? 300) * scale;
  // Garis luar libass diukur dari tepi glyph ke luar; -webkit-text-stroke
  // digambar di tengah garis, jadi setengahnya jatuh ke dalam huruf. Faktor 1.6
  // mengembalikan tebal yang terlihat setara.
  const strokePx = Math.max(0.8, (style?.outline_px ?? 7) * scale * 1.6);
  const anchorTop = style?.position === 'top';
  const anchorMiddle = style?.position === 'middle';

  const place = anchorMiddle
    ? { top: '50%' } : anchorTop ? { top: `${marginPx}px` } : { bottom: `${marginPx}px` };
  // Posisi tengah dan animasi masuk sama-sama memakai `transform`, jadi
  // keduanya digabung — bukan saling menimpa, yang membuat baris melompat ke
  // bawah tiap kali animasi menyala.
  const transform = [anchorMiddle ? 'translateY(-50%)' : '', entry.transform || '']
    .filter(Boolean).join(' ');

  return (
    <div
      onPointerDown={draggable ? onMoveStart : undefined}
      style={{
        position: 'absolute', left: '4%', right: '4%',
        ...place,
        textAlign: 'center',
        pointerEvents: draggable ? 'auto' : 'none',
        cursor: draggable ? (dragging === 'move' ? 'grabbing' : 'grab') : 'default',
        fontFamily: fontStack(style?.font),
        fontWeight: 800, lineHeight: 1.16, letterSpacing: '0.005em',
        fontSize: `${fontPx}px`,
        // Garis luar sungguhan, bukan tumpukan text-shadow. Empat bayangan
        // bergeser satu piksel menghasilkan tepi bergerigi pada teks besar —
        // itulah "pixel-pixel" yang terlihat di pratinjau, dan tidak pernah ada
        // di hasil render karena libass memang menggambar garis luar sungguhan.
        WebkitTextStroke: `${strokePx}px #000`,
        paintOrder: 'stroke fill',
        textShadow: `0 ${(fontPx * 0.06).toFixed(1)}px ${(fontPx * 0.2).toFixed(1)}px rgba(0,0,0,0.55)`,
        textTransform: uppercase ? 'uppercase' : 'none',
        opacity: ghost ? 0.45 : 1,
        outline: dragging === 'move' ? '1px dashed rgba(0,229,255,0.85)' : 'none',
        outlineOffset: '6px',
        ...entry,
        ...(transform ? { transform } : {}),
      }}
    >
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

      {draggable && (
        <span
          onPointerDown={onSizeStart}
          title="Tarik untuk mengubah ukuran teks"
          style={{
            position: 'absolute', right: '-13px', bottom: '-13px',
            width: '20px', height: '20px', borderRadius: '50%',
            background: 'var(--accent-cyan, #00E5FF)', border: '2px solid #06121a',
            cursor: 'ns-resize', boxShadow: '0 1px 5px rgba(0,0,0,0.6)',
            WebkitTextStroke: '0', opacity: dragging ? 1 : 0.75,
          }}
        />
      )}
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
