/**
 * Panel props animasi dari skemanya (JOB-4 M4.5).
 *
 * Masukannya JSON Schema (komposisi/skemaJson.js), bukan objek zod: skema
 * komponen buatan AI dihitung di dalam iframe kotak pasir dan dikirim ke
 * sini sebagai data. Semua nilai dari skema diperlakukan sebagai DATA (nama
 * kolom, batas, pilihan), tidak pernah dijalankan.
 *
 *   string                      -> kotak teks (maxLength)
 *   string + __remotion-color   -> pemilih warna
 *   string + __remotion-textarea-> kotak teks panjang
 *   enum                        -> pilihan
 *   number/integer + min & max  -> penggeser + angka
 *   number/integer              -> angka
 *   boolean                     -> sakelar
 *   object "posisi" {x, y}      -> dua angka persen + titik yang bisa
 *                                  diseret di pratinjau (PeganganUbah)
 *   lainnya                     -> JSON
 */
import React, { useState } from 'react';
import { useT } from '../../../lib/i18n';

const WARNA = /^#[0-9a-fA-F]{6}$/;

function judul(kunci) {
  const teks = String(kunci).replace(/_/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2');
  return teks.charAt(0).toUpperCase() + teks.slice(1);
}

export function kunciPosisi(skema) {
  return Object.entries(skema?.properties ?? {})
    .filter(([, s]) => s?.type === 'object' && s.description === 'posisi')
    .map(([k]) => k);
}

function KolomJson({ nilai, onUbah }) {
  const [teks, setTeks] = useState(() => JSON.stringify(nilai ?? null));
  const [salah, setSalah] = useState(false);
  return (
    <textarea rows={3} value={teks} className={salah ? 'salah' : ''}
              onChange={(e) => setTeks(e.target.value)}
              onBlur={() => {
                try { onUbah(JSON.parse(teks)); setSalah(false); } catch { setSalah(true); }
              }} />
  );
}

function Kolom({ kunci, s, nilai, onUbah }) {
  const t = useT();
  const label = judul(kunci);
  if (s?.type === 'string' && s.description === '__remotion-color') {
    return (
      <label className="montase-kolom">
        <span>{label}</span>
        <input type="color" value={WARNA.test(nilai ?? '') ? nilai : '#ffffff'} onChange={(e) => onUbah(e.target.value)} />
      </label>
    );
  }
  if (Array.isArray(s?.enum)) {
    return (
      <label className="montase-kolom">
        <span>{label}</span>
        <select value={String(nilai ?? '')} onChange={(e) => {
          const v = s.enum.find((x) => String(x) === e.target.value);
          onUbah(v);
        }}
        >
          {s.enum.map((x) => <option key={String(x)} value={String(x)}>{String(x)}</option>)}
        </select>
      </label>
    );
  }
  if (s?.type === 'string') {
    const panjang = s.description === '__remotion-textarea' || (s.maxLength ?? 0) > 80;
    return (
      <label className="montase-kolom">
        <span>{label}</span>
        {panjang
          ? <textarea rows={3} maxLength={s.maxLength} value={nilai ?? ''} onChange={(e) => onUbah(e.target.value)} />
          : <input maxLength={s.maxLength} value={nilai ?? ''} onChange={(e) => onUbah(e.target.value)} />}
      </label>
    );
  }
  if (s?.type === 'number' || s?.type === 'integer') {
    const min = s.minimum ?? s.exclusiveMinimum;
    const max = s.maximum ?? s.exclusiveMaximum;
    const langkah = s.type === 'integer' ? 1 : (max !== undefined && min !== undefined && max - min <= 2 ? 0.01 : 0.1);
    const ubahAngka = (v) => {
      let n = Number(v);
      if (!Number.isFinite(n)) return;
      if (s.type === 'integer') n = Math.round(n);
      if (min !== undefined) n = Math.max(min, n);
      if (max !== undefined) n = Math.min(max, n);
      onUbah(n);
    };
    return (
      <label className="montase-kolom">
        <span>{label}</span>
        <span className="montase-geser-angka">
          {min !== undefined && max !== undefined && (
            <input type="range" min={min} max={max} step={langkah} value={nilai ?? min}
                   onChange={(e) => ubahAngka(e.target.value)} />
          )}
          <input type="number" className="montase-angka-kecil" min={min} max={max} step={langkah}
                 value={nilai ?? ''} onChange={(e) => { if (e.target.value !== '') ubahAngka(e.target.value); }} />
        </span>
      </label>
    );
  }
  if (s?.type === 'boolean') {
    return (
      <label className="montase-centang">
        <input type="checkbox" checked={Boolean(nilai)} onChange={(e) => onUbah(e.target.checked)} />
        {label}
      </label>
    );
  }
  if (s?.type === 'object' && s.description === 'posisi') {
    const p = nilai ?? { x: 50, y: 50 };
    return (
      <div className="montase-kolom">
        <span>{label}</span>
        <div className="montase-kolom-dua">
          {['x', 'y'].map((sb) => (
            <label key={sb} className="montase-isian-akhiran">
              <small>{sb.toUpperCase()}</small>
              <input type="number" min={0} max={100} step={1} value={Math.round(p[sb] ?? 50)}
                     onChange={(e) => onUbah({ ...p, [sb]: Math.min(100, Math.max(0, Number(e.target.value) || 0)) })} />
              <small>%</small>
            </label>
          ))}
        </div>
        <small className="montase-petunjuk">{t('montase.props.seret_titik')}</small>
      </div>
    );
  }
  return (
    <label className="montase-kolom">
      <span>{label}</span>
      <KolomJson nilai={nilai} onUbah={onUbah} />
    </label>
  );
}

export default function PanelPropsSkema({ skema, nilai, onUbah }) {
  const t = useT();
  if (!skema?.properties) return <p className="montase-petunjuk">{t('montase.props.tanpa_skema')}</p>;
  return Object.entries(skema.properties).map(([k, s]) => (
    <Kolom key={k} kunci={k} s={s} nilai={nilai?.[k]} onUbah={(v) => onUbah({ ...nilai, [k]: v })} />
  ));
}
