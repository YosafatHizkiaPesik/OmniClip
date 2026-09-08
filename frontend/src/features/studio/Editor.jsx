import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowLeft, Scissors, Type, Palette, Download, Loader2, CheckCircle2,
  AlertTriangle, Crop, Plus, Trash2, Film,
} from 'lucide-react';
import { apiGet, apiPost, downloadToDisk } from '../../lib/api';
import { formatTime } from '../../utils/timeFormat';
import { useClipEditor } from './useClipEditor';
import ClipPreview from './ClipPreview';
import Timeline from './timeline/Timeline';
import { TrimPanel, SubtitlePanel, StylePanel } from './EditorPanels';

const DEFAULT_STYLE = {
  size: 96, primary: '#FFFFFF', highlight: '#FFE500', speaker2: '#7CFFB2',
  position: 'bottom', uppercase: true, animation: 'karaoke_pop', font: 'DejaVu Sans',
};

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
  const [style, setStyle] = useState(DEFAULT_STYLE);
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

  const { clips, selected, checked } = editor;

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

  const renderPayload = useCallback((clip) => ({
    source_path: videoId,
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
                       reframe={reframe} reframeLoading={reframeLoading} />
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
        }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '5px' }}>
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
                           onAutoSpeakers={editor.autoSpeakers} />
          )}
          {tab === 'style' && (
            <StylePanel style={style} onChange={setStyle}
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
            </div>
          )}
        </div>
      </div>

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

function Centered({ children }) {
  return (
    <div style={{ padding: '70px 20px', textAlign: 'center' }}>{children}</div>
  );
}
