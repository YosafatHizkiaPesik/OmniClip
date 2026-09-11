import React, {
  useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState,
} from 'react';
import { Crosshair, Scissors, Wand2, ZoomIn, ZoomOut } from 'lucide-react';
import { formatTime, formatTimeFine } from '../../utils/timeFormat';
import { frameInk } from './frames';
import { personSpans, withPersonKey } from './frames';

/**
 * Linimasa satu klip: batas potongan, tiap baris subtitle, dan arah bingkai —
 * semuanya di atas sumbu waktu yang sama, semuanya bisa dipegang.
 *
 * Sistem balok di atas menjawab "di mana klipnya jatuh dalam satu jam rekaman".
 * Pertanyaan yang tidak bisa dijawabnya adalah "di detik ke berapa baris ini
 * muncul, dan ke siapa bingkainya menoleh saat itu" — dan justru itu pekerjaan
 * yang dilakukan berulang-ulang. Sebelum layar ini, satu-satunya cara menggeser
 * subtitle adalah mengetik angka detik di kotak isian, tanpa melihat ucapannya.
 *
 * Waktu di sini adalah waktu KLIP, dimulai dari nol — sama dengan yang dipakai
 * subtitle, jejak wajah, dan berkas ASS. Video sumbernya dipetakan masuk lewat
 * `segments`, jadi menggeser sesuatu di sini selalu berarti hal yang sama
 * dengan yang akan terjadi di hasil render.
 */

// Tinggi tiap lajur. Baris per orang memuat DUA hal bertumpuk — ucapannya dan
// pita kehadirannya di kamera — jadi ia butuh lebih dari sekadar tinggi satu
// blok subtitle. Pada 36 piksel pitanya tinggal tiga piksel di dasar baris dan
// praktis tidak terlihat; 46 memberi keduanya ruang untuk dibaca.
const LANE_H = { seg: 34, sub: 30, aim: 30, frame: 22, orang: 46 };

// Turun sampai seperduapuluh detik. Sebuah kata diucapkan dalam sepertiga
// detik; tanpa tanda yang lebih rapat dari itu, membetulkan letak satu kata
// berarti membidik di antara dua tanda yang keduanya menyebut detik yang sama.
const TICK_STEPS = [0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300];
const ZOOMS = [1, 2, 4, 8, 16, 32, 64, 128, 256];

/**
 * Tanda arah bingkai diubah jadi POTONGAN yang bersambungan.
 *
 * Tanda sebagai titik menjawab "kapan bingkai berpindah", tapi yang sebenarnya
 * ingin dilihat dan dipegang adalah "dari detik ini sampai detik itu, wajah
 * siapa yang diambil". Itu sebuah rentang, bukan sebuah titik — dan begitu
 * digambar sebagai rentang, batasnya bisa diseret dan isinya bisa diganti.
 *
 * Potongan pertama boleh tanpa tanda: sebelum tanda pertama, bingkai memilih
 * sendiri. Itu diwakili `person: null` dengan `keyIndex: -1`.
 */
function aimCuts(keys, duration) {
  const sorted = [...(keys ?? [])]
    .map((k, i) => ({ t: Math.max(0, Math.min(duration, Number(k.t) || 0)), person: k.person, i }))
    .sort((a, b) => a.t - b.t);
  const cuts = [];
  let cursor = 0;
  let person = null;
  let keyIndex = -1;
  for (const k of sorted) {
    if (k.t > cursor + 1e-6) {
      cuts.push({ start: cursor, end: k.t, person, keyIndex });
      cursor = k.t;
    }
    person = k.person ?? null;
    keyIndex = k.i;
  }
  cuts.push({ start: cursor, end: duration, person, keyIndex });
  return cuts.filter((c) => c.end > c.start + 1e-6);
}

/**
 * Menaruh baris yang waktunya tumpang-tindih pada baris tumpuk yang berbeda.
 *
 * Dua alasan, dan keduanya penting. Yang terlihat: subtitle yang tumpang-tindih
 * memang akan tergambar bertimpa di video, dan pengguna harus melihat itu
 * sebelum merender, bukan sesudahnya. Yang tidak terlihat: blok yang tertimpa
 * kehilangan pegangannya — ujungnya tergambar di bawah blok tetangga dan tidak
 * pernah bisa disentuh, sehingga baris yang justru paling perlu dibetulkan
 * adalah satu-satunya yang tidak bisa dibetulkan.
 */
function packRows(lines, maxRows = 3) {
  const ends = [];
  const rows = Array.from({ length: lines.length }, () => 0);
  lines
    .map((l, i) => ({ i, s: Number(l.start) || 0, e: Number(l.end) || 0 }))
    .sort((a, b) => a.s - b.s)
    .forEach(({ i, s, e }) => {
      let r = ends.findIndex((end) => end <= s + 1e-6);
      if (r === -1) {
        r = ends.length < maxRows ? ends.length : 0;
        if (r === ends.length) ends.push(e);
      }
      ends[r] = Math.max(ends[r] ?? 0, e);
      rows[i] = r;
    });
  return { rows, count: Math.max(1, ends.length) };
}

/** Awal tiap segmen pada sumbu klip. */
function segmentOffsets(segments) {
  const out = [];
  let acc = 0;
  for (const s of segments ?? []) {
    out.push(acc);
    acc += Math.max(0, s.end - s.start);
  }
  return out;
}

export default function ClipTimeline({
  clip,
  reframe = null,
  personKeys = [],
  onPersonKeys = null,
  videoRef,
  onSeekClip = null,
  onMoveSubtitle = null,
  onSetSegmentBounds = null,
  onSelectSubtitle = null,
  selectedLine = null,
  speakerColors = [],
  reframeLoading = false,
  frameAiming = false,
  busy = false,
}) {
  // Lebar diukur dari KOLOM LAJURNYA, bukan dari pelatnya: kolom nama dan
  // padding memakan hampir seratus piksel, dan mengukur pelat membuat lajur
  // selebar itu menjulur keluar layar — ujung kanan penggaris dan pegangan
  // potongan jadi tidak bisa diraih sama sekali.
  const scrollRef = useRef(null);
  const laneRef = useRef(null);
  const headRefs = useRef([]);
  const [width, setWidth] = useState(900);
  const [zoom, setZoom] = useState(1);
  // Nilai yang sedang diseret hidup di ref, bukan state: menuliskannya ke state
  // tiap gerakan tetikus akan me-render ulang seluruh lajur 60 kali per detik.
  const ghostRef = useRef(null);
  const [ghost, setGhost] = useState(null);
  // Waktu playhead dalam satuan klip. Dibaca pada ~8 Hz dari loop yang sama
  // yang menggerakkan garisnya — cukup untuk tombol dan angka, dan tidak
  // me-render ulang lajur 60 kali per detik.
  const [now, setNow] = useState(0);
  const nowRef = useRef(0);
  // Digulir mengikuti garis main selama diputar, tapi tidak saat pengguna
  // sendiri sedang menggulir: merebut gulirannya kembali tiap bingkai membuat
  // linimasa terasa melawan tangan.
  const followRef = useRef(true);

  const segments = clip?.segments ?? [];
  const duration = Math.max(
    0.5, segments.reduce((a, s) => a + Math.max(0, s.end - s.start), 0),
  );
  const offsets = useMemo(() => segmentOffsets(segments), [segments]);
  const lines = clip?.subtitles ?? [];
  const packed = useMemo(() => packRows(lines), [lines]);
  const subLaneH = packed.count * LANE_H.sub + (packed.count - 1) * 3;

  useLayoutEffect(() => {
    const el = scrollRef.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width));
    ro.observe(el);
    setWidth(el.getBoundingClientRect().width);
    return () => ro.disconnect();
  }, [clip?.clip_id]);

  // Satu piksel dikurangi supaya tepi kanan lajur tidak jatuh persis di batas
  // wadahnya, yang membuat pegangan selebar 8px di ujungnya mustahil diraih.
  // Kartu judul menempati waktu DI DEPAN klip, bukan di atas detik-detik
  // pertamanya.
  //
  // Itu bukan perbedaan tampilan, melainkan perbedaan yang sudah ada di hasil
  // render: mode foto-diam dan foto-merayap disambungkan dengan `concat` di
  // depan klipnya, jadi klip 60 detik dengan kartu 4 detik menghasilkan berkas
  // 64 detik. Selama linimasa ini menggambar kartunya sebagai lapisan di atas
  // detik 0-4 klip, ia menceritakan hal yang tidak terjadi — dan detik-detik
  // awal klip terlihat seolah hilang.
  const card = clip?.title_card;
  const cardText = ((card?.text || '').trim() || (clip?.title || '').trim());
  const cardHead = (card?.enabled && cardText && card?.mode !== 'overlay')
    ? Math.max(1.2, Number(card.card_seconds || card.seconds || 3))
    : 0;
  const span = cardHead + duration;

  const laneW = Math.max(320, width - 2) * zoom;
  const pxPerSec = laneW / span;
  /** Letak sebuah DETIK KLIP pada sumbu, kartu judul ikut diperhitungkan. */
  const pct = useCallback((t) => `${((t + cardHead) / span) * 100}%`, [cardHead, span]);
  /** Panjang sebuah RENTANG pada sumbu. Bukan hal yang sama dengan letak:
      menambahkan kepala kartu ke sebuah lebar akan melebarkannya, bukan
      menggesernya. */
  const pctW = useCallback((d) => `${(d / span) * 100}%`, [span]);

  /** Detik klip di bawah kursor. Negatif berarti masih di dalam kartu judul. */
  const timeAt = useCallback((clientX) => {
    const el = laneRef.current;
    if (!el) return 0;
    const r = el.getBoundingClientRect();
    const t = ((clientX - r.left) / r.width) * span - cardHead;
    return Math.max(0, Math.min(duration, t));
  }, [duration, span, cardHead]);

  // Garis main: satu loop rAF untuk semua lajur, digerakkan lewat transform.
  useEffect(() => {
    let raf;
    let lastPublished = -1;
    const tick = () => {
      const v = videoRef?.current;
      if (v && segments.length) {
        // Waktu sumber → waktu klip, dihitung ulang tiap bingkai karena
        // pengguna bebas menggeser playhead ke luar batas klip.
        let acc = 0;
        let t = null;
        for (const s of segments) {
          const len = Math.max(0, s.end - s.start);
          if (v.currentTime >= s.start - 0.02 && v.currentTime <= s.end + 0.02) {
            t = acc + (v.currentTime - s.start);
            break;
          }
          acc += len;
        }
        // Kepala kartu judul ikut dihitung: tanpa itu garis mainnya berdiri
        // di tempat yang salah persis sebanyak lama kartunya.
        const px = t === null ? 0 : ((t + cardHead) / span) * laneW;
        headRefs.current.forEach((el) => {
          if (!el) return;
          if (t === null) { el.style.opacity = '0'; return; }
          el.style.opacity = '1';
          el.style.transform = `translateX(${px}px)`;
        });
        if (t !== null) {
          nowRef.current = t;
          if (Math.abs(t - lastPublished) > 0.12) {
            lastPublished = t;
            setNow(t);
          }
          // Menjaga garisnya tetap terlihat saat diperbesar. Tanpa ini,
          // memperbesar sampai sepersekian detik berarti gambarnya berjalan
          // keluar layar dalam sedetik dan harus dikejar dengan tangan.
          const sc = scrollRef.current;
          if (sc && followRef.current && !v.paused) {
            const pad = sc.clientWidth * 0.25;
            if (px < sc.scrollLeft + pad || px > sc.scrollLeft + sc.clientWidth - pad) {
              sc.scrollLeft = Math.max(0, px - sc.clientWidth / 2);
            }
          }
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [videoRef, segments, duration, laneW, cardHead, span]);

  const ticks = useMemo(() => {
    const step = TICK_STEPS.find((x) => (x * pxPerSec) >= 68) ?? 300;
    // Sebanyak angka di belakang koma yang benar-benar dibutuhkan langkahnya,
    // tidak lebih: "00:12.0" di penggaris berlangkah 5 detik hanya menambah
    // lebar tanpa menambah keterangan.
    const dec = step >= 1 ? 0 : step >= 0.1 ? 1 : 2;
    const out = [];
    // Tanda terakhir dilewati bila angkanya tidak muat sebelum tepi: label yang
    // terpotong separuh terbaca sebagai kesalahan, bukan sebagai penggaris.
    for (let i = 0; i * step <= duration + 1e-6; i += 1) {
      const t = Math.round(i * step * 1000) / 1000;
      if (t === 0 || (duration - t) * pxPerSec > 52) out.push(t);
    }
    return { at: out, dec };
  }, [pxPerSec, duration]);

  /* ── Menyeret ──────────────────────────────────────────────────────────
     Satu mesin untuk ketiga lajur. `commit` dipanggil sekali saat dilepas,
     bukan tiap gerakan: memanggil ulang perhitungan subtitle di server pada
     tiap piksel akan membanjiri antrean dan membuat kotaknya tersendat. */
  const beginDrag = useCallback((spec) => (e) => {
    if (busy) return;
    e.preventDefault();
    e.stopPropagation();
    const el = e.currentTarget;
    el.setPointerCapture?.(e.pointerId);
    const t0 = timeAt(e.clientX);
    const state = { start: spec.start, end: spec.end };
    ghostRef.current = { start: spec.start, end: spec.end };
    setGhost({ ...ghostRef.current, kind: spec.kind, index: spec.index });

    const onMove = (ev) => {
      const d = timeAt(ev.clientX) - t0;
      let start = state.start;
      let end = state.end;
      if (spec.handle === 'move') { start += d; end += d; }
      else if (spec.handle === 'start') start = Math.min(end - 0.2, start + d);
      else end = Math.max(start + 0.2, end + d);
      if (start < 0) { end -= start; start = 0; }
      if (end > duration) { start -= (end - duration); end = duration; }
      ghostRef.current = { start: Math.max(0, start), end: Math.min(duration, end) };
      setGhost({ ...ghostRef.current, kind: spec.kind, index: spec.index });
    };
    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      const g = ghostRef.current;
      setGhost(null);
      if (g && (Math.abs(g.start - spec.start) > 0.02 || Math.abs(g.end - spec.end) > 0.02)) {
        spec.commit(g.start, g.end);
      }
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  }, [busy, timeAt, duration]);

  /**
   * Memperbesar di sekitar garis main, bukan di sekitar tepi kiri.
   *
   * Memperbesar tanpa jangkar melompat ke awal klip: pada 64× itu berarti
   * gambarnya hilang dari layar tepat pada gerakan yang dilakukan justru untuk
   * melihatnya lebih dekat.
   */
  const setZoomAround = useCallback((next) => {
    const sc = scrollRef.current;
    const t = nowRef.current;
    setZoom(next);
    if (!sc) return;
    const laneNext = Math.max(320, width - 2) * next;
    requestAnimationFrame(() => {
      sc.scrollLeft = Math.max(0, (t / duration) * laneNext - sc.clientWidth / 2);
    });
  }, [width, duration]);

  const zoomStep = useCallback((dir) => {
    const i = ZOOMS.indexOf(zoom);
    const j = Math.max(0, Math.min(ZOOMS.length - 1, (i < 0 ? 0 : i) + dir));
    if (ZOOMS[j] !== zoom) setZoomAround(ZOOMS[j]);
  }, [zoom, setZoomAround]);

  /* ── Arah bingkai sebagai potongan ─────────────────────────────────────
     Inilah bentuk yang sebenarnya dicari: bukan deretan titik, melainkan
     rentang yang bisa dipotong di detik mana pun, lalu tiap potongannya
     ditunjuk ke wajah yang benar. */
  const cuts = useMemo(() => aimCuts(personKeys, duration), [personKeys, duration]);

  /**
   * Memotong arah bingkai di posisi garis main.
   *
   * Potongan baru selalu mulai dari OTOMATIS, tidak mewarisi arah potongan yang
   * dibelah. Bentuk warisan itu terasa rapi di atas kertas — memotong tidak
   * mengubah apa pun yang terlihat — tapi salah untuk cara benda ini dipakai.
   * Tanda arah adalah PEMBETULAN atas satu bagian yang meleset, dan pembetulan
   * harus berakhir. Dengan warisan, memilih wajah 2 di detik 3 lalu memotong
   * lagi di detik 5 membuat sisa klipnya tetap mengunci wajah 2 sampai habis;
   * mengembalikannya ke otomatis butuh satu tekanan lagi yang tidak terpikirkan
   * siapa pun. Sekarang memotong berarti "cukup sampai sini".
   */
  const cutHere = useCallback(() => {
    if (!onPersonKeys) return;
    onPersonKeys(withPersonKey(personKeys, nowRef.current, null));
  }, [onPersonKeys, personKeys]);

  /** Mengganti wajah yang dituju satu potongan. */
  const aimCut = useCallback((cut, person) => {
    if (!onPersonKeys) return;
    onPersonKeys(withPersonKey(personKeys, cut.start, person));
  }, [onPersonKeys, personKeys]);

  /** Menghapus batas potongan — potongan ini menyatu dengan yang sebelumnya. */
  const mergeCut = useCallback((cut) => {
    if (!onPersonKeys || cut.keyIndex < 0) return;
    onPersonKeys(personKeys.filter((_, i) => i !== cut.keyIndex));
  }, [onPersonKeys, personKeys]);

  /** Menggeser batas potongan ke detik lain. */
  const moveCut = useCallback((cut, t) => {
    if (!onPersonKeys || cut.keyIndex < 0) return;
    onPersonKeys(personKeys
      .map((k, i) => (i === cut.keyIndex
        ? { ...k, t: Math.max(0, Math.round(t * 100) / 100) } : k))
      .sort((a, b) => a.t - b.t));
  }, [onPersonKeys, personKeys]);

  const shownRect = (kind, index, start, end) => (
    ghost && ghost.kind === kind && ghost.index === index
      ? { start: ghost.start, end: ghost.end }
      : { start, end }
  );

  /* ── Lajur bingkai ─────────────────────────────────────────────────────
     Bukan sekadar deretan tanda: rentang di mana tiap orang benar-benar ada
     di kamera digambar lebih dulu. Tanpa itu, menaruh tanda berarti menebak —
     tidak ada cara mengetahui bahwa orang yang ditunjuk sedang tidak terlihat
     pada detik itu, yang persis kesalahan yang sedang dibetulkan. */
  const people = reframe?.people ?? [];
  const spans = useMemo(
    () => people.map((_, i) => personSpans(reframe, i)),
    [reframe, people],
  );

  /**
   * Siapa yang BENAR-BENAR muncul di klip ini.
   *
   * Nomor orang sekarang milik seluruh video, bukan milik klipnya — itulah yang
   * membuat "orang 2" tetap orang yang sama di klip mana pun. Konsekuensinya,
   * daftar yang datang memuat semua orang di video, termasuk yang tidak sekali
   * pun lewat di depan kamera pada rentang ini. Mereka disembunyikan, tapi
   * NOMORNYA tidak dipakai ulang: lajur bisa melompat dari 1 ke 3, dan lompatan
   * itu justru keterangan — ia berarti orang 2 memang tidak ada di sini.
   */
  const hadir = useMemo(
    () => people.map((_, i) => i).filter((i) => (spans[i] ?? []).length > 0),
    [people, spans],
  );

  const aimAt = useCallback((t, person) => {
    if (!onPersonKeys) return;
    onPersonKeys(withPersonKey(personKeys, t, person));
  }, [onPersonKeys, personKeys]);

  /* ── Subtitle duduk di baris ORANGNYA ──────────────────────────────────
     Selama subtitle punya lajurnya sendiri dan wajah punya lajurnya sendiri,
     tidak ada tempat di layar yang menjawab "orang ini bicara apa, dan
     bingkainya sedang menoleh ke siapa saat itu" — padahal itu satu-satunya
     pertanyaan yang membuat kedua lajur itu perlu dilihat bersama.

     Jembatannya `speaker_faces`: penomoran subtitle datang dari SUARA
     (diarisasi), penomoran wajah dari GAMBAR, dan keduanya tidak pernah
     otomatis sama. Tanpa peta itu, menaruh baris subtitle di baris seorang
     wajah hanya akan berbohong dengan rapi — jadi kalau petanya tidak ada,
     subtitle tetap memakai lajurnya sendiri seperti sebelumnya. */
  const speakerFaces = reframe?.speaker_faces ?? null;
  const byPerson = useMemo(() => {
    if (!speakerFaces || !Object.keys(speakerFaces).length || hadir.length < 2) {
      return null;
    }
    const rows = people.map(() => []);
    const sisa = [];
    lines.forEach((l, i) => {
      const f = speakerFaces[String(l.speaker ?? 0)];
      if (typeof f === 'number' && f >= 0 && f < people.length) rows[f].push(i);
      else sisa.push(i);
    });
    return { rows, sisa };
  }, [speakerFaces, people, lines]);

  /**
   * Satu baris subtitle sebagai blok yang bisa dipegang.
   *
   * Dipakai dua tempat: lajur subtitle datar (bila kita tidak tahu siapa milik
   * siapa) dan baris per orang (bila kita tahu). Satu fungsi, bukan dua salinan
   * — pegangan seret yang berperilaku beda di dua tempat adalah bug yang hanya
   * ketahuan oleh orang yang memakai keduanya.
   */
  const subBlock = (line, i, row) => {
    const r = shownRect('sub', i, line.start, line.end);
    const ink = speakerColors[line.speaker ?? 0];
    const on = selectedLine === i;
    const commit = (s2, e2) => onMoveSubtitle?.(i, s2, e2);
    return (
      <div key={i}
           className={`tl-block tl-block--sub${on ? ' is-on' : ''}`}
           style={{
             left: pct(r.start),
             // Celah 4px antar baris bukan hiasan: baris subtitle
             // bersambungan, dan tanpa celah blok berikutnya menutupi
             // pegangan kanan blok sebelumnya — pegangannya tergambar
             // tapi tidak pernah bisa dipegang.
             width: `calc(${pctW(Math.max(0.12, r.end - r.start))} - 4px)`,
             top: `${row * (LANE_H.sub + 3) + 3}px`,
             height: `${LANE_H.sub - 6}px`, bottom: 'auto',
             borderLeftColor: /^#[0-9a-f]{6}$/i.test(ink || '') ? ink : 'var(--cue)',
           }}
           title={`${formatTime(line.start)} → ${formatTime(line.end)} · ${line.text}`}
           onPointerDown={(e) => {
             onSelectSubtitle?.(i);
             beginDrag({
               kind: 'sub', index: i, handle: 'move',
               start: line.start, end: line.end, commit,
             })(e);
           }}>
        <span className="tl-grip tl-grip--l"
              onPointerDown={beginDrag({
                kind: 'sub', index: i, handle: 'start',
                start: line.start, end: line.end, commit,
              })} />
        <span className="tl-block-text">{line.text}</span>
        <span className="tl-grip tl-grip--r"
              onPointerDown={beginDrag({
                kind: 'sub', index: i, handle: 'end',
                start: line.start, end: line.end, commit,
              })} />
      </div>
    );
  };

  if (!clip) return null;

  const registerHead = (i) => (el) => { headRefs.current[i] = el; };

  return (
    <div className="plate clip-tl">
      <div className="plate-head">
        <span className="mark" style={{ color: 'var(--ink)' }}>Linimasa klip</span>
        <span style={{ fontSize: '.72rem', color: 'var(--ink-3)' }}>
          seret baris subtitle untuk memindahkannya · seret ujungnya untuk memanjangkan
        </span>
        <span style={{ marginLeft: 'auto', display: 'flex', gap: '5px' }}>
          <button className="btn-secondary tl-zoom" title="Perkecil"
                  disabled={zoom <= ZOOMS[0]}
                  onClick={() => zoomStep(-1)}>
            <ZoomOut size={13} />
          </button>
          <span className="tc" style={{
            fontSize: '.7rem', color: 'var(--ink-3)', alignSelf: 'center', minWidth: '26px',
            textAlign: 'center',
          }}>{zoom}×</span>
          <button className="btn-secondary tl-zoom" title="Perbesar"
                  disabled={zoom >= ZOOMS[ZOOMS.length - 1]}
                  onClick={() => zoomStep(1)}>
            <ZoomIn size={13} />
          </button>
        </span>
      </div>

      {/* Nama lajur hidup di kolom sendiri, bukan mengambang di atas isinya.
          Di dalam lajur, namanya menutupi rentang yang justru harus dibaca —
          dan ikut hanyut saat linimasanya digulir. */}
      <div className="clip-tl-body">
        <div className="clip-tl-names">
          <span className="tl-name-spacer" />
          <span className="tl-name" style={{ height: `${LANE_H.seg}px` }}>Potongan</span>
          {!byPerson && (
            <span className="tl-name" style={{ height: `${subLaneH}px` }}>Subtitle</span>
          )}
          {hadir.length > 1 && (
            <>
              <span className="tl-name tl-name--aim" style={{ height: `${LANE_H.aim}px` }}>
                Arah bingkai
              </span>
              {hadir.map((p) => (
                <span key={p} className="tl-name"
                      style={{ height: `${byPerson ? LANE_H.orang : LANE_H.frame}px` }}
                      title={byPerson
                        ? `Orang ${p + 1}: ucapannya, dan kapan ia terlihat di kamera`
                        : `Wajah ${p + 1}: kapan ia terlihat di kamera`}>
                  {byPerson ? `Orang ${p + 1}` : `Wajah ${p + 1}`}
                </span>
              ))}
              {byPerson && byPerson.sisa.length > 0 && (
                <span className="tl-name" style={{ height: `${LANE_H.orang}px` }}
                      title="Baris yang penuturnya tidak bisa dipastikan wajahnya">
                  Belum pasti
                </span>
              )}
            </>
          )}
        </div>
        <div className="clip-tl-scroll" ref={scrollRef}>
          <div ref={laneRef} className="clip-tl-lanes" style={{ width: `${laneW}px` }}>
            {/* penggaris */}
            <div className="tl-ruler" onPointerDown={(e) => onSeekClip?.(timeAt(e.clientX))}>
              {ticks.at.map((t) => (
                <span key={t} className="tl-tick" style={{ left: pct(t) }}>
                  <i />{formatTimeFine(t, ticks.dec)}
                </span>
              ))}
              <span ref={registerHead(0)} className="tl-head" style={{ opacity: 0 }}>
                <i className="tl-head-flag" />
              </span>
            </div>

            {/* potongan */}
            <div className="tl-lane" style={{ height: `${LANE_H.seg}px` }}
                 onPointerDown={(e) => {
                   if (e.target === e.currentTarget) onSeekClip?.(timeAt(e.clientX));
                 }}>
              {/* Kartu judul, berdiri di depan klipnya.
                  Warnanya sengaja berbeda dari potongan klip: yang biru bukan
                  rekaman yang dipotong, melainkan detik-detik yang DITAMBAHKAN
                  di depannya. Dua hal berbeda tidak boleh terlihat sama pada
                  satu sumbu waktu. */}
              {cardHead > 0 && (
                <div className="tl-block tl-block--card"
                     style={{ left: pct(-cardHead), width: pctW(cardHead) }}
                     title={`Kartu judul · ${cardHead.toFixed(1)} detik sebelum klip mulai`}>
                  <span className="tl-block-text">{cardText}</span>
                </div>
              )}
              {segments.map((seg, i) => {
                const len = Math.max(0, seg.end - seg.start);
                const r = shownRect('seg', i, offsets[i], offsets[i] + len);
                return (
                  <div key={i} className="tl-block tl-block--seg"
                       style={{ left: pct(r.start), width: pctW(r.end - r.start) }}
                       title={`Potongan ${i + 1} · ${formatTime(seg.start)} → ${formatTime(seg.end)}`}>
                    <span className="tl-grip tl-grip--l"
                          onPointerDown={beginDrag({
                            kind: 'seg', index: i, handle: 'start',
                            start: offsets[i], end: offsets[i] + len,
                            commit: (s, e2) => onSetSegmentBounds?.(
                              i, seg.start + (s - offsets[i]), seg.start + (e2 - offsets[i])),
                          })} />
                    <span className="tl-block-text tc">
                      {formatTime(seg.start)} → {formatTime(seg.end)}
                    </span>
                    <span className="tl-grip tl-grip--r"
                          onPointerDown={beginDrag({
                            kind: 'seg', index: i, handle: 'end',
                            start: offsets[i], end: offsets[i] + len,
                            commit: (s, e2) => onSetSegmentBounds?.(
                              i, seg.start + (s - offsets[i]), seg.start + (e2 - offsets[i])),
                          })} />
                  </div>
                );
              })}
              <span ref={registerHead(1)} className="tl-head" style={{ opacity: 0 }} />
            </div>

            {/* Subtitle datar: hanya bila kita TIDAK tahu suara mana milik
                wajah mana. Begitu petanya ada, barisnya pindah ke orangnya. */}
            {!byPerson && (
              <div className="tl-lane tl-lane--sub" style={{ height: `${subLaneH}px` }}
                   onPointerDown={(e) => {
                     if (e.target === e.currentTarget) onSeekClip?.(timeAt(e.clientX));
                   }}>
                {lines.map((line, i) => subBlock(line, i, packed.rows[i]))}
                <span ref={registerHead(2)} className="tl-head" style={{ opacity: 0 }} />
              </div>
            )}

            {/* arah bingkai: potongan bersambungan yang bisa dipotong lagi */}
            {hadir.length > 1 && (
              <div className="tl-lane tl-lane--aim" style={{ height: `${LANE_H.aim}px` }}
                   onPointerDown={(e) => {
                     if (e.target === e.currentTarget) onSeekClip?.(timeAt(e.clientX));
                   }}>
                {cuts.map((cut, ci) => {
                  const r = shownRect('aim', ci, cut.start, cut.end);
                  const auto = cut.person === null || cut.person === undefined;
                  // Potongan yang lebih sempit dari deretan tombolnya tidak
                  // menampilkannya sama sekali: tombol yang tumpah menutupi
                  // potongan tetangga, dan rentang sesempit itu memang harus
                  // diperbesar dulu sebelum bisa disunting dengan tepat.
                  const muat = (r.end - r.start) * pxPerSec
                    > (hadir.length + (cut.keyIndex >= 0 ? 2 : 1)) * 22 + 74;
                  const ink = auto ? 'var(--ink-3)' : frameInk(cut.person);
                  return (
                    <div key={`${cut.keyIndex}:${ci}`} className="tl-block tl-block--aim"
                         style={{
                           left: pct(r.start), width: `calc(${pctW(r.end - r.start)} - 2px)`,
                           background: auto
                             ? 'var(--plate-2)'
                             : `color-mix(in srgb, ${ink} 20%, var(--plate-3))`,
                           boxShadow: `inset 0 0 0 1px ${ink}`,
                         }}
                         title={auto
                           ? `${formatTime(cut.start)} → ${formatTime(cut.end)} · bingkai memilih sendiri`
                           : `${formatTime(cut.start)} → ${formatTime(cut.end)} · mengambil wajah ${cut.person + 1}`}>
                      {cut.keyIndex >= 0 && (
                        <span className="tl-grip tl-grip--l"
                              title="Geser batas potongan"
                              onPointerDown={beginDrag({
                                kind: 'aim', index: ci, handle: 'start',
                                start: cut.start, end: cut.end,
                                commit: (a) => moveCut(cut, a),
                              })} />
                      )}
                      {muat && (
                      <span className="tl-aim-pick">
                        {/* Nomornya diklik langsung: itu gerakan yang diminta —
                            di detik ini ambil wajah ini, di detik berikutnya
                            ambil sebelahnya. */}
                        <button type="button"
                                className={`tl-aim-btn${auto ? ' is-on' : ''}`}
                                title="Biarkan bingkai memilih sendiri di potongan ini"
                                onPointerDown={(e) => e.stopPropagation()}
                                onClick={() => aimCut(cut, null)}>A</button>
                        {hadir.map((pi) => (
                          <button key={pi} type="button"
                                  className={`tl-aim-btn${cut.person === pi ? ' is-on' : ''}`}
                                  style={cut.person === pi
                                    ? { background: frameInk(pi), borderColor: frameInk(pi) }
                                    : undefined}
                                  title={`Ambil wajah ${pi + 1} di potongan ini`}
                                  onPointerDown={(e) => e.stopPropagation()}
                                  onClick={() => aimCut(cut, pi)}>{pi + 1}</button>
                        ))}
                        {cut.keyIndex >= 0 && (
                          <button type="button" className="tl-aim-btn tl-aim-btn--x"
                                  title="Hapus batas ini — sambung dengan potongan sebelumnya"
                                  onPointerDown={(e) => e.stopPropagation()}
                                  onClick={() => mergeCut(cut)}>×</button>
                        )}
                        {/* Dibaca sekali pandang, tanpa harus menafsirkan tombol
                            mana yang sedang menyala. */}
                        <span className="tl-aim-say" style={auto ? undefined : { color: ink }}>
                          {auto ? 'otomatis' : `wajah ${cut.person + 1}`}
                        </span>
                      </span>
                      )}
                    </div>
                  );
                })}
                <span ref={registerHead(3)} className="tl-head" style={{ opacity: 0 }} />
              </div>
            )}

            {/* Satu baris per ORANG: kehadirannya di kamera dan ucapannya,
                pada sumbu waktu yang sama.
                Dulu keduanya lajur terpisah — subtitle di satu tempat, wajah di
                tempat lain — dan tidak ada satu titik pun di layar yang bisa
                menjawab "saat dia mengatakan ini, bingkainya sedang melihat
                siapa". Itulah satu-satunya alasan kedua lajur itu dilihat. */}
            {hadir.length > 1 && (
              <div className="tl-frame-lanes">
                {hadir.map((p) => {
                  const punya = byPerson ? byPerson.rows[p] : [];
                  const tinggi = byPerson ? LANE_H.orang : LANE_H.frame;
                  return (
                    <div key={p} className="tl-lane tl-lane--frame"
                         style={{ height: `${tinggi}px` }}
                         onPointerDown={(e) => {
                           if (e.target === e.currentTarget) aimAt(timeAt(e.clientX), p);
                         }}
                         title={`Klik ruang kosongnya untuk mengarahkan bingkai ke wajah ${p + 1} mulai detik itu`}>
                      {/* Kehadiran digambar sebagai pita tipis di dasar baris,
                          bukan sebagai balok penuh: yang dipegang di baris ini
                          adalah subtitle, dan pita setebal baris akan jadi
                          sasaran klik yang bersaing dengannya. */}
                      {spans[p].map(([a, b], k) => (
                        <span key={k} className="tl-seen"
                              style={{
                                left: pct(a), width: pctW(Math.max(0.05, b - a)),
                                ...(byPerson ? { top: 'auto', bottom: '3px', height: '8px' } : {}),
                              }} />
                      ))}
                      {punya.map((i) => subBlock(lines[i], i, 0))}
                      <span ref={registerHead(4 + p)} className="tl-head" style={{ opacity: 0 }} />
                    </div>
                  );
                })}

                {/* Baris yang penuturnya tidak bisa dipasangkan ke wajah mana
                    pun. Tidak dibuang dan tidak ditebak-tebak taruh di salah
                    satu orang: keduanya akan menyembunyikan kesalahan yang
                    justru perlu terlihat. */}
                {byPerson && byPerson.sisa.length > 0 && (
                  <div className="tl-lane tl-lane--frame"
                       style={{ height: `${LANE_H.orang}px` }}
                       onPointerDown={(e) => {
                         if (e.target === e.currentTarget) onSeekClip?.(timeAt(e.clientX));
                       }}
                       title="Baris yang penuturnya tidak bisa dipastikan wajahnya">
                    {byPerson.sisa.map((i) => subBlock(lines[i], i, 0))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {frameAiming && hadir.length <= 1 && (
        <div className="clip-tl-foot">
          <Crosshair size={12} style={{ color: 'var(--ink-3)' }} />
          <span>
            {reframeLoading
              ? 'Menyiapkan lajur bingkai — sistem sedang mencari wajah di klip ini…'
              : 'Klip ini hanya punya satu wajah di kamera, jadi tidak ada yang perlu ditunjuk.'}
          </span>
        </div>
      )}

      {hadir.length > 1 && (
        <div className="clip-tl-foot">
          <button className="btn-secondary tl-cut" onClick={cutHere} disabled={!onPersonKeys}
                  title="Membelah arah bingkai di posisi garis main">
            <Scissors size={12} /> Potong di {formatTimeFine(now, 1)}
          </button>
          <span>
            Tiap potongan di lajur <b>Arah bingkai</b> punya nomornya sendiri:
            tekan <b>1</b> atau <b>2</b> untuk memilih wajah mana yang diambil di
            rentang itu, <b>A</b> untuk membiarkan sistem memilih, dan{' '}
            <b>×</b> untuk menghapus batasnya. Batas potongan bisa diseret.
          </span>
          {(personKeys ?? []).length > 0 && (
            <button className="btn-secondary" style={{
              marginLeft: 'auto', fontSize: '.72rem', padding: '4px 9px', minHeight: '26px',
            }} onClick={() => onPersonKeys?.([])}>
              <Wand2 size={12} /> Lepas semua
            </button>
          )}
        </div>
      )}
    </div>
  );
}
