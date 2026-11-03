/**
 * Linimasa editor Montase (JOB-4 M2.2-M2.4, M2.7).
 *
 * Semua perubahan dokumen lewat fungsi murni di model/suntingan.js; komponen
 * ini hanya menerjemahkan penunjuk (mouse/pena/sentuh) menjadi panggilan
 * fungsi itu. Seretan selalu dihitung dari dokumen SAAT SERETAN DIMULAI
 * ditambah selisih penunjuk, bukan ditumpuk per gerakan, jadi tidak ada
 * galat pembulatan yang menumpuk dan satu seretan menjadi satu langkah batal
 * (`gabung` unik per seretan).
 *
 * Yang ada:
 *   - seret item (waktu dan, untuk satu item, pindah lajur sejenis), pangkas
 *     kiri/kanan dari tepinya, pilih banyak dengan Shift/Ctrl atau kotak seret;
 *     satu item yang dilepas di atas item lain DISISIPKAN di situ dan yang
 *     lain bergeser (cara menukar urutan klip, seperti CapCut);
 *   - magnet ke awal, garis putar, tepi item lain, dan penanda (8 piksel di
 *     layar, jadi makin diperbesar makin halus), bisa dimatikan;
 *   - penggaris untuk menggosok (scrub), penanda di penggaris;
 *   - perbesar/perkecil (tombol, Ctrl+gulir, + / −) berjangkar di garis putar
 *     atau di penunjuk;
 *   - kepala lajur: ganti nama (klik dua kali), kunci, bisu, sembunyi;
 *   - bahan diseret dari panel Bahan jatuh di lajur dan bingkai tempat dilepas.
 *
 * Lajur ditampilkan TERBALIK dari urutan di dokumen: lajur yang digambar
 * paling depan (terakhir di dokumen) tampil paling atas, sama dengan CapCut.
 * Lajur suara selalu di bawah.
 *
 * Kinerja (proyek 50 item): item dibungkus `memo` dan fungsi murni menjaga
 * identitas item yang tidak berubah, jadi menyeret satu item hanya menggambar
 * ulang item itu. Garis putar membaca penyimpan sendiri (garisPutar.js),
 * bukan state editor, jadi pemutaran tidak menggambar ulang linimasa.
 */
import React, {
  forwardRef, memo, useCallback, useEffect, useImperativeHandle, useLayoutEffect, useMemo,
  useRef, useState,
} from 'react';
import {
  Bookmark, Captions, CopyPlus, Eye, EyeOff, Film, FoldHorizontal, Image as Gambar, Lock, LockOpen, Magnet, Music,
  Redo2, Scissors, Snowflake, Sparkles, Trash2, Type, Undo2, Volume2, VolumeX, ZoomIn,
  ZoomOut, Maximize2,
} from 'lucide-react';
import { useT, angka } from '../../../lib/i18n';
import { alamatBahan } from '../api.js';
import { cariItem } from '../model/dokumen.js';
import {
  pangkasKanan, pangkasKiri, pindahItem, sisipkan, tempelKe, titikMagnet, titikSisip,
} from '../model/suntingan.js';
import { JENIS_SERET_BAHAN, kodeWaktu, useGaris } from './garisPutar.js';

const IKON_LAJUR = { video: Film, teks: Type, motion: Sparkles, audio: Music };
export const LEBAR_LABEL = 150;
const AMBANG_MAGNET = 8;
const AMBANG_SERET = 3;
export const PPS_MIN = 2;
export const PPS_MAX = 600;
const LANGKAH_ZOOM = 1.5;
const LANGKAH_PENGGARIS = [0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600];
const JARAK_LABEL = 72;

// Puncak suara per bahan, sekali ambil per sesi (berkasnya tidak berubah).
const simpananGelombang = new Map();
function ambilGelombang(token, bahanId) {
  if (!simpananGelombang.has(bahanId)) {
    const janji = fetch(alamatBahan(token, bahanId, { turunan: 'gelombang' }))
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null)
      .then((d) => {
        if (!d) simpananGelombang.delete(bahanId);
        return d;
      });
    simpananGelombang.set(bahanId, janji);
  }
  return simpananGelombang.get(bahanId);
}

/** Satu jalur SVG (bukan ribuan persegi) supaya audio lima menit tetap ringan. */
function Gelombang({ token, bahanId, potongAwal, durasi, fps, kecepatan, lebar }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    let hidup = true;
    if (!token) return undefined;
    ambilGelombang(token, bahanId).then((d) => { if (hidup) setData(d); });
    return () => { hidup = false; };
  }, [token, bahanId]);
  const jalur = useMemo(() => {
    if (!data?.puncak?.length) return null;
    const perDetik = data.per_detik || 20;
    const awal = Math.floor((potongAwal / fps) * perDetik);
    const n = Math.max(1, Math.ceil(((durasi * kecepatan) / fps) * perDetik));
    const potong = data.puncak.slice(awal, awal + n);
    if (!potong.length) return null;
    // Paling banyak satu titik per dua piksel layar.
    const langkah = Math.max(1, Math.ceil(potong.length / Math.max(1, lebar / 2)));
    const titik = [];
    for (let i = 0; i < potong.length; i += langkah) {
      let v = 0;
      for (let j = i; j < Math.min(potong.length, i + langkah); j += 1) v = Math.max(v, potong[j]);
      titik.push([i, v]);
    }
    const atas = titik.map(([x, v]) => `${x},${(50 - v * 48).toFixed(1)}`).join(' L');
    const bawah = titik.slice().reverse().map(([x, v]) => `${x},${(50 + v * 48).toFixed(1)}`).join(' L');
    return { d: `M${atas} L${bawah} Z`, lebar: potong.length };
  }, [data, potongAwal, durasi, fps, kecepatan, lebar]);
  if (!jalur) return null;
  return (
    <svg className="montase-gelombang" viewBox={`0 0 ${jalur.lebar} 100`} preserveAspectRatio="none" aria-hidden>
      <path d={jalur.d} />
    </svg>
  );
}

const ItemLinimasa = memo(function ItemLinimasa({
  item, pps, fps, token, dipilih, siap, bahan, kunci, onTekan,
}) {
  const t = useT();
  const kiri = (item.mulai / fps) * pps;
  const lebar = Math.max(3, (item.durasi / fps) * pps);
  const k = item.kecepatan || 1;
  const gaya = { left: kiri, width: lebar };
  // Strip dan gelombang baru diminta sesudah bahannya siap. Diminta lebih
  // awal, peramban menyimpan jawaban 404-nya dan tidak bertanya lagi.
  if (item.jenis === 'video' && token && siap) {
    const panjang = bahan?.durasi ? ((bahan.durasi / k) * pps) : lebar;
    gaya.backgroundImage = `url(${alamatBahan(token, item.bahan, { turunan: 'strip' })})`;
    gaya.backgroundSize = `${panjang}px 100%`;
    gaya.backgroundPositionX = item.beku ? 0 : -(((item.potong_awal || 0) / fps / k) * pps);
  } else if (item.jenis === 'gambar' && token && siap) {
    gaya.backgroundImage = `url(${alamatBahan(token, item.bahan, { turunan: 'sampul' })})`;
    gaya.backgroundSize = 'auto 100%';
    gaya.backgroundRepeat = 'repeat-x';
  }
  let label = '';
  if (item.jenis === 'teks') label = item.teks;
  else if (item.jenis === 'motion') label = item.komponen;
  else label = bahan?.nama || item.bahan;
  const bersuara = (item.jenis === 'audio' || (item.jenis === 'video' && bahan?.ada_suara)) && !item.beku;
  return (
    <div
      role="button"
      tabIndex={-1}
      className={`montase-item montase-item-${item.jenis} ${dipilih ? 'dipilih' : ''} ${kunci ? 'terkunci' : ''}`}
      style={gaya}
      onPointerDown={(e) => onTekan(e, item)}
      title={`${label} · ${kodeWaktu(item.durasi, fps)}`}
      aria-pressed={dipilih}
      aria-label={t('montase.linimasa.item', { nama: label })}
      data-item={item.id}
    >
      {bersuara && siap && (
        <Gelombang token={token} bahanId={item.bahan} potongAwal={item.potong_awal || 0}
                   durasi={item.durasi} fps={fps} kecepatan={k} lebar={lebar} />
      )}
      {item.fade_masuk > 0 && (
        <span className="montase-item-fade kiri" style={{ width: (item.fade_masuk / fps) * pps }} aria-hidden />
      )}
      {item.fade_keluar > 0 && (
        <span className="montase-item-fade kanan" style={{ width: (item.fade_keluar / fps) * pps }} aria-hidden />
      )}
      <span className="montase-item-label">
        {item.jenis === 'gambar' && <Gambar size={11} aria-hidden />}
        {item.beku && <Snowflake size={11} aria-hidden />}
        {k !== 1 && !item.beku && <b>{angka(k)}x</b>}
        {item.asal === 'ai' && <b>AI</b>}
        <span>{label}</span>
      </span>
      {!kunci && (
        <>
          <span className="montase-item-pangkas kiri" data-pegangan="kiri" aria-hidden />
          <span className="montase-item-pangkas kanan" data-pegangan="kanan" aria-hidden />
        </>
      )}
    </div>
  );
});

function KepalaLajur({ lajur, dipilih, onPilih, onUbah }) {
  const t = useT();
  const [ganti, setGanti] = useState(false);
  const batalGanti = useRef(false);
  const Ikon = IKON_LAJUR[lajur.jenis] ?? Film;
  const tombol = (aktif, IkonNyala, IkonMati, kunci, perubahan) => (
    <button
      type="button"
      className={`montase-lajur-sakelar ${aktif ? 'aktif' : ''}`}
      aria-pressed={aktif}
      title={t(kunci)}
      aria-label={`${t(kunci)}: ${lajur.nama}`}
      onPointerDown={(e) => e.stopPropagation()}
      onClick={(e) => { e.stopPropagation(); onUbah(lajur.id, perubahan); }}
    >
      {aktif ? <IkonNyala size={12} /> : <IkonMati size={12} />}
    </button>
  );
  return (
    <div
      className={`montase-lajur-label ${dipilih ? 'dipilih' : ''}`}
      style={{ width: LEBAR_LABEL }}
      onPointerDown={(e) => { e.stopPropagation(); onPilih(lajur.id); }}
      onDoubleClick={() => setGanti(true)}
      title={t('montase.linimasa.ganti_nama')}
    >
      <Ikon size={13} aria-hidden />
      {ganti ? (
        <input
          // eslint-disable-next-line jsx-a11y/no-autofocus
          autoFocus
          defaultValue={lajur.nama}
          maxLength={60}
          aria-label={t('montase.linimasa.nama_lajur')}
          onPointerDown={(e) => e.stopPropagation()}
          onKeyDown={(e) => {
            e.stopPropagation();
            if (e.key === 'Enter') e.currentTarget.blur();
            if (e.key === 'Escape') { batalGanti.current = true; e.currentTarget.blur(); }
          }}
          onBlur={(e) => {
            const nama = e.target.value.trim();
            if (!batalGanti.current && nama && nama !== lajur.nama) onUbah(lajur.id, { nama });
            batalGanti.current = false;
            setGanti(false);
          }}
        />
      ) : <span className="montase-lajur-nama" title={lajur.nama}>{lajur.nama}</span>}
      <span className="montase-lajur-tombol">
        {lajur.jenis !== 'audio'
          && tombol(Boolean(lajur.sembunyi), EyeOff, Eye, 'montase.linimasa.sembunyi', { sembunyi: !lajur.sembunyi })}
        {(lajur.jenis === 'video' || lajur.jenis === 'audio')
          && tombol(Boolean(lajur.bisu), VolumeX, Volume2, 'montase.linimasa.bisu', { bisu: !lajur.bisu })}
        {tombol(Boolean(lajur.kunci), Lock, LockOpen, 'montase.linimasa.kunci', { kunci: !lajur.kunci })}
      </span>
    </div>
  );
}

function GarisPutar({ garis, fps, pps, main, wadah }) {
  const f = useGaris(garis);
  const x = LEBAR_LABEL + (f / fps) * pps;
  // Saat diputar, linimasa mengikuti garis putar yang keluar dari layar.
  useEffect(() => {
    const el = wadah.current;
    if (!main || !el) return;
    if (x > el.scrollLeft + el.clientWidth - 24 || x < el.scrollLeft + LEBAR_LABEL) {
      el.scrollLeft = x - LEBAR_LABEL - 40;
    }
  }, [main, x, wadah]);
  return <div className="montase-garis-putar" style={{ left: x }} aria-hidden />;
}

function WaktuGaris({ garis, fps, durasi }) {
  const f = useGaris(garis);
  return (
    <span className="montase-linimasa-waktu" data-bingkai={f}>
      {kodeWaktu(f, fps)} / {kodeWaktu(durasi, fps)}
    </span>
  );
}

function labelPenggaris(detik, langkah, fps) {
  if (langkah < 1) return kodeWaktu(Math.round(detik * fps), fps);
  const m = Math.floor(detik / 60);
  const s = Math.round(detik % 60);
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
}

const Linimasa = forwardRef(function Linimasa({
  dokumen, token, bahanSiap, pilihan, onPilih, garis, main, onKe, onUbah, onUbahLajur,
  magnet, lajurDipilih, onPilihLajur, aksi, bisaBatal, bisaUlang, onJatuhBahan,
}, ref) {
  const t = useT();
  const wadah = useRef(null);
  const isi = useRef(null);
  const lajurEl = useRef(new Map());
  const seret = useRef(null);
  const nomorSeret = useRef(0);
  const jangkar = useRef(null);
  const [lebarWadah, setLebarWadah] = useState(800);
  const [zoom, setZoom] = useState(null);
  const [garisMagnet, setGarisMagnet] = useState(null);
  const [kotak, setKotak] = useState(null);
  const fps = dokumen.kanvas.fps;

  useEffect(() => {
    const el = wadah.current;
    if (!el) return undefined;
    const amati = new ResizeObserver(([e]) => setLebarWadah(e.contentRect.width));
    amati.observe(el);
    return () => amati.disconnect();
  }, []);

  const detikDokumen = dokumen.durasi / fps;
  const detikPas = Math.max(10, detikDokumen + 2);
  const ruang = Math.max(100, lebarWadah - LEBAR_LABEL - 16);
  const ppsPas = Math.min(PPS_MAX, Math.max(PPS_MIN, ruang / detikPas));
  const pps = zoom ?? ppsPas;
  // Mode "muat" pas selebar layar. Saat diperbesar, sisakan setengah layar
  // kosong sesudah item terakhir supaya item bisa diseret melewati ujung.
  const lebarIsi = zoom === null ? ruang : Math.max(ruang, detikDokumen * pps + lebarWadah / 2);
  const detikIsi = lebarIsi / pps;

  // Nilai terbaru untuk penangan penunjuk yang dipasang sekali.
  const kini = useRef({});
  kini.current = { dokumen, pilihan, pps, magnet, fps, onUbah, onPilih, onKe, garis };

  useLayoutEffect(() => {
    const j = jangkar.current;
    const el = wadah.current;
    if (!j || !el) return;
    el.scrollLeft = Math.max(0, LEBAR_LABEL + j.detik * pps - j.layar);
    jangkar.current = null;
  }, [pps]);

  const zoomKe = useCallback((ppsBaru, detik, layar) => {
    const p = Math.min(PPS_MAX, Math.max(PPS_MIN, ppsBaru));
    jangkar.current = { detik, layar };
    setZoom(p);
  }, []);

  /** Perbesar/perkecil berjangkar di garis putar (atau tengah layar bila garisnya di luar). */
  const zoomGaris = useCallback((kali) => {
    const el = wadah.current;
    const { pps: p, fps: f, garis: g } = kini.current;
    const detik = g.get() / f;
    let layar = LEBAR_LABEL + detik * p - (el?.scrollLeft ?? 0);
    if (!el || layar < LEBAR_LABEL || layar > el.clientWidth) layar = (el?.clientWidth ?? 800) / 2;
    zoomKe(p * kali, detik, layar);
  }, [zoomKe]);

  useImperativeHandle(ref, () => ({
    perbesar: () => zoomGaris(LANGKAH_ZOOM),
    perkecil: () => zoomGaris(1 / LANGKAH_ZOOM),
    pas: () => setZoom(null),
  }), [zoomGaris]);

  // Ctrl + gulir = perbesar di titik penunjuk. Harus pendengar tidak pasif
  // supaya halaman tidak ikut diperbesar peramban.
  useEffect(() => {
    const el = wadah.current;
    if (!el) return undefined;
    const gulir = (e) => {
      if (!e.ctrlKey && !e.metaKey) return;
      e.preventDefault();
      const r = isi.current.getBoundingClientRect();
      const { pps: p } = kini.current;
      const detik = Math.max(0, (e.clientX - r.left - LEBAR_LABEL) / p);
      const layar = e.clientX - el.getBoundingClientRect().left;
      zoomKe(p * (e.deltaY < 0 ? LANGKAH_ZOOM : 1 / LANGKAH_ZOOM), detik, layar);
    };
    el.addEventListener('wheel', gulir, { passive: false });
    return () => el.removeEventListener('wheel', gulir);
  }, [zoomKe]);

  const keBingkai = useCallback((clientX) => {
    const r = isi.current.getBoundingClientRect();
    const { pps: p, fps: f } = kini.current;
    return Math.max(0, Math.round(((clientX - r.left - LEBAR_LABEL) / p) * f));
  }, []);

  const lajurDi = useCallback((clientY) => {
    for (const [id, el] of lajurEl.current) {
      const r = el.getBoundingClientRect();
      if (clientY >= r.top && clientY < r.bottom) return id;
    }
    return null;
  }, []);

  // --- seretan ------------------------------------------------------------

  const proses = useCallback(() => {
    const s = seret.current;
    if (!s?.posisi) return;
    const { x, y } = s.posisi;
    if (!s.aktif) {
      if (Math.hypot(x - s.x0, y - s.y0) < AMBANG_SERET) return;
      s.aktif = true;
    }
    const { pps: p, fps: f, magnet: m, onUbah: ubah, onPilih: pilih, garis: g } = kini.current;
    const opsi = { gabung: s.gabung, jendela: Infinity };
    const delta = Math.round(((x - s.x0) / p) * f);
    const ambang = m ? (AMBANG_MAGNET / p) * f : 0;
    const titik = ambang && s.jenis !== 'kotak' && s.jenis !== 'gosok'
      ? titikMagnet(s.dokumen, { garis: g.get(), kecuali: s.ids }) : [];
    const tempel = (nilai) => {
      if (!ambang) return { nilai, kena: null };
      const hasil = tempelKe(nilai, titik, ambang);
      return titik.includes(hasil) ? { nilai: hasil, kena: hasil } : { nilai, kena: null };
    };

    if (s.jenis === 'gosok') {
      kini.current.onKe(keBingkai(x));
      return;
    }
    if (s.jenis === 'kotak') {
      const r = isi.current.getBoundingClientRect();
      const kiri = Math.min(s.x0, x);
      const kanan = Math.max(s.x0, x);
      const atas = Math.min(s.y0, y);
      const bawah = Math.max(s.y0, y);
      setKotak({ left: kiri - r.left, top: atas - r.top, width: kanan - kiri, height: bawah - atas });
      const f0 = ((kiri - r.left - LEBAR_LABEL) / p) * f;
      const f1 = ((kanan - r.left - LEBAR_LABEL) / p) * f;
      const kena = new Set(s.awal);
      for (const lajur of kini.current.dokumen.lajur) {
        const el = lajurEl.current.get(lajur.id);
        if (!el) continue;
        const rl = el.getBoundingClientRect();
        if (rl.bottom < atas || rl.top > bawah) continue;
        for (const i of lajur.item) {
          if (i.mulai < f1 && i.mulai + i.durasi > f0) kena.add(i.id);
        }
      }
      pilih([...kena]);
      return;
    }
    if (s.jenis === 'pindah') {
      const item = s.ids.map((id) => cariItem(s.dokumen, id)?.item).filter(Boolean);
      if (!item.length) return;
      const awal = Math.min(...item.map((i) => i.mulai));
      const akhir = Math.max(...item.map((i) => i.mulai + i.durasi));
      let geser = delta;
      let kena = null;
      const a = tempel(awal + delta);
      const b = tempel(akhir + delta);
      if (a.kena !== null && (b.kena === null || Math.abs(a.kena - awal - delta) <= Math.abs(b.kena - akhir - delta))) {
        geser = a.kena - awal; kena = a.kena;
      } else if (b.kena !== null) {
        geser = b.kena - akhir; kena = b.kena;
      }
      const tujuan = s.ids.length === 1 ? lajurDi(y) : null;
      let hasil = pindahItem(s.dokumen, s.ids, geser, tujuan);
      if (s.ids.length === 1) {
        // Menimpa klip lain di lajur yang sama: sisipkan (lihat titikSisip).
        const lajurAkhir = cariItem(hasil, s.ids[0])?.lajur.id;
        const di = titikSisip(s.dokumen, s.ids[0], lajurAkhir, item[0].mulai + geser, keBingkai(x));
        if (di !== null) {
          hasil = sisipkan(s.dokumen, s.ids[0], lajurAkhir, di);
          kena = di;
        }
      }
      ubah(() => hasil, opsi);
      setGarisMagnet(kena);
      return;
    }
    const item = cariItem(s.dokumen, s.ids[0])?.item;
    if (!item) return;
    if (s.jenis === 'pangkas-kiri') {
      const { nilai, kena } = tempel(item.mulai + delta);
      ubah(() => pangkasKiri(s.dokumen, item.id, nilai), opsi);
      setGarisMagnet(kena);
    } else if (s.jenis === 'pangkas-kanan') {
      const { nilai, kena } = tempel(item.mulai + item.durasi + delta);
      ubah(() => pangkasKanan(s.dokumen, item.id, nilai), opsi);
      setGarisMagnet(kena);
    }
  }, [keBingkai, lajurDi]);

  const gerak = useCallback((e) => {
    const s = seret.current;
    if (!s) return;
    s.posisi = { x: e.clientX, y: e.clientY };
    if (!s.raf) {
      s.raf = requestAnimationFrame(() => {
        if (seret.current === s) { s.raf = 0; proses(); }
      });
    }
  }, [proses]);

  const lepas = useCallback((e) => {
    const s = seret.current;
    window.removeEventListener('pointermove', gerak);
    window.removeEventListener('pointerup', lepas);
    window.removeEventListener('pointercancel', lepas);
    if (!s) return;
    if (s.raf) cancelAnimationFrame(s.raf);
    s.posisi = { x: e.clientX, y: e.clientY };
    s.raf = 0;
    proses();
    seret.current = null;
    setGarisMagnet(null);
    setKotak(null);
    if (!s.aktif) {
      if (s.jenis === 'pindah' && s.ids.length > 1) kini.current.onPilih([s.itemId]);
      if (s.jenis === 'kotak') {
        if (!s.tambah) kini.current.onPilih([]);
        kini.current.onKe(keBingkai(s.x0));
      }
    }
  }, [gerak, proses, keBingkai]);

  const mulaiSeret = useCallback((data, e) => {
    seret.current = {
      ...data, x0: e.clientX, y0: e.clientY, aktif: false, raf: 0, posisi: null,
      dokumen: kini.current.dokumen, gabung: `seret:${(nomorSeret.current += 1)}`,
    };
    window.addEventListener('pointermove', gerak);
    window.addEventListener('pointerup', lepas);
    window.addEventListener('pointercancel', lepas);
  }, [gerak, lepas]);

  useEffect(() => () => {
    window.removeEventListener('pointermove', gerak);
    window.removeEventListener('pointerup', lepas);
    window.removeEventListener('pointercancel', lepas);
  }, [gerak, lepas]);

  const tekanItem = useCallback((e, item) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    const { dokumen: d, pilihan: pil, onPilih: pilih } = kini.current;
    const hit = cariItem(d, item.id);
    if (!hit) return;
    if (e.shiftKey || e.ctrlKey || e.metaKey) {
      pilih(pil.includes(item.id) ? pil.filter((x) => x !== item.id) : [...pil, item.id]);
      return;
    }
    let ids = pil;
    if (!pil.includes(item.id)) { ids = [item.id]; pilih(ids); }
    if (hit.lajur.kunci) return;
    const pegangan = e.target?.dataset?.pegangan;
    if (pegangan) {
      mulaiSeret({ jenis: `pangkas-${pegangan}`, ids: [item.id], itemId: item.id }, e);
    } else {
      const bebas = ids.filter((id) => !cariItem(d, id)?.lajur.kunci);
      mulaiSeret({ jenis: 'pindah', ids: bebas, itemId: item.id }, e);
    }
  }, [mulaiSeret]);

  const tekanLatar = (e) => {
    if (e.button !== 0) return;
    const tambah = e.shiftKey || e.ctrlKey || e.metaKey;
    mulaiSeret({ jenis: 'kotak', ids: [], tambah, awal: tambah ? pilihan : [] }, e);
  };

  const tekanPenggaris = (e) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    onKe(keBingkai(e.clientX));
    mulaiSeret({ jenis: 'gosok', ids: [] }, e);
    seret.current.aktif = true;
  };

  // --- bahan dari panel ------------------------------------------------------

  const izinkanJatuh = (e) => {
    if (!e.dataTransfer.types.includes(JENIS_SERET_BAHAN)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
  };
  const jatuh = (lajurId) => (e) => {
    const data = e.dataTransfer.getData(JENIS_SERET_BAHAN);
    if (!data) return;
    e.preventDefault();
    let bahan;
    try { bahan = JSON.parse(data); } catch { return; }
    let mulai = keBingkai(e.clientX);
    if (magnet) {
      const titik = titikMagnet(dokumen, { garis: garis.get() });
      mulai = tempelKe(mulai, titik, (AMBANG_MAGNET / pps) * fps);
    }
    onJatuhBahan(bahan, { mulai, lajurId });
  };

  // --- tampilan ----------------------------------------------------------------

  const urutanTampil = useMemo(() => {
    const gambar = dokumen.lajur.filter((l) => l.jenis !== 'audio').slice().reverse();
    return [...gambar, ...dokumen.lajur.filter((l) => l.jenis === 'audio')];
  }, [dokumen.lajur]);
  const pilihanSet = useMemo(() => new Set(pilihan), [pilihan]);

  const langkah = LANGKAH_PENGGARIS.find((l) => l * pps >= JARAK_LABEL) ?? 600;
  const tanda = [];
  for (let i = 0; i * langkah <= detikIsi; i += 1) tanda.push(i * langkah);
  const adaPilihan = pilihan.length > 0;

  return (
    <section className="montase-linimasa" aria-label={t('montase.linimasa.judul')}>
      <div className="montase-linimasa-alat">
        <button type="button" className="btn-secondary montase-ikon" disabled={!bisaBatal}
                onClick={aksi.batal} title={t('montase.linimasa.batal')} aria-label={t('montase.linimasa.batal')}
        >
          <Undo2 size={13} />
        </button>
        <button type="button" className="btn-secondary montase-ikon" disabled={!bisaUlang}
                onClick={aksi.ulang} title={t('montase.linimasa.ulang')} aria-label={t('montase.linimasa.ulang')}
        >
          <Redo2 size={13} />
        </button>
        <span className="montase-alat-pemisah" aria-hidden />
        <button type="button" className="btn-secondary montase-ikon" onClick={aksi.belah}
                title={t('montase.linimasa.belah')} aria-label={t('montase.linimasa.belah')}
        >
          <Scissors size={13} />
        </button>
        <button type="button" className="btn-secondary montase-ikon" disabled={!adaPilihan}
                onClick={aksi.gandakan} title={t('montase.linimasa.gandakan')} aria-label={t('montase.linimasa.gandakan')}
        >
          <CopyPlus size={13} />
        </button>
        <button type="button" className="btn-secondary montase-ikon" disabled={!adaPilihan}
                onClick={aksi.bekukan} title={t('montase.linimasa.bekukan')} aria-label={t('montase.linimasa.bekukan')}
        >
          <Snowflake size={13} />
        </button>
        <button type="button" className="btn-secondary montase-ikon" onClick={aksi.rapatkan}
                title={t('montase.linimasa.rapatkan')} aria-label={t('montase.linimasa.rapatkan')}
        >
          <FoldHorizontal size={13} />
        </button>
        <button type="button" className="btn-secondary montase-ikon" disabled={!adaPilihan}
                onClick={aksi.hapus} title={t('montase.linimasa.hapus')} aria-label={t('montase.linimasa.hapus')}
        >
          <Trash2 size={13} />
        </button>
        <span className="montase-alat-pemisah" aria-hidden />
        <button type="button" className="btn-secondary montase-ikon" onClick={aksi.penanda}
                title={t('montase.linimasa.penanda')} aria-label={t('montase.linimasa.penanda')}
        >
          <Bookmark size={13} />
        </button>
        <button type="button" className={`btn-secondary montase-ikon ${magnet ? 'aktif' : ''}`}
                aria-pressed={magnet} onClick={aksi.magnet}
                title={t('montase.linimasa.magnet')} aria-label={t('montase.linimasa.magnet')}
        >
          <Magnet size={13} />
        </button>
        <span className="montase-alat-pemisah" aria-hidden />
        <button type="button" className="btn-secondary" onClick={aksi.tambahTeks}>
          <Type size={13} />{t('montase.linimasa.tambah_teks')}
        </button>
        <button type="button" className="btn-secondary" onClick={aksi.tambahMotion}>
          <Sparkles size={13} />{t('montase.linimasa.tambah_animasi')}
        </button>
        <button type="button" className="btn-secondary" onClick={aksi.subtitle} disabled={aksi.subtitleSibuk}
                title={t('montase.subtitle.tombol_ket')}
        >
          <Captions size={13} />{t('montase.subtitle.tombol')}
        </button>
        <select className="montase-tambah-lajur" value="" aria-label={t('montase.linimasa.tambah_lajur')}
                onChange={(e) => { if (e.target.value) aksi.tambahLajur(e.target.value); }}
        >
          <option value="">{t('montase.linimasa.tambah_lajur')}</option>
          {['video', 'teks', 'motion', 'audio'].map((j) => (
            <option key={j} value={j}>{t(`montase.lajur.${j}`)}</option>
          ))}
        </select>
        <span className="montase-linimasa-spasi" />
        <WaktuGaris garis={garis} fps={fps} durasi={dokumen.durasi} />
        <button type="button" className="btn-secondary montase-ikon" onClick={() => zoomGaris(1 / LANGKAH_ZOOM)}
                title={t('montase.linimasa.perkecil')} aria-label={t('montase.linimasa.perkecil')}
        >
          <ZoomOut size={13} />
        </button>
        <button type="button" className="btn-secondary montase-ikon" onClick={() => zoomGaris(LANGKAH_ZOOM)}
                title={t('montase.linimasa.perbesar')} aria-label={t('montase.linimasa.perbesar')}
        >
          <ZoomIn size={13} />
        </button>
        <button type="button" className={`btn-secondary montase-ikon ${zoom === null ? 'aktif' : ''}`}
                onClick={() => setZoom(null)}
                title={t('montase.linimasa.pas')} aria-label={t('montase.linimasa.pas')}
        >
          <Maximize2 size={13} />
        </button>
      </div>

      <div className="montase-linimasa-gulir" ref={wadah}>
        <div className="montase-linimasa-isi" ref={isi} style={{ width: lebarIsi + LEBAR_LABEL }}>
          <div className="montase-penggaris-baris">
            <div className="montase-penggaris-sudut" style={{ width: LEBAR_LABEL }} />
            <div className="montase-penggaris" style={{ width: lebarIsi }} onPointerDown={tekanPenggaris}>
              {tanda.map((d) => (
                <span key={d} style={{ left: d * pps }}>{labelPenggaris(d, langkah, fps)}</span>
              ))}
              {(dokumen.penanda ?? []).map((p) => (
                <button
                  key={p.t}
                  type="button"
                  className="montase-penanda"
                  style={{ left: (p.t / fps) * pps }}
                  title={p.label || kodeWaktu(p.t, fps)}
                  aria-label={t('montase.linimasa.ke_penanda', { nama: p.label || kodeWaktu(p.t, fps) })}
                  onPointerDown={(e) => { e.stopPropagation(); onKe(p.t); }}
                >
                  {p.label && <span>{p.label}</span>}
                </button>
              ))}
            </div>
          </div>
          {urutanTampil.map((lajur) => (
            <div key={lajur.id}
                 className={`montase-lajur montase-lajur-${lajur.jenis} ${lajur.kunci ? 'terkunci' : ''} ${lajur.sembunyi ? 'tersembunyi' : ''} ${lajur.bisu ? 'dibisukan' : ''}`}
            >
              <KepalaLajur lajur={lajur} dipilih={lajurDipilih === lajur.id}
                           onPilih={onPilihLajur} onUbah={onUbahLajur} />
              <div
                className="montase-lajur-isi"
                style={{ width: lebarIsi }}
                ref={(el) => { if (el) lajurEl.current.set(lajur.id, el); else lajurEl.current.delete(lajur.id); }}
                onPointerDown={tekanLatar}
                onDragOver={izinkanJatuh}
                onDrop={jatuh(lajur.id)}
              >
                {lajur.item.map((item) => (
                  <ItemLinimasa key={item.id} item={item} pps={pps} fps={fps} token={token}
                                dipilih={pilihanSet.has(item.id)} kunci={Boolean(lajur.kunci)}
                                bahan={item.bahan ? dokumen.bahan[item.bahan] : null}
                                siap={Boolean(item.bahan && bahanSiap?.has(item.bahan))}
                                onTekan={tekanItem} />
                ))}
              </div>
            </div>
          ))}
          <div className="montase-linimasa-sisa" onPointerDown={tekanLatar} />
          {garisMagnet !== null && (
            <div className="montase-garis-magnet" style={{ left: LEBAR_LABEL + (garisMagnet / fps) * pps }} aria-hidden />
          )}
          {kotak && <div className="montase-kotak-pilih" style={kotak} aria-hidden />}
          <GarisPutar garis={garis} fps={fps} pps={pps} main={main} wadah={wadah} />
        </div>
      </div>
    </section>
  );
});

export default Linimasa;
