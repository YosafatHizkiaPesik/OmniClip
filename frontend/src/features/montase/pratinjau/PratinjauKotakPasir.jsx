/**
 * Pratinjau Montase di dalam iframe kotak pasir, dikendalikan dari luar.
 *
 * Tombol dan penggeser digambar di sini, di LUAR iframe, supaya tetap bekerja
 * apa pun yang dilakukan kode di dalamnya. Alamat iframe selalu
 * `/pratinjau.html` dari server yang sama: Vite saat pengembangan, backend
 * saat aplikasi terbungkus.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Pause, Play } from 'lucide-react';
import { useT } from '../../../lib/i18n';
import { ukuranDokumen } from '../komposisi/index.js';
import { pesan, pesanSah } from './jembatan.js';

export default function PratinjauKotakPasir({ dokumen, sumber, onGalat }) {
  const t = useT();
  const bingkaiRef = useRef(null);
  const [siap, setSiap] = useState(false);
  const [bingkai, setBingkai] = useState(0);
  const [main, setMain] = useState(false);
  const u = ukuranDokumen(dokumen);

  const kirim = useCallback((jenis, isi) => {
    bingkaiRef.current?.contentWindow?.postMessage(pesan(jenis, isi), '*');
  }, []);

  useEffect(() => {
    const dengar = (e) => {
      if (e.source !== bingkaiRef.current?.contentWindow || !pesanSah(e.data)) return;
      const d = e.data;
      if (d.jenis === 'siap') setSiap(true);
      else if (d.jenis === 'bingkai') setBingkai(d.bingkai);
      else if (d.jenis === 'main') setMain(Boolean(d.main));
      else if (d.jenis === 'galat') onGalat?.(d.pesan);
    };
    window.addEventListener('message', dengar);
    return () => window.removeEventListener('message', dengar);
  }, [onGalat]);

  useEffect(() => {
    if (siap && dokumen) kirim('muat', { dokumen, sumber });
  }, [siap, dokumen, sumber, kirim]);

  const detik = (bingkai / u.fps).toFixed(2);
  return (
    <div className="montase-pratinjau" data-siap={siap ? 'ya' : 'tidak'}>
      <div className="montase-pratinjau-layar" style={{ aspectRatio: `${u.lebar} / ${u.tinggi}` }}>
        <iframe
          ref={bingkaiRef}
          src="/pratinjau.html"
          title={t('montase.pratinjau.judul')}
          sandbox="allow-scripts"
          allow="autoplay; fullscreen"
        />
      </div>
      <div className="montase-pratinjau-kendali">
        <button
          type="button"
          className="btn-secondary"
          disabled={!siap}
          onClick={() => kirim(main ? 'jeda' : 'putar')}
          aria-label={main ? t('montase.pratinjau.jeda') : t('montase.pratinjau.putar')}
        >
          {main ? <Pause size={14} /> : <Play size={14} />}
        </button>
        <input
          type="range"
          min={0}
          max={Math.max(0, u.durasi - 1)}
          value={bingkai}
          disabled={!siap}
          aria-label={t('montase.pratinjau.geser')}
          onChange={(e) => {
            const b = Number(e.target.value);
            setBingkai(b);
            kirim('ke', { bingkai: b });
          }}
        />
        <span className="montase-pratinjau-waktu" data-bingkai={bingkai}>
          {t('montase.pratinjau.posisi', { detik, bingkai })}
        </span>
      </div>
    </div>
  );
}
