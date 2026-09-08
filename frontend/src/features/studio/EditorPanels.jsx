import React, { useEffect, useState } from 'react';
import { Plus, Trash2, Loader2, Star, ChevronRight, Users } from 'lucide-react';
import { formatTime, parseTimeString } from '../../utils/timeFormat';
import { cachedFonts, fontStack, loadFonts } from '../../lib/fonts';
import {
  COLOR_GROUPS, COLOR_PAIRS, normalizeHex, useFavoriteColors, useRecentColors,
} from '../../lib/colors';

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
// Diindeks langsung: [0] milik orang pertama. Putih di posisi pertama supaya
// video satu narasumber tampil persis seperti sebelum fitur ini ada.
const DEFAULT_SPEAKER_COLORS = ['#FFFFFF', '#7CFFB2', '#FFB3C7', '#B39DFF',
                               '#FFD166', '#5BC8FF', '#FF9F1C', '#B8FF3A'];

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
export function SubtitlePanel({ clip, onUpdate, onRemove, style, onAutoSpeakers,
                               speakerCount = 2, speakerConfident = null,
                               onRedetect = null, redetecting = false }) {
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

  const palette = style?.speaker_colors ?? DEFAULT_SPEAKER_COLORS;
  const colorOf = (i) => palette[i] ?? style?.primary ?? '#FFFFFF';
  const total = Math.max(2, Math.min(8, speakerCount || 2));
  const tally = lines.reduce((acc, l) => {
    const i = l.speaker || 0;
    acc[i] = (acc[i] || 0) + 1;
    return acc;
  }, {});

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5 }}>
        {lines.length} baris. Perbaiki kata yang salah dengar langsung di sini, dan
        tekan lingkaran warna untuk menandai siapa yang bicara.
      </p>

      <div style={{
        padding: '10px 11px', borderRadius: 'var(--radius-sm)',
        background: 'var(--bg-glass)', border: '1px solid var(--border-color)',
      }}>
        <div style={{ fontSize: '0.75rem', fontWeight: 700, marginBottom: '4px' }}>
          {speakerConfident === null ? 'Penanda penutur'
            : speakerConfident
              ? `Terdeteksi ${speakerCount} narasumber`
              : 'Suara sulit dipisahkan otomatis'}
        </div>
        <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.55 }}>
          {speakerConfident === false
            ? 'Sistem harus menebak dua hal sekaligus: berapa orangnya, dan '
              + 'siapa bicara kapan. Yang pertama paling sering meleset — kalau '
              + 'Anda sudah tahu jumlahnya, isikan di bawah dan sisanya biasanya ikut membaik.'
            : 'Ditebak dari warna suara. Kalau jumlahnya keliru, setel sendiri '
              + 'di bawah lalu deteksi ulang.'}
        </p>

        {onRedetect && <SpeakerCountPicker current={speakerCount} busy={redetecting}
                                          onRedetect={onRedetect} />}

        <button className="btn-secondary" onClick={() => onAutoSpeakers?.(clip.clip_id)}
                disabled={redetecting}
                style={{ fontSize: '0.72rem', padding: '6px 9px', marginTop: '8px' }}>
          Tandai ulang dari jeda bicara
        </button>
        <p style={{ fontSize: '0.65rem', color: 'var(--text-muted)', margin: '5px 0 0', lineHeight: 1.5 }}>
          Cara cepat tanpa mendengarkan ulang: menganggap jeda panjang sebagai
          pergantian giliran. Hanya berlaku untuk klip ini.
        </p>
      </div>

      {/* Berapa baris yang jatuh ke tiap orang, dengan warnanya. Selama semua
          baris masih orang 1, mengganti warna di tab Gaya memang tidak akan
          mengubah apa pun — itu harus terlihat di sini, bukan ditebak. */}
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
        {Object.keys(tally).sort().map((k) => (
          <span key={k} style={{
            display: 'inline-flex', alignItems: 'center', gap: '5px', padding: '3px 8px',
            borderRadius: '99px', fontSize: '0.68rem', fontWeight: 700,
            background: 'var(--bg-glass)', border: '1px solid var(--border-color)',
          }}>
            <span style={{
              width: '10px', height: '10px', borderRadius: '50%',
              background: colorOf(Number(k)), border: '1px solid rgba(0,0,0,0.4)',
            }} />
            Orang {Number(k) + 1} · {tally[k]} baris
          </span>
        ))}
      </div>

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
                onClick={() => onUpdate(clip.clip_id, i, { speaker: (speaker + 1) % total })}
                title={`Orang ${speaker + 1} — klik untuk ganti`}
                aria-label="Ganti penanda pembicara"
                style={{
                  width: '20px', height: '20px', borderRadius: '50%', cursor: 'pointer',
                  background: colorOf(speaker), border: '2px solid var(--border-color)',
                  padding: 0, fontSize: '0.6rem', fontWeight: 900, color: '#00121a',
                }}
              >{speaker + 1}</button>
              <input
                value={line.text}
                onChange={(e) => onUpdate(clip.clip_id, i, { text: e.target.value })}
                style={{
                  ...field, fontSize: '0.8rem', padding: '7px 9px',
                  // Warna penutur dipakai langsung di kotak isian: menandai satu
                  // baris jadi terlihat hasilnya di detik itu juga, tanpa harus
                  // menunggu playhead kebetulan lewat di baris tersebut.
                  color: colorOf(speaker),
                  fontWeight: speaker ? 700 : 400,
                }}
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

/**
 * Memberitahukan jumlah narasumber kepada sistem.
 *
 * Menebak jumlah kelompok adalah bagian paling rapuh dari pemisahan suara
 * otomatis — jauh lebih rapuh daripada menentukan siapa bicara kapan begitu
 * jumlahnya diketahui. Pengguna sudah menonton videonya dan tahu jawabannya,
 * jadi membiarkannya menjawab menghapus separuh kesulitannya.
 */
function SpeakerCountPicker({ current, busy, onRedetect }) {
  const [value, setValue] = useState(Math.max(1, Math.min(6, current || 2)));
  return (
    <div style={{ marginTop: '10px' }}>
      <div style={{ ...label, fontSize: '0.66rem', marginBottom: '6px' }}>
        Jumlah narasumber
      </div>
      <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
        {[1, 2, 3, 4, 5, 6].map((n) => (
          <button key={n} onClick={() => setValue(n)} disabled={busy}
                  style={{
                    width: '30px', height: '30px', borderRadius: '7px',
                    cursor: busy ? 'default' : 'pointer', fontWeight: 800, fontSize: '0.8rem',
                    border: value === n ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                    background: value === n ? 'rgba(0,242,254,0.12)' : 'transparent',
                    color: value === n ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                  }}>{n}</button>
        ))}
      </div>
      <div style={{ display: 'flex', gap: '6px', marginTop: '8px', flexWrap: 'wrap' }}>
        <button className="btn-primary" disabled={busy}
                onClick={() => onRedetect(value)}
                style={{ fontSize: '0.73rem', padding: '6px 10px' }}>
          {busy ? <Loader2 size={13} className="animate-spin" /> : <Users size={13} />}
          Deteksi ulang dengan {value} orang
        </button>
        <button className="btn-secondary" disabled={busy}
                onClick={() => onRedetect(null)}
                style={{ fontSize: '0.73rem', padding: '6px 10px' }}>
          Biar sistem menebak
        </button>
      </div>
      <p style={{ fontSize: '0.65rem', color: 'var(--text-muted)', margin: '6px 0 0', lineHeight: 1.5 }}>
        Menandai ulang seluruh klip dari suaranya. Butuh sekitar dua menit untuk
        video satu jam — transkripnya tidak diulang.
      </p>
    </div>
  );
}

// --- Gaya teks ----------------------------------------------------------------


// Preset gaya. Bukan sekadar warna: tiap preset menyetel ukuran, animasi, font,
// dan posisi sekaligus, karena kombinasi itulah yang membuat sebuah gaya
// terbaca utuh — mengganti warna saja tidak mengubah kesannya.
const STYLE_PRESETS = [
  {
    id: 'tebal', label: 'Tebal', hint: 'Putih tebal, kata aktif kuning',
    patch: { size: 96, primary: '#FFFFFF', highlight: '#FFE500', font: 'Montserrat',
             uppercase: true, animation: 'karaoke_pop', position: 'bottom', outline_px: 7 },
  },
  {
    id: 'neon', label: 'Neon', hint: 'Besar, sorot biru elektrik',
    patch: { size: 110, primary: '#FFFFFF', highlight: '#00E5FF', font: 'Anton',
             uppercase: true, animation: 'karaoke_pop', position: 'bottom', outline_px: 8 },
  },
  {
    id: 'lembut', label: 'Lembut', hint: 'Huruf biasa, masuk memudar',
    patch: { size: 84, primary: '#FFFFFF', highlight: '#FFD166', font: 'Poppins',
             uppercase: false, animation: 'fade', position: 'bottom', outline_px: 5 },
  },
  {
    id: 'naik', label: 'Naik', hint: 'Baris naik dari bawah',
    patch: { size: 92, primary: '#FFFFFF', highlight: '#7CFF6B', font: 'Oswald',
             uppercase: true, animation: 'slide_up', position: 'bottom', outline_px: 7 },
  },
  {
    id: 'papan', label: 'Papan', hint: 'Blok tebal, sangat mencolok',
    patch: { size: 88, primary: '#FFFFFF', highlight: '#FF4D6D', font: 'Archivo Black',
             uppercase: true, animation: 'pop_in', position: 'bottom', outline_px: 9 },
  },
  {
    id: 'ramping', label: 'Ramping', hint: 'Sempit, banyak kata muat',
    patch: { size: 116, primary: '#FFFFFF', highlight: '#00F5D4', font: 'Bebas Neue',
             uppercase: true, animation: 'karaoke_wipe', position: 'bottom', outline_px: 6 },
  },
  {
    id: 'ceria', label: 'Ceria', hint: 'Bulat, gaya kartun',
    patch: { size: 94, primary: '#FFFFFF', highlight: '#FF9F1C', font: 'Lilita One',
             uppercase: true, animation: 'pop_in', position: 'bottom', outline_px: 8 },
  },
  {
    id: 'bersih', label: 'Bersih', hint: 'Tanpa animasi, tengah bawah',
    patch: { size: 88, primary: '#FFFFFF', highlight: '#FFFFFF', font: 'Rubik',
             uppercase: false, animation: 'none', position: 'bottom', outline_px: 5 },
  },
];

/**
 * Contoh sebuah preset, digambar memakai gaya preset itu sendiri.
 *
 * Daftar berbentuk teks tidak pernah menjawab pertanyaan yang sebenarnya
 * ditanyakan pengguna — "yang mana yang kelihatannya bagus?" — dan menjawabnya
 * dengan mencoba satu per satu berarti melewati render tiap kali. Petak ini
 * memakai nilai preset yang persis sama dengan yang dikirim ke ffmpeg.
 */
function PresetTile({ preset, active, onPick }) {
  const p = preset.patch;
  const words = p.uppercase ? ['AYO', 'MULAI'] : ['Ayo', 'mulai'];
  return (
    <button onClick={onPick} title={preset.hint}
            style={{
              padding: 0, cursor: 'pointer', overflow: 'hidden',
              borderRadius: 'var(--radius-sm)',
              border: active ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
              background: 'transparent',
            }}>
      <div style={{
        // Latar gelap sedikit bergradasi meniru bingkai video: teks putih di
        // atas putih tidak akan memberi tahu apa pun tentang keterbacaannya.
        background: 'linear-gradient(160deg, #1d2430 0%, #0d1119 100%)',
        padding: '15px 8px', display: 'flex', alignItems: 'center',
        justifyContent: 'center', gap: '0.28em', minHeight: '58px',
        fontFamily: fontStack(p.font), fontWeight: 800, fontSize: '0.92rem',
        lineHeight: 1.1, letterSpacing: '0.01em',
        WebkitTextStroke: `${Math.max(0.5, (p.outline_px ?? 7) * 0.16)}px #000`,
        paintOrder: 'stroke fill',
      }}>
        <span style={{ color: p.primary }}>{words[0]}</span>
        <span style={{ color: p.highlight }}>{words[1]}</span>
      </div>
      <div style={{
        padding: '5px 7px 6px', textAlign: 'left',
        background: active ? 'rgba(0,242,254,0.1)' : 'transparent',
      }}>
        <div style={{
          fontSize: '0.74rem', fontWeight: 800,
          color: active ? 'var(--accent-cyan)' : 'var(--text-primary)',
        }}>{preset.label}</div>
        <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', lineHeight: 1.3 }}>
          {preset.hint}
        </div>
      </div>
    </button>
  );
}

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

function Swatch({ color, selected, onClick, size = 26, title }) {
  return (
    <button onClick={onClick} title={title || color} aria-label={`Warna ${color}`}
            style={{
              width: `${size}px`, height: `${size}px`, borderRadius: '50%',
              cursor: 'pointer', background: color, padding: 0, flex: 'none',
              border: selected ? '3px solid var(--accent-cyan)'
                : '1px solid rgba(255,255,255,0.25)',
              boxShadow: selected ? '0 0 0 2px rgba(0,242,254,0.25)' : 'none',
            }} />
  );
}

/**
 * Pemilih warna: palet rekomendasi, favorit, riwayat, dan warna bebas.
 *
 * Ketiga baris teratas ada karena alasan berbeda. Palet menjawab "warna apa
 * yang aman terbaca di atas video"; favorit menjawab "warna merek saya";
 * riwayat menjawab "warna yang barusan saya pakai di klip sebelah" — dan
 * ketiganya hilang kalau yang tersedia hanya enam bulatan tetap.
 */
function ColorPicker({ value, onChange }) {
  const [favs, toggleFav] = useFavoriteColors();
  const [recent, remember] = useRecentColors();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(value);

  useEffect(() => setDraft(value), [value]);

  const pick = (c) => {
    const hex = normalizeHex(c);
    if (!hex) return;
    onChange(hex);
    remember(hex);
  };

  const isFav = favs.includes(normalizeHex(value) || '');

  return (
    <div style={{
      border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)',
      background: 'var(--bg-glass)', padding: '8px 9px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Swatch color={value} selected size={24} />
        <code style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', flex: 1 }}>
          {value}
        </code>
        <button onClick={() => toggleFav(value)} title={isFav ? 'Hapus dari favorit' : 'Simpan ke favorit'}
                aria-label="Favoritkan warna"
                style={{
                  background: 'none', border: 'none', cursor: 'pointer', display: 'flex',
                  color: isFav ? '#FFD166' : 'var(--text-muted)', padding: '2px',
                }}>
          <Star size={15} fill={isFav ? '#FFD166' : 'none'} />
        </button>
        <button onClick={() => setOpen((v) => !v)}
                style={{
                  background: 'none', border: '1px solid var(--border-color)',
                  borderRadius: '6px', cursor: 'pointer', fontSize: '0.7rem',
                  padding: '3px 8px', color: 'var(--text-secondary)', fontWeight: 700,
                }}>
          {open ? 'Tutup' : 'Pilih'}
        </button>
      </div>

      {open && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '9px', marginTop: '10px' }}>
          {favs.length > 0 && (
            <Row title="Favorit" colors={favs} value={value} onPick={pick} />
          )}
          {recent.length > 0 && (
            <Row title="Terakhir dipakai" colors={recent} value={value} onPick={pick} />
          )}
          {COLOR_GROUPS.map((g) => (
            <Row key={g.name} title={g.name} colors={g.colors} value={value} onPick={pick} />
          ))}

          <div>
            <div style={{ ...label, fontSize: '0.66rem', marginBottom: '5px' }}>Warna bebas</div>
            <div style={{ display: 'flex', gap: '7px', alignItems: 'center' }}>
              <input type="color" value={normalizeHex(value) || '#FFFFFF'}
                     onChange={(e) => pick(e.target.value)}
                     aria-label="Pemilih warna bebas"
                     style={{
                       width: '38px', height: '32px', padding: 0, cursor: 'pointer',
                       background: 'none', border: '1px solid var(--border-color)',
                       borderRadius: '6px',
                     }} />
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onBlur={() => (normalizeHex(draft) ? pick(draft) : setDraft(value))}
                onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
                placeholder="#FFE500"
                style={{ ...field, fontSize: '0.78rem', padding: '7px 9px', flex: 1 }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ title, colors, value, onPick }) {
  return (
    <div>
      <div style={{ ...label, fontSize: '0.66rem', marginBottom: '5px' }}>{title}</div>
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
        {colors.map((c) => (
          <Swatch key={c} color={c} selected={normalizeHex(c) === normalizeHex(value)}
                  onClick={() => onPick(c)} size={24} />
        ))}
      </div>
    </div>
  );
}

/** Satu bagian panel gaya. Hanya satu yang terbuka, supaya kolomnya tetap pendek. */
function Section({ id, title, note, openId, setOpenId, children }) {
  const open = openId === id;
  return (
    <div style={{
      border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)',
      overflow: 'hidden', background: open ? 'var(--bg-glass)' : 'transparent',
    }}>
      <button onClick={() => setOpenId(open ? null : id)}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: '8px',
                padding: '10px 11px', cursor: 'pointer', background: 'none',
                border: 'none', textAlign: 'left', color: 'inherit',
              }}>
        <ChevronRight size={14} style={{
          flex: 'none', color: 'var(--text-muted)',
          transform: open ? 'rotate(90deg)' : 'none', transition: 'transform 120ms',
        }} />
        <span style={{ fontSize: '0.79rem', fontWeight: 800, flex: 1 }}>{title}</span>
        {note && (
          <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>{note}</span>
        )}
      </button>
      {open && (
        <div style={{ padding: '2px 11px 13px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {children}
        </div>
      )}
    </div>
  );
}

/** Panel gaya teks — semua nilai di sini benar-benar sampai ke ffmpeg. */
export function StylePanel({
  style, onChange, aspectRatio, onAspectChange,
  showHook, onShowHookChange, hookText, onHookTextChange,
  speakerCount = 2,
  // Bagian yang terbuka saat panel dibuka. Bisa disetel dari luar supaya uji
  // asap bisa merender isi tiap bagian — isi bagian yang tertutup tidak pernah
  // dijalankan, jadi kesalahan di dalamnya tidak akan tertangkap.
  defaultSection = 'preset',
}) {
  const [openId, setOpenId] = useState(defaultSection);
  const [fonts, setFonts] = useState(cachedFonts);

  useEffect(() => { loadFonts().then(setFonts); }, []);

  const set = (patch) => onChange({ ...style, ...patch });
  const activePreset = STYLE_PRESETS.find(
    (p) => Object.entries(p.patch).every(([k, v]) => style[k] === v),
  );
  const speakers = Math.max(1, Math.min(8, speakerCount || 1));
  const palette = style.speaker_colors ?? DEFAULT_SPEAKER_COLORS;
  const fontLabel = fonts.find((f) => f.family === style.font)?.label ?? style.font;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '7px' }}>
      <Section id="preset" title="Gaya siap pakai" note={activePreset?.label ?? 'ubahan sendiri'}
               openId={openId} setOpenId={setOpenId}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '7px' }}>
          {STYLE_PRESETS.map((p) => (
            <PresetTile key={p.id} preset={p} active={activePreset?.id === p.id}
                        onPick={() => set(p.patch)} />
          ))}
        </div>
        <p style={{ fontSize: '0.67rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>
          Tiap contoh digambar dengan font, warna, dan huruf besar-kecil yang
          sebenarnya akan dipakai — jadi yang terlihat di sini itulah yang
          dibakar ke video.
        </p>
      </Section>

      <Section id="warna" title="Warna" openId={openId} setOpenId={setOpenId}
               note={<span style={{ display: 'inline-flex', gap: '3px' }}>
                 <Swatch color={style.primary} size={13} />
                 <Swatch color={style.highlight} size={13} />
               </span>}>
        <div>
          <div style={{ ...label, marginBottom: '7px' }}>Pasangan rekomendasi</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
            {COLOR_PAIRS.map((c) => {
              const on = style.primary === c.primary && style.highlight === c.highlight;
              return (
                <button key={c.id}
                        onClick={() => set({ primary: c.primary, highlight: c.highlight })}
                        style={{
                          display: 'flex', alignItems: 'center', gap: '7px', cursor: 'pointer',
                          padding: '6px 8px', borderRadius: 'var(--radius-sm)',
                          border: on ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                          background: on ? 'rgba(0,242,254,0.1)' : 'transparent',
                        }}>
                  <span style={{ display: 'flex' }}>
                    <span style={{
                      width: '14px', height: '14px', borderRadius: '50%',
                      background: c.primary, border: '1px solid rgba(0,0,0,0.4)',
                    }} />
                    <span style={{
                      width: '14px', height: '14px', borderRadius: '50%', marginLeft: '-5px',
                      background: c.highlight, border: '1px solid rgba(0,0,0,0.4)',
                    }} />
                  </span>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-secondary)' }}>
                    {c.name}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <div style={{ ...label, marginBottom: '6px' }}>Warna teks</div>
          <ColorPicker value={style.primary ?? '#FFFFFF'} onChange={(c) => set({ primary: c })} />
        </div>

        <div>
          <div style={{ ...label, marginBottom: '6px' }}>Warna kata aktif</div>
          <ColorPicker value={style.highlight ?? '#FFE500'} onChange={(c) => set({ highlight: c })} />
        </div>

        <div>
          <div style={{ ...label, marginBottom: '6px' }}>
            Warna per narasumber
          </div>
          <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', margin: '0 0 9px', lineHeight: 1.5 }}>
            Berlaku untuk baris yang ditandai di tab <strong>Subtitle</strong>.
            Deteksi otomatis mengisinya lebih dulu; kalau meleset, setel jumlah
            orangnya di tab Subtitle lalu betulkan barisnya di sana.
          </p>
          {Array.from({ length: speakers }, (_, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '9px', marginBottom: '7px' }}>
              <span style={{
                fontSize: '0.74rem', width: '58px', flex: 'none',
                color: 'var(--text-secondary)', fontWeight: 700,
              }}>
                Orang {i + 1}
              </span>
              <div style={{ flex: 1 }}>
                <ColorPicker
                  value={palette[i] ?? DEFAULT_SPEAKER_COLORS[i] ?? '#FFFFFF'}
                  onChange={(c) => {
                    const next = [...(style.speaker_colors ?? DEFAULT_SPEAKER_COLORS)];
                    while (next.length <= i) next.push(DEFAULT_SPEAKER_COLORS[next.length] ?? '#FFFFFF');
                    next[i] = c;
                    set({ speaker_colors: next });
                  }}
                />
              </div>
            </div>
          ))}
          <button className="btn-secondary"
                  onClick={() => set({ speaker_colors: [...DEFAULT_SPEAKER_COLORS] })}
                  style={{ fontSize: '0.73rem', padding: '6px 9px', marginTop: '4px' }}>
            Kembalikan warna bawaan
          </button>
        </div>
      </Section>

      <Section id="font" title="Font & ukuran" note={fontLabel}
               openId={openId} setOpenId={setOpenId}>
        <div>
          <div style={{ ...label, marginBottom: '7px' }}>Font — {fonts.length} pilihan</div>
          <div style={{
            display: 'flex', flexDirection: 'column', gap: '5px',
            maxHeight: '250px', overflowY: 'auto', paddingRight: '3px',
          }}>
            {fonts.map((f) => {
              const on = style.font === f.family;
              return (
                <button key={f.family} onClick={() => set({ font: f.family })}
                        style={{
                          display: 'flex', alignItems: 'baseline', gap: '8px', cursor: 'pointer',
                          padding: '7px 9px', textAlign: 'left', borderRadius: 'var(--radius-sm)',
                          border: on ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                          background: on ? 'rgba(0,242,254,0.1)' : 'transparent',
                        }}>
                  {/* Nama font digambar DENGAN font itu sendiri: bedanya harus
                      terlihat sebelum dipilih, bukan setelah dirender. */}
                  <span style={{
                    fontFamily: fontStack(f.family), fontSize: '0.98rem', fontWeight: 800,
                    color: on ? 'var(--accent-cyan)' : 'var(--text-primary)',
                    textTransform: 'uppercase', letterSpacing: '0.01em',
                  }}>{f.label}</span>
                  <span style={{ fontSize: '0.63rem', color: 'var(--text-muted)' }}>{f.note}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <div style={{ ...label, marginBottom: '8px' }}>Ukuran teks — {style.size}</div>
          <input type="range" min="44" max="190" step="2" value={style.size}
                 onChange={(e) => set({ size: Number(e.target.value) })}
                 style={{ width: '100%', accentColor: 'var(--accent-cyan)' }} />
          <p style={{ fontSize: '0.67rem', color: 'var(--text-muted)', margin: '5px 0 0' }}>
            Bisa juga ditarik langsung lewat bulatan di sudut subtitle pada pratinjau.
          </p>
        </div>

        <div>
          <div style={{ ...label, marginBottom: '8px' }}>
            Tebal garis luar — {style.outline_px ?? 7}
          </div>
          <input type="range" min="0" max="14" step="1" value={style.outline_px ?? 7}
                 onChange={(e) => set({ outline_px: Number(e.target.value) })}
                 style={{ width: '100%', accentColor: 'var(--accent-cyan)' }} />
          <p style={{ fontSize: '0.67rem', color: 'var(--text-muted)', margin: '5px 0 0', lineHeight: 1.5 }}>
            Garis hitam inilah yang menjaga teks tetap terbaca di atas latar terang.
            Nol berarti teks polos — bagus di atas gambar gelap, hilang di atas langit.
          </p>
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', fontSize: '0.84rem' }}>
          <input type="checkbox" checked={style.uppercase}
                 onChange={(e) => set({ uppercase: e.target.checked })}
                 style={{ accentColor: 'var(--accent-cyan)', width: '16px', height: '16px' }} />
          Huruf kapital semua
        </label>
      </Section>

      <Section id="posisi" title="Posisi & animasi" openId={openId} setOpenId={setOpenId}
               note={ANIMATIONS.find(([v]) => v === style.animation)?.[1]}>
        <div>
          <div style={{ ...label, marginBottom: '8px' }}>Jangkar teks</div>
          <Segmented columns={3} options={[['top', 'Atas'], ['middle', 'Tengah'], ['bottom', 'Bawah']]}
                     value={style.position} onChange={(v) => set({ position: v })} />
        </div>

        {style.position !== 'middle' && (
          <div>
            <div style={{ ...label, marginBottom: '8px' }}>
              Jarak dari tepi {style.position === 'top' ? 'atas' : 'bawah'} — {style.margin_v ?? 300}
            </div>
            <input type="range" min="60" max="1200" step="10" value={style.margin_v ?? 300}
                   onChange={(e) => set({ margin_v: Number(e.target.value) })}
                   style={{ width: '100%', accentColor: 'var(--accent-cyan)' }} />
            <p style={{ fontSize: '0.67rem', color: 'var(--text-muted)', margin: '5px 0 0' }}>
              Atau seret langsung subtitlenya di pratinjau.
            </p>
          </div>
        )}

        <div>
          <div style={{ ...label, marginBottom: '8px' }}>
            Lebar kotak teks — {Math.round(style.box_w ?? 84)}%
          </div>
          <input type="range" min="20" max="100" step="1" value={style.box_w ?? 84}
                 onChange={(e) => set({ box_w: Number(e.target.value) })}
                 style={{ width: '100%', accentColor: 'var(--accent-cyan)' }} />
          <p style={{ fontSize: '0.67rem', color: 'var(--text-muted)', margin: '5px 0 0', lineHeight: 1.5 }}>
            Menentukan di lebar berapa baris subtitle mulai dibungkus. Kotak
            sempit memberi baris pendek yang menumpuk — gaya yang biasa dipakai
            klip vertikal. Bisa juga ditarik langsung lewat batang di kiri/kanan
            subtitle pada pratinjau.
          </p>
        </div>

        <div>
          <div style={{ ...label, marginBottom: '8px' }}>
            Posisi mendatar — {Math.round(style.pos_x ?? 50)}%
          </div>
          <input type="range" min="0" max="100" step="1" value={style.pos_x ?? 50}
                 onChange={(e) => set({ pos_x: Number(e.target.value) })}
                 style={{ width: '100%', accentColor: 'var(--accent-cyan)' }} />
        </div>

        <div>
          <div style={{ ...label, marginBottom: '8px' }}>Animasi</div>
          <Segmented columns={2} options={ANIMATIONS} value={style.animation}
                     onChange={(v) => set({ animation: v })} />
        </div>
      </Section>

      <Section id="judul" title="Judul di atas video" openId={openId} setOpenId={setOpenId}
               note={showHook ? 'aktif' : 'mati'}>
        <label style={{
          display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer',
          fontSize: '0.84rem',
        }}>
          <input type="checkbox" checked={showHook}
                 onChange={(e) => onShowHookChange(e.target.checked)}
                 style={{ accentColor: 'var(--accent-cyan)', width: '16px', height: '16px' }} />
          Tampilkan judul
        </label>
        {showHook ? (
          <div>
            <textarea value={hookText} rows={2}
                      onChange={(e) => onHookTextChange(e.target.value)}
                      placeholder="Ketik judul, atau biarkan kutipan otomatis"
                      style={{ ...field, resize: 'vertical', lineHeight: 1.4 }} />
            <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', margin: '6px 0 0', lineHeight: 1.5 }}>
              Judul bawaan diambil dari kalimat pembuka klip, jadi isinya selalu
              benar-benar diucapkan. Anda bisa menggantinya dengan teks sendiri.
            </p>
          </div>
        ) : (
          <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>
            Mati secara bawaan — hasilnya lebih bersih. Nyalakan bila klipnya
            butuh konteks pembuka.
          </p>
        )}
      </Section>

      <Section id="rasio" title="Rasio video" note={aspectRatio}
               openId={openId} setOpenId={setOpenId}>
        <Segmented columns={4} options={[['9:16', '9:16'], ['1:1', '1:1'], ['4:5', '4:5'], ['16:9', '16:9']]}
                   value={aspectRatio} onChange={onAspectChange} />
      </Section>
    </div>
  );
}
