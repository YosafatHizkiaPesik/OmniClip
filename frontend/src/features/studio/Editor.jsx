import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowLeft, Scissors, Type, Palette, Download, Loader2, CheckCircle2,
  AlertTriangle, Crop, Plus, Trash2, Play, Save, Tag,
} from 'lucide-react';
import { apiGet, apiPost, downloadToDisk } from '../../lib/api';
import { loadFonts } from '../../lib/fonts';
import { formatTime } from '../../utils/timeFormat';
import { useClipEditor } from './useClipEditor';
import ClipPreview from './ClipPreview';
import StaveSystem, { rehearsalLetter } from './StaveSystem';
import { TrimPanel, SubtitlePanel, StylePanel } from './EditorPanels';
import FrameStage from './FrameStage';
import ClipTimeline from './ClipTimeline';
import FramePanel from './FramePanel';
import TitlePanel from './TitlePanel';
import {
  loadFraming, saveFraming, serializeLayout, clipTimeFor, sourceTimeFor,
  personKeyAt, withPersonKey,
} from './frames';

const DEFAULT_STYLE = {
  size: 96, primary: '#FFFFFF', highlight: '#FFE500',
  // Diindeks langsung: [0] orang pertama. Putih di depan supaya video satu
  // narasumber tampil persis seperti sebelum warna per orang ada.
  speaker_colors: ['#FFFFFF', '#7CFFB2', '#FFB3C7', '#B39DFF',
                   '#FFD166', '#5BC8FF', '#FF9F1C', '#B8FF3A'],
  position: 'bottom', margin_v: 300, outline_px: 7,
  // Penempatan mendatar dalam persen lebar kanvas: titik tengah kotak teks dan
  // lebarnya. Keduanya diubah dengan menyeret subtitle di pratinjau.
  pos_x: 50, box_w: 84,
  uppercase: true, animation: 'karaoke_pop', font: 'Montserrat',
  // Tanda air. Ikut gaya, bukan ikut klip: ini nama kanal, dan menuliskannya
  // ulang di tiap klip adalah pekerjaan yang tidak ada gunanya.
  watermark: '',
};

const STYLE_KEY = 'omniclip_caption_style';

/**
 * Gaya teks bertahan antar sesi.
 *
 * Menyetel font, warna, dan ukuran adalah pekerjaan sekali untuk sebuah kanal,
 * bukan sekali per klip. Tanpa ini, tiap kali editor dibuka semuanya kembali ke
 * bawaan dan seluruh penyetelan harus diulang.
 */
function loadStoredStyle() {
  try {
    const raw = JSON.parse(localStorage.getItem(STYLE_KEY) || 'null');
    return raw && typeof raw === 'object' ? { ...DEFAULT_STYLE, ...raw } : DEFAULT_STYLE;
  } catch {
    return DEFAULT_STYLE;
  }
}

const TABS = [
  { id: 'trim', label: 'Batas', Icon: Scissors },
  { id: 'subtitle', label: 'Subtitle', Icon: Type },
  { id: 'style', label: 'Gaya', Icon: Palette },
  { id: 'frame', label: 'Bingkai', Icon: Crop },
  { id: 'title', label: 'Judul', Icon: Tag },
];

/**
 * Editor klip: video sumber panjang di timeline, hasil klip di kiri.
 *
 * Bentuknya sengaja mengikuti editor video pada umumnya — pratinjau di tengah,
 * timeline membentang di bawah, daftar hasil di samping — supaya batas klip
 * bisa digeser sambil melihat gelombang suara dan posisi klip lain sekaligus.
 */
export default function Editor({ project, onBack }) {
  const videoId = project?.video_id;
  const editor = useClipEditor();
  const videoRef = useRef(null);

  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [peaks, setPeaks] = useState([]);
  // Dibuka pada baris lirik: itulah isi bidang pandang pertama yang
  // dijanjikan, dan itu pula pekerjaan yang paling sering dilakukan di sini.
  const [tab, setTab] = useState('subtitle');
  const [style, setStyle] = useState(loadStoredStyle);
  const patchStyle = useCallback((patch) => setStyle((prev) => ({ ...prev, ...patch })), []);
  const [aspectRatio, setAspectRatio] = useState('9:16');
  // Cara membingkai dan susunannya dipulihkan bersama-sama untuk video ini.
  // Susunan hidup di sini, bukan di dalam pratinjau, karena tiga tempat
  // membacanya sekaligus: meja bingkai, kanvas hasil, dan muatan render.
  const [framing] = useState(() => loadFraming(videoId));
  const [frameMode, setFrameMode] = useState(framing.mode);
  const [layout, setLayout] = useState(framing.layout);
  const [selectedFrameId, setSelectedFrameId] = useState(null);
  const [selectedLine, setSelectedLine] = useState(null);
  useEffect(() => { saveFraming(videoId, frameMode, layout); },
    [videoId, frameMode, layout]);
  const [constrained, setConstrained] = useState(true);
  // Judul mati secara bawaan: hasilnya lebih bersih, dan hook otomatis sering
  // kalah bagus dari klipnya sendiri.
  const [showHook, setShowHook] = useState(false);
  const [exporting, setExporting] = useState(false);
  // Unggah ke Drive tepat setelah klipnya jadi. Mati secara bawaan: mengirim
  // berkas keluar dari komputer harus jadi pilihan yang diambil, bukan yang
  // kebetulan terjadi karena tombol render ditekan.
  const [uploadAfter, setUploadAfter] = useState(false);
  const [googleReady, setGoogleReady] = useState(null);
  const [exportLog, setExportLog] = useState([]);
  // Rencana crop untuk pratinjau — sama persis dengan yang dipakai render.
  const [reframe, setReframe] = useState(null);
  const [reframeLoading, setReframeLoading] = useState(false);
  // Penanda masuk/keluar untuk memotong klip sendiri.
  const [mark, setMark] = useState({ in: null, out: null });
  const [redetecting, setRedetecting] = useState(false);
  const [retitling, setRetitling] = useState(false);
  const [saving, setSaving] = useState(null);
  const [sourceTime, setSourceTime] = useState(0);

  const { clips, selected, checked } = editor;

  /**
   * Tanda linimasa untuk mode ikut-wajah: [{t, person}] dalam waktu KLIP.
   *
   * Disimpan PADA KLIPNYA, bukan di state layar ini. Dua akibatnya keduanya
   * penting: tandanya ikut tersimpan bersama susunan, jadi tidak hilang saat
   * halaman ditutup; dan tiap klip membawa tandanya sendiri, jadi berpindah
   * huruf tidak lagi membuang pekerjaan — yang perlu, karena nomor orang
   * ditentukan per klip dan "orang 2" di klip lain belum tentu orang yang sama.
   */
  const personKeys = useMemo(() => selected?.person_keys ?? [], [selected]);
  const setPersonKeys = useCallback((next) => {
    if (!selected) return;
    const value = typeof next === 'function' ? next(selected.person_keys ?? []) : next;
    editor.updateClip(selected.clip_id, { person_keys: value });
  }, [selected, editor]);

  /**
   * Menyunting kartu judul dari mana pun — panel setelan maupun seretan
   * langsung di atas pratinjau.
   *
   * Satu jalan masuk untuk keduanya. Dua jalan berbeda akan berarti dua
   * gabungan yang sedikit berbeda, dan posisinya akan melompat tiap kali
   * pengguna berpindah antara menyeret dan mengetik angka.
   */
  const patchCard = useCallback((patch) => {
    if (!selected) return;
    editor.updateClip(selected.clip_id, {
      title_card: { ...selected.title_card, ...patch },
    });
  }, [selected, editor]);

  useEffect(() => { loadFonts(); }, []);

  useEffect(() => {
    let cancelled = false;
    apiGet('/uploads/google/status')
      .then((r) => { if (!cancelled) setGoogleReady(!!r.connected); })
      .catch(() => { if (!cancelled) setGoogleReady(false); });
    return () => { cancelled = true; };
  }, []);

  // Penyimpanan ditunda: menyeret subtitle memanggil patchStyle tiap frame, dan
  // menulis ke localStorage 60 kali per detik akan tersendat di perangkat lambat.
  useEffect(() => {
    const t = setTimeout(() => {
      try {
        localStorage.setItem(STYLE_KEY, JSON.stringify(style));
      } catch { /* mode privat: gaya tetap berlaku, hanya tidak diingat */ }
    }, 400);
    return () => clearTimeout(t);
  }, [style]);

  // Muat analisis tersimpan. Halaman ini hanya dibuka untuk project yang sudah
  // selesai, jadi tidak ada pekerjaan berat yang dimulai di sini.
  useEffect(() => {
    let cancelled = false;
    if (!videoId) return undefined;
    (async () => {
      try {
        const res = await apiGet(`/projects/${videoId}`);
        if (cancelled) return;
        setData(res);
        editor.load(videoId, res.clips || []);
      } catch (err) {
        if (!cancelled) setError(err);
      }
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId]);

  // Gelombang suara dihitung terpisah: pada video panjang butuh belasan detik
  // pada pemanggilan pertama, dan editor tidak perlu menunggunya untuk tampil.
  useEffect(() => {
    let cancelled = false;
    if (!videoId) return undefined;
    apiGet(`/videos/${videoId}/waveform?bins=1200`)
      .then((res) => { if (!cancelled) setPeaks(res.peaks || []); })
      .catch(() => { /* timeline tetap berguna tanpa gelombang */ });
    return () => { cancelled = true; };
  }, [videoId]);

  const duration = data?.duration || project?.duration || 0;

  // Ambil rencana reframe setiap kali klip, rasio, atau mode bingkai berubah.
  // Dikunci pada susunan segmen, jadi menggeser batas ikut memperbarui bingkai.
  const segmentKey = selected
    ? selected.segments.map((s) => `${s.start.toFixed(2)}-${s.end.toFixed(2)}`).join(',')
    : '';
  const followKey = (layout?.frames ?? []).map((f) => (f.follow ? '1' : '0')).join('');
  // Apa yang menentukan WAJAH-WAJAHNYA — beda dari apa yang menentukan ke mana
  // bingkai diarahkan. Hanya perubahan yang pertama yang boleh mengosongkan
  // linimasa bingkai.
  const sceneKey = `${videoId}|${segmentKey}|${frameMode}|${aspectRatio}|${followKey}`;
  const sceneKeyRef = useRef(null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { setSelectedLine(null); }, [segmentKey]);
  useEffect(() => {
    let cancelled = false;
    // Jejak wajah juga dibutuhkan oleh susunan sendiri, begitu ada satu bingkai
    // yang diminta mengikuti orang. Dulu ia hanya diambil di mode ikut-wajah,
    // jadi kotak pengikut di susunan sendiri diam saja di pratinjau meski
    // hasil rendernya bergerak.
    const wantsTrack = frameMode === 'smart'
      || (frameMode === 'layout' && (layout?.frames ?? []).some((f) => f.follow));
    if (!videoId || !selected || !wantsTrack || aspectRatio === '16:9') {
      setReframe(null);
      return undefined;
    }
    // Rencana klip SEBELUMNYA dibuang hanya bila yang berubah adalah KLIPNYA.
    //
    // Kalau yang berubah cuma tanda arah bingkai, wajah-wajahnya tetap wajah
    // yang sama — mengosongkan lajur di situ membuat linimasa bingkai lenyap
    // tepat saat pengguna sedang menyuntingnya, dan tiap tanda terasa seperti
    // memulai analisis baru. Tapi saat berpindah klip, menahannya berarti
    // menampilkan orang-orang klip yang barusan ditinggalkan — dan lajur itu
    // bisa diklik, jadi tanda bisa dipasang berdasarkan gambar yang salah.
    if (sceneKeyRef.current !== sceneKey) {
      sceneKeyRef.current = sceneKey;
      setReframe(null);
    }
    setReframeLoading(true);
    apiPost('/clip-reframe', {
      video_id: videoId,
      segments: selected.segments,
      aspect_ratio: aspectRatio,
      person_keys: personKeys,
      // Label penutur ikut dikirim: dengan itu server bisa mencocokkan wajah
      // dengan suara, dan crop mengikuti orang yang sedang bicara.
      subtitles: (selected.subtitles ?? []).map((l) => ({
        start: l.start, end: l.end, speaker: l.speaker,
      })),
    })
      .then((res) => { if (!cancelled) setReframe(res); })
      .catch(() => { if (!cancelled) setReframe(null); })
      .finally(() => { if (!cancelled) setReframeLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId, segmentKey, frameMode, aspectRatio, followKey, personKeys]);

  // Timecode dibaca dari elemen video pada ~10 Hz. `timeupdate` hanya menyala
  // sekitar 4 Hz dan angkanya terlihat tersendat; membacanya tiap frame dan
  // menaruhnya di state React akan me-render ulang pohon 60 kali per detik.
  useEffect(() => {
    let raf;
    let last = -1;
    const tick = () => {
      const v = videoRef.current;
      if (v && Math.abs(v.currentTime - last) > 0.09) {
        last = v.currentTime;
        setSourceTime(v.currentTime);
      }
      // Begitu videonya berjalan sendiri, sasaran lompatan tombol panah tidak
      // berlaku lagi — tekanan berikutnya harus menumpuk pada posisi nyata.
      if (v && !v.paused) seekTargetRef.current = null;
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  /**
   * Apakah sebuah detik masih berada DI DALAM klip yang sedang dipilih.
   *
   * Ini yang menentukan pratinjau menampilkan klipnya atau video sumbernya, dan
   * karena itu juga menentukan subtitle dan kotak ikut-wajah muncul atau tidak.
   */
  const insideClip = useCallback((t) => (
    (selected?.segments ?? []).some((sg) => t >= sg.start - 0.05 && t <= sg.end + 0.05)
  ), [selected]);

  // Sasaran lompatan terakhir. Menyetel `currentTime` bersifat asinkron: menekan
  // panah tiga kali cepat membaca `currentTime` yang MASIH LAMA pada tekanan
  // kedua dan ketiga, sehingga tiga tekanan hanya memundurkan satu langkah.
  // Itulah "mundurnya cuma sedikit". Dengan sasaran disimpan, tiap tekanan
  // menumpuk pada tekanan sebelumnya, bukan pada posisi pemutar yang tertinggal.
  const seekTargetRef = useRef(null);

  const seekSource = useCallback((time) => {
    const v = videoRef.current;
    if (!v) return;
    seekTargetRef.current = null;
    // Menjelajah keluar klip melepaskan pratinjau; masih di dalam klip tidak.
    setConstrained(insideClip(time));
    v.currentTime = time;
  }, [insideClip]);

  const selectClip = useCallback((clipId) => {
    editor.setSelectedId(clipId);
    seekTargetRef.current = null;
    setConstrained(true);
    const clip = clips.find((c) => c.clip_id === clipId);
    const v = videoRef.current;
    if (clip && v) v.currentTime = clip.segments[0].start;
  }, [clips, editor]);

  /** Detik keberapa di dalam klip yang sedang dipilih, dari playhead. */
  const clipNow = useCallback(() => (
    selected ? clipTimeFor(selected.segments, videoRef.current?.currentTime ?? 0) : 0
  ), [selected]);

  /** Melompat ke detik tertentu DI DALAM klip. */
  const seekClip = useCallback((t) => {
    const v = videoRef.current;
    if (!v || !selected) return;
    seekTargetRef.current = null;
    // Melompat ke dalam klip, jadi pratinjaunya harus kembali menampilkan klip.
    setConstrained(true);
    v.currentTime = sourceTimeFor(selected.segments, t);
  }, [selected]);

  /**
   * Menunjuk siapa yang harus diikuti bingkai, mulai dari playhead.
   *
   * Inilah jawaban untuk klip yang mengambil orang yang sedang diam: pencocokan
   * otomatis membaca gerak mulut, dan mulut yang tertutup mikrofon hampir tidak
   * bergerak di gambar. Yang dibutuhkan bukan tebakan yang lebih pintar, tapi
   * cara membetulkannya — pada detik yang tepat, bukan untuk seluruh klip.
   */
  const aimPerson = useCallback((person) => {
    setPersonKeys((keys) => withPersonKey(keys, clipNow(), person));
  }, [clipNow]);

  // Siapa yang sedang dituju bingkai. Dibaca dari `sourceTime`, yang sudah
  // berdenyut ~10 Hz — cukup untuk menyorot tombolnya tanpa loop sendiri.
  const aimedPerson = useMemo(() => (
    selected ? personKeyAt(personKeys, clipTimeFor(selected.segments, sourceTime)) : null
  ), [personKeys, selected, sourceTime]);

  /** Menambahkan potongan dari posisi playhead ke klip yang sedang dipilih. */
  const addSegmentAtPlayhead = () => {
    const v = videoRef.current;
    if (!v || !selected) return;
    const start = Math.max(0, v.currentTime);
    editor.addSegment(selected.clip_id, start, Math.min(duration || start + 20, start + 20));
    setConstrained(true);
  };

  /**
   * Melompat relatif terhadap posisi sekarang, dipakai panah kiri/kanan.
   *
   * Dua hal yang dulu salah di sini, dan keduanya terasa setiap kali dipakai.
   *
   * Pertama, ia SELALU melepaskan pratinjau dari klipnya. Maju satu detik di
   * tengah klip lalu kehilangan seluruh subtitle dan kotak ikut-wajahnya —
   * berganti jadi video sumber berbilah kabur — padahal playhead-nya tidak
   * pernah keluar dari klip itu. Sekarang yang menentukan adalah apakah
   * sasarannya benar-benar di luar klip.
   *
   * Kedua, ia menumpuk pada `v.currentTime`, yang belum berubah saat tombol
   * ditekan lagi sebelum pencarian sebelumnya selesai.
   */
  const nudgePlayhead = useCallback((delta) => {
    const v = videoRef.current;
    if (!v) return;
    const dur = duration || v.duration || 0;
    const base = seekTargetRef.current ?? v.currentTime;
    const t = Math.max(0, Math.min(dur, base + delta));
    seekTargetRef.current = t;
    setConstrained(insideClip(t));
    v.currentTime = t;
  }, [duration, insideClip]);

  const togglePlay = useCallback(() => {
    const v = videoRef.current;
    if (!v) return;
    if (v.paused) v.play().catch(() => { /* butuh interaksi pengguna */ });
    else v.pause();
  }, []);

  /**
   * Pintasan papan tik ala editor video.
   *
   * Menandai batas klip berarti bolak-balik antara memutar, mundur sedikit, dan
   * menandai — puluhan kali per klip. Dengan tetikus saja setiap putaran itu
   * berarti membidik tombol kecil, dan pekerjaan yang seharusnya mengalir jadi
   * tersendat.
   *
   * Dipasang di window, bukan pada satu elemen: playhead tidak punya fokus, dan
   * memaksa pengguna mengklik dulu sebelum spasi bekerja adalah persis
   * kejanggalan yang ingin dihilangkan. Yang perlu dijaga hanyalah tidak
   * membajak tombol saat pengguna sedang mengetik.
   */
  useEffect(() => {
    const onKey = (e) => {
      const el = e.target;
      const typing = el instanceof HTMLElement
        && (el.isContentEditable
          || ['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName));
      if (typing || e.metaKey || e.ctrlKey || e.altKey) return;

      const step = e.shiftKey ? 10 : 1;
      switch (e.key) {
        case ' ':
          e.preventDefault();
          togglePlay();
          break;
        case 'ArrowRight':
          e.preventDefault();
          nudgePlayhead(step);
          break;
        case 'ArrowLeft':
          e.preventDefault();
          nudgePlayhead(-step);
          break;
        case 'j': case 'J':
          e.preventDefault();
          nudgePlayhead(-5);
          break;
        case 'k': case 'K':
          e.preventDefault();
          togglePlay();
          break;
        case 'l': case 'L':
          e.preventDefault();
          nudgePlayhead(5);
          break;
        case 'i': case 'I':
          e.preventDefault();
          setMark((m) => ({ ...m, in: videoRef.current?.currentTime ?? 0 }));
          break;
        case 'o': case 'O':
          e.preventDefault();
          setMark((m) => ({ ...m, out: videoRef.current?.currentTime ?? 0 }));
          break;
        case 'Home':
          e.preventDefault();
          seekSource(selected?.segments[0].start ?? 0);
          break;
        default:
          break;
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [togglePlay, nudgePlayhead, seekSource, selected]);

  /** Membuat klip dari penanda masuk/keluar, atau dari posisi playhead. */
  const createFromMarks = useCallback(async () => {
    const v = videoRef.current;
    const here = v?.currentTime ?? 0;
    const start = mark.in ?? here;
    const end = mark.out ?? Math.min(duration || start + 30, start + 30);
    if (end - start < 1.5) return;
    await editor.createClip(start, end);
    setMark({ in: null, out: null });
    setConstrained(true);
  }, [mark, duration, editor]);

  /** Menandai ulang penutur di seluruh klip, dengan jumlah dari pengguna. */
  const redetectSpeakers = useCallback(async (speakers) => {
    if (!videoId) return;
    setRedetecting(true);
    try {
      const { job_id: jobId } = await apiPost('/clip-speakers', {
        video_id: videoId, speakers,
      });
      const job = await waitForJob(jobId, { interval: 2000 });
      if (job.status === 'done') {
        const fresh = await apiGet(`/projects/${videoId}`);
        setData(fresh);
        editor.load(videoId, fresh.clips || []);
      } else {
        setExportLog([{ name: 'Narasumber', status: 'failed',
                        message: job.error || 'Deteksi ulang gagal.' }]);
      }
    } catch (err) {
      setExportLog([{ name: 'Narasumber', status: 'failed', message: err.message }]);
    } finally {
      setRedetecting(false);
    }
  }, [videoId, editor]);

  /** Meminta Gemini menulis ulang judul & tagar klip yang masih heuristik. */
  const handleRetitle = useCallback(async () => {
    if (!videoId) return;
    setRetitling(true);
    try {
      const { job_id: jobId } = await apiPost('/clip-titles', { video_id: videoId });
      const job = await waitForJob(jobId, { interval: 2000 });
      if (job.status === 'done') {
        const fresh = await apiGet(`/projects/${videoId}`);
        setData(fresh);
        editor.load(videoId, fresh.clips || []);
      } else {
        setExportLog([{ name: 'Judul', status: 'failed',
                        message: job.error || 'Gagal menulis ulang judul.' }]);
      }
    } catch (err) {
      setExportLog([{ name: 'Judul', status: 'failed', message: err.message }]);
    } finally {
      setRetitling(false);
    }
  }, [videoId, editor]);

  const handleSaveClips = useCallback(async () => {
    setSaving('running');
    try {
      await editor.saveClips();
      setSaving('done');
      setTimeout(() => setSaving(null), 2500);
    } catch {
      setSaving('failed');
    }
  }, [editor]);

  const renderPayload = useCallback((clip) => ({
    source_path: videoId,
    clip_index: clip.index,
    segments: clip.segments,
    subtitles: clip.subtitles,
    hook_text: clip.hook_text,
    show_hook: showHook,
    // Judul klip, bukan judul video sumbernya: tanpa ini kelima belas klip
    // dari satu video keluar dengan nama berkas yang sama persis kecuali
    // nomornya.
    title: (clip.title || '').trim(),
    hashtags: clip.hashtags ?? [],
    aspect_ratio: aspectRatio,
    frame_mode: frameMode,
    frame_layout: frameMode === 'layout' ? serializeLayout(layout) : null,
    // Tanda milik KLIP INI, bukan klip yang sedang dibuka: ekspor berjalan
    // atas semua huruf yang dicentang, dan memakai tanda klip terpilih untuk
    // semuanya akan mengarahkan bingkai empat belas klip lain ke orang yang
    // tidak pernah ditunjuk untuk mereka.
    person_keys: frameMode === 'smart' ? (clip.person_keys ?? []) : [],
    // Kartu judul dikirim hanya bila pengguna menyalakannya untuk klip INI.
    // Teks kosong berarti memakai judul klipnya sendiri — dua judul yang sama
    // adalah kasus paling sering, dan mengetiknya dua kali tidak masuk akal.
    watermark: (style.watermark || '').trim(),
    title_card: clip.title_card?.enabled
      ? {
        ...clip.title_card,
        text: (clip.title_card.text || '').trim() || (clip.title || '').trim(),
      }
      : null,
    caption_style: style,
  }), [videoId, aspectRatio, frameMode, layout, style, showHook]);

  const handleExportSelected = async () => {
    const targets = clips.filter((c) => checked.has(c.clip_id));
    if (!targets.length) return;
    setExporting(true);
    setExportLog([]);
    for (const clip of targets) {
      const name = `Klip #${clip.index}`;
      setExportLog((l) => [...l, { name, status: 'running', message: 'Merender…' }]);
      try {
        // eslint-disable-next-line no-await-in-loop
        const { job_id: jobId } = await apiPost('/render-clip', renderPayload(clip));
        // eslint-disable-next-line no-await-in-loop
        const job = await waitForJob(jobId);
        if (job.status === 'done') {
          // eslint-disable-next-line no-await-in-loop
          await downloadToDisk('edited_clips', job.result.clip_name);
          const mode = job.result.frame_mode === 'smart' ? 'ikut wajah' : job.result.frame_mode;
          setExportLog((l) => l.map((e) => (e.name === name
            ? { ...e, status: 'done', message: `Tersimpan · bingkai ${mode}` } : e)));

          // Unggahan diantrekan, bukan ditunggu. Lane unggah lebarnya satu,
          // jadi klip naik satu per satu berapa pun yang dirender sekaligus —
          // dan render berikutnya tidak perlu menunggu jaringan.
          if (uploadAfter) {
            try {
              // eslint-disable-next-line no-await-in-loop
              await apiPost('/uploads', {
                clip_name: job.result.clip_name,
                target: 'drive',
                title: (clip.title || name).trim(),
                description: (clip.hashtags ?? []).join(' '),
                tags: clip.hashtags ?? [],
                privacy: 'private',
              });
              setExportLog((l) => l.map((e) => (e.name === name
                ? { ...e, message: `${e.message} · antre ke Drive` } : e)));
            } catch (err) {
              setExportLog((l) => l.map((e) => (e.name === name
                ? { ...e, message: `${e.message} · gagal antre unggah: ${err.message}` } : e)));
            }
          }
        } else {
          setExportLog((l) => l.map((e) => (e.name === name
            ? { ...e, status: 'failed', message: job.error || 'Gagal' } : e)));
        }
      } catch (err) {
        setExportLog((l) => l.map((e) => (e.name === name
          ? { ...e, status: 'failed', message: err.message } : e)));
      }
    }
    setExporting(false);
  };
  if (error) {
    return (
      <Centered>
        <AlertTriangle size={30} style={{ color: 'var(--danger)', marginBottom: '10px' }} />
        <h3 className="work-title" style={{ fontSize: '1.1rem', marginBottom: '7px' }}>
          Partitur ini tidak bisa dibuka
        </h3>
        <p style={{ fontSize: '.85rem', color: 'var(--ink-2)' }}>{error.message}</p>
        <button className="btn-secondary" onClick={onBack} style={{ marginTop: '16px' }}>
          <ArrowLeft size={14} /> Kembali
        </button>
      </Centered>
    );
  }

  if (!data) {
    return (
      <Centered>
        <Loader2 size={24} className="animate-spin" style={{ color: 'var(--reh)' }} />
        <p style={{ marginTop: '10px', fontSize: '.85rem', color: 'var(--ink-2)' }}>
          Membuka partitur…
        </p>
      </Centered>
    );
  }

  const letter = selected ? rehearsalLetter(clips.indexOf(selected)) : '—';

  return (
    <div className="page">
      {/* ── Blok judul karya ────────────────────────────────────────────── */}
      <div className="work-block">
        <button className="btn-secondary" onClick={onBack}
                style={{ padding: '8px 11px', marginTop: '3px' }} aria-label="Kembali">
          <ArrowLeft size={15} />
        </button>
        <div style={{ minWidth: 0, flex: '1 1 320px' }}>
          <h1 className="work-title">{data.title}</h1>
          <div className="sub">
            {clips.length} huruf latihan · {formatTime(duration)} ·{' '}
            {data.speaker_count > 1
              ? `${data.speaker_confident ? '' : '± '}${data.speaker_count} narasumber`
              : 'satu narasumber'} ·{' '}
            {data.transcript_source === 'whisper' ? 'transkrip Whisper lokal'
              : data.transcript_source === 'youtube_manual' ? 'transkrip resmi kanal'
                : 'transkrip otomatis YouTube'}
          </div>
        </div>
        <div className="actions">
          <label style={{
            display: 'flex', alignItems: 'center', gap: '7px', fontSize: '.82rem',
            cursor: 'pointer', color: 'var(--ink-2)',
          }}>
            <input type="checkbox"
                   checked={checked.size === clips.length && clips.length > 0}
                   onChange={(e) => editor.setAllChecked(e.target.checked)}
                   style={{ width: '15px', height: '15px' }} />
            {checked.size}/{clips.length}
          </label>
          <button className="btn-secondary" onClick={handleSaveClips}
                  disabled={saving === 'running'}>
            {saving === 'running' ? <Loader2 size={14} className="animate-spin" />
              : saving === 'done' ? <CheckCircle2 size={14} style={{ color: 'var(--entry)' }} />
                : <Save size={14} />}
            {saving === 'done' ? 'Tersimpan' : 'Simpan susunan'}
          </button>
          {/* Unggah otomatis ke Drive. Hanya muncul kalau akunnya memang
              sudah tersambung — menawarkan tombol yang pasti gagal adalah
              cara tercepat membuat orang berhenti mempercayainya. */}
          {googleReady && (
            <label style={{
              display: 'flex', alignItems: 'center', gap: '7px', fontSize: '.82rem',
              cursor: 'pointer', color: 'var(--ink-2)',
            }} title="Klip yang selesai dirender langsung diantrekan ke Google Drive, satu per satu">
              <input type="checkbox" checked={uploadAfter}
                     onChange={(e) => setUploadAfter(e.target.checked)}
                     style={{ width: '15px', height: '15px' }} />
              Unggah ke Drive
            </label>
          )}
          <button className="btn-primary" disabled={exporting || checked.size === 0}
                  onClick={handleExportSelected}>
            {exporting ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            Render &amp; simpan
          </button>
        </div>
      </div>

      {data.model_requested && data.model && data.model_requested !== data.model && (
        <div className="plate" style={{
          padding: '10px 13px', marginBottom: '14px', fontSize: '.8rem', lineHeight: 1.55,
          borderLeftColor: 'var(--warn)',
        }}>
          Model <b>{data.model_requested}</b> tidak bisa dipakai saat analisis ini berjalan —
          biasanya karena kuota hariannya habis. Sistem memakai <b>{data.model}</b> sebagai cadangan.
        </div>
      )}

      {exportLog.length > 0 && (
        <div className="plate" style={{
          padding: '10px 13px', marginBottom: '14px',
          display: 'flex', flexDirection: 'column', gap: '6px',
        }}>
          {exportLog.map((e) => (
            <div key={e.name} style={{
              display: 'flex', alignItems: 'center', gap: '9px', fontSize: '.8rem',
            }}>
              {e.status === 'running' && <Loader2 size={13} className="animate-spin" style={{ color: 'var(--reh)' }} />}
              {e.status === 'done' && <CheckCircle2 size={13} style={{ color: 'var(--entry)' }} />}
              {e.status === 'failed' && <AlertTriangle size={13} style={{ color: 'var(--danger)' }} />}
              <b style={{ minWidth: '64px' }}>{e.name}</b>
              <span style={{ color: 'var(--ink-2)' }}>{e.message}</span>
            </div>
          ))}
        </div>
      )}

      {/* ── Panggung: video sumber di ATAS, kanvas hasil di sampingnya ──────
          Pratinjau dulu berdiri di kolom kanan selebar 336px. Cukup untuk
          menonton, tidak cukup untuk memegang sebuah kotak crop dan
          menggesernya — dan tidak memperlihatkan apa pun tentang bagian mana
          dari video sumber yang sedang diambil. */}
      <div className="stage-row">
        <FrameStage src={data.local_url} videoRef={videoRef}
                    segments={selected?.segments ?? null}
                    frameMode={frameMode} reframe={reframe} aspectRatio={aspectRatio}
                    layout={layout} onLayoutChange={setLayout}
                    selectedFrameId={selectedFrameId} onSelectFrame={setSelectedFrameId}
                    personKeys={personKeys} onLockPerson={aimPerson} />

      {/* lubang orkestra */}
      <div className="pit editor-pit" style={{
        padding: '14px', display: 'flex', flexDirection: 'column',
        gap: '10px', alignItems: 'center', alignSelf: 'start',
      }}>
        <ClipPreview src={data.local_url} clip={selected} aspectRatio={aspectRatio}
                     style={{ ...style, showHook }} videoRef={videoRef}
                     constrained={constrained} frameMode={frameMode}
                     reframe={reframe} reframeLoading={reframeLoading}
                     onStyleChange={patchStyle} onCardChange={patchCard}
                     layout={layout} onLayoutChange={setLayout}
                     frameEditing={tab === 'frame'}
                     selectedFrameId={selectedFrameId}
                     onSelectFrame={setSelectedFrameId} />
        <div style={{ display: 'flex', gap: '7px', flexWrap: 'wrap', justifyContent: 'center' }}>
          <button className="btn-secondary" style={{ fontSize: '.76rem', padding: '6px 10px' }}
                  onClick={addSegmentAtPlayhead} disabled={!selected || editor.busy}>
            <Plus size={12} /> Sambung dari sini
          </button>
          {!constrained && (
            <button className="btn-secondary" style={{ fontSize: '.76rem', padding: '6px 10px' }}
                    onClick={() => selected && selectClip(selected.clip_id)}>
              Kembali ke huruf
            </button>
          )}
        </div>
      </div>
      </div>

      {/* ── Sistem balok: seluruh durasi terbaca sekaligus ───────────────── */}
      <StaveSystem
        duration={duration} peaks={peaks} clips={clips}
        selectedId={editor.selectedId}
        speakerCount={data.speaker_count || 1}
        speakerColors={style.speaker_colors ?? []}
        videoRef={videoRef}
        onSeek={seekSource} onSelectClip={selectClip}
        onTrimClip={editor.setSegmentBounds} busy={editor.busy}
        mark={mark}
      />

      {/* ── Linimasa klip terpilih: subtitle, potongan, dan arah bingkai ── */}
      <ClipTimeline clip={selected} reframe={reframe}
                    personKeys={personKeys} onPersonKeys={setPersonKeys}
                    videoRef={videoRef} onSeekClip={seekClip}
                    onMoveSubtitle={(i, a, b) => selected
                      && editor.moveSubtitle(selected.clip_id, i, a, b)}
                    onSetSegmentBounds={(i, a, b) => selected
                      && editor.setSegmentBounds(selected.clip_id, i, a, b)}
                    onSelectSubtitle={setSelectedLine}
                    selectedLine={selectedLine}
                    speakerColors={style.speaker_colors ?? []}
                    reframeLoading={reframeLoading}
                    frameAiming={frameMode === 'smart'}
                    busy={editor.busy} />

      {/* ── Transport ───────────────────────────────────────────────────── */}
      <div className="plate" style={{
        display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap',
        padding: '9px 12px', marginBottom: '16px',
      }}>
        <button className="btn-secondary" onClick={togglePlay} style={{ minWidth: '84px' }}>
          <Play size={13} /> Spasi
        </button>
        {/* Diberi nama karena bukan satu-satunya jam di halaman ini: pratinjau
            di atas menghitung dari awal klip, yang ini dari awal video. */}
        <div className="tc" style={{
          fontSize: '1.02rem', fontWeight: 700, color: 'var(--reh)',
          display: 'flex', alignItems: 'baseline', gap: '7px',
        }}>
          <span className="mark" style={{ color: 'var(--ink-3)' }}>Video</span>
          {formatTimecode(sourceTime)}
          <span style={{ color: 'var(--ink-3)', fontWeight: 500, fontSize: '.82rem' }}>
            {' / '}{formatTimecode(duration)}
          </span>
        </div>
        <span style={{ width: '1px', height: '20px', background: 'var(--rule-2)' }} />

        {/* Membuat klip sendiri.
            Dulu ini dua tombol bernama "Tandai I" dan "Tandai O" berdiri
            sendiri — nama yang hanya masuk akal kalau seseorang sudah tahu
            istilah in-point dan out-point dari editor lain. Sekarang ketiganya
            satu kelompok bernama, dan tiap tombol menyebut apa yang dilakukannya. */}
        <div className="cutter">
          <span className="mark cutter-title">Potong sendiri</span>
          <button className="btn-secondary cutter-btn"
                  title="Awal klip baru diambil dari posisi playhead sekarang"
                  onClick={() => setMark((m) => ({ ...m, in: videoRef.current?.currentTime ?? 0 }))}>
            Mulai di sini <kbd style={kbd}>I</kbd>
          </button>
          <button className="btn-secondary cutter-btn"
                  title="Akhir klip baru diambil dari posisi playhead sekarang"
                  onClick={() => setMark((m) => ({ ...m, out: videoRef.current?.currentTime ?? 0 }))}>
            Sampai sini <kbd style={kbd}>O</kbd>
          </button>
          <span className="tc cutter-range">
            {mark.in === null && mark.out === null
              ? 'tandai awal & akhirnya di rekaman'
              : `${mark.in === null ? '…' : formatTime(mark.in)} – ${mark.out === null ? '…' : formatTime(mark.out)}`
                + (mark.in !== null && mark.out !== null
                  ? ` · ${Math.max(0, mark.out - mark.in).toFixed(1)} dtk` : '')}
          </span>
          <button className="btn-primary cutter-btn" onClick={createFromMarks}
                  title="Membuat klip baru dari rentang yang ditandai"
                  disabled={editor.busy || (mark.in !== null && mark.out !== null
                    && mark.out - mark.in < 1.5)}>
            {editor.busy ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
            Jadikan klip
          </button>
        </div>

        <span className="mark" style={{ marginLeft: 'auto' }}>
          ← → 1 dtk · Shift 10 dtk · J K L 5 dtk · Home awal huruf
        </span>
      </div>

      {/* ── Badan: indeks · lirik+panel · lubang orkestra ────────────────── */}
      <div className="editor-grid">
        {/* indeks huruf latihan */}
        <aside className="plate" style={{ overflow: 'hidden', alignSelf: 'start' }}>
          <div className="plate-head">
            <span className="mark" style={{ color: 'var(--ink)' }}>Huruf latihan</span>
            <span className="tc" style={{ marginLeft: 'auto', fontSize: '.72rem', color: 'var(--ink-3)' }}>
              {clips.length}
            </span>
          </div>
          <div className="reh-index">
            {clips.map((clip, i) => {
              const on = clip.clip_id === editor.selectedId;
              return (
                <div key={clip.clip_id} onClick={() => selectClip(clip.clip_id)}
                     className={`reh-row${on ? ' is-on' : ''}`}>
                  <input type="checkbox" checked={checked.has(clip.clip_id)}
                         onClick={(e) => e.stopPropagation()}
                         onChange={() => editor.toggleChecked(clip.clip_id)}
                         style={{ width: '14px', height: '14px', marginTop: '3px' }} />
                  <span className={`reh${clip.source === 'manual' ? ' reh--manual' : ''}`}>
                    {rehearsalLetter(i)}
                  </span>
                  <div style={{ minWidth: 0 }}>
                    <div className="tc" style={{ fontSize: '.7rem', color: 'var(--ink-3)' }}>
                      {formatTime(clip.segments[0].start)} · {Math.round(clip.duration || 0)}s
                      {clip.score != null && ` · ${Math.round(clip.score)}`}
                      {clip.source === 'manual' && ' · tangan'}
                    </div>
                    <div style={{
                      fontSize: '.76rem', color: 'var(--ink-2)', lineHeight: 1.35,
                      display: '-webkit-box', WebkitLineClamp: 2,
                      WebkitBoxOrient: 'vertical', overflow: 'hidden',
                    }}>{clip.hook_text}</div>
                  </div>
                </div>
              );
            })}
          </div>
          {/* Mesin pemilih pasti melewatkan momen: ia menilai dari pola bicara
              dan kosakata, bukan dari apa yang lucu. Pintu untuk menambah
              sendiri harus ada DI SINI — di daftar klip — karena di sinilah
              orang melihat bahwa yang dicarinya tidak ada. */}
          <button className="btn-secondary" onClick={createFromMarks}
                  disabled={editor.busy}
                  style={{
                    width: '100%', borderRadius: 0, borderWidth: '1px 0 0',
                    justifyContent: 'flex-start', fontSize: '.78rem',
                  }}>
            {editor.busy ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
            {mark.in !== null || mark.out !== null
              ? 'Jadikan klip dari rentang bertanda'
              : 'Klip baru dari posisi playhead'}
          </button>
        </aside>

        {/* lirik + panel */}
        <div style={{ minWidth: 0, display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div className="plate" style={{ overflow: 'hidden' }}>
            <div className="plate-head">
              <span className={`reh${selected?.source === 'manual' ? ' reh--manual' : ''}`}>{letter}</span>
              <span className="tc" style={{ fontSize: '.76rem', color: 'var(--ink-2)' }}>
                {selected
                  ? `${formatTime(selected.segments[0].start)} → ${formatTime(selected.end_seconds)} · ${Math.round(selected.duration || 0)} dtk`
                  : 'belum ada huruf dipilih'}
              </span>
              {selected?.score != null && (
                <span className="mark" style={{ marginLeft: 'auto' }}>skor {Math.round(selected.score)}</span>
              )}
            </div>
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)',
              borderBottom: '1px solid var(--rule-2)',
            }}>
              {TABS.map(({ id, label, Icon }) => (
                <button key={id} onClick={() => setTab(id)} className={`tab-btn${tab === id ? ' is-on' : ''}`}>
                  <Icon size={14} strokeWidth={1.9} />{label}
                </button>
              ))}
            </div>
            <div style={{ padding: '13px' }}>
              {tab === 'trim' && (
                <TrimPanel clip={selected} videoDuration={duration} busy={editor.busy}
                           onNudge={editor.nudgeSegment} onSetBounds={editor.setSegmentBounds}
                           onAddSegment={editor.addSegment} onRemoveSegment={editor.removeSegment} />
              )}
              {tab === 'subtitle' && (
                <SubtitlePanel clip={selected} onUpdate={editor.updateSubtitle}
                               onRemove={editor.removeSubtitle} style={style}
                               selectedLine={selectedLine} onSelectLine={setSelectedLine}
                               onSeekLine={seekClip}
                               onAutoSpeakers={editor.autoSpeakers}
                               speakerCount={data.speaker_count || 2}
                               speakerConfident={data.speaker_confident ?? null}
                               onRedetect={redetectSpeakers} redetecting={redetecting} />
              )}
              {tab === 'style' && (
                <StylePanel style={style} onChange={setStyle}
                            speakerCount={Math.max(data.speaker_count || 1, 2)}
                            aspectRatio={aspectRatio} onAspectChange={setAspectRatio}
                            showHook={showHook} onShowHookChange={setShowHook}
                            hookText={selected?.hook_text ?? ''}
                            onHookTextChange={(t) => selected
                              && editor.updateClip(selected.clip_id, { hook_text: t })} />
              )}
              {tab === 'title' && (
                <TitlePanel clip={selected}
                            onRetitle={handleRetitle} retitling={retitling}
                            onChange={(patch) => selected
                              && editor.updateClip(selected.clip_id, patch)} />
              )}
              {tab === 'frame' && (
                <FramePanel frameMode={frameMode} onFrameModeChange={setFrameMode}
                            layout={layout} onLayoutChange={setLayout}
                            selectedFrameId={selectedFrameId}
                            onSelectFrame={setSelectedFrameId}
                            faceTrackAvailable={!!reframe?.people?.length}
                            peopleCount={reframe?.people?.length ?? 0}
                            aimedPerson={aimedPerson} onAimPerson={aimPerson}
                            keyCount={personKeys.length}
                            onClearKeys={() => setPersonKeys([])} />
              )}
            </div>
          </div>

          {selected && selected.segments.length > 1 && (
            <div className="plate" style={{
              padding: '9px 12px', display: 'flex', alignItems: 'center',
              gap: '9px', flexWrap: 'wrap', fontSize: '.78rem',
            }}>
              <b>Huruf {letter} menyambung {selected.segments.length} potongan:</b>
              {selected.segments.map((s, i) => (
                <span key={i} className="tc" style={{
                  display: 'inline-flex', alignItems: 'center', gap: '6px',
                  padding: '3px 8px', background: 'var(--plate-2)',
                  border: '1px solid var(--rule-2)', borderRadius: 'var(--r-sm)',
                }}>
                  {formatTime(s.start)}–{formatTime(s.end)}
                  <Trash2 size={11} style={{ cursor: 'pointer', color: 'var(--danger)' }}
                          onClick={() => editor.removeSegment(selected.clip_id, i)} />
                </span>
              ))}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}

async function waitForJob(jobId, { interval = 1200, limit = 2400000 } = {}) {
  const started = Date.now();
  for (;;) {
    // eslint-disable-next-line no-await-in-loop
    const job = await apiGet(`/jobs/${jobId}`);
    if (['done', 'failed', 'cancelled'].includes(job.status)) return job;
    if (Date.now() - started > limit) return { status: 'failed', error: 'Waktu render habis.' };
    // eslint-disable-next-line no-await-in-loop
    await new Promise((r) => setTimeout(r, interval));
  }
}

const kbd = {
  display: 'inline-block', padding: '1px 5px', margin: '0 1px',
  borderRadius: '4px', background: 'var(--bg-glass)',
  border: '1px solid var(--border-color)', fontSize: '0.66rem',
  fontFamily: 'inherit', fontWeight: 700, color: 'var(--text-secondary)',
};

/**
 * Timecode gaya editor: HH:MM:SS.d
 *
 * Sepersepuluh detik ikut ditampilkan karena batas klip disetel pada ketelitian
 * itu; MM:SS saja membuat dua posisi yang berbeda terlihat identik persis saat
 * pengguna sedang mencoba membedakannya.
 */
function formatTimecode(seconds) {
  const t = Math.max(0, Number(seconds) || 0);
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = Math.floor(t % 60);
  const d = Math.floor((t % 1) * 10);
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(h)}:${pad(m)}:${pad(s)}.${d}`;
}

function Centered({ children }) {
  return (
    <div style={{ padding: '70px 20px', textAlign: 'center' }}>{children}</div>
  );
}
