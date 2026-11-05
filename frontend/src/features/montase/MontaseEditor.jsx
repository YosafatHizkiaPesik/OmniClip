/**
 * Editor satu proyek Montase (/montase/:proyekId, JOB-4 M1.7-M1.9, Tahap 2).
 *
 * Empat area yang ukurannya bisa diatur: Bahan (kiri), Pratinjau (tengah),
 * Properti (kanan), Linimasa (bawah). Semua perubahan lewat fungsi murni di
 * model/ (dokumen.js, suntingan.js), dicatat di riwayat batal/ulang
 * (riwayat.js, 100 langkah), lalu disimpan otomatis 1,5 detik sesudah
 * perubahan terakhir.
 *
 * Riwayat dipegang di ref DAN state: ref adalah kebenaran (dibaca penangan
 * tombol dan seretan tanpa menunggu React menggambar), state memicu gambar
 * ulang. Dengan begitu dua operasi dalam satu peristiwa tidak saling menimpa.
 *
 * Penyimpanan BERURUTAN: simpan berikutnya menunggu yang sebelumnya selesai
 * dan memakai revisi yang baru dikembalikan. Tanpa itu, dua perubahan cepat
 * berangkat dengan revisi yang sama dan yang kedua ditolak 409 oleh server
 * kita sendiri. 409 yang sungguhan (tab atau perangkat lain) menghentikan
 * simpan otomatis dan meminta muat ulang, bukan menimpa diam-diam.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft, Check, CircleHelp, CloudOff, Download, Loader2, MonitorSmartphone, RefreshCw, Send, Upload,
} from 'lucide-react';
import { useT } from '../../lib/i18n';
import { useJobRunner } from '../../hooks/useJob';
import JobProgress from '../../components/JobProgress';
import SiapkanTerbit from '../../components/SiapkanTerbit';
import UploadModal from '../../components/UploadModal';
import { BAWAAN } from './komposisi/index.js';
import {
  ambilProyek, ambilToken, buatNarasi, fontDipakai, komponenDipakai, periksaKemiripan, pulihkanVersi,
  simpanProyek,
  sumberPratinjau,
} from './api.js';
import useSkemaKomponen from './editor/useSkemaKomponen.js';
import {
  cariItem, tambahBahan, tambahMotion, tambahTeks, ubahItem, ubahProyek,
} from './model/dokumen.js';
import {
  aturUlangTransform, bekukan, belah, bisaHapusLajur, gandakan, gantiBahanItem, hapusBanyak,
  hapusBeriak, hapusLajur, hapusPenanda, hapusPunch, kurvaKeyframe, pasangSubtitle, rapatkan,
  rendamMusik, salin, semuaItem, tambahLajur, tambahPenanda, tambahPunch, tambahStiker, taruhSuara,
  tempel, tombolKeyframe, ubahKecepatan, ubahLajur, ubahPenanda, ubahSifatDiBingkai, ubahTransform,
} from './model/suntingan.js';
import {
  batal, bisaBatal, bisaUlang, buatRiwayat, catat, ulang,
} from './model/riwayat.js';
import PratinjauKotakPasir from './pratinjau/PratinjauKotakPasir.jsx';
import PanelBahan from './editor/PanelBahan.jsx';
import PanelProperti from './editor/PanelProperti.jsx';
import Linimasa from './editor/Linimasa.jsx';
import PeganganUbah from './editor/PeganganUbah.jsx';
import { buatGaris } from './editor/garisPutar.js';
import { TombolUsulan } from './editor/PanelAsisten.jsx';
import RiwayatVersi from './editor/RiwayatVersi.jsx';
import MeterOrisinalitas from './editor/MeterOrisinalitas.jsx';
import Teleprompter from './editor/Teleprompter.jsx';
import { hitungOrisinalitas } from './model/orisinalitas.js';
import { JendelaBantuan } from './BantuanMontase.jsx';
import { terapkanOperasi } from './model/usulan.js';

const JEDA_SIMPAN = 1500;
const ULANG_GAGAL = 5000;
const KUNCI_TATA = 'omniclip.montase.tata';
const KUNCI_MAGNET = 'omniclip.montase.magnet';
// Draf lokal (M6.4): perubahan yang belum sampai ke server bila aplikasi atau
// peramban tertutup mendadak. Dicatat per proyek, dihapus begitu tersimpan.
const KUNCI_DRAF = 'omniclip.montase.draf.';

function bacaDraf(id) {
  try { return JSON.parse(localStorage.getItem(KUNCI_DRAF + id) || 'null'); } catch { return null; }
}
function tulisDraf(id, isi) {
  try {
    if (isi) localStorage.setItem(KUNCI_DRAF + id, JSON.stringify(isi));
    else localStorage.removeItem(KUNCI_DRAF + id);
  } catch { /* penyimpanan penuh atau dimatikan: draf lokal hanya cadangan */ }
}
const TATA_BAWAAN = { kiri: 280, kanan: 300, bawah: 300 };
const DETIK_BEKU = 3;
// Selama usulan tampil, linimasa tidak menyunting: terima atau tolak dulu.
const abaikan = () => {};

// Papan klip di luar komponen: Ctrl+C di satu proyek, Ctrl+V di proyek lain.
// Metadata bahannya ikut, jadi item tetap bisa dirender di proyek tujuan.
let papanKlip = null;

function bacaMagnet() {
  try {
    return localStorage.getItem(KUNCI_MAGNET) !== '0';
  } catch {
    return true;
  }
}

/** Item di bawah garis putar pada lajur yang tidak terkunci dan terlihat. */
function itemDiGaris(dokumen, f, jenis = null) {
  return dokumen.lajur
    .filter((l) => !l.kunci && !l.sembunyi)
    .flatMap((l) => l.item)
    .filter((i) => i.mulai < f && i.mulai + i.durasi > f && (!jenis || i.jenis === jenis))
    .map((i) => i.id);
}

/** Elemen yang sedang menerima ketikan: pintasan tidak boleh mencurinya. */
function sedangMengetik(el) {
  return Boolean(el?.closest?.('input, textarea, select, [contenteditable="true"]'));
}

function bacaTata() {
  try {
    return { ...TATA_BAWAAN, ...JSON.parse(localStorage.getItem(KUNCI_TATA) || '{}') };
  } catch {
    return TATA_BAWAAN;
  }
}

function useLayarSempit() {
  const [sempit, setSempit] = useState(() => window.matchMedia('(max-width: 899px)').matches);
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 899px)');
    const ubah = (e) => setSempit(e.matches);
    mq.addEventListener('change', ubah);
    return () => mq.removeEventListener('change', ubah);
  }, []);
  return sempit;
}

/** Pembatas yang bisa diseret untuk mengubah lebar/tinggi satu area. */
function Pembatas({ arah, onGeser }) {
  const mulai = (e) => {
    e.preventDefault();
    const awal = arah === 'tegak' ? e.clientX : e.clientY;
    const gerak = (ev) => onGeser((arah === 'tegak' ? ev.clientX : ev.clientY) - awal, false);
    const lepas = (ev) => {
      onGeser((arah === 'tegak' ? ev.clientX : ev.clientY) - awal, true);
      window.removeEventListener('pointermove', gerak);
      window.removeEventListener('pointerup', lepas);
    };
    window.addEventListener('pointermove', gerak);
    window.addEventListener('pointerup', lepas);
  };
  return (
    <div className={`montase-pembatas montase-pembatas-${arah}`} onPointerDown={mulai}
         role="separator" aria-orientation={arah === 'tegak' ? 'vertical' : 'horizontal'} />
  );
}

function StatusSimpan({ status, onMuatUlang, onCobaLagi }) {
  const t = useT();
  if (status === 'menyimpan' || status === 'belum') {
    return <span className="montase-simpan"><Loader2 size={12} className="animate-spin" />{t('montase.editor.menyimpan')}</span>;
  }
  if (status === 'bentrok') {
    return (
      <span className="montase-simpan montase-simpan-galat">
        <CloudOff size={12} />{t('montase.editor.bentrok')}
        <button type="button" className="btn-secondary" onClick={onMuatUlang}>
          <RefreshCw size={12} />{t('umum.muat_ulang')}
        </button>
      </span>
    );
  }
  if (status === 'gagal') {
    return (
      <span className="montase-simpan montase-simpan-galat" role="alert">
        <CloudOff size={12} />{t('montase.editor.gagal_simpan')}
        <button type="button" className="btn-secondary" onClick={onCobaLagi}>
          <RefreshCw size={12} />{t('montase.editor.coba_lagi')}
        </button>
      </span>
    );
  }
  return <span className="montase-simpan"><Check size={12} />{t('montase.editor.tersimpan')}</span>;
}

export default function MontaseEditor() {
  const t = useT();
  const { proyekId } = useParams();
  const navigate = useNavigate();
  const sempit = useLayarSempit();
  const [riwayat, setRiwayat] = useState(null);
  const [galat, setGalat] = useState(null);
  const [galatPratinjau, setGalatPratinjau] = useState(null);
  const [token, setToken] = useState(null);
  const [pilihan, setPilihan] = useState([]);
  const [lajurDipilih, setLajurDipilih] = useState(null);
  const [magnet, setMagnet] = useState(bacaMagnet);
  const [main, setMain] = useState(false);
  const [status, setStatus] = useState('tersimpan');
  const [tata, setTata] = useState(bacaTata);
  const [bahanSiap, setBahanSiap] = useState(() => new Set());
  // Asal tiap bahan (unduhan, klip_jadi, impor, tts, rekam, ...) untuk meter orisinalitas (JOB-5 O1).
  const [asalBahan, setAsalBahan] = useState(() => new Map());
  const [garis] = useState(() => buatGaris(0));
  // Usulan asisten (M5.2): {operasi, pilih: Set, sumber, peringatan}. Selama ada,
  // pratinjau dan linimasa memperlihatkan dokumen + operasi terpilih.
  const [usulan, setUsulan] = useState(null);
  // Saran judul, caption, dan tagar untuk hasil ekspor (M5.6, keterangan.py).
  const [terbit, setTerbit] = useState(null);
  // Unggah ke YouTube/Drive lewat formulir yang sama dengan Klip jadi (M6.1).
  const [unggah, setUnggah] = useState(null);
  const [drafLama, setDrafLama] = useState(null);
  const [bantuan, setBantuan] = useState(false);
  // Teleprompter narasi (JOB-5 O2): daftar {id, teks, direkam} yang sedang direkam ulang.
  const [teleprompter, setTeleprompter] = useState(null);
  const catatBahan = useCallback((daftar) => {
    setBahanSiap(new Set(daftar.filter((b) => b.siap).map((b) => b.id)));
    setAsalBahan(new Map(daftar.map((b) => [b.id, b.asal])));
  }, []);
  const tataSeret = useRef(tata);
  const pratinjau = useRef(null);
  const linimasa = useRef(null);
  const ekspor = useJobRunner();
  const subtitleKerja = useJobRunner();
  const subtitleDipasang = useRef(null);

  const revisi = useRef(null);
  const kotor = useRef(false);
  const riwayatRef = useRef(null);
  const antrean = useRef(Promise.resolve());
  const dokumen = riwayat?.kini ?? null;

  const muat = useCallback(() => {
    setGalat(null);
    ambilProyek(proyekId)
      .then((p) => {
        revisi.current = p.revisi;
        kotor.current = false;
        riwayatRef.current = buatRiwayat(p.dokumen);
        setRiwayat(riwayatRef.current);
        setStatus('tersimpan');
        // Draf dari sesi yang tertutup sebelum sempat menyimpan: hanya berlaku
        // bila dibuat di atas revisi yang sama dengan yang ada di server.
        const draf = bacaDraf(proyekId);
        if (draf && draf.revisi === p.revisi && JSON.stringify(draf.dokumen) !== JSON.stringify(p.dokumen)) {
          setDrafLama(draf);
        } else if (draf) {
          tulisDraf(proyekId, null);
        }
      })
      .catch((e) => setGalat(e.message));
    ambilToken().then(setToken).catch(() => {});
  }, [proyekId]);
  useEffect(() => { muat(); }, [muat]);

  const simpanSekarang = useCallback(() => {
    antrean.current = antrean.current.then(async () => {
      const d = riwayatRef.current?.kini;
      if (!kotor.current || !d) return;
      kotor.current = false;
      setStatus('menyimpan');
      try {
        const r = await simpanProyek(proyekId, d, revisi.current);
        revisi.current = r.revisi;
        if (!kotor.current) tulisDraf(proyekId, null);
        setStatus(kotor.current ? 'belum' : 'tersimpan');
        setGalat(null);
      } catch (e) {
        kotor.current = true;
        setStatus(e.status === 409 ? 'bentrok' : 'gagal');
        setGalat(e.message);
      }
    });
    return antrean.current;
  }, [proyekId]);

  useEffect(() => {
    if (!kotor.current || status === 'bentrok') return undefined;
    if (status !== 'gagal') setStatus('belum');
    const id = setTimeout(simpanSekarang, JEDA_SIMPAN);
    return () => clearTimeout(id);
    // `status` sengaja tidak ikut: perubahannya bukan alasan menyimpan.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dokumen, simpanSekarang]);

  // Gagal karena jaringan atau server sibuk: dicoba lagi sendiri, jadi
  // pengguna yang tidak membaca pemberitahuannya pun tidak kehilangan kerja.
  useEffect(() => {
    if (status !== 'gagal') return undefined;
    const id = setTimeout(simpanSekarang, ULANG_GAGAL);
    return () => clearTimeout(id);
  }, [status, simpanSekarang]);

  useEffect(() => {
    const tahan = (e) => { if (kotor.current) { e.preventDefault(); e.returnValue = ''; } };
    window.addEventListener('beforeunload', tahan);
    return () => window.removeEventListener('beforeunload', tahan);
  }, []);

  /** Menerapkan dokumen baru dan mencatatnya di riwayat. */
  const terapkan = useCallback((baru, opsi) => {
    const r = riwayatRef.current;
    if (!r || !baru || baru === r.kini) return false;
    kotor.current = true;
    riwayatRef.current = catat(r, baru, opsi);
    setRiwayat(riwayatRef.current);
    return true;
  }, []);
  const ubah = useCallback((fn, opsi) => {
    const r = riwayatRef.current;
    if (r) terapkan(fn(r.kini), opsi);
  }, [terapkan]);
  const dok = () => riwayatRef.current?.kini;

  const lompat = useCallback((fn) => {
    const r = riwayatRef.current;
    if (!r) return;
    const baru = fn(r);
    if (baru === r) return;
    kotor.current = true;
    riwayatRef.current = baru;
    setRiwayat(baru);
  }, []);

  const tampilUsulan = useMemo(
    () => (dokumen && usulan ? terapkanOperasi(dokumen, usulan.operasi, usulan.pilih) : null),
    [dokumen, usulan],
  );
  const dTampil = tampilUsulan?.dokumen ?? dokumen;
  // Dihitung dari yang TAMPIL: usulan asisten yang belum diterima ikut terlihat dampaknya.
  const orisinal = useMemo(() => (dTampil ? hitungOrisinalitas(dTampil, asalBahan) : null), [dTampil, asalBahan]);
  const sumber = useMemo(
    () => (dTampil ? sumberPratinjau(dTampil, token) : null),
    // Hanya daftar bahan dan font yang menentukan alamat; perubahan item tidak.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [dTampil && Object.keys(dTampil.bahan).join(','), dTampil && fontDipakai(dTampil).join(','),
      dTampil && Object.keys(komponenDipakai(dTampil, '-')).join(','), token],
  );
  const terimaUsulan = useCallback((pilih) => {
    if (!usulan) return;
    const { dokumen: baru } = terapkanOperasi(riwayatRef.current.kini, usulan.operasi, pilih);
    terapkan(baru);
    setUsulan(null);
  }, [usulan, terapkan]);
  const tolakUsulan = useCallback(() => setUsulan(null), []);
  // Draf lokal ditunda 400 ms: localStorage sinkron, dan menyeret item
  // mengubah dokumen tiap bingkai (kinerja M6.3 diukur dengan ini menyala).
  useEffect(() => {
    if (!dokumen || !kotor.current) return undefined;
    const id = setTimeout(() => {
      if (kotor.current) tulisDraf(proyekId, { revisi: revisi.current, waktu: Date.now(), dokumen });
    }, 400);
    return () => clearTimeout(id);
  }, [dokumen, proyekId]);
  const pulihkanDraf = () => {
    if (drafLama) terapkan(drafLama.dokumen);
    setDrafLama(null);
  };
  const buangDraf = () => {
    tulisDraf(proyekId, null);
    setDrafLama(null);
  };
  const pulihkan = useCallback(async (versiId) => {
    await simpanSekarang();
    const r = await pulihkanVersi(proyekId, versiId, revisi.current);
    revisi.current = r.revisi;
    kotor.current = false;
    tulisDraf(proyekId, null);
    riwayatRef.current = buatRiwayat(r.dokumen);
    setRiwayat(riwayatRef.current);
    setUsulan(null);
    setStatus('tersimpan');
  }, [proyekId, simpanSekarang]);

  const semuaId = useMemo(
    () => new Set((dokumen?.lajur ?? []).flatMap((l) => l.item.map((i) => i.id))),
    [dokumen?.lajur],
  );
  const pilihanSah = useMemo(() => pilihan.filter((id) => semuaId.has(id)), [pilihan, semuaId]);
  const itemTerpilih = dokumen && pilihanSah.length === 1 ? cariItem(dokumen, pilihanSah[0])?.item : null;
  // Skema props animasi terpilih (M4.5): bawaan di sini, komponen AI dari kotak pasir.
  const infoSkema = useSkemaKomponen(itemTerpilih, pratinjau, token);

  const pilih = useCallback((ids) => {
    setPilihan(ids);
    if (ids.length) setLajurDipilih(null);
  }, []);
  const pilihLajur = useCallback((id) => {
    setLajurDipilih(id);
    setPilihan([]);
  }, []);

  const keBingkai = useCallback((b) => {
    const d = riwayatRef.current?.kini;
    const tepat = Math.max(0, Math.min((d?.durasi ?? 1) - 1, Math.round(b)));
    garis.set(tepat);
    pratinjau.current?.ke(tepat);
  }, [garis]);
  const keGaris = useCallback((b) => garis.set(b), [garis]);

  // --- aksi ------------------------------------------------------------------

  const fps = dokumen?.kanvas.fps ?? 30;
  const tambahKeLinimasa = (b, posisi) => {
    const hasil = tambahBahan(dok(), b, posisi);
    if (terapkan(hasil.dokumen)) pilih([hasil.itemId]);
  };
  /** Narasi atau rekaman baru di garis putar (M3.3). */
  const tambahSuara = (b, narasi) => {
    const hasil = taruhSuara(dok(), b, { mulai: garis.get(), narasi });
    if (terapkan(hasil.dokumen)) pilih([hasil.itemId]);
  };
  /** Narasi di linimasa, urut waktu; `ids` membatasi, tanpa `ids` yang belum direkam (atau semua). */
  const bukaTeleprompter = (ids = null) => {
    const semua = dok().lajur.flatMap((l) => l.item)
      .filter((i) => i.jenis === 'audio' && i.narasi?.teks)
      .sort((a, b) => a.mulai - b.mulai)
      .map((i) => ({ id: i.id, teks: i.narasi.teks, direkam: Boolean(i.narasi.direkam) }));
    let daftar = ids ? semua.filter((x) => ids.includes(x.id)) : semua.filter((x) => !x.direkam);
    if (!daftar.length && !ids) daftar = semua;
    if (daftar.length) setTeleprompter(daftar);
  };
  const rekamanNarasi = (itemId, bahan) => {
    const it = cariItem(dok(), itemId)?.item;
    if (!it) return;
    terapkan(gantiBahanItem(dok(), itemId, bahan, { narasi: { ...it.narasi, direkam: true } }));
    setAsalBahan((m) => new Map(m).set(bahan.id, 'rekam'));
  };
  const buatUlangNarasi = async (itemId, narasi) => {
    const bahan = await buatNarasi(narasi.teks, narasi.suara, narasi.kecepatan);
    terapkan(gantiBahanItem(dok(), itemId, bahan, { narasi }));
  };
  const tambahTeksDiGaris = () => {
    const hasil = tambahTeks(dok(), { mulai: garis.get(), teks: t('montase.editor.teks_baru') });
    if (terapkan(hasil.dokumen)) pilih([hasil.itemId]);
  };
  const tambahAnimasiDiGaris = (komponen = 'ko_hitung_mundur') => {
    const modul = BAWAAN[komponen];
    if (!modul) return;
    // Bilah progres dibentang sepanjang video, mulai dari awal.
    const panjang = komponen === 'ko_bilah_progres';
    let hasil = tambahMotion(dok(), { komponen, modul, mulai: panjang ? 0 : garis.get() });
    if (panjang) hasil = { ...hasil, dokumen: ubahItem(hasil.dokumen, hasil.itemId, { durasi: Math.max(dok().durasi, 1) }) };
    if (terapkan(hasil.dokumen)) pilih([hasil.itemId]);
  };
  /** Animasi buatan AI (versi yang lolos) di bingkai `mulai` (M4.3, M4.7). */
  const tambahAnimasiAi = (v, { mulai, durasi }) => {
    let hasil = tambahMotion(dok(), {
      komponen: v.id, modul: { contohProps: {}, durasiBawaan: Math.max(1, Math.round(durasi)) }, mulai,
    });
    hasil = {
      ...hasil,
      dokumen: ubahItem(hasil.dokumen, hasil.itemId, {
        versi: v.versi, asal: 'ai', alasan: (v.catatan?.alasan || v.permintaan || '').slice(0, 500),
        nama: (v.nama || '').slice(0, 80) || undefined,
      }),
    };
    if (terapkan(hasil.dokumen)) pilih([hasil.itemId]);
  };
  const tambahStikerDiGaris = (emoji) => {
    const hasil = tambahStiker(dok(), { mulai: garis.get(), emoji });
    if (hasil.itemId && terapkan(hasil.dokumen)) pilih([hasil.itemId]);
  };
  const aksiHapus = () => {
    if (pilihanSah.length) terapkan(hapusBanyak(dok(), pilihanSah));
  };
  const aksiHapusBeriak = () => {
    let d = dok();
    const urut = pilihanSah.map((id) => cariItem(d, id)?.item).filter(Boolean)
      .sort((a, b) => b.mulai - a.mulai);
    for (const i of urut) d = hapusBeriak(d, i.id);
    terapkan(d);
  };
  const aksiBelah = () => {
    let d = dok();
    const f = garis.get();
    const sasaran = pilihanSah.length ? pilihanSah : itemDiGaris(d, f);
    const kanan = [];
    for (const id of sasaran) {
      const hasil = belah(d, id, f);
      if (hasil.itemBaru) { d = hasil.dokumen; kanan.push(hasil.itemBaru); }
    }
    if (terapkan(d)) pilih(kanan);
  };
  const aksiBekukan = () => {
    const d = dok();
    const f = garis.get();
    const calon = (pilihanSah.length ? pilihanSah : itemDiGaris(d, f, 'video'))
      .map((id) => cariItem(d, id)?.item)
      .find((i) => i?.jenis === 'video' && !i.beku && i.mulai <= f && i.mulai + i.durasi > f);
    if (!calon) return;
    const hasil = bekukan(d, calon.id, f, DETIK_BEKU * fps);
    if (hasil.itemBaru && terapkan(hasil.dokumen)) pilih([hasil.itemBaru]);
  };
  const aksiSalin = () => {
    const papan = salin(dok(), pilihanSah);
    if (papan) papanKlip = papan;
  };
  const aksiPotong = () => {
    aksiSalin();
    aksiHapus();
  };
  const aksiTempel = () => {
    if (!papanKlip) return;
    const hasil = tempel(dok(), papanKlip, garis.get());
    if (terapkan(hasil.dokumen)) pilih(hasil.itemBaru);
  };
  const aksiGandakan = () => {
    const hasil = gandakan(dok(), pilihanSah);
    if (terapkan(hasil.dokumen)) pilih(hasil.itemBaru);
  };
  const aksiPenanda = () => terapkan(tambahPenanda(dok(), garis.get(), ''));
  /** Rapatkan lajur item terpilih; tanpa pilihan, lajur video pertama. */
  const aksiRapatkan = () => {
    let d = dok();
    const lajurIds = pilihanSah.length
      ? [...new Set(pilihanSah.map((id) => cariItem(d, id)?.lajur.id).filter(Boolean))]
      : [d.lajur.find((l) => l.jenis === 'video')?.id].filter(Boolean);
    for (const id of lajurIds) d = rapatkan(d, id);
    terapkan(d);
  };
  const aksiMagnet = () => {
    setMagnet((m) => {
      try { localStorage.setItem(KUNCI_MAGNET, m ? '0' : '1'); } catch { /* tidak apa */ }
      return !m;
    });
  };
  const aksiTambahLajur = (jenis) => {
    const hasil = tambahLajur(dok(), jenis);
    if (terapkan(hasil.dokumen)) pilihLajur(hasil.lajurId);
  };
  const aksiUbahLajur = useCallback((id, p) => {
    ubah((d) => ubahLajur(d, id, p), { gabung: `lajur:${id}:${Object.keys(p).join(',')}` });
  }, [ubah]);

  /** Subtitle otomatis (M3.2): simpan dulu, karena pekerjaannya membaca dokumen tersimpan. */
  const aksiSubtitle = async () => {
    await simpanSekarang();
    if (kotor.current) return;
    subtitleKerja.run(`/montase/proyek/${encodeURIComponent(proyekId)}/subtitle`).catch(() => {});
  };

  const aksi = {
    subtitle: aksiSubtitle,
    subtitleSibuk: subtitleKerja.active,
    batal: () => lompat(batal),
    ulang: () => lompat(ulang),
    belah: aksiBelah,
    hapus: aksiHapus,
    rapatkan: aksiRapatkan,
    gandakan: aksiGandakan,
    bekukan: aksiBekukan,
    penanda: aksiPenanda,
    magnet: aksiMagnet,
    tambahTeks: tambahTeksDiGaris,
    tambahMotion: tambahAnimasiDiGaris,
    tambahStiker: tambahStikerDiGaris,
    tambahLajur: aksiTambahLajur,
  };

  // Hasil subtitle diterapkan sekali per pekerjaan, sebagai satu langkah batal.
  const hasilSubtitle = subtitleKerja.result;
  const idSubtitle = subtitleKerja.job?.job_id;
  useEffect(() => {
    if (!hasilSubtitle || !idSubtitle || subtitleDipasang.current === idSubtitle) return;
    subtitleDipasang.current = idSubtitle;
    if (!hasilSubtitle.potongan?.length) {
      setGalat(t('montase.subtitle.kosong'));
      return;
    }
    const hasil = pasangSubtitle(riwayatRef.current.kini, hasilSubtitle.potongan, {
      nama: t('montase.subtitle.lajur'), alasan: t('montase.subtitle.alasan'),
    });
    if (terapkan(hasil.dokumen)) pilihLajur(hasil.lajurId);
  }, [hasilSubtitle, idSubtitle, terapkan, pilihLajur, t]);

  // --- pintasan keyboard (JOB-4 M2.4) -------------------------------------------

  const tombol = (e) => {
    const ctrl = e.ctrl || e.meta;
    const { key } = e;
    const huruf = key.length === 1 ? key.toLowerCase() : key;
    const jalankan = (fn) => { e.preventDefault?.(); fn(); };
    if (key === ' ') return jalankan(() => pratinjau.current?.putarJeda());
    if (key === 'ArrowLeft' || key === 'ArrowRight') {
      const arah = key === 'ArrowLeft' ? -1 : 1;
      return jalankan(() => keBingkai(garis.get() + arah * (e.shift ? fps : 1)));
    }
    if (key === 'Home') return jalankan(() => keBingkai(0));
    if (key === 'End') return jalankan(() => keBingkai(dok().durasi - 1));
    if (ctrl && huruf === 'z') return jalankan(() => lompat(e.shift ? ulang : batal));
    if (ctrl && huruf === 'y') return jalankan(() => lompat(ulang));
    if (ctrl && huruf === 'b') return jalankan(aksiBelah);
    if (ctrl && huruf === 'c') return jalankan(aksiSalin);
    if (ctrl && huruf === 'x') return jalankan(aksiPotong);
    if (ctrl && huruf === 'v') return jalankan(aksiTempel);
    if (ctrl && huruf === 'd') return jalankan(aksiGandakan);
    if (ctrl && huruf === 'a') return jalankan(() => pilih(semuaItem(dok())));
    if (key === 'Delete' || key === 'Backspace') return jalankan(e.shift ? aksiHapusBeriak : aksiHapus);
    if (key === 'Escape') return jalankan(() => { setPilihan([]); setLajurDipilih(null); });
    if (ctrl || e.alt) return undefined;
    if (huruf === 'm') return jalankan(aksiPenanda);
    if (huruf === 'n') return jalankan(aksiMagnet);
    if (key === '+' || key === '=') return jalankan(() => linimasa.current?.perbesar());
    if (key === '-' || key === '_') return jalankan(() => linimasa.current?.perkecil());
    return undefined;
  };
  const tombolRef = useRef(tombol);
  tombolRef.current = tombol;
  useEffect(() => {
    const tekan = (e) => {
      if (e.defaultPrevented || e.isComposing) return;
      if (sedangMengetik(e.target)) {
        // Esc keluar dari kotak isian supaya pintasan kembali bekerja.
        if (e.key === 'Escape') e.target.blur();
        return;
      }
      if (!riwayatRef.current) return;
      // Spasi di tombol yang sedang fokus akan "mengekliknya"; lepaskan fokusnya.
      if (e.key === ' ' && e.target?.tagName === 'BUTTON') e.target.blur();
      tombolRef.current({
        key: e.key, shift: e.shiftKey, ctrl: e.ctrlKey, meta: e.metaKey, alt: e.altKey,
        preventDefault: () => e.preventDefault(),
      });
    };
    window.addEventListener('keydown', tekan);
    return () => window.removeEventListener('keydown', tekan);
  }, []);
  const tombolPratinjau = useCallback((d) => {
    if (riwayatRef.current) tombolRef.current(d);
  }, []);

  const mulaiEkspor = async () => {
    await simpanSekarang();
    if (kotor.current) return;
    ekspor.run(`/montase/proyek/${encodeURIComponent(proyekId)}/ekspor`).catch(() => {});
  };

  const geser = (kunci, tanda, batas) => (delta, selesai) => {
    const nilai = Math.min(batas[1], Math.max(batas[0], tataSeret.current[kunci] + tanda * delta));
    const baru = { ...tata, [kunci]: nilai };
    setTata(baru);
    if (selesai) {
      tataSeret.current = baru;
      try { localStorage.setItem(KUNCI_TATA, JSON.stringify(baru)); } catch { /* tidak apa */ }
    }
  };

  if (sempit) {
    return (
      <div className="page montase-sempit">
        <MonitorSmartphone size={32} aria-hidden />
        <h1>{t('montase.editor.sempit_judul')}</h1>
        <p>{t('montase.editor.sempit_ket')}</p>
        <Link className="btn-secondary" to="/montase"><ArrowLeft size={14} />{t('montase.editor.kembali')}</Link>
      </div>
    );
  }
  if (!dokumen) {
    return (
      <div className="page montase-memuat">
        {galat ? <p className="montase-galat" role="alert">{galat}</p> : <Loader2 size={20} className="animate-spin" />}
      </div>
    );
  }

  const terpilih = pilihanSah.length === 1 ? cariItem(dokumen, pilihanSah[0]) : null;
  const lajur = lajurDipilih ? dokumen.lajur.find((l) => l.id === lajurDipilih) ?? null : null;
  const hasil = ekspor.result;
  return (
    <div className="montase-editor"
         style={{ gridTemplateRows: `auto minmax(0, 1fr) 6px ${tata.bawah}px` }}
    >
      <header className="montase-editor-kepala">
        <button type="button" className="btn-secondary montase-ikon" onClick={() => navigate('/montase')}
                aria-label={t('montase.editor.kembali')} title={t('montase.editor.kembali')}
        >
          <ArrowLeft size={14} />
        </button>
        <h1 title={dokumen.nama}>{dokumen.nama}</h1>
        <StatusSimpan status={status} onMuatUlang={muat} onCobaLagi={simpanSekarang} />
        {orisinal && (
          <MeterOrisinalitas hasil={orisinal} onKe={keBingkai} onRekamNarasi={() => bukaTeleprompter()}
                             onPeriksaKemiripan={async () => { await simpanSekarang(); return periksaKemiripan(proyekId); }} />
        )}
        <button type="button" className="btn-secondary montase-ikon" onClick={() => setBantuan(true)}
                aria-label={t('montase.bantuan.judul')} title={t('montase.bantuan.judul')}
        >
          <CircleHelp size={14} />
        </button>
        <span className="montase-linimasa-spasi" />
        {(subtitleKerja.active || subtitleKerja.error) && (
          <div className="montase-ekspor-kabar">
            <JobProgress job={subtitleKerja.job} error={subtitleKerja.error} onCancel={subtitleKerja.cancel} compact />
          </div>
        )}
        {(ekspor.job || ekspor.error) && (
          <div className="montase-ekspor-kabar">
            <JobProgress job={ekspor.job} error={ekspor.error} onCancel={ekspor.cancel} compact />
          </div>
        )}
        {hasil && (
          <Link className="btn-secondary" to="/clips">{t('montase.editor.lihat_klip', { berkas: hasil.berkas })}</Link>
        )}
        {hasil && (
          <button type="button" className="btn-secondary" onClick={() => setTerbit({ file_name: hasil.berkas, metadata: {} })}
                  title={t('klip.siapkan_judul')}
          >
            <Send size={14} />{t('klip.siapkan')}
          </button>
        )}
        {hasil && (
          <button type="button" className="btn-secondary"
                  onClick={() => setUnggah({ file_name: hasil.berkas, metadata: { title: dokumen.nama } })}
          >
            <Upload size={14} />{t('montase.editor.unggah')}
          </button>
        )}
        <button type="button" className="btn-primary" onClick={mulaiEkspor}
                disabled={ekspor.active || status === 'bentrok'}
        >
          {ekspor.active ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
          {t('montase.editor.ekspor')}
        </button>
      </header>

      <div className="montase-editor-tengah"
           style={{ gridTemplateColumns: `${tata.kiri}px 6px minmax(0, 1fr) 6px ${tata.kanan}px` }}
      >
        <PanelBahan token={token} onTambahKeLinimasa={tambahKeLinimasa} onTambahSuara={tambahSuara}
                    onBahan={catatBahan}
                    animasi={{
                      proyekId, dokumen, garis, terpilih, onSimpanDulu: simpanSekarang,
                      onTambahBawaan: tambahAnimasiDiGaris, onTambahAi: tambahAnimasiAi,
                    }}
                    asisten={{
                      proyekId, terpilih, fps, usulan, onUsulan: setUsulan, onTerima: terimaUsulan,
                      onRekamNarasi: () => bukaTeleprompter(), adaNarasi: Boolean(orisinal?.detik.suara),
                      onTolak: tolakUsulan, onSimpanDulu: simpanSekarang,
                    }} />
        <Pembatas arah="tegak" onGeser={geser('kiri', 1, [220, 520])} />
        <section className="montase-panel montase-panel-pratinjau" aria-label={t('montase.pratinjau.judul')}>
          {galat && status !== 'bentrok' && status !== 'gagal' && <p className="montase-galat" role="alert">{galat}</p>}
          {galatPratinjau && <p className="montase-galat" role="alert">{galatPratinjau}</p>}
          {drafLama && (
            <div className="montase-bilah-usulan" role="alert">
              <span>{t('montase.versi.draf', { waktu: new Date(drafLama.waktu).toLocaleString() })}</span>
              <div className="montase-baris-tombol">
                <button type="button" className="btn-primary" onClick={pulihkanDraf}>{t('montase.versi.draf_pulihkan')}</button>
                <button type="button" className="btn-secondary" onClick={buangDraf}>{t('montase.versi.draf_buang')}</button>
              </div>
            </div>
          )}
          {usulan && (
            <div className="montase-bilah-usulan" role="status">
              <span>{t('montase.asisten.bilah', { n: usulan.pilih.size, total: usulan.operasi.length })}</span>
              <TombolUsulan usulan={usulan} onTerima={terimaUsulan} onTolak={tolakUsulan} ringkas />
            </div>
          )}
          <PratinjauKotakPasir ref={pratinjau} dokumen={dTampil} sumber={sumber} lengkap
                               onBingkai={keGaris} onGalat={setGalatPratinjau} onMain={setMain}
                               onTombol={tombolPratinjau}
          >
            <PeganganUbah key={terpilih?.item.id ?? 'kosong'} dokumen={dokumen} terpilih={terpilih}
                          garis={garis} onUbah={ubah} infoSkema={infoSkema} />
          </PratinjauKotakPasir>
        </section>
        <Pembatas arah="tegak" onGeser={geser('kanan', -1, [240, 520])} />
        <PanelProperti
          dokumen={dokumen}
          terpilih={terpilih}
          jumlahPilihan={pilihanSah.length}
          lajur={lajur}
          onUbahItem={(id, p) => ubah((d) => ubahItem(d, id, p), { gabung: `properti:${id}:${Object.keys(p).join(',')}` })}
          onKecepatan={(id, k) => ubah((d) => ubahKecepatan(d, id, k), { gabung: `kecepatan:${id}` })}
          onTransform={(id, s) => ubah((d) => ubahTransform(d, id, s), { gabung: `ubah:${id}:${Object.keys(s).join(',')}` })}
          onHapus={aksiHapus}
          onGandakan={aksiGandakan}
          onUbahProyek={(p) => ubah((d) => ubahProyek(d, p), { gabung: `proyek:${Object.keys(p).join(',')}` })}
          onUbahLajur={aksiUbahLajur}
          onHapusLajur={(id) => { if (terapkan(hapusLajur(dok(), id))) setLajurDipilih(null); }}
          bisaHapusLajur={lajur ? bisaHapusLajur(dokumen, lajur.id) : false}
          onKe={keBingkai}
          onUbahPenanda={(tt, label) => ubah((d) => ubahPenanda(d, tt, label), { gabung: `penanda:${tt}` })}
          onHapusPenanda={(tt) => terapkan(hapusPenanda(dok(), tt))}
          onBuatUlangNarasi={buatUlangNarasi}
          onRekamNarasi={bukaTeleprompter}
          infoSkema={infoSkema}
          riwayatVersi={<RiwayatVersi proyekId={proyekId} revisi={revisi.current} onPulihkan={pulihkan} />}
          garis={garis}
          onUbahSifat={(id, s) => ubah((d) => {
            const it = cariItem(d, id)?.item;
            return it ? ubahSifatDiBingkai(d, id, s, garis.get() - it.mulai) : d;
          }, { gabung: `sifat:${id}:${Object.keys(s).join(',')}` })}
          onTombolKeyframe={(id, sifat) => ubah((d) => {
            const it = cariItem(d, id)?.item;
            return it ? tombolKeyframe(d, id, sifat, garis.get() - it.mulai) : d;
          })}
          onKurvaKeyframe={(id, k) => ubah((d) => {
            const it = cariItem(d, id)?.item;
            return it ? kurvaKeyframe(d, id, garis.get() - it.mulai, k) : d;
          })}
          onAturUlangTransform={(id) => terapkan(aturUlangTransform(dok(), id))}
          onRendam={(id, turun) => terapkan(rendamMusik(dok(), id, { turun }))}
          onPunch={(id) => {
            const it = cariItem(dok(), id)?.item;
            if (it) terapkan(tambahPunch(dok(), id, garis.get() - it.mulai, Math.round(fps * 0.8)));
          }}
          onHapusPunch={(id, tt) => terapkan(hapusPunch(dok(), id, tt))}
        />
      </div>

      <Pembatas arah="datar" onGeser={geser('bawah', -1, [150, 520])} />
      <Linimasa
        ref={linimasa}
        dokumen={dTampil}
        itemUsulan={tampilUsulan?.itemUsulan}
        token={token}
        bahanSiap={bahanSiap}
        pilihan={pilihanSah}
        onPilih={pilih}
        garis={garis}
        main={main}
        onKe={keBingkai}
        onUbah={usulan ? abaikan : ubah}
        onUbahLajur={aksiUbahLajur}
        magnet={magnet}
        lajurDipilih={lajurDipilih}
        onPilihLajur={pilihLajur}
        aksi={aksi}
        bisaBatal={bisaBatal(riwayat)}
        bisaUlang={bisaUlang(riwayat)}
        onJatuhBahan={tambahKeLinimasa}
      />
      {terbit && <SiapkanTerbit clip={terbit} onClose={() => setTerbit(null)} onSelesai={() => {}} />}
      {unggah && <UploadModal clip={unggah} onClose={() => setUnggah(null)} onDone={() => {}} />}
      {bantuan && <JendelaBantuan onTutup={() => setBantuan(false)} />}
      {teleprompter && (
        <Teleprompter daftar={teleprompter} onRekaman={rekamanNarasi} onTutup={() => setTeleprompter(null)} />
      )}
    </div>
  );
}
