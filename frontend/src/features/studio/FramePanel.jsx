import React from 'react';
import { Plus, Trash2, ArrowUp, ArrowDown, ScanFace } from 'lucide-react';
import {
  LAYOUT_PRESETS, addedFrame, clampRect, frameInk, presetLayout,
} from './frames';

export const FRAME_MODES = [
  { id: 'smart', label: 'Ikuti wajah', hint: 'Kamera mengikuti pembicara. Layar penuh, tanpa bilah kabur.' },
  { id: 'layout', label: 'Susun sendiri', hint: 'Satu bingkai atau lebih, masing-masing bisa diatur letak dan ukurannya.' },
  { id: 'blur', label: 'Bilah kabur', hint: 'Video utuh di tengah, sisi atas-bawah diisi versi kabur.' },
  { id: 'center', label: 'Potong tengah', hint: 'Ambil bagian tengah frame. Paling cepat, tanpa analisis.' },
  { id: 'original', label: 'Orisinal', hint: 'Bingkai video sumber apa adanya, tanpa dipotong sama sekali.' },
];

/**
 * Tab Bingkai.
 *
 * Susunannya mengikuti urutan pekerjaannya: pilih caranya, lalu — kalau
 * disusun sendiri — pilih titik berangkat dari susunan siap pakai, baru
 * setel tiap bingkainya. Angka di bagian bawah adalah untuk membetulkan hasil
 * seretan sampai persis, bukan untuk menggantikannya.
 */
export default function FramePanel({
  frameMode, onFrameModeChange,
  layout, onLayoutChange,
  selectedFrameId, onSelectFrame,
  faceTrackAvailable = false,
}) {
  const frames = layout?.frames ?? [];
  const selected = frames.find((f) => f.id === selectedFrameId) ?? frames[0] ?? null;

  const patch = (id, key, rect) => onLayoutChange({
    ...layout,
    frames: layout.frames.map((f) => (f.id === id ? { ...f, [key]: clampRect(rect) } : f)),
  });

  const setField = (id, patchObj) => onLayoutChange({
    ...layout,
    frames: layout.frames.map((f) => (f.id === id ? { ...f, ...patchObj } : f)),
  });

  const remove = (id) => {
    const next = frames.filter((f) => f.id !== id);
    onLayoutChange({ ...layout, frames: next });
    if (selectedFrameId === id) onSelectFrame(next[0]?.id ?? null);
  };

  /** Urutan daftar = urutan tumpukan. Yang di bawah daftar tergambar di atas. */
  const move = (id, dir) => {
    const i = frames.findIndex((f) => f.id === id);
    const j = i + dir;
    if (i < 0 || j < 0 || j >= frames.length) return;
    const next = [...frames];
    [next[i], next[j]] = [next[j], next[i]];
    onLayoutChange({ ...layout, frames: next });
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '9px' }}>
      <div className="mark" style={{ color: 'var(--ink)' }}>Cara membingkai</div>
      {FRAME_MODES.map((m) => (
        <button key={m.id} onClick={() => onFrameModeChange(m.id)}
                className={`choice${frameMode === m.id ? ' is-on' : ''}`}>
          <div className="choice-t">{m.label}</div>
          <div className="choice-h">{m.hint}</div>
        </button>
      ))}

      {frameMode !== 'layout' && (
        <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.5, margin: '4px 0 0' }}>
          Mode ikut-wajah menganalisis klip sebelum render. Bila wajah jarang
          terlihat — misalnya rekaman layar — sistem otomatis memakai bilah kabur.
          Untuk klip main game atau reaksi streamer, pakai <b>Susun sendiri</b>.
        </p>
      )}

      {frameMode === 'layout' && layout && (
        <>
          <div style={{ height: '1px', background: 'var(--rule-2)', margin: '4px 0' }} />

          <div className="mark" style={{ color: 'var(--ink)' }}>Mulai dari susunan</div>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {LAYOUT_PRESETS.map((p) => (
              <button key={p.id} className="chip" title={p.hint}
                      onClick={() => {
                        const next = presetLayout(p.id);
                        onLayoutChange({ ...next, background: layout.background });
                        onSelectFrame(next.frames[0].id);
                      }}>
                {p.label}
              </button>
            ))}
          </div>

          <div className="mark" style={{ color: 'var(--ink)', marginTop: '6px' }}>
            Isi celah antar bingkai
          </div>
          <div style={{ display: 'flex', gap: '6px' }}>
            {[['blur', 'Kabur dari sumber'], ['black', 'Hitam pekat']].map(([id, label]) => (
              <button key={id} className={`chip${layout.background === id ? ' is-on' : ''}`}
                      onClick={() => onLayoutChange({ ...layout, background: id })}>
                {label}
              </button>
            ))}
          </div>

          <div className="plate-head" style={{ marginTop: '8px', padding: '0 0 6px' }}>
            <span className="mark" style={{ color: 'var(--ink)' }}>
              Bingkai ({frames.length})
            </span>
            <button className="btn-secondary" style={{ marginLeft: 'auto', fontSize: '.72rem', padding: '5px 8px' }}
                    onClick={() => {
                      const f = addedFrame(frames);
                      onLayoutChange({ ...layout, frames: [...frames, f] });
                      onSelectFrame(f.id);
                    }}>
              <Plus size={12} /> Tambah
            </button>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
            {frames.map((f, i) => (
              <div key={f.id}
                   className={`frame-row${f.id === selected?.id ? ' is-on' : ''}`}
                   onClick={() => onSelectFrame(f.id)}>
                <span className="frame-swatch" style={{ background: frameInk(i) }} />
                <input value={f.label} className="field"
                       onClick={(e) => e.stopPropagation()}
                       onChange={(e) => setField(f.id, { label: e.target.value })}
                       style={{ flex: 1, minWidth: 0, padding: '4px 7px', fontSize: '.78rem' }} />
                <IconBtn title={f.follow ? 'Berhenti mengikuti orang' : 'Ikuti orang'}
                         active={f.follow}
                         onClick={(e) => { e.stopPropagation(); setField(f.id, { follow: !f.follow }); }}>
                  <ScanFace size={12} />
                </IconBtn>
                <IconBtn title="Naikkan" onClick={(e) => { e.stopPropagation(); move(f.id, -1); }}>
                  <ArrowUp size={12} />
                </IconBtn>
                <IconBtn title="Turunkan" onClick={(e) => { e.stopPropagation(); move(f.id, 1); }}>
                  <ArrowDown size={12} />
                </IconBtn>
                <IconBtn title="Hapus bingkai" danger
                         disabled={frames.length <= 1}
                         onClick={(e) => { e.stopPropagation(); remove(f.id); }}>
                  <Trash2 size={12} />
                </IconBtn>
              </div>
            ))}
          </div>

          <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.5, margin: '2px 0 0' }}>
            Urutan daftar adalah urutan tumpukan: yang paling bawah tergambar
            paling atas. Seret kotak di video sumber untuk memilih bagian yang
            diambil, dan kotak di kanvas hasil untuk menaruhnya.
          </p>

          {/* Ikuti orang. Ditaruh di sini, bukan sebagai mode tersendiri:
              "ikuti wajah" dan "susun sendiri" bukan dua pilihan yang saling
              meniadakan — bingkai reaksi yang mengikuti gamer di atas gameplay
              yang diam adalah satu susunan, bukan dua. */}
          <div style={{
            display: 'flex', gap: '9px', alignItems: 'flex-start',
            padding: '9px 11px', borderRadius: 'var(--r-sm)',
            border: '1px solid var(--rule-2)', background: 'var(--plate-3)',
          }}>
            <ScanFace size={15} style={{ flex: 'none', marginTop: '2px', color: 'var(--cue)' }} />
            <div style={{ fontSize: '.74rem', color: 'var(--ink-2)', lineHeight: 1.55 }}>
              <b style={{ color: 'var(--ink)' }}>Ikuti orang:</b> tekan ikon wajah
              pada baris bingkai. Kotaknya berhenti diam dan mulai membuntuti
              pembicara — Anda tetap yang menentukan seberapa rapat dan setinggi
              apa bingkainya, sistem hanya menjaga orangnya tetap di dalam.
              {!faceTrackAvailable && (
                <> Untuk klip ini wajah belum terlacak, jadi bingkai pengikut
                akan diam di tempat kotaknya.</>
              )}
            </div>
          </div>

          {selected && (
            <>
              <div style={{ height: '1px', background: 'var(--rule-2)', margin: '6px 0 2px' }} />
              <div className="mark" style={{ color: 'var(--ink)' }}>
                Angka bingkai “{selected.label}”
              </div>

              <RectFields label="Diambil dari video sumber" rect={selected.src}
                          onChange={(r) => patch(selected.id, 'src', r)} />
              <RectFields label="Ditaruh di kanvas hasil" rect={selected.dst}
                          onChange={(r) => patch(selected.id, 'dst', r)} />

              <div style={{ display: 'flex', gap: '6px', alignItems: 'center', marginTop: '2px' }}>
                <span style={{ fontSize: '.74rem', color: 'var(--ink-2)' }}>Isi kotak:</span>
                {[['cover', 'Penuhi (potong sisa)'], ['contain', 'Muat semua (sisakan bilah)']].map(([id, label]) => (
                  <button key={id} className={`chip${(selected.fit ?? 'cover') === id ? ' is-on' : ''}`}
                          onClick={() => setField(selected.id, { fit: id })}>
                    {label}
                  </button>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}

function IconBtn({ children, danger, active, ...rest }) {
  return (
    <button type="button" {...rest}
            aria-pressed={active === undefined ? undefined : !!active}
            style={{
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              width: '24px', height: '24px', flex: 'none', cursor: 'pointer',
              background: active ? 'var(--cue)' : 'transparent',
              border: `1px solid ${active ? 'var(--cue)' : 'var(--rule-2)'}`,
              borderRadius: 'var(--r-sm)',
              color: active ? '#fff' : danger ? 'var(--danger)' : 'var(--ink-2)',
              opacity: rest.disabled ? 0.4 : 1,
            }}>
      {children}
    </button>
  );
}

/**
 * Empat angka satu persegi, dalam persen.
 *
 * Persen dan bukan piksel karena itulah satuan yang disimpan; menampilkan
 * piksel akan berarti angka yang terlihat di sini berubah sendiri saat video
 * sumber lain dibuka, padahal susunannya tidak diubah sama sekali.
 */
function RectFields({ label, rect, onChange }) {
  const set = (key) => (e) => {
    const v = parseFloat(e.target.value);
    onChange({ ...rect, [key]: Number.isFinite(v) ? v : rect[key] });
  };
  return (
    <div>
      <div style={{ fontSize: '.72rem', color: 'var(--ink-2)', marginBottom: '4px' }}>{label}</div>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '5px' }}>
        {[['x', 'Kiri'], ['y', 'Atas'], ['w', 'Lebar'], ['h', 'Tinggi']].map(([k, name]) => (
          <label key={k} style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            <span style={{ fontSize: '.64rem', color: 'var(--ink-3)' }}>{name} %</span>
            <input type="number" className="field" value={rect[k]} step="0.5"
                   min="0" max="100" onChange={set(k)}
                   style={{ padding: '4px 6px', fontSize: '.76rem', width: '100%' }} />
          </label>
        ))}
      </div>
    </div>
  );
}
