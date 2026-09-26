import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { apiGet } from '../../lib/api';
import { CARD_VARIANTS } from './cardStyles';

/**
 * Judul bertema: latar, warna, huruf, dan geraknya satu paket.
 *
 * Gambarnya TIDAK ditiru dengan CSS. Server menggambarnya dengan libass, mesin
 * yang sama yang nanti membakarnya ke MP4, lalu mengirimnya sebagai PNG
 * tembus pandang seukuran kanvas. CSS dan libass mengukur huruf dengan cara
 * yang berbeda (selisihnya terukur lebih dari 30%), jadi tiruan CSS akan
 * memperlihatkan judul yang lain dari hasil render.
 */

export const DEFAULT_JUDUL_VIDEO = {
  aktif: false, teks: '', tema: 'kartu-putih',
  pos_x: 50, pos_y: 14, box_w: 84, ukuran: 72,
  mulai: 0, durasi: null,
};

/** Varian lama hanya menggerakkan teks; selain itu berarti tema lengkap. */
const VARIAN_LAMA = new Set(CARD_VARIANTS.map((v) => v.id));
export const iniTema = (id) => !!id && !VARIAN_LAMA.has(id);

let _daftar = null;
/** Daftar tema, diambil sekali per halaman. */
export function useDaftarTema() {
  const [tema, setTema] = useState(_daftar?.tema || []);
  useEffect(() => {
    if (_daftar) return undefined;
    let batal = false;
    apiGet('/judul/tema')
      .then((r) => { _daftar = r; if (!batal) setTema(r.tema || []); })
      .catch(() => {});
    return () => { batal = true; };
  }, []);
  return tema;
}

// Gambar yang sudah diterima, per parameter. Menyeret penggeser bolak-balik
// meminta nilai yang sama berulang kali.
const _gambar = new Map();
const _GAMBAR_MAKS = 120;

/** Kotak judul di dalam PNG (persen kanvas), dari piksel yang tidak tembus. */
async function kotakDariGambar(blob) {
  const bmp = await createImageBitmap(blob);
  const { width: w, height: h } = bmp;
  const kanvas = document.createElement('canvas');
  kanvas.width = w;
  kanvas.height = h;
  const ctx = kanvas.getContext('2d', { willReadFrequently: true });
  ctx.drawImage(bmp, 0, 0);
  const data = ctx.getImageData(0, 0, w, h).data;
  let x0 = w; let y0 = h; let x1 = -1; let y1 = -1;
  for (let y = 0; y < h; y += 1) {
    const baris = y * w * 4;
    for (let x = 0; x < w; x += 1) {
      if (data[baris + x * 4 + 3] > 10) {
        if (x < x0) x0 = x;
        if (x > x1) x1 = x;
        if (y < y0) y0 = y;
        if (y > y1) y1 = y;
      }
    }
  }
  bmp.close?.();
  if (x1 < 0) return null;
  return {
    x0: (x0 / w) * 100, y0: (y0 / h) * 100,
    x1: ((x1 + 1) / w) * 100, y1: ((y1 + 1) / h) * 100,
  };
}

async function ambilGambar(p) {
  const kunci = JSON.stringify(p);
  if (_gambar.has(kunci)) return _gambar.get(kunci);
  const r = await fetch('/api/judul/gambar', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(p),
  });
  if (!r.ok) throw new Error('Judul gagal digambar.');
  const blob = await r.blob();
  const hasil = { url: URL.createObjectURL(blob), kotak: await kotakDariGambar(blob), p };
  _gambar.set(kunci, hasil);
  if (_gambar.size > _GAMBAR_MAKS) {
    const [lama, isi] = _gambar.entries().next().value;
    URL.revokeObjectURL(isi.url);
    _gambar.delete(lama);
  }
  return hasil;
}

/**
 * Gambar judul untuk parameter ini, ditunda sebentar saat parameternya masih
 * berubah (diseret, diketik). Gambar yang lama tetap dipegang sampai yang
 * baru datang, jadi judulnya tidak pernah berkedip hilang.
 */
export function useGambarJudul(p, jeda = 140) {
  const [hasil, setHasil] = useState(null);
  const [memuat, setMemuat] = useState(false);
  const kunci = p ? JSON.stringify(p) : '';
  useEffect(() => {
    if (!p || !(p.teks || '').trim()) { setHasil(null); return undefined; }
    let batal = false;
    const siap = _gambar.get(kunci);
    if (siap) { setHasil(siap); return undefined; }
    setMemuat(true);
    const t = setTimeout(() => {
      ambilGambar(p)
        .then((h) => { if (!batal) setHasil(h); })
        .catch(() => {})
        .finally(() => { if (!batal) setMemuat(false); });
    }, jeda);
    return () => { batal = true; clearTimeout(t); };
  }, [kunci]);       // eslint-disable-line react-hooks/exhaustive-deps
  return { hasil, memuat };
}

/** Satu contoh tema di galeri: judulnya sendiri, digambar oleh libass. */
function ContohTema({ t, teks, aktif, onPilih }) {
  const [putar, setPutar] = useState(0);
  const { hasil } = useGambarJudul({
    tema: t.id, teks, pos_x: 50, pos_y: 50, box_w: 92, ukuran: 100, aspek: '9:16',
  }, 0);
  return (
    <button type="button" onClick={onPilih} onMouseEnter={() => setPutar((n) => n + 1)}
            className={`judul-contoh tema-contoh${aktif ? ' is-on' : ''}`} title={t.catatan}>
      <span className="judul-contoh-layar">
        {hasil
          ? <img key={putar} src={hasil.url} alt="" className={`gerak-${t.gerak}`} />
          : <Loader2 size={14} className="animate-spin" style={{ color: 'rgba(255,255,255,.5)' }} />}
      </span>
      <span className="judul-contoh-nama">{t.label}</span>
    </button>
  );
}

/** Galeri tema lengkap. */
export function GaleriTema({ teks, pilihan, onPilih }) {
  const daftar = useDaftarTema();
  const pendek = (teks || 'JUDUL KLIP ANDA').trim();
  // Teks contoh dipotong supaya muat dua baris di kotak kecil.
  const contoh = pendek.length > 34 ? `${pendek.slice(0, 32).trim()}…` : pendek;
  if (!daftar.length) {
    return <p style={{ fontSize: '.74rem', color: 'var(--ink-3)', margin: 0 }}>Memuat tema…</p>;
  }
  return (
    <div className="judul-galeri">
      {daftar.map((t) => (
        <ContohTema key={t.id} t={t} teks={contoh} aktif={pilihan === t.id}
                    onPilih={() => onPilih(t.id)} />
      ))}
    </div>
  );
}

/**
 * Judul bertema di atas pratinjau: bisa diseret untuk dipindah, dan gagang
 * pojoknya melebarkan kotak sekaligus membesarkan hurufnya.
 *
 * Selama gambar baru belum datang, gambar lama digeser dan diperbesar dengan
 * CSS sebesar selisih parameternya, jadi seretan terasa langsung meski setiap
 * gambar dibuat di server.
 *
 * `nilai`: {tema, teks, pos_x, pos_y, box_w, ukuran}. `onUbah(patch)` dengan
 * nama bidang yang sama.
 */
export function LapisJudul({ nilai, aspek = '9:16', boxW, boxH, onUbah, gerak = '', zIndex = 3 }) {
  const p = {
    tema: nilai.tema, teks: nilai.teks,
    pos_x: Number(nilai.pos_x ?? 50), pos_y: Number(nilai.pos_y ?? 50),
    box_w: Number(nilai.box_w ?? 84), ukuran: Number(nilai.ukuran ?? 72),
    aspek,
  };
  const { hasil } = useGambarJudul(p);
  const [seret, setSeret] = useState(null);
  const nilaiRef = useRef(p);
  nilaiRef.current = p;

  const mulaiSeret = useCallback((mode) => (e) => {
    if (!onUbah || !boxW || !boxH) return;
    e.preventDefault();
    e.stopPropagation();
    e.currentTarget.setPointerCapture?.(e.pointerId);
    setSeret(mode);
    const x0 = e.clientX;
    const y0 = e.clientY;
    const awal = { ...nilaiRef.current };
    const onMove = (ev) => {
      const dx = ((ev.clientX - x0) / boxW) * 100;
      const dy = ((ev.clientY - y0) / boxH) * 100;
      if (mode === 'pindah') {
        onUbah({
          pos_x: Math.round(Math.max(0, Math.min(100, awal.pos_x + dx)) * 10) / 10,
          pos_y: Math.round(Math.max(3, Math.min(97, awal.pos_y + dy)) * 10) / 10,
        });
      } else {
        onUbah({
          box_w: Math.round(Math.max(20, Math.min(100, awal.box_w + dx * 2))),
          ukuran: Math.round(Math.max(24, Math.min(240, awal.ukuran + dy * 1920 * 0.0055))),
        });
      }
    };
    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      setSeret(null);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  }, [onUbah, boxW, boxH]);

  if (!hasil || !hasil.kotak) return null;
  const k = hasil.kotak;
  const r = hasil.p;
  // Selisih antara yang diminta dan yang sudah tergambar.
  const skala = p.ukuran / Math.max(1, r.ukuran);
  const cx = (k.x0 + k.x1) / 2;
  const cy = (k.y0 + k.y1) / 2;
  const geser = `translate(${p.pos_x - r.pos_x}%, ${p.pos_y - r.pos_y}%) scale(${skala})`;

  return (
    <>
    <div style={{
      position: 'absolute', inset: 0, zIndex, pointerEvents: 'none',
      transform: geser, transformOrigin: `${cx}% ${cy}%`,
    }}>
      <div className={gerak ? `gerak-${gerak}` : undefined}
           style={{ position: 'absolute', inset: 0, transformOrigin: `${cx}% ${cy}%` }}>
        <img src={hasil.url} alt="" draggable={false}
             style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
      </div>
      {onUbah && (
        <div onPointerDown={mulaiSeret('pindah')}
             title="Seret untuk memindahkan judul"
             style={{
               position: 'absolute', pointerEvents: 'auto', cursor: 'move',
               left: `${k.x0}%`, top: `${k.y0}%`,
               width: `${k.x1 - k.x0}%`, height: `${k.y1 - k.y0}%`,
               outline: seret ? '1px dashed rgba(255,255,255,.7)' : 'none',
               outlineOffset: '4px',
             }}>
          <span onPointerDown={mulaiSeret('ukuran')}
                title="Seret untuk mengubah ukuran judul"
                style={{
                  position: 'absolute', right: '-8px', bottom: '-8px',
                  width: '15px', height: '15px', borderRadius: '50%',
                  background: 'var(--hl)', border: '2px solid #000',
                  cursor: 'nwse-resize',
                }} />
        </div>
      )}
    </div>
      {seret && (
        <div style={{
          position: 'absolute', right: '8px', top: '8px', padding: '3px 8px', zIndex: zIndex + 1,
          borderRadius: '99px', fontSize: '0.62rem', fontWeight: 800,
          background: 'rgba(0,0,0,0.8)', color: '#00E5FF',
          fontVariantNumeric: 'tabular-nums',
        }}>
          {seret === 'pindah'
            ? `X ${Math.round(p.pos_x)}% · Y ${Math.round(p.pos_y)}%`
            : `Lebar ${Math.round(p.box_w)}% · huruf ${Math.round(p.ukuran)}`}
        </div>
      )}
    </>
  );
}
