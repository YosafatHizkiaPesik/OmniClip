import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowLeft, Scissors, Type, Palette, Download, Loader2, CheckCircle2,
  AlertTriangle, Crop, Plus, Trash2, Film, Play, Save,
} from 'lucide-react';
import { apiGet, apiPost, downloadToDisk } from '../../lib/api';
import { loadFonts } from '../../lib/fonts';
import { formatTime } from '../../utils/timeFormat';
import { useClipEditor } from './useClipEditor';
import ClipPreview from './ClipPreview';
import Timeline from './timeline/Timeline';
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
  const [tab, setTab] = useState('trim');
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
        <AlertTriangle size={34} style={{ color: 'var(--accent-red, #ff4d6d)', marginBottom: '12px' }} />
        <h3 style={{ fontWeight: 700, marginBottom: '7px' }}>Gagal membuka project</h3>
        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{error.message}</p>
        <button className="btn-primary" onClick={onBack} style={{ marginTop: '16px' }}>
          <ArrowLeft size={14} /> Kembali ke Studio
        </button>
      </Centered>
    );
  }

  if (!data) {
    return (
      <Centered>
        <Loader2 size={26} className="animate-spin" style={{ color: 'var(--accent-cyan)' }} />
        <p style={{ marginTop: '10px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
          Memuat editor…
        </p>
      </Centered>
    );
  }

  return (
    <div style={{ paddingBottom: '30px' }}>
      {/* Kepala */}
      <header style={{
        display: 'flex', alignItems: 'center', gap: '12px',
        flexWrap: 'wrap', marginBottom: '14px',
      }}>
        <button className="btn-secondary" onClick={onBack} style={{ fontSize: '0.8rem' }}>
          <ArrowLeft size={14} /> Studio
        </button>
        <div style={{ minWidth: 0, flex: 1 }}>
          <h1 style={{
            fontSize: '1rem', fontWeight: 800, marginBottom: '2px',
            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {data.title}
          </h1>
          <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
            {clips.length} klip · {formatTime(duration)} ·{' '}
            {data.speaker_count > 1 && (
              <>{data.speaker_confident ? `± ${data.speaker_count} narasumber`
                : 'narasumber sulit dipisahkan'} · </>
            )}
            {data.transcript_source === 'whisper' ? 'transkrip Whisper lokal'
              : data.transcript_source === 'youtube_manual' ? 'transkrip resmi kanal'
                : 'transkrip otomatis YouTube'}
          </div>
        </div>
        <label style={{ display: 'flex', alignItems: 'center', gap: '7px', fontSize: '0.8rem', cursor: 'pointer' }}>
          <input type="checkbox"
                 checked={checked.size === clips.length && clips.length > 0}
                 onChange={(e) => editor.setAllChecked(e.target.checked)}
                 style={{ accentColor: 'var(--accent-cyan)', width: '15px', height: '15px' }} />
          {checked.size}/{clips.length}
        </label>
        <button className="btn-primary" disabled={exporting || checked.size === 0}
                onClick={handleExportSelected} style={{ fontSize: '0.8rem' }}>
          {exporting ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
          Render &amp; simpan
        </button>
      </header>

      {data.model_requested && data.model && data.model_requested !== data.model && (
        <div style={{
          marginBottom: '14px', padding: '10px 13px', fontSize: '0.79rem',
          borderRadius: 'var(--radius-md)', lineHeight: 1.55,
          background: 'rgba(255,159,28,0.1)', border: '1px solid rgba(255,159,28,0.32)',
        }}>
          Model <strong>{data.model_requested}</strong> tidak bisa dipakai saat analisis
          ini berjalan — biasanya karena kuota harian model itu habis. Sistem memakai{' '}
          <strong>{data.model}</strong> sebagai cadangan.
        </div>
      )}

      {exportLog.length > 0 && (
        <div style={{
          marginBottom: '14px', padding: '10px 13px', background: 'var(--bg-card)',
          border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)',
          display: 'flex', flexDirection: 'column', gap: '6px',
        }}>
          {exportLog.map((e) => (
            <div key={e.name} style={{ display: 'flex', alignItems: 'center', gap: '9px', fontSize: '0.79rem' }}>
              {e.status === 'running' && <Loader2 size={13} className="animate-spin" style={{ color: 'var(--accent-cyan)' }} />}
              {e.status === 'done' && <CheckCircle2 size={13} style={{ color: '#10b981' }} />}
              {e.status === 'failed' && <AlertTriangle size={13} style={{ color: 'var(--accent-red, #ff4d6d)' }} />}
              <strong style={{ minWidth: '64px' }}>{e.name}</strong>
              <span style={{ color: 'var(--text-secondary)' }}>{e.message}</span>
            </div>
          ))}
        </div>
      )}

      {/* Badan: daftar klip | pratinjau | panel */}
      <div className="editor-grid" style={{
        display: 'grid', gridTemplateColumns: '250px minmax(0, 1fr) 320px',
        gap: '14px', alignItems: 'start', marginBottom: '14px',
      }}>
        {/* Kiri: hasil klip */}
        <aside style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-md)', overflow: 'hidden',
          display: 'flex', flexDirection: 'column', maxHeight: '520px',
        }}>
          <div style={{
            padding: '9px 12px', borderBottom: '1px solid var(--border-color)',
            fontSize: '0.75rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '7px',
          }}>
            <Film size={13} style={{ color: 'var(--accent-cyan)' }} />
            Hasil klip ({clips.length})
          </div>
          <div style={{ overflowY: 'auto', flex: 1 }}>
            {clips.map((clip) => {
              const active = clip.clip_id === editor.selectedId;
              return (
                <div key={clip.clip_id} onClick={() => selectClip(clip.clip_id)}
                     style={{
                       display: 'flex', gap: '9px', padding: '10px 11px', cursor: 'pointer',
                       borderBottom: '1px solid var(--border-color)',
                       background: active ? 'rgba(0,242,254,0.09)' : 'transparent',
                       borderLeft: active ? '3px solid var(--accent-cyan)' : '3px solid transparent',
                     }}>
                  <input type="checkbox" checked={checked.has(clip.clip_id)}
                         onClick={(e) => e.stopPropagation()}
                         onChange={() => editor.toggleChecked(clip.clip_id)}
                         style={{ accentColor: 'var(--accent-cyan)', width: '14px', height: '14px', marginTop: '2px' }} />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '3px' }}>
                      <strong style={{ fontSize: '0.78rem' }}>#{clip.index}</strong>
                      <span style={{
                        fontSize: '0.65rem', fontWeight: 800, padding: '1px 6px', borderRadius: '99px',
                        background: 'rgba(0,242,254,0.15)', color: 'var(--accent-cyan)',
                      }}>{Math.round(clip.score)}</span>
                      <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
                        {formatTime(clip.segments[0].start)} · {Math.round(clip.duration || 0)}s
                      </span>
                    </div>
                    <div style={{
                      fontSize: '0.72rem', color: 'var(--text-secondary)', lineHeight: 1.4,
                      display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden',
                    }}>
                      {clip.hook_text}
                    </div>
                    {clip.segments.length > 1 && (
                      <div style={{ fontSize: '0.66rem', color: 'var(--accent-cyan)', marginTop: '3px' }}>
                        {clip.segments.length} potongan digabung
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </aside>

        {/* Tengah: pratinjau */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-md)', padding: '14px',
          display: 'flex', flexDirection: 'column', gap: '10px', alignItems: 'center',
        }}>
          <ClipPreview src={data.local_url} clip={selected} aspectRatio={aspectRatio}
                       style={{ ...style, showHook }} videoRef={videoRef}
                       constrained={constrained} frameMode={frameMode}
                       reframe={reframe} reframeLoading={reframeLoading}
                       onStyleChange={patchStyle} />
          <div style={{ display: 'flex', gap: '7px', flexWrap: 'wrap', justifyContent: 'center' }}>
            <button className="btn-secondary" style={{ fontSize: '0.74rem', padding: '5px 10px' }}
                    onClick={addSegmentAtPlayhead} disabled={!selected || editor.busy}
                    title="Ambil bagian dari posisi playhead dan sambungkan ke klip ini">
              <Plus size={12} /> Sambung dari posisi ini
            </button>
            {!constrained && (
              <button className="btn-secondary" style={{ fontSize: '0.74rem', padding: '5px 10px' }}
                      onClick={() => selected && selectClip(selected.clip_id)}>
                Kembali ke klip
              </button>
            )}
          </div>
        </div>

        {/* Kanan: panel edit */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-md)', padding: '13px',
          display: 'flex', flexDirection: 'column', gap: '12px',
          // Panel ini bisa sangat panjang (daftar font, daftar subtitle, palet
          // warna). Dibatasi dan digulirkan sendiri supaya kolom pratinjau di
          // sebelahnya tidak ikut terdorong dan meninggalkan ruang kosong.
          position: 'sticky', top: '14px',
          maxHeight: 'calc(100vh - 150px)', overflowY: 'auto',
        }}>
          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '5px',
            position: 'sticky', top: 0, zIndex: 2,
            background: 'var(--bg-card)', paddingBottom: '8px',
          }}>
            {TABS.map(({ id, label, Icon }) => (
              <button key={id} onClick={() => setTab(id)} style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '3px',
                padding: '7px 3px', borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                fontSize: '0.65rem', fontWeight: 700,
                border: tab === id ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                background: tab === id ? 'rgba(0,242,254,0.1)' : 'transparent',
                color: tab === id ? 'var(--accent-cyan)' : 'var(--text-secondary)',
              }}>
                <Icon size={14} />{label}
              </button>
            ))}
          </div>

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
              <div style={{ fontSize: '0.72rem', fontWeight: 800, color: 'var(--text-secondary)' }}>
                CARA MEMBINGKAI
              </div>
              {FRAME_MODES.map((m) => (
                <button key={m.id} onClick={() => setFrameMode(m.id)} style={{
                  textAlign: 'left', padding: '9px 11px', cursor: 'pointer',
                  borderRadius: 'var(--radius-sm)',
                  border: frameMode === m.id ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                  background: frameMode === m.id ? 'rgba(0,242,254,0.08)' : 'transparent',
                }}>
                  <div style={{
                    fontSize: '0.79rem', fontWeight: 700, marginBottom: '3px',
                    color: frameMode === m.id ? 'var(--accent-cyan)' : 'var(--text-primary)',
                  }}>{m.label}</div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
                    {m.hint}
                  </div>
                </button>
              ))}
              <p style={{ fontSize: '0.69rem', color: 'var(--text-muted)', lineHeight: 1.5, margin: '4px 0 0' }}>
                Mode ikut-wajah menganalisis klip sebelum render (beberapa detik).
                Bila wajah jarang terlihat — misalnya rekaman layar — sistem otomatis
                memakai bilah kabur.
              </p>
              {frameMode === 'original' && (
                <p style={{ fontSize: '0.69rem', color: 'var(--text-muted)', lineHeight: 1.5, margin: '2px 0 0' }}>
                  Pilihan rasio di tab Gaya diabaikan pada mode ini: hasilnya memakai
                  ukuran dan bingkai video aslinya, dan ukuran teks ikut disesuaikan.
                </p>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Bar transport: jam, penanda, dan pembuat klip manual */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap',
        padding: '9px 12px', marginBottom: '10px',
        background: 'var(--bg-card)', border: '1px solid var(--border-color)',
        borderRadius: 'var(--radius-md)',
      }}>
        <button className="btn-secondary" onClick={togglePlay}
                style={{ fontSize: '0.76rem', padding: '5px 11px' }}>
          <Play size={13} /> Spasi
        </button>

        {/* Jam sumber. Font tabular supaya angkanya tidak bergoyang tiap detik —
            timecode yang bergerak-gerak sendiri sangat sulit dibaca. */}
        <div style={{
          fontVariantNumeric: 'tabular-nums', fontSize: '0.95rem', fontWeight: 800,
          letterSpacing: '0.02em', color: 'var(--accent-cyan)',
        }}>
          {formatTimecode(sourceTime)}
          <span style={{ color: 'var(--text-muted)', fontWeight: 600, fontSize: '0.8rem' }}>
            {' / '}{formatTimecode(duration)}
          </span>
        </div>

        <div style={{ width: '1px', height: '22px', background: 'var(--border-color)' }} />

        <button className="btn-secondary" style={{ fontSize: '0.74rem', padding: '5px 9px' }}
                onClick={() => setMark((m) => ({ ...m, in: videoRef.current?.currentTime ?? 0 }))}>
          Tandai masuk <kbd style={kbd}>I</kbd>
        </button>
        <button className="btn-secondary" style={{ fontSize: '0.74rem', padding: '5px 9px' }}
                onClick={() => setMark((m) => ({ ...m, out: videoRef.current?.currentTime ?? 0 }))}>
          Tandai keluar <kbd style={kbd}>O</kbd>
        </button>

        <span style={{
          fontSize: '0.74rem', color: 'var(--text-secondary)',
          fontVariantNumeric: 'tabular-nums',
        }}>
          {mark.in === null && mark.out === null
            ? 'Belum ada rentang ditandai'
            : `${mark.in === null ? '…' : formatTime(mark.in)} – `
              + `${mark.out === null ? '…' : formatTime(mark.out)}`
              + (mark.in !== null && mark.out !== null
                ? ` · ${Math.max(0, mark.out - mark.in).toFixed(1)}s` : '')}
        </span>

        <button className="btn-primary" onClick={createFromMarks}
                disabled={editor.busy || (mark.in !== null && mark.out !== null
                  && mark.out - mark.in < 1.5)}
                style={{ fontSize: '0.76rem', padding: '5px 11px' }}>
          {editor.busy ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
          Jadikan klip
        </button>

        <div style={{ flex: 1 }} />

        <button className="btn-secondary" onClick={handleSaveClips}
                disabled={saving === 'running'}
                style={{ fontSize: '0.74rem', padding: '5px 10px' }}>
          {saving === 'running' ? <Loader2 size={13} className="animate-spin" />
            : saving === 'done' ? <CheckCircle2 size={13} style={{ color: '#10b981' }} />
              : <Save size={13} />}
          {saving === 'done' ? 'Tersimpan' : 'Simpan susunan klip'}
        </button>
      </div>

      <p style={{
        fontSize: '0.68rem', color: 'var(--text-muted)', margin: '0 0 10px',
        lineHeight: 1.6,
      }}>
        Pintasan: <kbd style={kbd}>Spasi</kbd> putar/jeda ·
        {' '}<kbd style={kbd}>←</kbd> <kbd style={kbd}>→</kbd> geser 1 detik
        (tahan <kbd style={kbd}>Shift</kbd> untuk 10 detik) ·
        {' '}<kbd style={kbd}>J</kbd> <kbd style={kbd}>K</kbd> <kbd style={kbd}>L</kbd>{' '}
        mundur/jeda/maju 5 detik · <kbd style={kbd}>I</kbd> <kbd style={kbd}>O</kbd>{' '}
        tandai rentang · <kbd style={kbd}>Home</kbd> kembali ke awal klip.
      </p>

      {/* Bawah: timeline video sumber */}
      <Timeline
        duration={duration}
        peaks={peaks}
        clips={clips}
        selectedId={editor.selectedId}
        videoRef={videoRef}
        busy={editor.busy}
        onSeek={seekSource}
        onSelectClip={selectClip}
        onCommitSegment={commitSegment}
      />

      {selected && selected.segments.length > 1 && (
        <div style={{
          marginTop: '10px', padding: '9px 12px', fontSize: '0.76rem',
          background: 'var(--bg-card)', border: '1px solid var(--border-color)',
          borderRadius: 'var(--radius-md)', display: 'flex', alignItems: 'center',
          gap: '10px', flexWrap: 'wrap',
        }}>
          <strong>Klip #{selected.index} menggabungkan {selected.segments.length} potongan:</strong>
          {selected.segments.map((s, i) => (
            <span key={i} style={{
              display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '3px 8px',
              borderRadius: '99px', background: 'rgba(0,242,254,0.1)',
              color: 'var(--accent-cyan)', fontVariantNumeric: 'tabular-nums',
            }}>
              {formatTime(s.start)}–{formatTime(s.end)}
              <Trash2 size={11} style={{ cursor: 'pointer' }}
                      onClick={() => editor.removeSegment(selected.clip_id, i)} />
            </span>
          ))}
        </div>
      )}
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
