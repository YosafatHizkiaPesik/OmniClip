/**
 * Pratinjau Montase di dalam iframe kotak pasir, dikendalikan dari luar.
 *
 * Tombol, penggeser, dan garis zona aman digambar di sini, di LUAR iframe,
 * supaya tetap bekerja apa pun yang dilakukan kode di dalamnya. Alamat iframe
 * selalu `/pratinjau.html` dari server yang sama: Vite saat pengembangan,
 * backend saat aplikasi terbungkus.
 *
 * Editor mengendalikannya lewat ref: `ke(bingkai)`, `putar()`, `jeda()`,
 * `putarJeda()`, dan menerima bingkai yang sedang tampil lewat `onBingkai`,
 * status putar lewat `onMain`, dan tombol keyboard yang ditekan saat fokus
 * berada di dalam iframe lewat `onTombol` (supaya pintasan tetap jalan
 * sesudah pratinjau diklik). `children` digambar di atas iframe: pegangan
 * transformasi editor.
 */
import React, {
  forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState,
} from 'react';
import {
  ChevronLeft, ChevronRight, Maximize, Pause, Play, ScanLine,
} from 'lucide-react';
import { useT } from '../../../lib/i18n';
import { ukuranDokumen } from '../komposisi/index.js';
import { pesan, pesanSah } from './jembatan.js';
import { zonaAman } from './zonaAman.js';

const JEDA_LAPORAN = 600;

const PratinjauKotakPasir = forwardRef(function PratinjauKotakPasir(
  {
    dokumen, sumber, onGalat, onBingkai, onMain, onTombol, lengkap = false, children,
  }, ref,
) {
  const t = useT();
  const bingkaiRef = useRef(null);
  const layarRef = useRef(null);
  const [siap, setSiap] = useState(false);
  const [bingkai, setBingkai] = useState(0);
  const [main, setMain] = useState(false);
  const [garis, setGaris] = useState(false);
  const u = ukuranDokumen(dokumen);

  const kirim = useCallback((jenis, isi) => {
    bingkaiRef.current?.contentWindow?.postMessage(pesan(jenis, isi), '*');
  }, []);

  // Lompatan terakhir dari sini. Laporan bingkai dari iframe datang
  // terlambat: menekan panah cepat-cepat bisa membuat laporan untuk lompatan
  // SEBELUMNYA tiba sesudah lompatan baru, dan garis putar meloncat mundur.
  // Saat tidak diputar, laporan yang berbeda dari lompatan terakhir dalam
  // JEDA_LAPORAN diabaikan.
  const lompatan = useRef({ bingkai: null, waktu: 0 });
  const mainRef = useRef(false);

  const ke = useCallback((b) => {
    const tepat = Math.max(0, Math.min(u.durasi - 1, Math.round(b)));
    lompatan.current = { bingkai: tepat, waktu: performance.now() };
    setBingkai(tepat);
    kirim('ke', { bingkai: tepat });
  }, [kirim, u.durasi]);

  useImperativeHandle(ref, () => ({
    ke,
    putar: () => kirim('putar'),
    jeda: () => kirim('jeda'),
    putarJeda: () => kirim(main ? 'jeda' : 'putar'),
    main: () => main,
  }), [ke, kirim, main]);

  useEffect(() => {
    const dengar = (e) => {
      if (e.source !== bingkaiRef.current?.contentWindow || !pesanSah(e.data)) return;
      const d = e.data;
      if (d.jenis === 'siap') setSiap(true);
      else if (d.jenis === 'bingkai') {
        const l = lompatan.current;
        if (!mainRef.current && l.bingkai !== null && d.bingkai !== l.bingkai
            && performance.now() - l.waktu < JEDA_LAPORAN) return;
        setBingkai(d.bingkai);
        onBingkai?.(d.bingkai);
      } else if (d.jenis === 'main') {
        mainRef.current = Boolean(d.main);
        setMain(Boolean(d.main));
        onMain?.(Boolean(d.main));
      }
      else if (d.jenis === 'galat') onGalat?.(d.pesan);
      else if (d.jenis === 'tombol' && typeof d.key === 'string') onTombol?.(d);
    };
    window.addEventListener('message', dengar);
    return () => window.removeEventListener('message', dengar);
  }, [onGalat, onBingkai, onMain, onTombol]);

  useEffect(() => {
    if (siap && dokumen) kirim('muat', { dokumen, sumber });
  }, [siap, dokumen, sumber, kirim]);

  const layarPenuh = () => {
    const el = layarRef.current;
    if (!el) return;
    if (document.fullscreenElement) document.exitFullscreen?.();
    else el.requestFullscreen?.();
  };

  const zona = zonaAman(u.lebar, u.tinggi);
  const detik = (bingkai / u.fps).toFixed(2);
  return (
    <div className="montase-pratinjau" data-siap={siap ? 'ya' : 'tidak'}>
      <div ref={layarRef} className="montase-pratinjau-layar"
           style={{ aspectRatio: `${u.lebar} / ${u.tinggi}` }}
      >
        <iframe
          ref={bingkaiRef}
          src="/pratinjau.html"
          title={t('montase.pratinjau.judul')}
          sandbox="allow-scripts"
          allow="autoplay; fullscreen"
        />
        {garis && (
          <div className="montase-zona-wadah" aria-hidden>
            <div className="montase-zona-aman"
                 style={{
                   left: `${zona.kiri}%`, right: `${zona.kanan}%`,
                   top: `${zona.atas}%`, bottom: `${zona.bawah}%`,
                 }}
            />
          </div>
        )}
        {children}
      </div>
      <div className="montase-pratinjau-kendali">
        {lengkap && (
          <button type="button" className="btn-secondary montase-ikon" disabled={!siap}
                  onClick={() => ke(bingkai - 1)} aria-label={t('montase.pratinjau.mundur')}
                  title={t('montase.pratinjau.mundur')}
          >
            <ChevronLeft size={14} />
          </button>
        )}
        <button
          type="button"
          className="btn-secondary montase-ikon"
          disabled={!siap}
          onClick={() => kirim(main ? 'jeda' : 'putar')}
          aria-label={main ? t('montase.pratinjau.jeda') : t('montase.pratinjau.putar')}
        >
          {main ? <Pause size={14} /> : <Play size={14} />}
        </button>
        {lengkap && (
          <button type="button" className="btn-secondary montase-ikon" disabled={!siap}
                  onClick={() => ke(bingkai + 1)} aria-label={t('montase.pratinjau.maju')}
                  title={t('montase.pratinjau.maju')}
          >
            <ChevronRight size={14} />
          </button>
        )}
        <input
          type="range"
          min={0}
          max={Math.max(0, u.durasi - 1)}
          value={Math.min(bingkai, u.durasi - 1)}
          disabled={!siap}
          aria-label={t('montase.pratinjau.geser')}
          onChange={(e) => ke(Number(e.target.value))}
        />
        <span className="montase-pratinjau-waktu" data-bingkai={bingkai}>
          {t('montase.pratinjau.posisi', { detik, bingkai })}
        </span>
        {lengkap && (
          <>
            <button type="button" className={`btn-secondary montase-ikon ${garis ? 'aktif' : ''}`}
                    aria-pressed={garis} onClick={() => setGaris((v) => !v)}
                    title={t('montase.pratinjau.zona')} aria-label={t('montase.pratinjau.zona')}
            >
              <ScanLine size={14} />
            </button>
            <button type="button" className="btn-secondary montase-ikon" onClick={layarPenuh}
                    title={t('montase.pratinjau.penuh')} aria-label={t('montase.pratinjau.penuh')}
            >
              <Maximize size={14} />
            </button>
          </>
        )}
      </div>
    </div>
  );
});

export default PratinjauKotakPasir;
