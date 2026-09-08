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
export function SubtitlePanel({ clip, onUpdate, onRemove, style, onAutoSpeakers }) {
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

  const color2 = style?.speaker2 ?? '#7CFFB2';
  const color1 = style?.primary ?? '#FFFFFF';
  const marked = lines.filter((l) => (l.speaker || 0) === 1).length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5 }}>
        {lines.length} baris. Perbaiki kata yang salah dengar langsung di sini, dan
        tekan lingkaran warna untuk menandai siapa yang bicara.
      </p>

      <button className="btn-secondary" onClick={() => onAutoSpeakers?.(clip.clip_id)}
              style={{ fontSize: '0.76rem', padding: '7px 10px', justifyContent: 'center' }}>
        Tandai otomatis dari jeda bicara
      </button>
      <p style={{ fontSize: '0.67rem', color: 'var(--text-muted)', margin: '-4px 0 0', lineHeight: 1.5 }}>
        Ini tebakan dari panjang jeda, bukan pengenalan suara — sistem tidak
        mendengar siapa yang bicara. Periksa dan perbaiki manual bila meleset.
        {marked > 0 && ` Saat ini ${marked} baris ditandai orang kedua.`}
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '380px', overflowY: 'auto' }}>
        {lines.map((line, i) => {
          const speaker = line.speaker || 0;
          return (
            <div key={i} style={{
              display: 'grid', gridTemplateColumns: '52px 22px 1fr 26px', gap: '7px',
              alignItems: 'center',
            }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
                {line.start.toFixed(1)}s
              </span>
              <button
                onClick={() => onUpdate(clip.clip_id, i, { speaker: speaker === 1 ? 0 : 1 })}
                title={speaker === 1 ? 'Orang kedua — klik untuk kembalikan' : 'Orang pertama — klik untuk tandai orang kedua'}
                aria-label="Ganti penanda pembicara"
                style={{
                  width: '20px', height: '20px', borderRadius: '50%', cursor: 'pointer',
                  background: speaker === 1 ? color2 : color1,
                  border: '2px solid var(--border-color)', padding: 0,
                }}
              />
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
          );
        })}
      </div>
    </div>
  );
}

const FONT_CHOICES = ['DejaVu Sans', 'Liberation Sans', 'Noto Sans', 'Ubuntu'];
const HIGHLIGHTS = ['#FFE500', '#00E5FF', '#FF4D6D', '#7CFF6B', '#FF9F1C', '#FFFFFF'];
const SPEAKER2_COLORS = ['#7CFFB2', '#FFB3C7', '#B39DFF', '#FFD166', '#FFFFFF'];

// Preset gaya. Bukan sekadar warna: tiap preset menyetel ukuran, animasi, dan
// posisi sekaligus, karena kombinasi itulah yang membuat sebuah gaya terbaca
// utuh — mengganti warna saja tidak mengubah kesannya.
const STYLE_PRESETS = [
  {
    id: 'tebal', label: 'Tebal', hint: 'Putih tebal, kata aktif kuning',
    patch: { size: 96, primary: '#FFFFFF', highlight: '#FFE500',
             uppercase: true, animation: 'karaoke_pop', position: 'bottom' },
  },
  {
    id: 'neon', label: 'Neon', hint: 'Besar, sorot biru elektrik',
    patch: { size: 110, primary: '#FFFFFF', highlight: '#00E5FF',
             uppercase: true, animation: 'karaoke_pop', position: 'bottom' },
  },
  {
    id: 'lembut', label: 'Lembut', hint: 'Huruf biasa, masuk memudar',
    patch: { size: 84, primary: '#FFFFFF', highlight: '#FFD166',
             uppercase: false, animation: 'fade', position: 'bottom' },
  },
  {
    id: 'naik', label: 'Naik', hint: 'Baris naik dari bawah',
    patch: { size: 92, primary: '#FFFFFF', highlight: '#7CFF6B',
             uppercase: true, animation: 'slide_up', position: 'bottom' },
  },
  {
    id: 'pop', label: 'Pop', hint: 'Baris membesar saat muncul',
    patch: { size: 100, primary: '#FFFFFF', highlight: '#FF4D6D',
             uppercase: true, animation: 'pop_in', position: 'bottom' },
  },
  {
    id: 'bersih', label: 'Bersih', hint: 'Tanpa animasi, tengah bawah',
    patch: { size: 88, primary: '#FFFFFF', highlight: '#FFFFFF',
             uppercase: false, animation: 'none', position: 'bottom' },
  },
];

const ANIMATIONS = [
  ['karaoke_pop', 'Karaoke pantul'],
  ['karaoke_wipe', 'Karaoke warna'],
  ['fade', 'Memudar'],
  ['slide_up', 'Naik'],
  ['pop_in', 'Membesar'],
  ['none', 'Tanpa animasi'],
];

function Segmented({ options, value, onChange, columns = 3, size = '0.76rem' }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${columns}, 1fr)`, gap: '6px' }}>
      {options.map(([v, t]) => (
        <button key={v} onClick={() => onChange(v)}
                style={{
                  padding: '9px 2px', fontSize: size, fontWeight: 700, cursor: 'pointer',
                  borderRadius: 'var(--radius-sm)',
                  border: value === v ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                  background: value === v ? 'rgba(0,242,254,0.12)' : 'transparent',
                  color: value === v ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                }}>{t}</button>
      ))}
    </div>
  );
}

function Swatches({ colors, value, onChange }) {
  return (
    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
      {colors.map((c) => (
        <button key={c} onClick={() => onChange(c)} aria-label={`Warna ${c}`}
                style={{
                  width: '32px', height: '32px', borderRadius: '50%', cursor: 'pointer',
                  background: c,
                  border: value === c ? '3px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                }} />
      ))}
    </div>
  );
}

/** Panel gaya teks — semua nilai di sini benar-benar sampai ke ffmpeg. */
export function StylePanel({
  style, onChange, aspectRatio, onAspectChange,
  showHook, onShowHookChange, hookText, onHookTextChange,
}) {
  const set = (patch) => onChange({ ...style, ...patch });
  const activePreset = STYLE_PRESETS.find(
    (p) => Object.entries(p.patch).every(([k, v]) => style[k] === v),
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
      <div>
        <div style={{ ...label, marginBottom: '8px' }}>Gaya siap pakai</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
          {STYLE_PRESETS.map((p) => {
            const on = activePreset?.id === p.id;
            return (
              <button key={p.id} onClick={() => set(p.patch)} title={p.hint}
                      style={{
                        padding: '8px 9px', textAlign: 'left', cursor: 'pointer',
                        borderRadius: 'var(--radius-sm)',
                        border: on ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                        background: on ? 'rgba(0,242,254,0.1)' : 'transparent',
                      }}>
                <div style={{
                  fontSize: '0.79rem', fontWeight: 800,
                  color: on ? 'var(--accent-cyan)' : 'var(--text-primary)',
                }}>{p.label}</div>
                <div style={{ fontSize: '0.66rem', color: 'var(--text-muted)', lineHeight: 1.35 }}>
                  {p.hint}
                </div>
              </button>
            );
          })}
        </div>
      </div>

      <div>
        <div style={{ ...label, marginBottom: '8px' }}>Rasio video</div>
        <Segmented columns={4} options={[['9:16', '9:16'], ['1:1', '1:1'], ['4:5', '4:5'], ['16:9', '16:9']]}
                   value={aspectRatio} onChange={onAspectChange} />
      </div>

      {/* Judul */}
      <div>
        <label style={{
          display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer',
          fontSize: '0.84rem', marginBottom: showHook ? '8px' : 0,
        }}>
          <input type="checkbox" checked={showHook}
                 onChange={(e) => onShowHookChange(e.target.checked)}
                 style={{ accentColor: 'var(--accent-cyan)', width: '16px', height: '16px' }} />
          Tampilkan judul di atas video
        </label>
        {showHook ? (
          <>
            <textarea value={hookText} rows={2}
                      onChange={(e) => onHookTextChange(e.target.value)}
                      placeholder="Ketik judul, atau biarkan kutipan otomatis"
                      style={{ ...field, resize: 'vertical', lineHeight: 1.4 }} />
            <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', margin: '6px 0 0', lineHeight: 1.5 }}>
              Judul bawaan diambil dari kalimat pembuka klip, jadi isinya selalu
              benar-benar diucapkan. Anda bisa menggantinya dengan teks sendiri.
            </p>
          </>
        ) : (
          <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', margin: '6px 0 0', lineHeight: 1.5 }}>
            Mati secara bawaan — hasilnya lebih bersih. Nyalakan bila klipnya
            butuh konteks pembuka.
          </p>
        )}
      </div>

      <div>
        <div style={{ ...label, marginBottom: '8px' }}>Ukuran teks — {style.size}</div>
        <input type="range" min="56" max="140" step="4" value={style.size}
               onChange={(e) => set({ size: Number(e.target.value) })}
               style={{ width: '100%', accentColor: 'var(--accent-cyan)' }} />
      </div>

      <div>
        <div style={{ ...label, marginBottom: '8px' }}>Warna kata aktif</div>
        <Swatches colors={HIGHLIGHTS} value={style.highlight}
                  onChange={(c) => set({ highlight: c })} />
      </div>

      <div>
        <div style={{ ...label, marginBottom: '8px' }}>Warna narasumber kedua</div>
        <Swatches colors={SPEAKER2_COLORS} value={style.speaker2 ?? '#7CFFB2'}
                  onChange={(c) => set({ speaker2: c })} />
        <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', margin: '7px 0 0', lineHeight: 1.5 }}>
          Dipakai untuk baris yang Anda tandai sebagai orang kedua di tab
          Subtitle, supaya percakapan dua orang bisa dibedakan sekilas.
        </p>
      </div>

      <div>
        <div style={{ ...label, marginBottom: '8px' }}>Animasi</div>
        <Segmented columns={2} options={ANIMATIONS} value={style.animation}
                   onChange={(v) => set({ animation: v })} />
      </div>

      <div>
        <div style={{ ...label, marginBottom: '8px' }}>Font</div>
        <select value={style.font} onChange={(e) => set({ font: e.target.value })} style={field}>
          {FONT_CHOICES.map((f) => <option key={f} value={f}>{f}</option>)}
        </select>
      </div>

      <div>
        <div style={{ ...label, marginBottom: '8px' }}>Posisi teks</div>
        <Segmented columns={3} options={[['top', 'Atas'], ['middle', 'Tengah'], ['bottom', 'Bawah']]}
                   value={style.position} onChange={(v) => set({ position: v })} />
      </div>

      <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', fontSize: '0.84rem' }}>
        <input type="checkbox" checked={style.uppercase}
               onChange={(e) => set({ uppercase: e.target.checked })}
               style={{ accentColor: 'var(--accent-cyan)', width: '16px', height: '16px' }} />
        Huruf kapital semua
      </label>
    </div>
  );
}
