import React, { useEffect, useMemo, useState } from 'react';
import { Languages, Loader2, ArrowUpDown, Trash2 } from 'lucide-react';
import { apiGet, apiPost } from '../../lib/api';
import { cachedFonts, loadFonts } from '../../lib/fonts';

const kecil = { fontSize: '0.7rem', color: 'var(--text-secondary)', lineHeight: 1.45 };
const label = { fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-secondary)' };
const kontrol = {
  padding: '5px 7px', fontSize: '0.76rem', fontFamily: 'inherit',
  borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)',
  background: 'var(--bg-card)', color: 'var(--text-primary)',
};

const WARNA = ['#FFFFFF', '#FFE500', '#00E5FF', '#7CFFB2', '#FFB3C7', '#FF9F1C'];
const POSISI = [['top', 'Atas'], ['middle', 'Tengah'], ['bottom', 'Bawah']];

/** Sidik subtitle utama: berubah bila teks atau waktunya berubah. */
function sidikUtama(lines) {
  return (lines ?? []).map((l) => `${(+l.start).toFixed(2)}|${(+l.end).toFixed(2)}|${l.text}`).join('\n');
}

/**
 * Subtitle kedua — biasanya terjemahan.
 *
 * Baris-baris subtitle utama diterjemahkan satu lawan satu, dan tiap baris
 * terjemahan menyalin waktu baris aslinya. Karena itu keduanya muncul dan hilang
 * bersamaan: Inggris di atas, Indonesia di bawah, atau terjemahannya saja bila
 * subtitle utama dimatikan.
 */
// Terjemahan DI ATAS subtitle asli — sama dengan terjemahan otomatis di
// backend (terjemah.GAYA_KEDUA_OTOMATIS). Bukan di bawahnya: anime fansub
// membawa subtitle tertanam di bagian bawah gambar, dan terjemahan di sana
// tertimpa.
export const GAYA_KEDUA_BAWAAN = {
  font: 'Poppins', size: 70, primary: '#FFE500', uppercase: false,
  position: 'bottom', margin_v: 560, outline_px: 6, animation: 'fade', bg: false,
};

/** Isi subtitle_kedua untuk satu klip dari hasil /clip-terjemah. */
export function buatKedua(clip, bahasa, teks, gayaLama) {
  const utama = clip?.subtitles ?? [];
  return {
    aktif: true, bahasa,
    lines: utama.map((l, i) => ({ start: l.start, end: l.end, text: teks[i] ?? l.text })),
    style: gayaLama ?? GAYA_KEDUA_BAWAAN,
    sumber_sidik: sidikUtama(utama),
  };
}

export default function TerjemahPanel({ clip, videoId, styleUtama, onStyleUtama, onChange,
                                        onSemua = null }) {
  const [bahasaList, setBahasaList] = useState([]);
  const [bahasa, setBahasa] = useState('id');
  const [sibuk, setSibuk] = useState(false);
  const [galat, setGalat] = useState(null);
  const [fonts, setFonts] = useState(cachedFonts);

  useEffect(() => { loadFonts().then(setFonts); }, []);
  useEffect(() => {
    apiGet('/settings/languages').then((r) => setBahasaList(r.common || [])).catch(() => {});
  }, []);

  const kedua = clip?.subtitle_kedua ?? null;
  useEffect(() => { if (kedua?.bahasa) setBahasa(kedua.bahasa); }, [kedua?.bahasa]);

  const utama = clip?.subtitles ?? [];
  const usang = useMemo(
    () => !!kedua && kedua.sumber_sidik && kedua.sumber_sidik !== sidikUtama(utama),
    [kedua, utama]);

  const ubahGaya = (patch) => onChange({ ...kedua, style: { ...(kedua?.style ?? {}), ...patch } });

  const terjemahkan = async () => {
    if (!utama.length) return;
    setSibuk(true); setGalat(null);
    try {
      const r = await apiPost('/clip-terjemah', {
        video_id: videoId, bahasa, teks: utama.map((l) => l.text || ''),
      });
      // Posisi bawaan: di ATAS subtitle asli bila aslinya di bawah; bila
      // aslinya di atas, terjemahannya ke bawah layar.
      const posUtama = styleUtama?.position ?? 'bottom';
      const gaya = kedua?.style ?? (posUtama === 'bottom'
        ? GAYA_KEDUA_BAWAAN : { ...GAYA_KEDUA_BAWAAN, margin_v: 300 });
      onChange(buatKedua(clip, bahasa, r.teks, gaya));
    } catch (e) {
      setGalat(e.message);
    } finally {
      setSibuk(false);
    }
  };

  const tukarPosisi = () => {
    const a = styleUtama?.position ?? 'bottom';
    const b = kedua?.style?.position ?? 'top';
    onStyleUtama({ ...styleUtama, position: b });
    ubahGaya({ position: a });
  };

  const st = kedua?.style ?? {};
  return (
    <div style={{
      border: '1px solid var(--accent-cyan)', borderRadius: 'var(--radius-md)',
      padding: '11px 12px', marginBottom: '14px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '7px', marginBottom: '6px' }}>
        <Languages size={15} style={{ color: 'var(--accent-cyan)' }} />
        <b style={{ fontSize: '0.84rem' }}>Subtitle kedua / terjemahan</b>
      </div>
      <p style={{ ...kecil, margin: '0 0 9px' }}>
        Baris subtitle diterjemahkan satu per satu dan muncul bersamaan dengan
        aslinya, misalnya Indonesia di atas, Jepang di bawahnya. Video berbahasa
        asing diterjemahkan otomatis saat dianalisis (atur di Pengaturan). Untuk
        terjemahan saja, matikan subtitle asli.
      </p>

      <div style={{ display: 'flex', gap: '7px', flexWrap: 'wrap', alignItems: 'center' }}>
        <select value={bahasa} onChange={(e) => setBahasa(e.target.value)} style={kontrol}>
          {(bahasaList.length ? bahasaList : [{ code: 'id', label: 'Indonesia' }, { code: 'en', label: 'Inggris' }])
            .map((b) => <option key={b.code} value={b.code}>{b.label}</option>)}
        </select>
        <button className="btn-primary" onClick={terjemahkan} disabled={sibuk || !utama.length}
                style={{ fontSize: '0.78rem', display: 'inline-flex', gap: '6px', alignItems: 'center' }}>
          {sibuk ? <Loader2 size={13} className="animate-spin" /> : <Languages size={13} />}
          {sibuk ? 'Menerjemahkan…' : kedua ? 'Terjemahkan ulang' : `Terjemahkan ${utama.length} baris`}
        </button>
        {onSemua && (
          <button className="btn-secondary" onClick={() => onSemua(bahasa)} disabled={sibuk}
                  title="Klip yang belum punya terjemahan (atau terjemahannya usang) diterjemahkan semuanya"
                  style={{ fontSize: '0.76rem' }}>
            Terjemahkan semua klip
          </button>
        )}
      </div>
      {galat && <p style={{ ...kecil, color: 'var(--danger)', margin: '8px 0 0' }}>{galat}</p>}
      {usang && (
        <p style={{ ...kecil, color: 'var(--warn, #F59E0B)', margin: '8px 0 0' }}>
          Subtitle utama sudah berubah sejak diterjemahkan. Terjemahkan ulang supaya
          baris dan waktunya cocok lagi.
        </p>
      )}

      {kedua && (
        <div style={{ marginTop: '12px', display: 'grid', gap: '9px' }}>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', fontSize: '0.76rem' }}>
            <label style={{ display: 'inline-flex', gap: '5px', alignItems: 'center' }}>
              <input type="checkbox" checked={kedua.aktif !== false}
                     onChange={(e) => onChange({ ...kedua, aktif: e.target.checked })} />
              Tampilkan terjemahan
            </label>
            <label style={{ display: 'inline-flex', gap: '5px', alignItems: 'center' }}>
              <input type="checkbox" checked={styleUtama?.aktif !== false}
                     onChange={(e) => onStyleUtama({ ...styleUtama, aktif: e.target.checked })} />
              Tampilkan subtitle asli
            </label>
          </div>

          <div>
            <div style={label}>Posisi</div>
            <div style={{ display: 'flex', gap: '5px', marginTop: '4px', flexWrap: 'wrap' }}>
              {POSISI.map(([v, t]) => (
                <button key={v} onClick={() => ubahGaya({ position: v })}
                        className="btn-secondary"
                        style={{ fontSize: '0.74rem', padding: '4px 10px',
                                 ...(st.position === v ? { borderColor: 'var(--accent-cyan)', color: 'var(--accent-cyan)' } : {}) }}>
                  {t}
                </button>
              ))}
              <button className="btn-secondary" onClick={tukarPosisi} title="Tukar posisi dengan subtitle asli"
                      style={{ fontSize: '0.74rem', padding: '4px 10px', display: 'inline-flex', gap: '4px', alignItems: 'center' }}>
                <ArrowUpDown size={12} /> Tukar dengan asli
              </button>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
            <label style={label}>Font
              <select value={st.font ?? 'Poppins'} onChange={(e) => ubahGaya({ font: e.target.value })}
                      style={{ ...kontrol, width: '100%', marginTop: '4px' }}>
                {fonts.map((f) => <option key={f.family} value={f.family}>{f.label ?? f.family}</option>)}
              </select>
            </label>
            <label style={label}>Ukuran {st.size ?? 72}
              <input type="range" min="36" max="140" value={st.size ?? 72}
                     onChange={(e) => ubahGaya({ size: Number(e.target.value) })}
                     style={{ width: '100%', marginTop: '8px' }} />
            </label>
          </div>

          <label style={label}>Jarak dari tepi {st.margin_v ?? 260}
            <input type="range" min="40" max="900" step="10" value={st.margin_v ?? 260}
                   onChange={(e) => ubahGaya({ margin_v: Number(e.target.value) })}
                   style={{ width: '100%', marginTop: '6px' }} />
          </label>

          <div>
            <div style={label}>Warna</div>
            <label style={{ display: 'flex', gap: '6px', alignItems: 'center', fontSize: '0.76rem',
                            margin: '5px 0 6px' }}>
              <input type="checkbox" checked={st.ikut_warna_orang === true}
                     onChange={(e) => ubahGaya({ ikut_warna_orang: e.target.checked })} />
              Ikuti warna tiap orang (sama dengan subtitle asli)
            </label>
            {st.ikut_warna_orang === true && styleUtama?.per_speaker_colors === false && (
              <p style={{ ...kecil, margin: '0 0 6px' }}>
                Warna per orang sedang dimatikan di subtitle asli, jadi terjemahan
                memakai warna di bawah.
              </p>
            )}
            <div style={{ display: 'flex', gap: '6px', marginTop: '5px', alignItems: 'center',
                          ...(st.ikut_warna_orang === true && styleUtama?.per_speaker_colors !== false
                            ? { opacity: 0.4, pointerEvents: 'none' } : {}) }}>
              {WARNA.map((w) => (
                <button key={w} onClick={() => ubahGaya({ primary: w })} title={w}
                        style={{ width: '22px', height: '22px', borderRadius: '50%', background: w, cursor: 'pointer',
                                 border: (st.primary ?? '#FFE500') === w ? '2px solid var(--accent-cyan)' : '1px solid rgba(0,0,0,.4)' }} />
              ))}
              <input type="color" value={st.primary ?? '#FFE500'}
                     onChange={(e) => ubahGaya({ primary: e.target.value.toUpperCase() })} />
            </div>
          </div>

          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', fontSize: '0.76rem' }}>
            <label style={{ display: 'inline-flex', gap: '5px', alignItems: 'center' }}>
              <input type="checkbox" checked={!!st.uppercase}
                     onChange={(e) => ubahGaya({ uppercase: e.target.checked })} />
              Huruf besar
            </label>
            <label style={{ display: 'inline-flex', gap: '5px', alignItems: 'center' }}>
              <input type="checkbox" checked={!!st.bg}
                     onChange={(e) => ubahGaya({ bg: e.target.checked, bg_color: '#000000', bg_opacity: 0.55, bg_pad: 12 })} />
              Pelat gelap di belakang teks
            </label>
          </div>

          <button className="btn-secondary" onClick={() => onChange(null)}
                  style={{ fontSize: '0.74rem', justifySelf: 'start', display: 'inline-flex', gap: '5px', alignItems: 'center' }}>
            <Trash2 size={12} /> Hapus subtitle kedua
          </button>
        </div>
      )}
    </div>
  );
}
