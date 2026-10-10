import React, { useEffect, useState } from 'react';
import { Loader2, Search, ImagePlus } from 'lucide-react';
import { apiGet, apiPost, apiPut } from '../../lib/api';

/**
 * Gambar stok dari Pexels (JOB-2 F2-6): orangnya mencari, MEMILIH sendiri,
 * baru gambarnya diunduh ke pustaka aset dan dipasang sebagai sisipan.
 * Tidak ada yang dipasang otomatis: gambar yang salah arti lebih buruk
 * daripada tidak ada gambar.
 */
export default function StokPanel({ clip, waktuSekarang = 0, durasiKlip = 0, onLayers }) {
  const [terpasang, setTerpasang] = useState(null);
  const [kunci, setKunci] = useState('');
  const [kata, setKata] = useState('');
  const [foto, setFoto] = useState([]);
  const [sibuk, setSibuk] = useState('');
  const [galat, setGalat] = useState('');

  useEffect(() => {
    apiGet('/aset/stok/kunci').then((r) => setTerpasang(!!r.terpasang)).catch(() => setTerpasang(false));
  }, []);
  useEffect(() => { setFoto([]); setKata(''); }, [clip?.clip_id]);
  if (!clip || terpasang === null) return null;

  const simpanKunci = async () => {
    setSibuk('kunci'); setGalat('');
    try { setTerpasang(!!(await apiPut('/aset/stok/kunci', { kunci })).terpasang); setKunci(''); }
    catch (e) { setGalat(e.message); } finally { setSibuk(''); }
  };
  const cari = async () => {
    setSibuk('cari'); setGalat('');
    try { setFoto((await apiPost('/aset/stok/cari', { kata })).foto || []); }
    catch (e) { setGalat(e.message); } finally { setSibuk(''); }
  };
  const pasang = async (f) => {
    setSibuk(String(f.id)); setGalat('');
    try {
      const a = await apiPost('/aset/stok/ambil', { url: f.unduh, nama: f.alt || kata });
      const t = Math.min(Math.max(0, waktuSekarang), Math.max(0, durasiKlip - 0.5));
      onLayers([...(clip.media_layers ?? []), {
        id: `st${Date.now().toString(36)}`, aset: a.id, nama: a.nama, jenis: 'gambar',
        t: Math.round(t * 100) / 100, dur: Math.min(3, Math.max(0.5, durasiKlip - t)),
        posisi: 'tengah', isi: 'muat', opasitas: 1, fade_masuk: 0.2, fade_keluar: 0.2,
        volume: 0, asal: 'stok', alasan: f.fotografer ? `Foto: ${f.fotografer} (Pexels)` : 'Pexels',
      }]);
    } catch (e) { setGalat(e.message); } finally { setSibuk(''); }
  };

  return (
    <div style={{ borderTop: '1px solid var(--line)', marginTop: '14px', paddingTop: '12px',
                  display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <b style={{ fontSize: '.84rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
        <ImagePlus size={14} /> Gambar stok (Pexels)
      </b>
      {!terpasang ? (
        <>
          <span style={{ fontSize: '.74rem', color: 'var(--ink-3)', lineHeight: 1.5 }}>
            Butuh kunci API Pexels yang gratis. Daftar di pexels.com/api, salin kuncinya ke sini.
            Foto Pexels boleh dipakai gratis, termasuk untuk kanal yang dimonetisasi.
          </span>
          <div style={{ display: 'flex', gap: '6px' }}>
            <input className="field" value={kunci} placeholder="Kunci API Pexels"
                   onChange={(e) => setKunci(e.target.value)} />
            <button className="btn-secondary" onClick={simpanKunci} disabled={!kunci.trim() || !!sibuk}>
              Simpan
            </button>
          </div>
        </>
      ) : (
        <>
          <span style={{ fontSize: '.74rem', color: 'var(--ink-3)', lineHeight: 1.5 }}>
            Cari gambar yang menjelaskan yang sedang dibicarakan. Gambar dipasang di posisi pemutar
            selama 3 detik; geser atau ubah lamanya di daftar sisipan.
          </span>
          <form style={{ display: 'flex', gap: '6px' }}
                onSubmit={(e) => { e.preventDefault(); if (kata.trim()) cari(); }}>
            <input className="field" value={kata} placeholder="Contoh: kapal nelayan"
                   onChange={(e) => setKata(e.target.value)} />
            <button className="btn-secondary" type="submit" disabled={!kata.trim() || !!sibuk}>
              {sibuk === 'cari' ? <Loader2 size={13} className="animate-spin" /> : <Search size={13} />}
              Cari
            </button>
          </form>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '6px' }}>
            {foto.map((f) => (
              <button key={f.id} type="button" onClick={() => pasang(f)} disabled={!!sibuk}
                      title={`${f.alt || ''}${f.fotografer ? ` · ${f.fotografer}` : ''}`}
                      style={{ padding: 0, border: '1px solid var(--line)', background: 'none',
                               cursor: 'pointer', position: 'relative', aspectRatio: '3 / 4',
                               overflow: 'hidden', borderRadius: '4px' }}>
                <img src={f.pratinjau} alt={f.alt || ''} loading="lazy"
                     style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                {sibuk === String(f.id) && (
                  <Loader2 size={18} className="animate-spin"
                           style={{ position: 'absolute', inset: 0, margin: 'auto', color: '#fff' }} />
                )}
              </button>
            ))}
          </div>
        </>
      )}
      {galat && <div style={{ fontSize: '.74rem', color: 'var(--danger)' }}>{galat}</div>}
    </div>
  );
}
