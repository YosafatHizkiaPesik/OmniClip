import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Play, Pause, RotateCcw, Loader2, Move, Maximize2, Minimize2 } from 'lucide-react';
import { apiPost } from '../../lib/api';
import { fontStack } from '../../lib/fonts';
import { CARD_VARIANTS } from './cardStyles';
import { CANVAS_ASPECT, coverPercent, followX, frameInk } from './frames';
import { beginRectDrag } from './rectDrag';

// `r` adalah rasio yang sama dengan `aspect`, dalam bentuk angka. Batas tinggi
// kanvas dinyatakan lewat lebar (lebar = tinggi x rasio) karena membatasi
// tingginya langsung akan membuat kotak lebih lebar daripada gambarnya, dan
// kotak bingkai di atasnya berhenti menunjuk tempat yang benar.
const RATIO_BOX = {
  '9:16': { width: 300, aspect: '9 / 16', r: 9 / 16 },
  '1:1': { width: 380, aspect: '1 / 1', r: 1 },
  '4:5': { width: 340, aspect: '4 / 5', r: 4 / 5 },
  '16:9': { width: 520, aspect: '16 / 9', r: 16 / 9 },
};

// Ukuran dan margin subtitle disimpan dalam satuan kanvas setinggi 1920 —
// satuan yang sama yang dipakai render, yang menyekalakan gaya ke tinggi kanvas
// sebenarnya. Karena Fontsize pada ASS relatif terhadap PlayResY, pecahan
// nilai/1920 berlaku untuk SEMUA rasio, jadi pratinjau bisa memakai satu rumus.
const CANVAS_H = 1920;

// Sama persis dengan WARNA_BAWAAN di backend/app/services/subtitles.py.
// Kalibrasi CSS -> libass. Dipakai subtitle DAN tanda air, karena keduanya
// memakai satuan yang sama di berkas ASS.
const ASS_FONT_RATIO = 0.521 / 0.756;

const WARNA_BAWAAN = ['#FFFFFF', '#7CFFB2', '#FFB3C7', '#B39DFF',
                      '#FFD166', '#5BC8FF', '#FF9F1C', '#B8FF3A'];

function hexAlpha(hex, opacity) {
  const c = String(hex || '').trim().replace('#', '');
  if (c.length !== 6) return `rgba(255,255,255,${opacity})`;
  const n = parseInt(c, 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${opacity})`;
}

function padPalette(warna) {
  const out = [...(warna ?? [])];
  for (let i = out.length; i < WARNA_BAWAAN.length; i += 1) out.push(WARNA_BAWAAN[i]);
  return out;
}

/** m:dd — satuan yang sama dengan yang tertulis di bilah transport. */
function clockTime(seconds) {
  const t = Math.max(0, Number(seconds) || 0);
  return `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`;
}

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
  layout = null,           // {background, frames:[{id,label,src,dst,fit}]}
  onLayoutChange = null,   // menggeser kotak TUJUAN langsung di atas hasil
  frameEditing = false,    // kotak bingkai hanya bisa dipegang di tab Bingkai
  selectedFrameId = null,
  onSelectFrame = null,
  onStyleChange = null,    // menggeser/mengubah ukuran subtitle di atas gambar
  onCardChange = null,     // menggeser/mengubah ukuran JUDUL kartu di atas gambar
}) {
  const innerRef = useRef(null);
  const videoRef = externalRef ?? innerRef;
  const bgRef = useRef(null);
  const boxRef = useRef(null);
  // Elemen video tambahan untuk bingkai ke-2 dan seterusnya. Bingkai pertama
  // memakai pemutar utama supaya suara dan waktu tetap datang dari satu tempat.
  const extraRefs = useRef([]);
  // Elemen video tiap bingkai, dipetakan dari id-nya. Bingkai pengikut
  // menggeser videonya tiap frame lewat ref.
  const frameVideoRefs = useRef({});
  // Rasio sumber dibaca dari berkasnya. Geometri 'cover' tiap bingkai bergantung
  // padanya, dan menebak 16:9 akan menggeser potongan pada sumber 4:3.
  const [sourceAspect, setSourceAspect] = useState(16 / 9);
  const [segIndex, setSegIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [clipTime, setClipTime] = useState(0);
  const [boxH, setBoxH] = useState(0);
  const [boxW, setBoxW] = useState(0);
  const wellRef = useRef(null);
  const [well, setWell] = useState({ w: 0, h: 0 });
  const [dragging, setDragging] = useState(null);   // 'move' | 'size' | null
  const stageRef = useRef(null);
  const [fullscreen, setFullscreen] = useState(false);
  // Kartu judul sebagai LAPISAN WAKTU tersendiri di depan klip.
  //
  // Sebelumnya kartunya digambar di atas detik-detik pertama klip yang sedang
  // berjalan: judulnya terlihat, tapi videonya jalan terus di belakangnya dan
  // suaranya tidak dibacakan sama sekali. Itu bukan yang akan dirender — pada
  // mode foto-diam dan foto-merayap ffmpeg menyambung kartunya DI DEPAN,
  // sehingga klipnya baru mulai setelah judulnya selesai dibaca.
  //
  // `cardLeft` null berarti tidak sedang di kartu. Angka berarti sekian detik
  // lagi klipnya mulai, dan selama itu videonya ditahan.
  const [cardLeft, setCardLeft] = useState(null);
  const [cardBusy, setCardBusy] = useState(false);
  const cardAudioRef = useRef(null);
  const cardTimerRef = useRef(null);
  const [cardDrag, setCardDrag] = useState(null);   // 'move' | 'size' | null

  const card = clip?.title_card;
  const cardText = ((card?.text || '').trim() || (clip?.title || '').trim());
  const cardSeconds = Math.max(1.2, Number(card?.card_seconds || card?.seconds || 3));
  const cardOn = !!card?.enabled && !!cardText;
  // Hanya dua mode yang benar-benar menahan layar. "Klip langsung jalan"
  // sengaja tidak: itulah artinya.
  const cardHolds = cardOn && card?.mode !== 'overlay';
  // Tanda pengenal bacaan: teks, suara, dan temponya. Begitu salah satunya
  // berubah, berkas suara yang tersimpan sudah membacakan judul yang lain —
  // dan memutarnya berarti penonton mendengar judul lama di atas judul baru.
  const cardSig = `${cardText}|${card?.voice_id || ''}|${card?.rate || 1}`;

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

  // Ruang yang tersedia untuk kanvas, diamati sekali per perubahan ukuran.
  useLayoutEffect(() => {
    const el = wellRef.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(([entry]) => {
      setWell({ w: entry.contentRect.width, h: entry.contentRect.height });
    });
    ro.observe(el);
    const r = el.getBoundingClientRect();
    setWell({ w: r.width, h: r.height });
    return () => ro.disconnect();
  }, []);

  // Tinggi kotak diukur, bukan ditebak, supaya ukuran teks pratinjau benar-benar
  // sebanding dengan hasil render pada rasio apa pun.
  useLayoutEffect(() => {
    const el = boxRef.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(([entry]) => {
      setBoxH(entry.contentRect.height);
      setBoxW(entry.contentRect.width);
    });
    ro.observe(el);
    const rect = el.getBoundingClientRect();
    setBoxH(rect.height);
    setBoxW(rect.width);
    return () => ro.disconnect();
  }, [aspectRatio, frameMode]);

  // Tombol Esc dan tombol layar-penuh bawaan browser sama-sama bisa keluar dari
  // mode ini, jadi keadaannya dibaca dari dokumen — bukan ditebak dari klik.
  useEffect(() => {
    const sync = () => setFullscreen(document.fullscreenElement === stageRef.current);
    document.addEventListener('fullscreenchange', sync);
    return () => document.removeEventListener('fullscreenchange', sync);
  }, []);

  const toggleFullscreen = useCallback(() => {
    if (document.fullscreenElement) document.exitFullscreen?.();
    else stageRef.current?.requestFullscreen?.().catch(() => { /* ditolak browser */ });
  }, []);

  const frames = layout?.frames ?? [];
  const useLayout = frameMode === 'layout' && frames.length > 0;
  const useReframe = frameMode === 'smart' && reframe?.available && constrained && !useLayout;
  const useCenter = frameMode === 'center' && !useLayout;
  const useOriginal = frameMode === 'original' && !useLayout;
  const useBlur = !useReframe && !useCenter && !useOriginal && !useLayout;
  // Susunan bingkai jarang menutupi seluruh kanvas — celah di antaranya diisi
  // versi kabur dari sumbernya, kecuali bila pengguna memilih hitam pekat.
  const showBlurBg = useBlur || (useLayout && layout?.background !== 'black');
  const canvasAspect = CANVAS_ASPECT[aspectRatio] ?? 9 / 16;

  const secondaries = useCallback(
    () => [bgRef.current, ...extraRefs.current].filter(Boolean), []);

  const readAspect = useCallback((e) => {
    const { videoWidth: w, videoHeight: h } = e.currentTarget;
    if (w > 0 && h > 0) setSourceAspect(w / h);
  }, []);

  // Daftar cermin dipangkas saat jumlah bingkai berkurang. Tanpa ini, elemen
  // yang sudah dilepas React tetap tercatat di sini dan loop sinkronisasi
  // menyetel `currentTime` pada node yang tidak lagi ada di halaman.
  useEffect(() => {
    extraRefs.current.length = Math.max(0, frames.length - 1);
  }, [frames.length]);

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

  /**
   * Geseran video, satu-satunya sumber kebenaran.
   *
   * Ada DUA pihak yang menulis `transform` ke elemen yang sama: React lewat
   * objek gaya, dan loop rAF mode ikut-wajah lewat DOM langsung. Keduanya
   * harus setuju, dan satu-satunya cara membuatnya setuju adalah satu nilai
   * yang dibaca keduanya.
   *
   * Versi sebelumnya menulis `transform = ''` untuk membersihkan sisa geseran
   * mode ikut-wajah. Itu memang membersihkannya — sekaligus MENGHAPUS geseran
   * yang dibutuhkan potong-tengah, yang baru saja dipasang React. Videonya
   * lalu duduk mulai dari tengah kotak, dan separuh kiri kanvas tergambar
   * hitam. Ini kambuhan dari bug bilah-kabur yang dulu, dengan arah terbalik.
   */
  const baseTransform = useReframe ? 'translateX(0)'
    : useCenter ? 'translateX(-50%)' : 'none';

  useEffect(() => {
    if (!useReframe && videoRef.current) {
      videoRef.current.style.transform = baseTransform;
    }
  }, [useReframe, videoRef, aspectRatio, frameMode, reframe, baseTransform]);

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
        // Sebelum pemutar sempat melompat ke awal segmen, currentTime masih 0
        // dan selisihnya negatif. Angka negatif di timecode terbaca sebagai
        // kerusakan, padahal ia hanya berarti "belum mulai".
        const t = constrained && seg
          ? Math.max(0, (offsets[segIndex] ?? 0) + (v.currentTime - seg.start))
          : v.currentTime;

        if (useReframe && cropXAt) {
          const x = cropXAt(Math.max(0, t));
          v.style.transform = `translateX(${(-x / reframe.source_w) * 100}%)`;
        }
        // Bingkai pengikut: geser videonya mengikuti jejak wajah. Rumusnya
        // sama dengan yang dipakai render, dari jejak yang sama, jadi yang
        // terlihat di sini adalah yang akan keluar dari ffmpeg.
        if (useLayout && reframe?.people?.length) {
          for (const f of frames) {
            const entry = frameVideoRefs.current[f.id];
            if (!f.follow || !entry?.el || !entry.geo) continue;
            const x = followX(reframe, f, t);
            if (x === null) continue;
            entry.el.style.left =
              `${entry.geo.left + ((f.src.x - x) / 100) * entry.geo.width}%`;
          }
        }

        // Semua elemen cermin — latar kabur dan bingkai kedua dan seterusnya —
        // dibetulkan hanya saat sudah menyimpang. Menyetel `currentTime` tiap
        // frame membuat dekoder mencari terus dan gambarnya tersendat.
        for (const m of secondaries()) {
          if (Math.abs(m.currentTime - v.currentTime) > 0.25) m.currentTime = v.currentTime;
          if (v.paused && !m.paused) m.pause();
          else if (!v.paused && m.paused) m.play().catch(() => { /* diabaikan */ });
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
  }, [videoRef, segments, segIndex, offsets, constrained, useReframe, cropXAt,
      reframe, secondaries, useLayout, frames]);

  const handleTimeUpdate = () => {
    const v = videoRef.current;
    const seg = segments[segIndex];
    if (!v || !seg) return;
    if (!constrained) return;
    // Batas klip hanya berlaku saat SEDANG DIPUTAR.
    //
    // Keduanya di bawah memulangkan playhead ke awal klip, dan selama ia juga
    // berjalan saat dijeda, mengklik dekat akhir klip di linimasa rekaman
    // mustahil: begitu playhead mendarat di sana, denyut berikutnya langsung
    // memulangkannya. Yang terlihat pengguna adalah klik yang tidak pernah
    // sampai. Saat dijeda, tempat playhead diletakkan adalah tempat yang
    // dimaksud — termasuk persis di ujung, tempat orang memeriksa apakah
    // kalimatnya terpotong.
    if (v.paused) return;

    // Mundur ke segmen SEBELUMNYA dikenali, bukan dilawan.
    //
    // `segIndex` dulu hanya pernah maju — disetel ke 0 atau ke segmen
    // berikutnya, tidak pernah ke belakang. Padahal memundurkan video bisa
    // mendaratkan playhead di segmen mana pun. Yang terjadi kemudian: penjaga
    // di bawah melihat waktu yang "sebelum awal segmen ini", lalu menyeretnya
    // maju ke awal segmen yang dianggapnya aktif — setiap denyut, berkali-kali
    // dalam sedetik. Yang dilihat pengguna adalah gambar yang mengulang-ulang
    // dirinya dengan cepat dan tidak bisa dimundurkan.
    //
    // Diperiksa lebih dulu daripada kedua penjaga di bawah, karena keduanya
    // menghitung dari `seg` yang justru sedang salah.
    const di = segments.findIndex((g) => v.currentTime >= g.start - 0.05
                                      && v.currentTime < g.end);
    if (di !== -1 && di !== segIndex) {
      setSegIndex(di);
      return;
    }

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
    // Hanya berlaku bila waktunya di luar SELURUH segmen — kalau ia masih di
    // dalam salah satunya, cabang di atas sudah memindahkan segmen aktifnya.
    if (di === -1 && v.currentTime < seg.start - 0.5) v.currentTime = seg.start;
  };

  /** Menghentikan kartu yang sedang berjalan dan membereskan sisanya. */
  const stopCard = useCallback(() => {
    if (cardTimerRef.current) {
      clearTimeout(cardTimerRef.current);
      cardTimerRef.current = null;
    }
    const a = cardAudioRef.current;
    if (a) { a.pause(); a.currentTime = 0; }
    setCardLeft(null);
  }, []);

  // Ganti klip, ganti judul, ganti suara — kartunya berhenti. Membiarkannya
  // berjalan berarti suara judul klip sebelumnya terus dibacakan di atas klip
  // yang sekarang.
  useEffect(() => stopCard, [stopCard]);
  useEffect(() => { stopCard(); }, [clip?.clip_id, cardSig, stopCard]);

  /**
   * Menjalankan kartu judul, lalu klipnya.
   *
   * Suaranya diambil saat dibutuhkan dan disimpan di klipnya bersama tanda
   * pengenalnya, jadi menekan putar dua kali tidak membuat dua permintaan.
   * Kalau pembuatan suaranya gagal — model belum terpasang, jaringan mati —
   * kartunya tetap menahan layar selama waktunya, tanpa suara. Diam itu jujur;
   * yang tidak jujur adalah melompati kartunya seolah ia tidak ada.
   */
  const runCard = useCallback(async () => {
    const v = videoRef.current;
    if (!v) return;
    v.pause();
    for (const m of secondaries()) m.pause();
    if (segments[0]) v.currentTime = segments[0].start;
    setSegIndex(0);
    setClipTime(0);

    let detik = cardSeconds;
    let url = card?.voice_url;
    if (card?.voice !== false && card?.voice_sig !== cardSig) url = null;

    if (card?.voice !== false && !url && cardText.trim()) {
      setCardBusy(true);
      try {
        const r = await apiPost('/title-voice', {
          text: cardText, rate: card?.rate ?? 1.05, voice_id: card?.voice_id,
        });
        url = r.url;
        detik = Math.max(1.2, Number(r.card_seconds) || detik);
        // Disimpan ke klipnya supaya render, linimasa, dan pratinjau semuanya
        // memakai panjang yang SAMA — panjang bacaan sungguhan, bukan angka
        // bawaan yang kebetulan tertulis di setelan.
        onCardChange?.({ card_seconds: r.card_seconds, voice_url: r.url,
                         voice_sig: cardSig });
      } catch {
        url = null;      // kartunya tetap tampil, hanya tanpa suara
      } finally {
        setCardBusy(false);
      }
    }

    setCardLeft(detik);
    setPlaying(true);

    const a = cardAudioRef.current;
    if (url && a) {
      a.src = url;
      a.currentTime = 0;
      try { await a.play(); } catch { /* peramban menahan; kartunya tetap jalan */ }
    }

    cardTimerRef.current = setTimeout(() => {
      cardTimerRef.current = null;
      setCardLeft(null);
      const vid = videoRef.current;
      if (!vid) return;
      vid.play().catch(() => { /* dibatalkan oleh pause berikutnya */ });
      for (const m of secondaries()) {
        m.play().catch(() => { /* cermin boleh gagal diam-diam */ });
      }
    }, detik * 1000);
  }, [videoRef, segments, cardSeconds, card?.voice, card?.voice_url,
      card?.voice_sig, card?.rate, card?.voice_id, cardText, cardSig,
      onCardChange, secondaries]);

  const toggle = () => {
    const v = videoRef.current;
    if (!v) return;
    // Sedang di kartu judul? Menekan putar berarti membatalkannya dan langsung
    // masuk ke klipnya — bukan menjeda sesuatu yang tidak sedang berjalan.
    if (cardLeft !== null) {
      stopCard();
      setPlaying(false);
      return;
    }
    if (playing) {
      v.pause();
      for (const m of secondaries()) m.pause();
    } else if (cardHolds && clipTime < 0.25 && !cardBusy) {
      runCard();
      return;
    } else {
      const seg = segments[segIndex];
      if (constrained && seg && (v.currentTime < seg.start || v.currentTime > seg.end)) {
        v.currentTime = seg.start;
      }
      // play() mengembalikan promise yang ditolak bila pause() menyusul
      // sebelum ia sempat selesai. Itu bukan kegagalan yang perlu ditangani —
      // hanya perlu tidak dibiarkan jadi penolakan promise yang menganggur.
      v.play().catch(() => { /* dibatalkan oleh pause berikutnya */ });
      for (const m of secondaries()) {
        m.play().catch(() => { /* cermin boleh gagal diam-diam */ });
      }
    }
  };

  const restart = () => {
    const v = videoRef.current;
    if (!v || !segments[0]) return;
    stopCard();
    setSegIndex(0);
    v.currentTime = segments[0].start;
    setClipTime(0);
    // Mengulang dari awal berarti dari awal KARTUNYA, bukan dari detik pertama
    // klip: kartu adalah bagian dari yang akan ditonton orang.
    if (cardHolds && !cardBusy) { runCard(); return; }
    v.play().catch(() => { /* dibatalkan oleh pause berikutnya */ });
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
    const w = activeLine?.words;
    if (!w?.length) return -1;
    // Mode tanpa animasi memang tidak menyorot kata, di sini maupun di ASS.
    const anim = style?.animation ?? 'karaoke_pop';
    if (anim === 'none' || anim === 'block') return -1;
    // Sorotan bertahan sampai kata BERIKUTNYA mulai, bukan sampai kata ini
    // selesai — aturan yang sama dengan yang dipakai berkas ASS, tempat tiap
    // kejadian berakhir tepat saat kejadian berikutnya dimulai. Dengan aturan
    // lama, jeda antar kata (1,6% sampai 5,3% kata pada rekaman uji) membuat
    // sorotan padam sesaat di editor padahal di video ia menyala terus.
    if (clipTime < w[0].s) return -1;
    for (let i = w.length - 1; i >= 0; i -= 1) {
      if (clipTime >= w[i].s) return i;
    }
    return -1;
  }, [activeLine, clipTime, style?.animation]);

  /**
   * Menggeser dan mengubah ukuran subtitle langsung di atas gambar.
   *
   * Nilainya ditulis dalam satuan kanvas 1920 supaya apa yang terlihat di sini
   * benar-benar nilai yang dikirim ke ffmpeg — bukan angka pratinjau yang nanti
   * diterjemahkan lagi.
   */
  const startDrag = useCallback((mode) => (e) => {
    if (!onStyleChange || !boxH || !boxW) return;
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.setPointerCapture?.(e.pointerId);
    setDragging(mode);

    const y0 = e.clientY;
    const x0 = e.clientX;
    // Kotak teks pada saat seretan dimulai. Diambil dari elemen induk gagang —
    // yaitu kotak subtitle itu sendiri — karena tingginya bergantung pada
    // berapa baris yang terbentuk, dan itu hanya diketahui setelah dirender.
    const captionRect = e.currentTarget.parentElement?.getBoundingClientRect();
    const startWmX = style?.wm_x ?? 92;
    const startWmY = style?.wm_y ?? 95;
    const startMargin = style?.margin_v ?? 300;
    const startPosX = style?.pos_x ?? 50;
    const startSize = style?.size ?? 96;
    const startBoxW = style?.box_w ?? 84;
    const anchorTop = style?.position === 'top';
    const perPx = CANVAS_H / boxH;      // piksel layar -> satuan kanvas

    // Tepi kotak saat seretan dimulai. Menahan salah satu tepi tetap di
    // tempatnya adalah yang membuat gagangnya terasa seperti kotak teks di
    // editor mana pun: menarik tepi kanan memperlebar ke kanan, bukan
    // memekarkan kotak dari tengah ke dua arah sekaligus.
    const left0 = startPosX - startBoxW / 2;
    const right0 = startPosX + startBoxW / 2;
    const MIN_W = 14;

    const onMove = (ev) => {
      const dy = (ev.clientY - y0) * perPx;
      const dx = ((ev.clientX - x0) / boxW) * 100;   // piksel layar -> persen lebar

      if (mode === 'wm-move') {
        // Tanda air digeser dalam PERSEN kedua sumbu, bukan lewat margin:
        // ia tidak berjangkar ke tepi mana pun, jadi tidak ada tepi yang
        // menjadi acuan. Dijepit 1% dari tiap sisi supaya tidak bisa
        // diseret sampai keluar bingkai dan hilang.
        const dyPct = ((ev.clientY - y0) / boxH) * 100;
        onStyleChange({
          wm_x: Math.round(Math.max(1, Math.min(99, startWmX + dx)) * 10) / 10,
          wm_y: Math.round(Math.max(1, Math.min(99, startWmY + dyPct)) * 10) / 10,
        });
        return;
      }

      if (mode === 'move') {
        // Dua sumbu sekaligus. Jangkar bawah: menyeret ke bawah mengecilkan
        // margin. Mendatar dibatasi setengah lebar kotak dari tiap tepi supaya
        // teksnya tidak bisa diseret sampai keluar bingkai.
        const half = startBoxW / 2;
        onStyleChange({
          margin_v: Math.round(Math.max(20, Math.min(1700,
            anchorTop ? startMargin + dy : startMargin - dy))),
          pos_x: Math.round(Math.max(half, Math.min(100 - half, startPosX + dx)) * 10) / 10,
        });
        return;
      }

      if (mode === 'width-right') {
        const right = Math.max(left0 + MIN_W, Math.min(100, right0 + dx));
        onStyleChange({
          box_w: Math.round((right - left0) * 10) / 10,
          pos_x: Math.round(((left0 + right) / 2) * 10) / 10,
        });
        return;
      }

      if (mode === 'width-left') {
        const left = Math.min(right0 - MIN_W, Math.max(0, left0 + dx));
        onStyleChange({
          box_w: Math.round((right0 - left) * 10) / 10,
          pos_x: Math.round(((left + right0) / 2) * 10) / 10,
        });
        return;
      }

      if (mode === 'scale' && captionRect) {
        // Skala proporsional dari pojok kanan-bawah, dengan pojok kiri-atas
        // ditahan diam — perilaku yang sama dengan menarik sudut kotak teks di
        // Canva, Figma, atau editor mana pun.
        //
        // Faktornya diukur dari JARAK pointer ke jangkar, bukan dari selisih X
        // atau Y sendiri-sendiri. Mengambil salah satu sumbu saja membuat
        // gerakan diagonal terasa meleset, karena jari bergerak di dua sumbu
        // sekaligus sementara kotaknya hanya menanggapi satu.
        const ax = captionRect.left;
        const ay = captionRect.top;
        const d0 = Math.hypot(x0 - ax, y0 - ay);
        const d1 = Math.hypot(ev.clientX - ax, ev.clientY - ay);
        if (d0 < 8) return;
        const factor = Math.max(0.3, Math.min(3.2, d1 / d0));

        const width = Math.max(MIN_W, Math.min(100, startBoxW * factor));
        const left = Math.max(0, Math.min(100 - width, left0));
        onStyleChange({
          box_w: Math.round(width * 10) / 10,
          pos_x: Math.round((left + width / 2) * 10) / 10,
          size: Math.round(Math.max(36, Math.min(220, startSize * factor))),
        });
        return;
      }

      // mode === 'size': ukuran huruf saja, menyeret ke atas memperbesar.
      onStyleChange({ size: Math.round(Math.max(36, Math.min(220, startSize - dy))) });
    };
    const onUp = () => {
      setDragging(null);
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  }, [onStyleChange, boxH, boxW, style?.margin_v, style?.pos_x, style?.size,
      style?.box_w, style?.position]);

  // Bingkai orisinal mengabaikan pilihan rasio: kotaknya harus mengikuti bentuk
  // video sumber, bukan 9:16, atau pratinjaunya berbohong soal hasil akhir.
  const box = useOriginal
    ? RATIO_BOX['16:9']
    : (RATIO_BOX[aspectRatio] ?? RATIO_BOX['9:16']);
  /** Kanvas terbesar berasio `box.r` yang masih muat di ruang yang tersedia. */
  const fit = useMemo(() => {
    if (!well.w || !well.h) return { w: 0, h: 0 };
    const r = box.r ?? 9 / 16;
    const w = Math.min(well.w, well.h * r);
    return { w: Math.round(w), h: Math.round(w / r) };
  }, [well.w, well.h, box.r]);

  const showHook = constrained && clipTime < 3.5 && (clip?.hook_text || '').trim()
    && style?.showHook !== false;

  /**
   * Kartu judul, digambar di pratinjau seperti yang akan dirender.
   *
   * Sebelum ini kartunya hanya ada di setelan dan di berkas hasil — pengguna
   * menyalakannya lalu tidak melihat apa pun berubah, jadi satu-satunya cara
   * mengetahui bentuknya adalah merender. Di sini ia muncul di detik-detik awal
   * klip, dengan teks, ukuran, dan lama yang sama dengan yang dipakai ffmpeg.
   *
   * Untuk mode `freeze` dan `zoom` kartunya berdiri di DEPAN klip, jadi di
   * pratinjau ia menutupi seluruh kanvas dan videonya ditahan — sama seperti
   * bingkai beku yang nanti disambungkan.
   */
  // Mode "klip langsung jalan" memang menumpang di atas klip yang berjalan —
  // di situ kartunya bukan lapisan waktu, dan `cardLeft` tidak dipakai.
  const showCard = constrained && cardOn
    && (cardHolds ? cardLeft !== null : clipTime < cardSeconds);

  /**
   * Letak dan ukuran judul, dalam satuan yang SAMA dengan yang dipakai render.
   *
   * Versi sebelumnya menyatakan ukuran hurufnya dalam `vw` — satuan lebar
   * JENDELA PERAMBAN, bukan lebar kotak pratinjau. Karena itu judulnya
   * tergambar besar di kotak kecil dan mendadak "pas" begitu di-layar-penuh-
   * kan: yang berubah bukan judulnya, melainkan kotak di sekelilingnya.
   * Subtitle di berkas ini sudah lama memakai perbandingan terhadap tinggi
   * kotak; kartunya sekarang memakai perbandingan yang sama.
   */
  const cardBoxW = Math.max(20, Math.min(100, Number(card?.box_w ?? 84)));
  const cardBox = {
    w: cardBoxW,
    left: Math.max(0, Math.min(100 - cardBoxW,
      Number(card?.pos_x ?? 50) - cardBoxW / 2)),
    top: Math.max(6, Math.min(94, Number(card?.pos_y ?? 50))),
  };
  const cardStyleSpec = CARD_VARIANTS.find((v) => v.id === (card?.variant || 'garis'))
    ?? CARD_VARIANTS[0];
  const cardTextStyle = {
    display: 'inline-block',
    color: card?.color || '#FFFFFF',
    fontWeight: 900,
    fontFamily: fontStack(style?.font),
    // Tinggi kotak, bukan lebar jendela. Inilah perbaikannya.
    fontSize: `${Math.max(9, (Number(card?.size ?? 104) * boxH) / CANVAS_H)}px`,
    lineHeight: 1.14,
    textTransform: 'uppercase',
    letterSpacing: '0.005em',
    ...cardStyleSpec.css(card?.shadow || '#000000', boxH / CANVAS_H),
  };

  /**
   * Menggeser dan mengubah ukuran judul langsung di atas gambar.
   *
   * Sengaja memakai perhitungan yang sama persis dengan subtitle: satu
   * kebiasaan tangan untuk dua hal yang terlihat sama di layar. Nilainya
   * ditulis dalam satuan kanvas 1920, yaitu satuan yang dikirim ke ffmpeg —
   * jadi yang terlihat di sini bukan terjemahan dari nilai sebenarnya,
   * melainkan nilai sebenarnya.
   */
  const startCardDrag = useCallback((mode) => (e) => {
    if (!onCardChange || !boxH || !boxW) return;
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.setPointerCapture?.(e.pointerId);
    setCardDrag(mode);

    const x0 = e.clientX;
    const y0 = e.clientY;
    const posX0 = Number(card?.pos_x ?? 50);
    const posY0 = Number(card?.pos_y ?? 50);
    const size0 = Number(card?.size ?? 104);
    const boxW0 = cardBoxW;

    const onMove = (ev) => {
      const dx = ((ev.clientX - x0) / boxW) * 100;
      const dy = ((ev.clientY - y0) / boxH) * 100;
      if (mode === 'move') {
        onCardChange({
          pos_x: Math.round(Math.max(boxW0 / 2,
            Math.min(100 - boxW0 / 2, posX0 + dx)) * 10) / 10,
          pos_y: Math.round(Math.max(6, Math.min(94, posY0 + dy)) * 10) / 10,
        });
      } else {
        // Gagang pojok mengubah DUA hal sekaligus, seperti gagang pojok pada
        // subtitle: menyeret ke kanan melebarkan kotak pembungkusnya, ke bawah
        // membesarkan hurufnya. Memisahkannya jadi dua gagang berarti mengubah
        // ukuran judul selalu butuh dua gerakan.
        onCardChange({
          box_w: Math.round(Math.max(20, Math.min(100, boxW0 + dx * 2))),
          size: Math.round(Math.max(28, Math.min(240,
            size0 + (dy / 100) * CANVAS_H * 0.55))),
        });
      }
    };
    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      setCardDrag(null);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  }, [onCardChange, boxH, boxW, card?.pos_x, card?.pos_y, card?.size, cardBoxW]);

  // Geometri crop. Lebar video dilebihkan sebesar rasio sumber terhadap crop,
  // lalu digeser; hasilnya jendela crop persis mengisi kotak pratinjau.
  const zoom = reframe?.source_w && reframe?.crop_w
    ? (reframe.source_w / reframe.crop_w) * 100 : 100;

  // `transform` HARUS muncul di setiap cabang, termasuk yang tidak memakainya.
  //
  // Loop rAF mode ikut-wajah menulis translateX langsung ke elemen DOM. React
  // membandingkan objek gaya lama dengan yang baru, bukan dengan isi DOM
  // sebenarnya — jadi kalau kedua objek itu sama-sama TIDAK menyebut
  // `transform`, React tidak melihat perubahan apa pun dan geseran terakhir
  // tetap menempel. Bilah kabur lalu tampil melenceng ke kiri, dan baru pulih
  // setelah mampir ke potong-tengah, satu-satunya mode yang kebetulan menyebut
  // `transform` sehingga memaksa React menuliskannya ulang.
  const videoStyle = useReframe
    ? {
      position: 'absolute', top: 0, left: 0, height: '100%', width: `${zoom}%`,
      objectFit: 'cover', willChange: 'transform', background: '#000',
      transform: baseTransform,         // ditimpa tiap frame oleh loop rAF
    }
    : useOriginal
      ? {
        position: 'absolute', inset: 0, width: '100%', height: '100%',
        objectFit: 'contain', background: '#000', transform: baseTransform,
      }
      : useCenter
        ? {
          position: 'absolute', top: 0, left: '50%', height: '100%', width: 'auto',
          transform: baseTransform, background: '#000',
        }
        : {
          position: 'absolute', top: 0, left: 0, width: '100%', height: '100%',
          objectFit: 'contain', background: 'transparent', transform: baseTransform,
        };

  return (
    <div className="clip-preview">
      {/* Yang di-layar-penuh-kan adalah PEMBUNGKUS, bukan kotak videonya.
          Elemen layar penuh dipaksa selebar dan setinggi layar oleh browser,
          yang akan menghapus rasio 9:16 kotaknya; membungkusnya membuat kotak
          tetap memegang rasionya sendiri dan sekadar dipusatkan. */}
      <div ref={(el) => { stageRef.current = el; wellRef.current = el; }}
           className="clip-preview-stage" style={{
        width: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center',
        ...(fullscreen ? { background: '#000', height: '100%' } : {}),
      }}>
      <div ref={boxRef} className="clip-preview-box" style={{
        position: 'relative', background: '#000',
        aspectRatio: box.aspect,
        overflow: 'hidden', boxShadow: 'var(--shadow-card)',
        touchAction: dragging ? 'none' : 'auto',
        // Ukurannya DIHITUNG dari ruang yang tersedia, bukan diserahkan ke CSS.
        //
        // Dua percobaan sebelumnya gagal, dan keduanya gagal dengan cara yang
        // sama. `width: 100%` dengan plafon `46vh * rasio` mengabaikan tinggi
        // yang benar-benar tersisa di studio berlabuh, jadi bagian bawah kanvas
        // terpotong. Lalu `height: 100%` dengan `width: auto` membiarkan
        // `max-width` menjepit lebarnya sementara tingginya tetap 100% — dan
        // kotaknya jadi gepeng: terukur 166x424, rasio 0,39 untuk kanvas yang
        // seharusnya 0,563, sehingga apa yang dilihat pengguna bukan lagi
        // bentuk video yang akan dirender.
        //
        // Elemen ber-`aspect-ratio` tidak bisa "muat ke dalam kotak" dengan CSS
        // saja: sisi yang ditetapkan selalu menang atas rasionya. Jadi ruangnya
        // diukur dan ukurannya dihitung, sekali per perubahan.
        ...(fullscreen
          ? { height: '100vh', width: 'auto', maxWidth: 'none', borderRadius: 0 }
          : fit.w > 0
            ? { width: `${fit.w}px`, height: `${fit.h}px`, borderRadius: '14px' }
            : { width: '100%', borderRadius: '14px' }),
      }}>
        {src ? (
          <>
            {/* Latar kabur — mencerminkan bilah kabur pada hasil render, dan
                mengisi celah di antara bingkai pada susunan sendiri. */}
            {showBlurBg && (
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

            {useLayout ? frames.map((f, i) => {
              // Semuanya persen kotak tujuan: tidak ada satu pun angka di sini
              // yang berasal dari pengukuran, jadi tidak ada yang bisa basi
              // ketika kotaknya berubah lebar.
              const geo = coverPercent(f.src, f.dst, sourceAspect, canvasAspect, f.fit);
              const inner = geo
                ? {
                  position: 'absolute',
                  left: `${geo.left}%`, top: `${geo.top}%`,
                  width: `${geo.width}%`, height: `${geo.height}%`,
                  objectFit: 'fill', transform: 'none', background: '#000',
                }
                : {
                  position: 'absolute', inset: 0, width: '100%', height: '100%',
                  objectFit: f.fit === 'contain' ? 'contain' : 'cover',
                  transform: 'none', background: '#000',
                };
              return (
                <div key={f.id} style={{
                  position: 'absolute',
                  left: `${f.dst.x}%`, top: `${f.dst.y}%`,
                  width: `${f.dst.w}%`, height: `${f.dst.h}%`,
                  overflow: 'hidden', background: '#000',
                }}>
                  {/* Bingkai pertama memakai pemutar utama: suara dan waktu
                      klip hanya boleh datang dari satu elemen. */}
                  {i === 0 ? (
                    <video ref={(el) => {
                             videoRef.current = el;
                             frameVideoRefs.current[f.id] = { el, geo };
                           }} src={src}
                           onTimeUpdate={handleTimeUpdate}
                           onLoadedMetadata={readAspect}
                           onPlay={() => setPlaying(true)}
                           onPause={() => setPlaying(false)}
                           playsInline style={inner} />
                  ) : (
                    <video ref={(el) => {
                             extraRefs.current[i - 1] = el;
                             frameVideoRefs.current[f.id] = { el, geo };
                           }}
                           src={src} muted playsInline aria-hidden="true"
                           style={inner} />
                  )}
                </div>
              );
            }) : (
              <video
                ref={videoRef}
                src={src}
                onTimeUpdate={handleTimeUpdate}
                onLoadedMetadata={readAspect}
                onPlay={() => setPlaying(true)}
                onPause={() => setPlaying(false)}
                playsInline
                style={videoStyle}
              />
            )}

            {/* Kotak tujuan yang bisa dipegang. Hanya hidup di tab Bingkai —
                di tab lain ia akan berebut jari dengan kotak subtitle yang
                menempati kanvas yang sama. */}
            {useLayout && frameEditing && onLayoutChange && !fullscreen
              && frames.map((f, i) => {
                const on = f.id === selectedFrameId;
                const ink = frameInk(i);
                const drag = (handle) => (e) => {
                  onSelectFrame?.(f.id);
                  beginRectDrag(e, {
                    boxW, boxH, rect: f.dst, handle,
                    onChange: (dst) => onLayoutChange({
                      ...layout,
                      frames: layout.frames.map((g) => (g.id === f.id ? { ...g, dst } : g)),
                    }),
                  });
                };
                return (
                  <div key={`h-${f.id}`}
                       className={`frame-rect${on ? ' is-on' : ''}`}
                       onPointerDown={drag(null)}
                       style={{
                         left: `${f.dst.x}%`, top: `${f.dst.y}%`,
                         width: `${f.dst.w}%`, height: `${f.dst.h}%`,
                         borderColor: ink, cursor: 'grab', zIndex: on ? 6 : 5,
                       }}>
                    <span className="frame-rect-tag" style={{ background: ink }}>
                      {i + 1}. {f.label}
                    </span>
                    {['nw', 'ne', 'sw', 'se'].map((h) => (
                      <span key={h} className={`frame-grip grip-${h}`}
                            style={{ borderColor: ink }} onPointerDown={drag(h)} />
                    ))}
                  </div>
                );
              })}
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
            background: 'rgba(0,0,0,0.72)', color: (useReframe || useLayout) ? '#00E5FF' : '#cbd5e1',
            display: 'flex', alignItems: 'center', gap: '5px', pointerEvents: 'none',
          }}>
            {reframeLoading && <Loader2 size={10} className="animate-spin" />}
            {reframeLoading ? 'Melacak wajah…'
              : useLayout ? `${frames.length} bingkai`
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
              ? `X ${Math.round(style?.pos_x ?? 50)}% · Y ${style?.margin_v ?? 300}`
              : dragging === 'scale'
                ? `${Math.round(style?.box_w ?? 84)}% · teks ${style?.size ?? 96}`
                : dragging === 'size'
                  ? `Ukuran teks ${style?.size ?? 96}`
                  : `Lebar kotak ${Math.round(style?.box_w ?? 84)}%`}
          </div>
        )}

        {showCard && boxH > 0 && (
          <>
            {/* Latar gelap hanya untuk mode yang MENAHAN layar. Di mode "klip
                langsung jalan" gambarnya memang harus terus terlihat. */}
            {cardHolds && (
              <div style={{
                position: 'absolute', inset: 0, zIndex: 2,
                background: 'rgba(0,0,0,0.45)', pointerEvents: 'none',
              }} />
            )}
            <div style={{
              position: 'absolute', zIndex: 3,
              left: `${cardBox.left}%`, width: `${cardBox.w}%`,
              top: `${cardBox.top}%`, transform: 'translateY(-50%)',
              textAlign: 'center',
              pointerEvents: onCardChange ? 'auto' : 'none',
              cursor: onCardChange ? 'move' : 'default',
              outline: cardDrag ? '1px dashed rgba(255,255,255,.55)' : 'none',
              outlineOffset: '5px',
            }}
                 onPointerDown={onCardChange ? startCardDrag('move') : undefined}>
              <span style={cardTextStyle}>{cardText}</span>
              {onCardChange && (
                <span
                  onPointerDown={startCardDrag('size')}
                  title="Seret untuk mengubah ukuran judul"
                  style={{
                    position: 'absolute', right: '-7px', bottom: '-7px',
                    width: '15px', height: '15px', borderRadius: '50%',
                    background: 'var(--hl)', border: '2px solid #000',
                    cursor: 'nwse-resize',
                  }} />
              )}
            </div>
          </>
        )}

        {showCard && (
          <div className="tc" style={{
            position: 'absolute', left: '8px', top: '8px', zIndex: 4,
            padding: '3px 7px', borderRadius: '6px', pointerEvents: 'none',
            background: 'rgba(0,0,0,0.72)', color: '#FFE500',
            fontSize: '0.62rem', fontWeight: 700,
          }}>
            {cardBusy
              ? 'Menyiapkan suara judul…'
              : `Kartu judul · ${(cardLeft ?? cardSeconds).toFixed(1)}s`}
          </div>
        )}

        {/* Pembacaan judul. Elemen tersembunyi, bukan `new Audio()`: dengan
            elemen di pohon DOM, React membereskannya sendiri saat pratinjau
            dilepas — dan suara judul tidak bisa tertinggal berbunyi setelah
            penggunanya berpindah klip. */}
        <audio ref={cardAudioRef} preload="auto" style={{ display: 'none' }} />

        {/* Tanda air, digambar seperti libass menggambarnya: pojok kanan
            bawah, kecil, setengah tembus pandang. */}
        {constrained && (style?.watermark || '').trim() && (
          <div
            onPointerDown={onStyleChange ? startDrag('wm-move') : undefined}
            title={onStyleChange ? 'Seret untuk memindahkan tanda air' : undefined}
            style={{
              position: 'absolute', zIndex: 3,
              // Titik yang disimpan adalah TITIK TENGAH teksnya, sama seperti
              // \pos pada berkas ASS — jadi satu pasang angka cukup untuk
              // menaruhnya di mana pun, termasuk di tengah gambar.
              left: `${style?.wm_x ?? 92}%`, top: `${style?.wm_y ?? 95}%`,
              transform: 'translate(-50%, -50%)',
              whiteSpace: 'nowrap',
              color: hexAlpha(style?.wm_color ?? '#FFFFFF', style?.wm_opacity ?? 0.62),
              fontWeight: 650,
              fontFamily: fontStack((style?.wm_font || '').trim() || style?.font),
              fontSize: `${Math.max(6, (style?.wm_size ?? 34) * (boxH / CANVAS_H)
                * ASS_FONT_RATIO)}px`,
              WebkitTextStroke: `${Math.max(0, (style?.wm_outline ?? 2)
                * (boxH / CANVAS_H) * 1.6)}px rgba(0,0,0,0.5)`,
              paintOrder: 'stroke fill',
              pointerEvents: onStyleChange ? 'auto' : 'none',
              cursor: onStyleChange ? (dragging === 'wm-move' ? 'grabbing' : 'grab') : 'default',
              userSelect: 'none', touchAction: 'none',
            }}>{style.watermark.trim()}</div>
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

        {src && (
          <button onClick={toggleFullscreen}
                  title={fullscreen ? 'Keluar dari layar penuh' : 'Lihat layar penuh'}
                  aria-label="Layar penuh"
                  style={{
                    position: 'absolute', right: '8px', bottom: '8px', zIndex: 3,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    width: '30px', height: '30px', borderRadius: '8px', cursor: 'pointer',
                    background: 'rgba(0,0,0,0.66)', border: '1px solid rgba(255,255,255,0.22)',
                    color: '#e2e8f0',
                  }}>
            {fullscreen ? <Minimize2 size={15} /> : <Maximize2 size={15} />}
          </button>
        )}

        {shownLine && boxH > 0 && (
          <CaptionOverlay line={shownLine} activeWordIndex={activeWordIndex}
                          style={style} clipTime={clipTime} boxH={boxH}
                          ghost={!activeLine}
                          draggable={Boolean(onStyleChange)}
                          dragging={dragging}
                          onMoveStart={startDrag('move')}
                          onSizeStart={startDrag('size')}
                          onScaleStart={startDrag('scale')}
                          onWidthLeftStart={startDrag('width-left')}
                          onWidthRightStart={startDrag('width-right')} />
        )}
      </div>
      </div>

      <div className="preview-side">
      <div className="preview-controls">
        {/* Ikon saja, tanpa kata.
            Barisnya duduk di bawah kanvas selebar 160 piksel; dengan kata
            "Putar" saja ia sudah 208 piksel — lebih lebar daripada gambarnya,
            sehingga pelatnya terpaksa melebar dan kembali terlihat sebagai
            kotak yang tidak terisi. Putar dan ulang termasuk segelintir ikon
            yang benar-benar universal. */}
        <button className="btn-secondary preview-btn preview-btn--icon"
                onClick={toggle} disabled={!src}
                aria-label={playing ? 'Jeda' : 'Putar'}
                title={playing ? 'Jeda' : 'Putar klip dari posisi sekarang'}>
          {playing ? <Pause size={13} /> : <Play size={13} />}
        </button>
        <button className="btn-secondary preview-btn preview-btn--icon"
                onClick={restart} disabled={!src}
                title="Ulang dari awal klip" aria-label="Ulang dari awal">
          <RotateCcw size={13} />
        </button>
        {/* Dua jam berjalan di layar ini sekaligus, dan tanpa nama keduanya
            tidak bisa dibedakan: yang ini menghitung dari awal KLIP, yang di
            bilah transport menghitung dari awal VIDEO. Angka "2,5 dtk" dan
            "00:02:01.8" untuk momen yang sama memang membingungkan sampai
            masing-masing menyebut dirinya menghitung apa. */}
        <span style={{ color: 'var(--text-secondary)', fontVariantNumeric: 'tabular-nums',
                       display: 'inline-flex', alignItems: 'baseline', gap: '5px' }}>
          {constrained
            ? `${clockTime(clipTime)} / ${clockTime(totalDuration)}`
              + (segments.length > 1 ? ` · ${segIndex + 1}/${segments.length}` : '')
            : 'jelajah video sumber'}
        </span>
      </div>

      {/* Petunjuk seret, sebagai SATU BARIS.
          Sebelumnya tiga baris penuh di bawah kanvas — 95 piksel terukur, yang
          di ruang berlabuh diambil langsung dari tinggi kanvasnya sendiri.
          Kanvas 9:16 adalah bagian tersempit di layar lanskap; membayar
          seperempat tingginya untuk kalimat yang sudah dibaca sekali dan tidak
          pernah dibaca lagi adalah pertukaran yang salah. Kalimat penuhnya
          pindah ke tooltip, tempat ia tetap ada saat benar-benar dicari. */}
      {/* Petunjuk seret DIHAPUS.
          Dulu di sini ada ikon panah-empat-arah 11 piksel dengan `cursor:
          help`, yang tooltipnya menerangkan subtitle bisa diseret di atas
          gambar. Pemilik aplikasinya sendiri tidak bisa menebak itu apa dan
          mengira ia tombol yang rusak — sebuah petunjuk yang harus ditebak
          lebih dulu bukan petunjuk, ia bagian dari teka-tekinya. Yang
          diterangkannya juga terungkap sendiri: subtitle di pratinjau memang
          langsung bisa ditarik, dan orang menemukannya dengan menariknya. */}
      </div>
    </div>
  );
}

/**
 * Subtitle di pratinjau, mencerminkan gaya yang akan dibakar ke video.
 *
 * Diekspor supaya bisa diuji sendiri: di dalam ClipPreview ia baru muncul
 * setelah ResizeObserver mengisi tinggi kotak, jadi ia tidak pernah ikut
 * ter-render pada uji asap — padahal justru bagian ini yang paling sering
 * berubah.
 *
 * Ukuran, jarak dari tepi, dan tebal garis luar semuanya dihitung dari satuan
 * kanvas 1920 yang sama dengan file ASS, jadi yang terlihat di sini benar-benar
 * proporsi hasil akhirnya — bukan perkiraan berbasis lebar layar.
 */
export function CaptionOverlay({
  line, activeWordIndex, style, clipTime, boxH, ghost,
  draggable, dragging, onMoveStart, onSizeStart, onScaleStart,
  onWidthLeftStart, onWidthRightStart,
}) {
  const [hover, setHover] = useState(false);
  const words = line.words?.length ? line.words : [{ w: line.text }];
  const anim = style?.animation ?? 'karaoke_pop';
  const uppercase = style?.uppercase !== false;
  const scale = boxH / CANVAS_H;

  // Warna per penutur. Penutur pertama memakai warna teks utama, sehingga video
  // satu narasumber tampil persis seperti sebelum fitur ini ada.
  // Diindeks langsung: palette[0] milik orang pertama. Versi sebelumnya
  // melewati indeks 0 dan memaksa orang pertama memakai `primary`, sehingga
  // warnanya tidak bisa disetel sendiri.
  // Palet ditambal dari daftar bawaan, bukan dibiarkan jatuh ke warna dasar.
  // Gaya tersimpan bisa berasal dari versi lama yang cuma punya tiga warna,
  // dan tanpa tambalan orang keempat ke atas jadi putih di sini sementara
  // hasil render memberinya warna — atau sebaliknya. Satu aturan, dua tempat.
  const palette = padPalette(style?.speaker_colors);
  const sp = line.speaker || 0;
  // Mode "satu warna untuk seluruh klip" dihormati DI SINI juga, bukan hanya
  // saat render. Kalau tidak, mematikannya mengubah video tapi tidak mengubah
  // pratinjau — dan pratinjau yang tidak sama dengan hasilnya adalah cacat
  // yang lebih buruk daripada fitur yang tidak ada.
  const speakerColor = style?.per_speaker_colors === false
    ? (style?.primary ?? '#FFFFFF')
    : (palette[sp] ?? style?.primary ?? '#FFFFFF');

  const age = clipTime - line.start;
  const entry = ghost || anim === 'none' ? {} : lineEntryStyle(anim, age);

  // Kalibrasi ke libass, dan ini bukan angka hiasan.
  //
  // `size` adalah Fontsize di berkas ASS, dan libass TIDAK memperlakukannya
  // seperti font-size CSS: ia memuatkan ascender+descender font ke dalam angka
  // itu, sedangkan CSS memakainya sebagai tinggi em. Diukur dengan merender
  // "GIMANA" ke bingkai 1080x1920 polos pada empat ukuran, tinggi kapitalnya
  // 25, 37, 50, dan 75 piksel untuk Fontsize 48, 72, 96, dan 144 — lurus,
  // dengan kemiringan 0,521. Pratinjau memakai 0,756 dari angka yang sama.
  //
  // Akibatnya terlihat persis seperti yang dikeluhkan: subtitle di editor 1,45x
  // lebih besar daripada di hasil render, jadi barisnya pun terbungkus di
  // tempat yang berbeda — "GIMANA YA, BANG?" dua baris di layar, satu baris di
  // video. Pratinjau yang berbohong tentang ukuran adalah pratinjau yang
  // membuat setiap penyetelan ukuran dan posisi harus diulang setelah render.
  //
  // Yang disamakan adalah pratinjau ke libass, bukan sebaliknya: hasil render
  // adalah produknya, dan mengubah sisi itu akan mengubah semua video yang
  // sudah pernah dibuat.
  const fontPx = Math.max(9, (style?.size ?? 96) * scale * ASS_FONT_RATIO);
  const marginPx = (style?.margin_v ?? 300) * scale;
  // Garis luar libass diukur dari tepi glyph ke luar; -webkit-text-stroke
  // digambar di tengah garis, jadi setengahnya jatuh ke dalam huruf. Faktor 1.6
  // mengembalikan tebal yang terlihat setara.
  const strokePx = Math.max(0.8, (style?.outline_px ?? 7) * scale * 1.6);
  const anchorTop = style?.position === 'top';
  const anchorMiddle = style?.position === 'middle';

  const place = anchorMiddle
    ? { top: '50%' } : anchorTop ? { top: `${marginPx}px` } : { bottom: `${marginPx}px` };

  // Penempatan mendatar memakai satuan yang sama dengan MarginL/MarginR pada
  // file ASS: titik tengah kotak dan lebarnya, keduanya dalam persen lebar
  // kanvas. Jadi apa yang terlihat di sini benar-benar nilai yang dikirim.
  const boxWidth = style?.box_w ?? 84;
  const posX = style?.pos_x ?? 50;
  // Posisi tengah dan animasi masuk sama-sama memakai `transform`, jadi
  // keduanya digabung — bukan saling menimpa, yang membuat baris melompat ke
  // bawah tiap kali animasi menyala.
  const transform = [anchorMiddle ? 'translateY(-50%)' : '', entry.transform || '']
    .filter(Boolean).join(' ');

  return (
    <div
      onPointerDown={draggable ? onMoveStart : undefined}
      onPointerEnter={() => setHover(true)}
      onPointerLeave={() => setHover(false)}
      style={{
        position: 'absolute',
        left: `${posX - boxWidth / 2}%`, width: `${boxWidth}%`,
        ...place,
        textAlign: 'center',
        pointerEvents: draggable ? 'auto' : 'none',
        cursor: draggable ? (dragging === 'move' ? 'grabbing' : 'grab') : 'default',
        fontFamily: fontStack(style?.font),
        fontWeight: 800, lineHeight: 1.16, letterSpacing: '0.005em',
        // libass memakai WrapStyle 0, yang MENYEIMBANGKAN panjang baris alih-alih
        // sekadar memotong saat penuh. Tanpa ini, baris yang sama pecah di kata
        // yang berbeda: "YANG GUA EE TEMUKAN / ITU" di layar, "YANG GUA EE /
        // TEMUKAN ITU" di video. Ukurannya sudah sama — yang tersisa tinggal
        // aturan pemotongannya.
        textWrap: 'balance',
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
        // Kotak batas ditampilkan saat disentuh. Tanpa melihat kotaknya, tidak
        // ada cara tahu bahwa lebarnya bisa diubah — dan lebar itulah yang
        // menentukan di kata keberapa barisnya dibungkus.
        outline: dragging || hover ? '1px dashed rgba(0,229,255,0.8)' : 'none',
        outlineOffset: '5px',
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
        <>
          {/* Gagang tepi: mengubah LEBAR kotak, tepi seberangnya diam.
              Gagang sudut: mengubah UKURAN HURUF. Dua hal berbeda yang
              sebelumnya ditumpuk pada satu bulatan, sehingga menyempitkan
              subtitle sama sekali tidak bisa dilakukan. */}
          <Handle side="left" active={dragging === 'width-left'} visible={hover || !!dragging}
                  onPointerDown={onWidthLeftStart} />
          <Handle side="right" active={dragging === 'width-right'} visible={hover || !!dragging}
                  onPointerDown={onWidthRightStart} />
          {/* Pojok kanan-bawah: menskalakan kotak DAN hurufnya bersama-sama,
              dengan pojok kiri-atas ditahan diam. Gagang tepi mengubah satu
              dimensi; gagang sudut mengubah keseluruhan proporsinya. */}
          <span
            onPointerDown={onScaleStart ?? onSizeStart}
            title="Tarik menyerong untuk memperbesar/memperkecil kotak beserta hurufnya"
            style={{
              position: 'absolute', right: '-15px', bottom: '-15px',
              width: '19px', height: '19px', borderRadius: '50%',
              background: 'var(--accent-cyan, #00E5FF)', border: '2px solid #06121a',
              cursor: 'nwse-resize', boxShadow: '0 1px 5px rgba(0,0,0,0.6)',
              WebkitTextStroke: '0',
              opacity: dragging === 'scale' ? 1 : (hover || dragging ? 0.9 : 0.55),
              transition: 'opacity 120ms',
            }}
          />
        </>
      )}
    </div>
  );
}

/** Gagang tepi kiri/kanan untuk melebarkan dan menyempitkan kotak teks. */
function Handle({ side, active, visible, onPointerDown }) {
  return (
    <span
      onPointerDown={onPointerDown}
      title={`Tarik untuk ${side === 'left' ? 'melebarkan ke kiri' : 'melebarkan ke kanan'}`}
      style={{
        position: 'absolute', top: '50%', transform: 'translateY(-50%)',
        [side]: '-11px',
        width: '9px', height: '34px', borderRadius: '5px',
        background: active ? 'var(--accent-cyan, #00E5FF)' : 'rgba(0,229,255,0.85)',
        border: '2px solid #06121a', cursor: 'ew-resize',
        boxShadow: '0 1px 5px rgba(0,0,0,0.6)', WebkitTextStroke: '0',
        opacity: active ? 1 : (visible ? 0.9 : 0),
        transition: 'opacity 120ms',
      }}
    />
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
