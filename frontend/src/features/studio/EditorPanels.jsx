import React, { useEffect, useState } from 'react';
import { Plus, Trash2, Scissors, Loader2 } from 'lucide-react';
import { formatTime, parseTimeString } from '../../utils/timeFormat';

const label = {
  fontSize: '0.72rem',
  fontWeight: 700,
  color: 'var(--text-secondary)',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
};

const field = {
  width: '100%',
  padding: '9px 11px',
  borderRadius: 'var(--radius-sm)',
  border: '1px solid var(--border-color)',
  background: 'var(--bg-glass)',
  color: 'var(--text-primary)',
  fontSize: '0.84rem',
  fontFamily: 'inherit',
};

/**
 * Input waktu MM:SS yang bisa benar-benar diketik.
 *
 * Versi lama sepenuhnya terkendali dan memformat ulang setiap ketukan, sehingga
 * mengetik "2:30" mustahil: menekan "2" langsung berubah jadi "00:02" dan ":"
 * kemudian ditolak. Sekarang nilai draft dibiarkan apa adanya sampai blur/Enter.
 */
function TimeInput({ value, onCommit, disabled }) {
  const [draft, setDraft] = useState(formatTime(value));
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    if (!editing) setDraft(formatTime(value));
  }, [value, editing]);

  const commit = () => {
    setEditing(false);
    const parsed = parseTimeString(draft);
    if (Number.isFinite(parsed) && parsed >= 0) onCommit(parsed);
    else setDraft(formatTime(value));
  };

  return (
    <input
      value={draft}
      disabled={disabled}
      onFocus={() => setEditing(true)}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === 'Enter') e.currentTarget.blur();
        if (e.key === 'Escape') { setDraft(formatTime(value)); setEditing(false); e.currentTarget.blur(); }
      }}
      style={{ ...field, textAlign: 'center', fontVariantNumeric: 'tabular-nums' }}
    />
  );
}

/** Panel batas klip dan penggabungan potongan. */
export function TrimPanel({ clip, videoDuration, busy, onNudge, onSetBounds, onAddSegment, onRemoveSegment }) {
  if (!clip) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
        Tarik batas mundur untuk menambah konteks sebelumnya, atau maju untuk memperpanjang.
        Subtitle otomatis dihitung ulang mengikuti batas baru.
      </p>

      {clip.segments.map((seg, idx) => (
        <div key={idx} style={{
          border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)',
          padding: '12px', background: 'var(--bg-glass)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <span style={label}>
              {clip.segments.length > 1 ? `Potongan ${idx + 1}` : 'Rentang klip'}
            </span>
            {clip.segments.length > 1 && (
              <button onClick={() => onRemoveSegment(clip.clip_id, idx)} disabled={busy}
                      aria-label="Hapus potongan"
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--accent-red)', display: 'flex' }}>
                <Trash2 size={15} />
              </button>
            )}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            {['start', 'end'].map((edge) => (
              <div key={edge}>
                <div style={{ ...label, marginBottom: '5px' }}>{edge === 'start' ? 'Mulai' : 'Selesai'}</div>
                <TimeInput
                  value={seg[edge]}
                  disabled={busy}
                  onCommit={(v) => onSetBounds(clip.clip_id, idx,
                    edge === 'start' ? v : seg.start,
                    edge === 'start' ? seg.end : v)}
                />
                <div style={{ display: 'flex', gap: '5px', marginTop: '6px' }}>
                  {[-5, -1, +1, +5].map((d) => (
                    <button key={d} disabled={busy}
                            onClick={() => onNudge(clip.clip_id, idx, edge, d, videoDuration)}
                            style={{
                              flex: 1, padding: '5px 0', fontSize: '0.72rem', fontWeight: 700,
                              borderRadius: '6px', cursor: busy ? 'default' : 'pointer',
                              border: '1px solid var(--border-color)',
                              background: 'transparent', color: 'var(--text-secondary)',
                            }}>
                      {d > 0 ? `+${d}` : d}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      <button
        className="btn-secondary"
        disabled={busy}
        onClick={() => {
          const last = clip.segments[clip.segments.length - 1];
          const start = Math.min((videoDuration || last.end + 60) - 20, last.end + 30);
          onAddSegment(clip.clip_id, Math.max(0, start), Math.max(0, start) + 15);
        }}
        style={{ fontSize: '0.8rem' }}
      >
        {busy ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
        Gabungkan potongan lain
      </button>
      <p style={{ fontSize: '0.74rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>
        Potongan baru bisa diambil dari bagian mana pun di video — misalnya menit 10
        digabung dengan menit 50. Atur waktunya di kotak yang muncul.
      </p>
    </div>
  );
}

/** Panel penyuntingan subtitle per baris. */
export function SubtitlePanel({ clip, onUpdate, onRemove }) {
  if (!clip) return null;
  const lines = clip.subtitles ?? [];

  if (!lines.length) {
    return (
      <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
        Klip ini tidak punya subtitle. Kalau video sumbernya tidak memiliki transkrip,
        sistem tidak membuat teks apa pun — subtitle karangan justru berbahaya karena
        akan ikut terbakar ke video.
      </p>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: 0 }}>
        {lines.length} baris. Perbaiki kata yang salah dengar langsung di sini.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '420px', overflowY: 'auto' }}>
        {lines.map((line, i) => (
          <div key={i} style={{
            display: 'grid', gridTemplateColumns: '58px 1fr 28px', gap: '8px',
            alignItems: 'center',
          }}>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
              {line.start.toFixed(1)}s
            </span>
            <input
              value={line.text}
              onChange={(e) => onUpdate(clip.clip_id, i, { text: e.target.value })}
              style={{ ...field, fontSize: '0.8rem', padding: '7px 9px' }}
            />
            <button onClick={() => onRemove(clip.clip_id, i)} aria-label="Hapus baris"
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex' }}>
              <Trash2 size={14} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

const FONT_CHOICES = ['DejaVu Sans', 'Liberation Sans', 'Noto Sans', 'Ubuntu'];
const HIGHLIGHTS = ['#FFE500', '#00E5FF', '#FF4D6D', '#7CFF6B', '#FFFFFF'];

/** Panel gaya teks — semua nilai di sini benar-benar sampai ke ffmpeg. */
export function StylePanel({ style, onChange, aspectRatio, onAspectChange }) {
  const set = (patch) => onChange({ ...style, ...patch });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
      <div>
        <div style={{ ...label, marginBottom: '8px' }}>Rasio video</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '6px' }}>
          {['9:16', '1:1', '4:5', '16:9'].map((r) => (
            <button key={r} onClick={() => onAspectChange(r)}
                    style={{
                      padding: '9px 0', fontSize: '0.78rem', fontWeight: 700, cursor: 'pointer',
                      borderRadius: 'var(--radius-sm)',
                      border: aspectRatio === r ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                      background: aspectRatio === r ? 'rgba(0,242,254,0.12)' : 'transparent',
                      color: aspectRatio === r ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                    }}>{r}</button>
          ))}
        </div>
      </div>

      <div>
        <div style={{ ...label, marginBottom: '8px' }}>Ukuran teks — {style.size}</div>
        <input type="range" min="56" max="140" step="4" value={style.size}
               onChange={(e) => set({ size: Number(e.target.value) })}
               style={{ width: '100%', accentColor: 'var(--accent-cyan)' }} />
      </div>

      <div>
        <div style={{ ...label, marginBottom: '8px' }}>Warna kata aktif</div>
        <div style={{ display: 'flex', gap: '8px' }}>
          {HIGHLIGHTS.map((c) => (
            <button key={c} onClick={() => set({ highlight: c })} aria-label={`Warna ${c}`}
                    style={{
                      width: '34px', height: '34px', borderRadius: '50%', cursor: 'pointer',
                      background: c,
                      border: style.highlight === c ? '3px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                    }} />
          ))}
        </div>
      </div>

      <div>
        <div style={{ ...label, marginBottom: '8px' }}>Font</div>
        <select value={style.font} onChange={(e) => set({ font: e.target.value })} style={field}>
          {FONT_CHOICES.map((f) => <option key={f} value={f}>{f}</option>)}
        </select>
      </div>

      <div>
        <div style={{ ...label, marginBottom: '8px' }}>Posisi teks</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px' }}>
          {[['top', 'Atas'], ['middle', 'Tengah'], ['bottom', 'Bawah']].map(([v, t]) => (
            <button key={v} onClick={() => set({ position: v })}
                    style={{
                      padding: '9px 0', fontSize: '0.78rem', fontWeight: 700, cursor: 'pointer',
                      borderRadius: 'var(--radius-sm)',
                      border: style.position === v ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                      background: style.position === v ? 'rgba(0,242,254,0.12)' : 'transparent',
                      color: style.position === v ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                    }}>{t}</button>
          ))}
        </div>
      </div>

      <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', fontSize: '0.84rem' }}>
        <input type="checkbox" checked={style.uppercase}
               onChange={(e) => set({ uppercase: e.target.checked })}
               style={{ accentColor: 'var(--accent-cyan)', width: '16px', height: '16px' }} />
        Huruf kapital semua
      </label>

      <div>
        <div style={{ ...label, marginBottom: '8px' }}>Animasi</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
          {[['karaoke_pop', 'Karaoke per kata'], ['block', 'Per baris']].map(([v, t]) => (
            <button key={v} onClick={() => set({ animation: v })}
                    style={{
                      padding: '9px 0', fontSize: '0.76rem', fontWeight: 700, cursor: 'pointer',
                      borderRadius: 'var(--radius-sm)',
                      border: style.animation === v ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                      background: style.animation === v ? 'rgba(0,242,254,0.12)' : 'transparent',
                      color: style.animation === v ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                    }}>{t}</button>
          ))}
        </div>
      </div>
    </div>
  );
}
