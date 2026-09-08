import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowLeft, Scissors, Type, Palette, Download, Loader2, CheckCircle2,
  AlertTriangle, Crop, Plus, Trash2, Play, Save,
} from 'lucide-react';
import { apiGet, apiPost, downloadToDisk } from '../../lib/api';
import { loadFonts } from '../../lib/fonts';
import { formatTime } from '../../utils/timeFormat';
import { useClipEditor } from './useClipEditor';
import ClipPreview from './ClipPreview';
import StaveSystem, { rehearsalLetter } from './StaveSystem';
import { TrimPanel, SubtitlePanel, StylePanel } from './EditorPanels';

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
];

const FRAME_MODES = [
  { id: 'smart', label: 'Ikuti wajah', hint: 'Kamera mengikuti pembicara. Layar penuh, tanpa bilah kabur.' },
  { id: 'blur', label: 'Bilah kabur', hint: 'Video utuh di tengah, sisi atas-bawah diisi versi kabur.' },
  { id: 'center', label: 'Potong tengah', hint: 'Ambil bagian tengah frame. Paling cepat, tanpa analisis.' },
  { id: 'original', label: 'Orisinal', hint: 'Bingkai video sumber apa adanya, tanpa dipotong sama sekali.' },
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
  const [frameMode, setFrameMode] = useState('smart');
  const [constrained, setConstrained] = useState(true);
  // Judul mati secara bawaan: hasilnya lebih bersih, dan hook otomatis sering
  // kalah bagus dari klipnya sendiri.
  const [showHook, setShowHook] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportLog, setExportLog] = useState([]);
  // Rencana crop untuk pratinjau — sama persis dengan yang dipakai render.
  const [reframe, setReframe] = useState(null);
  const [reframeLoading, setReframeLoading] = useState(false);
  // Penanda masuk/keluar untuk memotong klip sendiri.
  const [mark, setMark] = useState({ in: null, out: null });
  const [redetecting, setRedetecting] = useState(false);
  const [saving, setSaving] = useState(null);
  const [sourceTime, setSourceTime] = useState(0);

  const { clips, selected, checked } = editor;

  useEffect(() => { loadFonts(); }, []);

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
  useEffect(() => {
    let cancelled = false;
    if (!videoId || !selected || frameMode !== 'smart' || aspectRatio === '16:9') {
      setReframe(null);
      return undefined;
    }
    setReframeLoading(true);
    apiPost('/clip-reframe', {
      video_id: videoId,
      segments: selected.segments,
      aspect_ratio: aspectRatio,
    })
      .then((res) => { if (!cancelled) setReframe(res); })
      .catch(() => { if (!cancelled) setReframe(null); })
      .finally(() => { if (!cancelled) setReframeLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId, segmentKey, frameMode, aspectRatio]);

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
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, []);

  const seekSource = useCallback((time) => {
    const v = videoRef.current;
    if (!v) return;
    setConstrained(false);       // jelajah bebas sampai klip dipilih lagi
    v.currentTime = time;
  }, []);

  const selectClip = useCallback((clipId) => {
    editor.setSelectedId(clipId);
    setConstrained(true);
    const clip = clips.find((c) => c.clip_id === clipId);
    const v = videoRef.current;
    if (clip && v) v.currentTime = clip.segments[0].start;
  }, [clips, editor]);

  const commitSegment = useCallback((clipId, segIndex, start, end) => {
    editor.setSegmentBounds(clipId, segIndex, start, end);
  }, [editor]);

  /** Menambahkan potongan dari posisi playhead ke klip yang sedang dipilih. */
  const addSegmentAtPlayhead = () => {
    const v = videoRef.current;
    if (!v || !selected) return;
    const start = Math.max(0, v.currentTime);
    editor.addSegment(selected.clip_id, start, Math.min(duration || start + 20, start + 20));
    setConstrained(true);
  };

  /** Melompat relatif terhadap posisi sekarang, dipakai panah kiri/kanan. */
  const nudgePlayhead = useCallback((delta) => {
    const v = videoRef.current;
    if (!v) return;
    setConstrained(false);
    v.currentTime = Math.max(0, Math.min(duration || v.duration || 0,
                                         v.currentTime + delta));
  }, [duration]);

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
    aspect_ratio: aspectRatio,
    frame_mode: frameMode,
    caption_style: style,
  }), [videoId, aspectRatio, frameMode, style, showHook]);

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

      {/* ── Sistem balok: seluruh durasi terbaca sekaligus ───────────────── */}
      <StaveSystem
        duration={duration} peaks={peaks} clips={clips}
        selectedId={editor.selectedId}
        speakerCount={data.speaker_count || 1}
        speakerColors={style.speaker_colors ?? []}
        videoRef={videoRef}
        onSeek={seekSource} onSelectClip={selectClip}
      />

      {/* ── Transport ───────────────────────────────────────────────────── */}
      <div className="plate" style={{
        display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap',
        padding: '9px 12px', marginBottom: '16px',
      }}>
        <button className="btn-secondary" onClick={togglePlay} style={{ minWidth: '84px' }}>
          <Play size={13} /> Spasi
        </button>
        <div className="tc" style={{
          fontSize: '1.02rem', fontWeight: 700, color: 'var(--reh)',
        }}>
          {formatTimecode(sourceTime)}
          <span style={{ color: 'var(--ink-3)', fontWeight: 500, fontSize: '.82rem' }}>
            {' / '}{formatTimecode(duration)}
          </span>
        </div>
        <span style={{ width: '1px', height: '20px', background: 'var(--rule-2)' }} />
        <button className="btn-secondary" style={{ fontSize: '.76rem', padding: '7px 10px' }}
                onClick={() => setMark((m) => ({ ...m, in: videoRef.current?.currentTime ?? 0 }))}>
          Tandai <kbd style={kbd}>I</kbd>
        </button>
        <button className="btn-secondary" style={{ fontSize: '.76rem', padding: '7px 10px' }}
                onClick={() => setMark((m) => ({ ...m, out: videoRef.current?.currentTime ?? 0 }))}>
          Tandai <kbd style={kbd}>O</kbd>
        </button>
        <span className="tc" style={{ fontSize: '.76rem', color: 'var(--ink-2)' }}>
          {mark.in === null && mark.out === null
            ? 'belum ada rentang'
            : `${mark.in === null ? '…' : formatTime(mark.in)} – ${mark.out === null ? '…' : formatTime(mark.out)}`
              + (mark.in !== null && mark.out !== null
                ? ` · ${Math.max(0, mark.out - mark.in).toFixed(1)}s` : '')}
        </span>
        <button className="btn-primary" onClick={createFromMarks}
                disabled={editor.busy || (mark.in !== null && mark.out !== null
                  && mark.out - mark.in < 1.5)}
                style={{ fontSize: '.78rem', padding: '7px 11px' }}>
          {editor.busy ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
          Huruf baru
        </button>
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
              display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
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
              {tab === 'frame' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <div className="mark" style={{ color: 'var(--ink)' }}>Cara membingkai</div>
                  {FRAME_MODES.map((m) => (
                    <button key={m.id} onClick={() => setFrameMode(m.id)}
                            className={`choice${frameMode === m.id ? ' is-on' : ''}`}>
                      <div className="choice-t">{m.label}</div>
                      <div className="choice-h">{m.hint}</div>
                    </button>
                  ))}
                  <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.5, margin: '4px 0 0' }}>
                    Mode ikut-wajah menganalisis klip sebelum render. Bila wajah jarang
                    terlihat — misalnya rekaman layar — sistem otomatis memakai bilah kabur.
                  </p>
                </div>
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

        {/* lubang orkestra */}
        <div className="pit editor-pit" style={{
          padding: '14px', display: 'flex', flexDirection: 'column',
          gap: '10px', alignItems: 'center', alignSelf: 'start',
        }}>
          <ClipPreview src={data.local_url} clip={selected} aspectRatio={aspectRatio}
                       style={{ ...style, showHook }} videoRef={videoRef}
                       constrained={constrained} frameMode={frameMode}
                       reframe={reframe} reframeLoading={reframeLoading}
                       onStyleChange={patchStyle} />
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
