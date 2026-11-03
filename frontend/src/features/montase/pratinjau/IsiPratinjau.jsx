/**
 * Isi iframe kotak pasir: satu Remotion Player yang dikendalikan induknya.
 *
 * Halaman ini dimuat dengan `sandbox="allow-scripts"` tanpa
 * `allow-same-origin`, jadi kode di dalamnya (termasuk komponen animasi buatan
 * AI) tidak bisa membaca cookie, penyimpanan, atau DOM editor. Ia hanya
 * menerima dokumen lewat postMessage dan melaporkan bingkai yang sedang tampil.
 *
 * Tidak ada teks antarmuka di sini: semua yang dilihat pengguna digambar oleh
 * induknya (pegangan, garis zona aman, tombol), lihat PratinjauKotakPasir.jsx.
 */
import React, { useEffect, useRef, useState } from 'react';
import { Player } from '@remotion/player';
import { Komposisi, ukuranDokumen } from '../komposisi/index.js';
import { pesan, pesanSah } from './jembatan.js';

function kirim(jenis, isi) {
  window.parent.postMessage(pesan(jenis, isi), '*');
}

export default function IsiPratinjau() {
  const pemutar = useRef(null);
  const [muatan, setMuatan] = useState(null);

  useEffect(() => {
    const dengar = (e) => {
      if (e.source !== window.parent || !pesanSah(e.data)) return;
      const d = e.data;
      if (d.jenis === 'muat') setMuatan({ dokumen: d.dokumen, sumber: d.sumber ?? {} });
      else if (d.jenis === 'putar') pemutar.current?.play();
      else if (d.jenis === 'jeda') pemutar.current?.pause();
      else if (d.jenis === 'ke' && Number.isFinite(d.bingkai)) pemutar.current?.seekTo(d.bingkai);
    };
    const galat = (e) => kirim('galat', { pesan: String(e?.message ?? e?.reason?.message ?? e?.reason ?? e) });
    window.addEventListener('message', dengar);
    window.addEventListener('error', galat);
    window.addEventListener('unhandledrejection', galat);
    kirim('siap');
    return () => {
      window.removeEventListener('message', dengar);
      window.removeEventListener('error', galat);
      window.removeEventListener('unhandledrejection', galat);
    };
  }, []);

  useEffect(() => {
    const p = pemutar.current;
    if (!p) return undefined;
    const bingkai = (e) => kirim('bingkai', { bingkai: e.detail.frame });
    const main = () => kirim('main', { main: true });
    const jeda = () => kirim('main', { main: false });
    const galat = (e) => kirim('galat', { pesan: String(e.detail?.error?.message ?? e.detail?.error ?? 'galat') });
    p.addEventListener('frameupdate', bingkai);
    p.addEventListener('play', main);
    p.addEventListener('pause', jeda);
    p.addEventListener('ended', jeda);
    p.addEventListener('error', galat);
    return () => {
      p.removeEventListener('frameupdate', bingkai);
      p.removeEventListener('play', main);
      p.removeEventListener('pause', jeda);
      p.removeEventListener('ended', jeda);
      p.removeEventListener('error', galat);
    };
  }, [muatan]);

  if (!muatan) return null;
  const u = ukuranDokumen(muatan.dokumen);
  return (
    <Player
      ref={pemutar}
      component={Komposisi}
      inputProps={muatan}
      durationInFrames={u.durasi}
      compositionWidth={u.lebar}
      compositionHeight={u.tinggi}
      fps={u.fps}
      style={{ width: '100%', height: '100%' }}
      acknowledgeRemotionLicense
    />
  );
}
