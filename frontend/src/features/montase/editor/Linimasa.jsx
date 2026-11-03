/**
 * Linimasa editor Montase, versi Tahap 1 (JOB-4 M1.7).
 *
 * Yang ada sekarang: lajur dan item yang lebarnya sebanding waktu, strip
 * gambar dan gelombang suara di item, garis putar, klik penggaris untuk
 * melompat, pilih item, tukar urutan, dan hapus. Seret, pangkas, belah,
 * magnet, perbesar, dan pintasan keyboard datang di Tahap 2.
 *
 * Lajur ditampilkan TERBALIK dari urutan di dokumen: lajur yang digambar
 * paling depan (terakhir di dokumen) tampil paling atas, sama dengan CapCut.
 * Lajur suara selalu di bawah.
 */
import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ArrowLeft, ArrowRight, Film, Image as Gambar, Music, Sparkles, Trash2, Type,
} from 'lucide-react';
import { useT } from '../../../lib/i18n';
import { formatTime } from '../../../utils/timeFormat';
import { alamatBahan } from '../api.js';

const IKON_LAJUR = { video: Film, teks: Type, motion: Sparkles, audio: Music };
const LEBAR_LABEL = 120;

function Gelombang({ token, bahanId, potongAwal, durasi, fps }) {
  const [puncak, setPuncak] = useState(null);
  useEffect(() => {
    let hidup = true;
    if (!token) return undefined;
    fetch(alamatBahan(token, bahanId, { turunan: 'gelombang' }))
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => { if (hidup) setPuncak(d); })
      .catch(() => {});
    return () => { hidup = false; };
  }, [token, bahanId]);
  if (!puncak?.puncak?.length) return null;
  const perDetik = puncak.per_detik || 20;
  const awal = Math.floor((potongAwal / fps) * perDetik);
  const n = Math.max(1, Math.ceil((durasi / fps) * perDetik));
  const potong = puncak.puncak.slice(awal, awal + n);
  return (
    <svg className="montase-gelombang" viewBox={`0 0 ${potong.length} 100`} preserveAspectRatio="none" aria-hidden>
      {potong.map((v, i) => (
        <rect key={i} x={i} y={50 - v * 48} width={0.8} height={Math.max(1, v * 96)} />
      ))}
    </svg>
  );
}

function Item({ item, pps, fps, token, dipilih, onPilih, namaBahan, siap }) {
  const t = useT();
  const kiri = (item.mulai / fps) * pps;
  const lebar = Math.max(4, (item.durasi / fps) * pps);
  // Strip dan gelombang baru diminta sesudah bahannya siap. Diminta lebih
  // awal, peramban menyimpan jawaban 404-nya dan tidak bertanya lagi.
  const strip = item.jenis === 'video' && token && siap
    ? `url(${alamatBahan(token, item.bahan, { turunan: 'strip' })})` : undefined;
  let label = '';
  if (item.jenis === 'teks') label = item.teks;
  else if (item.jenis === 'motion') label = item.komponen;
  else label = namaBahan ?? item.bahan;
  return (
    <button
      type="button"
      className={`montase-item montase-item-${item.jenis} ${dipilih ? 'dipilih' : ''}`}
      style={{ left: kiri, width: lebar, backgroundImage: strip }}
      onClick={(e) => { e.stopPropagation(); onPilih(item.id); }}
      title={`${label} · ${formatTime(item.durasi / fps)}`}
      aria-pressed={dipilih}
      aria-label={t('montase.linimasa.item', { nama: label })}
    >
      {item.jenis === 'gambar' && <Gambar size={12} aria-hidden />}
      {item.jenis === 'audio' && siap && (
        <Gelombang token={token} bahanId={item.bahan} potongAwal={item.potong_awal || 0}
                   durasi={item.durasi} fps={fps} />
      )}
      <span className="montase-item-label">{label}</span>
    </button>
  );
}

export default function Linimasa({
  dokumen, bingkai, token, dipilih, onPilih, onKe, onTambahTeks, onTambahMotion,
  onHapus, onPindah, bahanSiap,
}) {
  const t = useT();
  const wadah = useRef(null);
  const [lebarWadah, setLebarWadah] = useState(800);
  const fps = dokumen.kanvas.fps;
  const detikTotal = Math.max(10, dokumen.durasi / fps + 2);

  useEffect(() => {
    const el = wadah.current;
    if (!el) return undefined;
    const amati = new ResizeObserver(([e]) => setLebarWadah(e.contentRect.width));
    amati.observe(el);
    return () => amati.disconnect();
  }, []);

  // Muat seluruh isi di lebar yang ada; perbesar/perkecil datang di Tahap 2.
  const pps = Math.max(8, (lebarWadah - LEBAR_LABEL - 16) / detikTotal);
  const lebarIsi = detikTotal * pps;
  const langkah = pps >= 60 ? 1 : pps >= 25 ? 2 : pps >= 12 ? 5 : 10;

  const urutanTampil = useMemo(() => {
    const gambar = dokumen.lajur.filter((l) => l.jenis !== 'audio').slice().reverse();
    return [...gambar, ...dokumen.lajur.filter((l) => l.jenis === 'audio')];
  }, [dokumen.lajur]);

  const lompatKe = (e) => {
    const kotak = e.currentTarget.getBoundingClientRect();
    const detik = (e.clientX - kotak.left) / pps;
    onKe(Math.max(0, Math.round(detik * fps)));
  };

  const garisPutar = (bingkai / fps) * pps;
  return (
    <section className="montase-linimasa" aria-label={t('montase.linimasa.judul')}>
      <div className="montase-linimasa-alat">
        <span className="montase-linimasa-waktu">
          {formatTime(bingkai / fps)} / {formatTime(dokumen.durasi / fps)}
        </span>
        <button type="button" className="btn-secondary" onClick={onTambahTeks}>
          <Type size={13} />{t('montase.linimasa.tambah_teks')}
        </button>
        <button type="button" className="btn-secondary" onClick={onTambahMotion}>
          <Sparkles size={13} />{t('montase.linimasa.tambah_animasi')}
        </button>
        <span className="montase-linimasa-spasi" />
        <button type="button" className="btn-secondary montase-ikon" disabled={!dipilih}
                onClick={() => onPindah(-1)} title={t('montase.linimasa.ke_kiri')}
                aria-label={t('montase.linimasa.ke_kiri')}
        >
          <ArrowLeft size={13} />
        </button>
        <button type="button" className="btn-secondary montase-ikon" disabled={!dipilih}
                onClick={() => onPindah(1)} title={t('montase.linimasa.ke_kanan')}
                aria-label={t('montase.linimasa.ke_kanan')}
        >
          <ArrowRight size={13} />
        </button>
        <button type="button" className="btn-secondary montase-ikon" disabled={!dipilih}
                onClick={onHapus} title={t('montase.linimasa.hapus')}
                aria-label={t('montase.linimasa.hapus')}
        >
          <Trash2 size={13} />
        </button>
      </div>

      <div className="montase-linimasa-gulir" ref={wadah} onClick={() => onPilih(null)}>
        <div className="montase-linimasa-isi" style={{ width: lebarIsi + LEBAR_LABEL }}>
          <div className="montase-penggaris" style={{ marginLeft: LEBAR_LABEL, width: lebarIsi }}
               onClick={(e) => { e.stopPropagation(); lompatKe(e); }}
          >
            {Array.from({ length: Math.floor(detikTotal / langkah) + 1 }, (_, i) => (
              <span key={i} style={{ left: i * langkah * pps }}>{formatTime(i * langkah)}</span>
            ))}
          </div>
          {urutanTampil.map((lajur) => {
            const Ikon = IKON_LAJUR[lajur.jenis] ?? Film;
            return (
              <div key={lajur.id} className={`montase-lajur montase-lajur-${lajur.jenis}`}>
                <div className="montase-lajur-label" style={{ width: LEBAR_LABEL }}>
                  <Ikon size={13} aria-hidden />
                  <span>{lajur.nama}</span>
                </div>
                <div className="montase-lajur-isi" style={{ width: lebarIsi }}>
                  {lajur.item.map((item) => (
                    <Item key={item.id} item={item} pps={pps} fps={fps} token={token}
                          dipilih={dipilih === item.id} onPilih={onPilih}
                          namaBahan={dokumen.bahan[item.bahan]?.nama}
                          siap={Boolean(item.bahan && bahanSiap?.has(item.bahan))} />
                  ))}
                </div>
              </div>
            );
          })}
          <div className="montase-garis-putar" style={{ left: LEBAR_LABEL + garisPutar }} aria-hidden />
        </div>
      </div>
    </section>
  );
}
