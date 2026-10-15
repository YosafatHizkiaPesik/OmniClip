import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Film, Image as ImageIcon, Music, Upload, Loader2, Trash2, Wand2, Play, Square,
  Crosshair, Sparkles, X, ChevronUp, ChevronDown, Type,
} from 'lucide-react';
import { apiDelete, apiGet, apiPatch, apiPost } from '../../lib/api';
import { formatTime } from '../../utils/timeFormat';
import { useT } from '../../lib/i18n';

/**
 * Tiga rak pustaka.
 *
 * `jenis` menjawab "berkas apa ini", `kategori` menjawab "dipakai untuk apa".
 * Keduanya berbeda tepat pada berkas suara: mp3 tiga menit dan mp3 setengah
 * detik sama-sama audio, tapi yang satu musik latar dan yang lain efek. Satu
 * daftar berisi keduanya membuat musik tenggelam begitu efeknya berpuluh.
 *
 * Pembagiannya sama persis dengan `KATEGORI` di backend/app/services/aset.py.
 */
const RAK = [
  { id: 'musik', label: 'rak.musik', kosong: 'rak.musik_kosong' },
  { id: 'efek', label: 'rak.efek', kosong: 'rak.efek_kosong' },
  { id: 'media', label: 'rak.media', kosong: 'rak.media_kosong' },
];

const IKON = { video: Film, gambar: ImageIcon, audio: Music, teks: Type };

// Font untuk sisipan tulisan. Sama dengan yang dibundel di
// backend/app/assets/fonts, jadi pratinjau dan hasil render memakai yang sama.
const FONT_TEKS = [
  'Archivo Black', 'Anton', 'Bebas Neue', 'Bungee', 'Fjalla One', 'Lilita One',
  'Luckiest Guy', 'Montserrat', 'Oswald', 'Playfair Display', 'Poppins',
  'Rubik', 'Teko',
];

export const POSISI = [
  ['penuh', 'petak.penuh'],
  ['atas', 'petak.atas'],
  ['bawah', 'petak.bawah'],
  ['tengah', 'petak.tengah'],
  ['sudut', 'petak.sudut'],
];

const RASIO = { '9:16': 9 / 16, '1:1': 1, '4:5': 4 / 5, '16:9': 16 / 9 };

/**
 * Preset lama diubah jadi petak persen, supaya SATU bentuk saja yang disimpan.
 *
 * Preset dan rect yang hidup berdampingan berarti dua sumber kebenaran, dan
 * yang kalah selalu pratinjau: menekan "Pojok" lalu menyeret kotaknya akan
 * membuat keduanya berbeda tanpa ada yang salah. Menekan preset sekarang
 * MENULIS rect, jadi menggeser sesudahnya hanya mengubah angka yang sama.
 *
 * `sudut` tingginya ditentukan rasio 16:9 dari LEBARNYA, jadi ia bergantung
 * pada rasio kanvas dan harus dihitung, bukan dipatok.
 */
export function rectDariPreset(posisi, aspectRatio = '9:16') {
  const r = RASIO[aspectRatio] ?? 9 / 16;
  switch (posisi) {
    case 'atas': return { x: 0, y: 0, w: 100, h: 50 };
    case 'bawah': return { x: 0, y: 50, w: 100, h: 50 };
    case 'tengah': return { x: 0, y: 25, w: 100, h: 50 };
    case 'sudut': {
      const h = Math.min(100, 46 * r * (9 / 16));
      return { x: 50, y: 6, w: 46, h: Number(h.toFixed(2)) };
    }
    default: return { x: 0, y: 0, w: 100, h: 100 };
  }
}

/** Petak yang berlaku untuk sebuah sisipan: rect bebas, atau presetnya. */
function petakBerlaku(l, aspectRatio) {
  return (l?.rect && Number.isFinite(l.rect.w))
    ? l.rect : rectDariPreset(l?.posisi ?? 'penuh', aspectRatio);
}

const kecil = { fontSize: '0.7rem', color: 'var(--text-secondary)', lineHeight: 1.45 };
const judul = {
  fontSize: '0.72rem', fontWeight: 800, letterSpacing: '0.04em',
  textTransform: 'uppercase', color: 'var(--text-secondary)', margin: '0 0 8px',
};
const kartu = {
  border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)',
  padding: '11px 12px', marginBottom: '12px',
};
const angka = {
  width: '64px', padding: '4px 6px', fontSize: '0.74rem', fontFamily: 'inherit',
  borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)',
  background: 'transparent', color: 'var(--text-primary)',
};

let urutId = 0;
const idBaru = () => `l${Date.now().toString(36)}${(urutId += 1)}`;

/**
 * Sisipan: berkas dari LUAR video sumber — cuplikan, gambar, musik, efek suara.
 *
 * Sutradara pindah ke panelnya sendiri (`SutradaraPanel`): menyusun bingkai
 * sepanjang klip bukan "menyisipkan berkas", dan menaruhnya di bawah pustaka
 * musik membuatnya nyaris tidak pernah ditemukan.
 */
export default function MediaPanel({
  clip, videoId, aspectRatio, waktuSekarang = 0, durasiKlip = 0,
  onLayers, frameKeys = [], onFrameKeys, sorot = null, onSorot = null,
}) {
  const t = useT();
  const [aset, setAset] = useState(null);
  const [rak, setRak] = useState('media');
  const [galat, setGalat] = useState(null);
  const [unggah, setUnggah] = useState(false);
  const [dengar, setDengar] = useState(null);
  const berkasRef = useRef(null);
  const audioRef = useRef(null);

  const lapisan = useMemo(() => clip?.media_layers ?? [], [clip]);
  const barisRef = useRef({});
  // Blok yang diklik di linimasa digulirkan ke pandangan di sini.
  useEffect(() => {
    if (sorot) barisRef.current[sorot]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [sorot]);
  const asetById = useMemo(
    () => Object.fromEntries((aset ?? []).map((a) => [a.id, a])), [aset]);

  const muat = () => apiGet('/aset').then((r) => setAset(r.aset || []))
    .catch((e) => setGalat(e.message));
  useEffect(() => { muat(); }, []);

  const ubah = (id, patch) => onLayers(lapisan.map((l) => (l.id === id ? { ...l, ...patch } : l)));
  const hapus = (id) => onLayers(lapisan.filter((l) => l.id !== id));
  /** Memindahkan sebuah sisipan satu langkah di dalam urutan tumpuk. */
  const geser = (id, arah) => {
    const i = lapisan.findIndex((l) => l.id === id);
    const j = i + arah;
    if (i < 0 || j < 0 || j >= lapisan.length) return;
    const next = [...lapisan];
    [next[i], next[j]] = [next[j], next[i]];
    onLayers(next);
  };

  const tambah = (a) => {
    const mulai = Math.max(0, Math.min(waktuSekarang, Math.max(0, durasiKlip - 0.2)));
    const sisa = Math.max(0.2, durasiKlip - mulai);
    const id = idBaru();
    // Langsung terpilih: kotaknya muncul di pratinjau tanpa harus dicari dan
    // diklik dulu, dan menaruh sesuatu lalu langsung menggesernya adalah urutan
    // yang dilakukan orang setiap kali.
    onSorot?.(id);
    onLayers([...lapisan, {
      id, aset: a.id, jenis: a.jenis, nama: a.nama, t: Number(mulai.toFixed(2)),
      // Gambar tidak punya panjang sendiri: bawaannya empat detik. Video dan
      // suara sepanjang berkasnya, dipotong di akhir klip.
      dur: a.jenis === 'gambar' ? Math.min(4, sisa) : Number(Math.min(a.durasi || sisa, sisa).toFixed(2)),
      mulai_sumber: 0,
      posisi: a.jenis === 'gambar' ? 'sudut' : (a.jenis === 'video' ? 'bawah' : 'penuh'),
      // Cuplikan video dibisukan secara bawaan: suara orang yang sedang
      // membahasnya hampir selalu yang lebih penting.
      volume: a.jenis === 'video' ? 0 : (a.bawaan ? 0.8 : 0.35),
      // Musik (bukan efek) mengecil sendiri saat orang bicara.
      redam: a.jenis === 'audio' && !a.bawaan,
      asal: 'pengguna',
    }]);
  };

  /**
   * Tempelan TULISAN, tanpa berkas apa pun.
   *
   * Diminta pemiliknya 30 September 2026 dengan alasan yang konkret: ada
   * kampanye yang mensyaratkan tulisan tertentu muncul di klip, misalnya
   * "@motionklip" berikut logonya. Itu bukan judul klip — judul punya tema,
   * animasi, dan tempatnya sendiri di awal — melainkan tempelan yang berdiri
   * sendiri: bisa ditaruh di mana saja, selama apa saja, dan ketembusannya
   * diatur seperti tempelan lain.
   */
  const tambahTeks = () => {
    const mulai = Math.max(0, Math.min(waktuSekarang, Math.max(0, durasiKlip - 0.2)));
    const id = idBaru();
    onSorot?.(id);
    onLayers([...lapisan, {
      id, jenis: 'teks', nama: t('sisipan.tulisan'), teks: '@namakanal',
      t: Number(mulai.toFixed(2)),
      // Sepanjang sisa klip: syarat kampanye hampir selalu "sepanjang video".
      dur: Number(Math.max(0.2, durasiKlip - mulai).toFixed(2)),
      posisi: 'sudut', ukuran: 4.5,
      warna: '#FFFFFF', garis: '#000000', tebal_garis: 3,
      keluarga: 'Archivo Black', opasitas: 0.85,
      volume: 0, asal: 'pengguna',
    }]);
  };

  /**
   * Mengambil suara dari papan suara di internet.
   *
   * Diminta pemiliknya 30 September 2026 sesudah menolak dua kali usaha
   * membuat efek suara sendiri: ia menunjuk halaman pencarian Indonesia di
   * myinstants.com. Yang di sana rekaman milik orang lain, jadi yang dibangun
   * bukan bundel yang ikut di dalam aplikasi melainkan pengimpor: ia menempel
   * tautan yang ia pilih, dan berkasnya masuk ke pustakanya sendiri.
   */
  const [sbUrl, setSbUrl] = useState('');
  const [sbHasil, setSbHasil] = useState(null);
  const [sbSibuk, setSbSibuk] = useState(false);
  const [sbAmbil, setSbAmbil] = useState(null);

  const cariSoundboard = async () => {
    if (!sbUrl.trim()) return;
    setSbSibuk(true); setGalat(null); setSbHasil(null);
    try {
      const r = await apiPost('/aset/soundboard/cari', { url: sbUrl.trim() }, { timeout: 60000 });
      setSbHasil(r?.suara ?? []);
    } catch (err) { setGalat(err.message); } finally { setSbSibuk(false); }
  };

  const ambilSoundboard = async (x) => {
    setSbAmbil(x.url); setGalat(null);
    try {
      const baru = await apiPost('/aset/soundboard/ambil',
                                 { url: x.url, nama: x.nama }, { timeout: 120000 });
      await muat();
      tambah(baru);
    } catch (err) { setGalat(err.message); } finally { setSbAmbil(null); }
  };

  const kirimBerkas = async (e) => {
    const f = e.target.files?.[0];
    e.target.value = '';
    if (!f) return;
    setUnggah(true); setGalat(null);
    try {
      const data = new FormData();
      data.append('berkas', f);
      const baru = await apiPost('/aset', data);
      await muat();
      tambah(baru);
    } catch (err) { setGalat(err.message); } finally { setUnggah(false); }
  };

  const hapusAset = async (a) => {
    if (!window.confirm(t('sisipan.yakin_hapus', { nama: a.nama }))) return;
    try { await apiDelete(`/aset/${a.id}`); await muat(); } catch (err) { setGalat(err.message); }
  };

  const putar = (a) => {
    const el = audioRef.current;
    if (!el) return;
    if (dengar === a.id) { el.pause(); setDengar(null); return; }
    el.src = `/api/aset/${encodeURIComponent(a.id)}/berkas`;
    el.currentTime = 0;
    el.play().then(() => setDengar(a.id)).catch(() => setDengar(null));
  };


  if (!clip) return <p style={kecil}>{t('studio.pilih_klip_dulu')}</p>;

  const efek = (aset ?? []).filter((a) => a.bawaan);
  const milik = (aset ?? []).filter((a) => !a.bawaan);
  // Rak asetnya sendiri yang menyatakan, bukan ditebak ulang di sini: tebakan
  // awal memang dari durasi, tapi pengguna boleh memindahkannya, dan pilihan
  // itulah yang tersimpan.
  const diRak = milik.filter((a) => (a.kategori || 'media') === rak);
  const jumlahRak = Object.fromEntries(RAK.map((r) => [
    r.id, milik.filter((a) => (a.kategori || 'media') === r.id).length]));

  /** Memindahkan aset ke rak lain, lalu memuat ulang pustakanya. */
  const pindahRak = async (a, tujuan) => {
    try {
      await apiPatch(`/aset/${a.id}/rak`, { kategori: tujuan });
      await muat();
      setRak(tujuan);
    } catch (err) { setGalat(err.message); }
  };
  const urut = [...lapisan].sort((a, b) => (a.t ?? 0) - (b.t ?? 0));

  return (
    <div>
      <audio ref={audioRef} onEnded={() => setDengar(null)} hidden />

      {galat && <p style={{ ...kecil, color: 'var(--danger)' }}>{galat}</p>}

      {/* --- Sisipan di klip ini ------------------------------------------- */}
      <div style={judul}>{t('sisipan.di_klip', { n: urut.length })}</div>
      {!urut.length && (
        <p style={{ ...kecil, margin: '0 0 12px' }}>
          {t('sisipan.kosong', { waktu: formatTime(waktuSekarang) })}
        </p>
      )}
      {urut.map((l) => {
        const teksLayer = l.jenis === 'teks';
        const a = teksLayer
          ? { jenis: 'teks', nama: l.nama || t('sisipan.tulisan'), durasi: l.dur }
          : asetById[l.aset];
        // Indeks di daftar ASLI, bukan di daftar yang sudah diurut waktu:
        // yang menentukan tumpukan adalah urutan daftarnya.
        const indeks = lapisan.findIndex((x) => x.id === l.id);
        const Ikon = IKON[a?.jenis] ?? Music;
        const visual = a?.jenis === 'video' || a?.jenis === 'gambar' || teksLayer;
        const bersuara = a?.jenis === 'audio' || (a?.jenis === 'video' && a?.punya_suara);
        return (
          <div key={l.id} ref={(el) => { barisRef.current[l.id] = el; }}
               onClick={() => onSorot?.(l.id)}
               style={{ ...kartu, padding: '9px 10px',
                        ...(sorot === l.id ? { borderColor: 'var(--hl)', background: 'var(--hl-wash)' } : {}) }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
              <Ikon size={14} style={{ flexShrink: 0, color: 'var(--text-secondary)' }} />
              <b style={{ fontSize: '0.78rem', flex: 1, minWidth: 0, overflow: 'hidden',
                          textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {a?.nama ?? t('sisipan.aset_hilang')}
              </b>
              {l.asal === 'otomatis' && (
                <span style={{ fontSize: '0.62rem', fontWeight: 800, padding: '1px 6px',
                               borderRadius: '99px', background: 'var(--hl-wash)',
                               color: 'var(--accent-cyan)' }}>{t('sisipan.otomatis')}</span>
              )}
              {/* Urutan tumpuk. Yang di BAWAH daftar digambar paling akhir,
                  jadi ia yang menutupi. Urutan daftar itu sendiri yang dipakai
                  render, jadi tombol ini benar-benar memindahkan lapisannya,
                  bukan menyimpan angka z tersendiri yang bisa berbeda. */}
              {visual && (
                <>
                  <button className="btn-secondary studio-icon"
                          title={t('sisipan.ke_belakang')}
                          disabled={indeks <= 0}
                          onClick={() => geser(l.id, -1)}><ChevronDown size={13} /></button>
                  <button className="btn-secondary studio-icon"
                          title={t('sisipan.ke_depan')}
                          disabled={indeks >= lapisan.length - 1}
                          onClick={() => geser(l.id, 1)}><ChevronUp size={13} /></button>
                </>
              )}
              <button className="btn-secondary studio-icon" title={t('sisipan.hapus')}
                      onClick={() => hapus(l.id)}><X size={13} /></button>
            </div>
            {l.alasan && <p style={{ ...kecil, margin: '4px 0 0' }}>{l.alasan}</p>}
            {!a && (
              <p style={{ ...kecil, color: 'var(--danger)', margin: '4px 0 0' }}>
                {t('sisipan.berkas_hilang')}
              </p>
            )}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center',
                          marginTop: '7px', fontSize: '0.72rem' }}>
              <label>{t('sisipan.mulai')} <input type="number" step="0.1" min="0" style={angka}
                                  value={l.t ?? 0}
                                  onChange={(e) => ubah(l.id, { t: Math.max(0, Number(e.target.value) || 0) })} /></label>
              <button className="btn-secondary" style={{ fontSize: '0.68rem', padding: '3px 7px' }}
                      title={t('sisipan.ke_sini_judul')}
                      onClick={() => ubah(l.id, { t: Number(waktuSekarang.toFixed(2)) })}>
                <Crosshair size={11} /> {t('sisipan.ke_sini')}
              </button>
              <label>{t('sisipan.lama')} <input type="number" step="0.1" min="0.1" style={angka}
                                 value={l.dur ?? ''}
                                 onChange={(e) => ubah(l.id, { dur: Math.max(0.1, Number(e.target.value) || 0.1) })} /></label>
              {a?.jenis === 'video' && (
                <label title={t('sisipan.dari_detik_judul')}>
                  {t('sisipan.dari_detik')} <input type="number" step="0.1" min="0" style={angka}
                                    value={l.mulai_sumber ?? 0}
                                    onChange={(e) => ubah(l.id, { mulai_sumber: Math.max(0, Number(e.target.value) || 0) })} />
                </label>
              )}
              {bersuara && (
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                  {t('sisipan.volume')}
                  <input type="range" min="0" max="2" step="0.05" value={l.volume ?? 1}
                         onChange={(e) => ubah(l.id, { volume: Number(e.target.value) })} />
                  <span style={{ width: '32px' }}>{Math.round((l.volume ?? 1) * 100)}%</span>
                </label>
              )}
              {bersuara && (
                <label title={t('sisipan.redam_judul')}
                       style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <input type="checkbox" checked={!!l.redam}
                         onChange={(e) => ubah(l.id, { redam: e.target.checked })} />
                  {t('sisipan.redam')}
                </label>
              )}
              {a?.jenis !== 'gambar' && (
                <label title={t('sisipan.ulang_judul')}
                       style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <input type="checkbox" checked={!!l.ulang}
                         onChange={(e) => ubah(l.id, { ulang: e.target.checked })} />
                  {t('sisipan.ulang')}
                </label>
              )}
            </div>

            {/* Lembut masuk dan keluar. Berlaku untuk gambar, cuplikan, dan
                suara sekaligus, jadi ia berdiri di luar cabang jenis. Pada
                visual ia bekerja di saluran alfa: yang memudar sisipannya,
                bukan gambar di bawahnya. */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center',
                          marginTop: '6px', fontSize: '0.72rem' }}>
              <label title={t('sisipan.fade_masuk_judul')}>
                {t('sisipan.fade_masuk')} <input type="number" step="0.1" min="0" max="10" style={angka}
                                    value={l.fade_masuk ?? 0}
                                    onChange={(e) => ubah(l.id, { fade_masuk: Math.max(0, Number(e.target.value) || 0) })} />
              </label>
              <label title={t('sisipan.fade_keluar_judul')}>
                {t('sisipan.fade_keluar')} <input type="number" step="0.1" min="0" max="10" style={angka}
                                     value={l.fade_keluar ?? 0}
                                     onChange={(e) => ubah(l.id, { fade_keluar: Math.max(0, Number(e.target.value) || 0) })} />
              </label>
            </div>

            {/* --- Petak: bebas, bukan lima pilihan tetap ------------------ */}
            {visual && (() => {
              const petak = petakBerlaku(l, aspectRatio);
              const setPetak = (patch) => ubah(l.id, {
                rect: {
                  x: Number(Math.max(0, Math.min(98, patch.x ?? petak.x)).toFixed(2)),
                  y: Number(Math.max(0, Math.min(98, patch.y ?? petak.y)).toFixed(2)),
                  w: Number(Math.max(2, Math.min(100, patch.w ?? petak.w)).toFixed(2)),
                  h: Number(Math.max(2, Math.min(100, patch.h ?? petak.h)).toFixed(2)),
                },
              });
              const bebas = !!(l.rect && Number.isFinite(l.rect.w));
              return (
                <div style={{ marginTop: '8px', paddingTop: '8px',
                              borderTop: '1px solid var(--border-color)' }}>
                  <div style={{ ...kecil, marginBottom: '6px' }}>
                    <b style={{ color: 'var(--text-primary)' }}>{t('sisipan.petak_judul')}</b>{' '}
                    {t('sisipan.petak_ket')}
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px', marginBottom: '7px' }}>
                    {POSISI.map(([v, kunciLabel]) => (
                      <button key={v} className="btn-secondary"
                              style={{ fontSize: '0.68rem', padding: '3px 8px' }}
                              onClick={() => ubah(l.id, { posisi: v, rect: rectDariPreset(v, aspectRatio) })}>
                        {t(kunciLabel)}
                      </button>
                    ))}
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center',
                                fontSize: '0.72rem' }}>
                    <label>{t('sisipan.kiri_p')} <input type="number" step="1" style={angka} value={petak.x}
                                         onChange={(e) => setPetak({ x: Number(e.target.value) || 0 })} /></label>
                    <label>{t('sisipan.atas_p')} <input type="number" step="1" style={angka} value={petak.y}
                                         onChange={(e) => setPetak({ y: Number(e.target.value) || 0 })} /></label>
                    <label>{t('sisipan.lebar_p')} <input type="number" step="1" style={angka} value={petak.w}
                                          onChange={(e) => setPetak({ w: Number(e.target.value) || 2 })} /></label>
                    <label>{t('sisipan.tinggi_p')} <input type="number" step="1" style={angka} value={petak.h}
                                           onChange={(e) => setPetak({ h: Number(e.target.value) || 2 })} /></label>
                  </div>
                  {teksLayer && (
                    <div style={{ marginTop: '8px', paddingTop: '8px',
                                  borderTop: '1px solid var(--border-color)' }}>
                      <textarea
                        value={l.teks ?? ''}
                        rows={2}
                        placeholder="@namakanal"
                        onChange={(e) => ubah(l.id, { teks: e.target.value })}
                        style={{ width: '100%', fontSize: '0.8rem', padding: '6px 8px',
                                 borderRadius: 'var(--r-sm)', border: '1px solid var(--rule-2)',
                                 background: 'var(--plate-3)', color: 'var(--ink)',
                                 resize: 'vertical', fontFamily: 'inherit' }} />
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '9px',
                                    alignItems: 'center', fontSize: '0.72rem', marginTop: '7px' }}>
                        <label>{t('gaya.font')}{' '}
                          <select value={l.keluarga ?? 'Archivo Black'}
                                  onChange={(e) => ubah(l.id, { keluarga: e.target.value })}
                                  style={{ ...angka, width: 'auto' }}>
                            {FONT_TEKS.map((f) => <option key={f} value={f}>{f}</option>)}
                          </select>
                        </label>
                        <label title={t('sisipan.ukuran_judul')}>
                          {t('sisipan.ukuran_p')}{' '}
                          <input type="number" step="0.5" min="1" max="40" style={angka}
                                 value={l.ukuran ?? 4.5}
                                 onChange={(e) => ubah(l.id, { ukuran: Number(e.target.value) || 4.5 })} />
                        </label>
                        <label>{t('gaya.warna')}{' '}
                          <input type="color" value={l.warna ?? '#FFFFFF'}
                                 onChange={(e) => ubah(l.id, { warna: e.target.value })}
                                 style={{ width: '32px', height: '22px', padding: 0, border: 'none',
                                          background: 'none', verticalAlign: 'middle' }} />
                        </label>
                        <label title={t('sisipan.garis_judul')}>
                          {t('sisipan.garis')}{' '}
                          <input type="color" value={l.garis ?? '#000000'}
                                 onChange={(e) => ubah(l.id, { garis: e.target.value })}
                                 style={{ width: '32px', height: '22px', padding: 0, border: 'none',
                                          background: 'none', verticalAlign: 'middle' }} />
                          <input type="number" step="1" min="0" max="12" style={{ ...angka, marginLeft: '4px' }}
                                 value={l.tebal_garis ?? 3}
                                 onChange={(e) => ubah(l.id, { tebal_garis: Number(e.target.value) || 0 })} />
                        </label>
                        <label title={t('sisipan.latar_judul')}>
                          <input type="checkbox" checked={!!l.latar}
                                 onChange={(e) => ubah(l.id, { latar: e.target.checked ? '#000000' : '' })} />
                          {' '}{t('sisipan.latar')}
                          {l.latar ? (
                            <input type="color" value={l.latar}
                                   onChange={(e) => ubah(l.id, { latar: e.target.value })}
                                   style={{ width: '32px', height: '22px', padding: 0, border: 'none',
                                            background: 'none', verticalAlign: 'middle', marginLeft: '4px' }} />
                          ) : null}
                        </label>
                      </div>
                    </div>
                  )}
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center',
                                marginTop: '7px', fontSize: '0.72rem' }}>
                    {!teksLayer && (
                    <label title={t('sisipan.isi_judul')}>
                      {t('sisipan.isi')}{' '}
                      <select value={l.isi ?? (a?.jenis === 'gambar' ? 'muat' : 'penuh')}
                              onChange={(e) => ubah(l.id, { isi: e.target.value })}
                              style={{ ...angka, width: 'auto' }}>
                        <option value="penuh">{t('sisipan.penuhi')}</option>
                        <option value="muat">{t('sisipan.muat')}</option>
                      </select>
                    </label>
                    )}
                    <label style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                      {t('sisipan.ketembusan')}
                      <input type="range" min="0.05" max="1" step="0.05"
                             value={l.opasitas ?? 1}
                             onChange={(e) => ubah(l.id, { opasitas: Number(e.target.value) })} />
                      <span style={{ width: '32px' }}>{Math.round((l.opasitas ?? 1) * 100)}%</span>
                    </label>
                    {bebas && (
                      <button className="btn-secondary"
                              style={{ fontSize: '0.68rem', padding: '3px 8px' }}
                              title={t('sisipan.kembalikan_judul')}
                              onClick={() => ubah(l.id, { rect: null })}>
                        {t('bingkai.kembalikan')}
                      </button>
                    )}
                  </div>
                </div>
              );
            })()}
          </div>
        );
      })}

      {/* --- Pustaka ------------------------------------------------------- */}
      <div style={{ ...judul, marginTop: '16px' }}>{t('sisipan.berkas_anda')}</div>
      <button className="btn-secondary" onClick={() => berkasRef.current?.click()} disabled={unggah}
              style={{ fontSize: '0.8rem', display: 'inline-flex', gap: '6px', alignItems: 'center',
                       marginBottom: '9px' }}>
        {unggah ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
        {unggah ? t('sisipan.mengunggah') : t('sisipan.impor')}
      </button>
      <input ref={berkasRef} type="file" hidden onChange={kirimBerkas}
             accept="video/*,audio/*,image/png,image/jpeg,image/webp,image/gif" />
      <button className="btn-secondary" onClick={tambahTeks}
              title={t('sisipan.tulisan_judul')}
              style={{ fontSize: '0.8rem', display: 'inline-flex', gap: '6px',
                       alignItems: 'center', marginBottom: '9px', marginLeft: '7px' }}>
        <Type size={14} /> {t('sisipan.tambah_tulisan')}
      </button>
      {/* Papan suara. Ditaruh sebelum daftar rak karena inilah cara pustaka
          suara terisi sekarang: tidak ada lagi efek bawaan. */}
      <div style={{ ...kartu, padding: '10px 11px', marginBottom: '10px' }}>
        <div style={{ fontSize: '0.78rem', fontWeight: 800, marginBottom: '5px' }}>
          {t('sisipan.papan_suara')}
        </div>
        <p style={{ ...kecil, margin: '0 0 7px', lineHeight: 1.55 }}>
          {t('sisipan.papan_ket')}
        </p>
        <div style={{ display: 'flex', gap: '6px' }}>
          <input
            value={sbUrl}
            onChange={(e) => setSbUrl(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') cariSoundboard(); }}
            placeholder="https://www.myinstants.com/en/search/?name=indonesia"
            style={{ flex: 1, minWidth: 0, fontSize: '0.76rem', padding: '6px 8px',
                     borderRadius: 'var(--r-sm)', border: '1px solid var(--rule-2)',
                     background: 'var(--plate-3)', color: 'var(--ink)' }} />
          <button className="btn-secondary" onClick={cariSoundboard} disabled={sbSibuk}
                  style={{ fontSize: '0.76rem', padding: '5px 10px', flex: 'none' }}>
            {sbSibuk ? <Loader2 size={13} className="animate-spin" /> : t('umum.cari')}
          </button>
        </div>
        {sbHasil && sbHasil.length === 0 && (
          <p style={{ ...kecil, margin: '7px 0 0' }}>
            {t('sisipan.papan_kosong')}
          </p>
        )}
        {sbHasil && sbHasil.length > 0 && (
          <>
            <p style={{ ...kecil, margin: '8px 0 5px' }}>
              {t('sisipan.papan_n', { n: sbHasil.length })}
            </p>
            <div style={{ maxHeight: '190px', overflowY: 'auto', display: 'flex',
                          flexDirection: 'column', gap: '3px' }}>
              {sbHasil.map((x) => (
                <button key={x.url} className="btn-secondary"
                        onClick={() => ambilSoundboard(x)}
                        disabled={sbAmbil === x.url}
                        title={x.url}
                        style={{ fontSize: '0.74rem', padding: '5px 8px',
                                 textAlign: 'left', display: 'flex',
                                 alignItems: 'center', gap: '6px' }}>
                  {sbAmbil === x.url
                    ? <Loader2 size={12} className="animate-spin" />
                    : <Music size={12} style={{ flex: 'none' }} />}
                  <span style={{ flex: 1, minWidth: 0, overflow: 'hidden',
                                 textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {x.nama}
                  </span>
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      <p style={{ ...kecil, margin: '0 0 10px', lineHeight: 1.55 }}>
        {t('sisipan.bukan_judul')}
      </p>
      {aset === null && <p style={kecil}><Loader2 size={12} className="animate-spin" /> {t('umum.memuat')}</p>}

      {/* Tiga rak. Selalu tergambar, juga saat kosong: rak yang hilang karena
          belum ada isinya menyembunyikan tempat berkas itu nanti mendarat. */}
      <div style={{ display: 'flex', gap: '5px', marginBottom: '9px' }}>
        {RAK.map((r) => (
          <button key={r.id} onClick={() => setRak(r.id)}
                  className={`chip${rak === r.id ? ' is-on' : ''}`}
                  style={{ flex: 1, justifyContent: 'center' }}>
            {t(r.label)}{jumlahRak[r.id] ? ` (${jumlahRak[r.id]})` : ''}
          </button>
        ))}
      </div>

      {aset && !diRak.length && (
        <p style={{ ...kecil, margin: '0 0 12px' }}>
          {t(RAK.find((r) => r.id === rak)?.kosong ?? '')}
        </p>
      )}
      {diRak.map((a) => {
        const Ikon = IKON[a.jenis] ?? Music;
        return (
          <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: '7px',
                                   padding: '6px 0', borderBottom: '1px solid var(--border-color)' }}>
            <Ikon size={14} style={{ color: 'var(--text-secondary)', flexShrink: 0 }} />
            <span style={{ fontSize: '0.76rem', flex: 1, minWidth: 0, overflow: 'hidden',
                           textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.nama}</span>
            <span style={kecil}>{a.jenis === 'gambar' ? t('sisipan.gambar') : formatTime(a.durasi)}</span>
            {a.jenis === 'audio' && (
              <button className="btn-secondary studio-icon" onClick={() => putar(a)}
                      title={t('sisipan.dengarkan')}>{dengar === a.id ? <Square size={12} /> : <Play size={12} />}</button>
            )}
            {/* Berkas suara ditaruh di raknya dengan menebak dari durasi, dan
                durasi tidak tahu apa-apa soal maksud: jingle lima detik itu
                musik, rekaman tawa satu menit itu efek. Jadi raknya bisa
                dipindahkan, dan hanya untuk suara — video dan foto tidak
                punya rak lain untuk dituju. */}
            {a.jenis === 'audio' && (
              <button className="btn-secondary" style={{ fontSize: '0.7rem', padding: '3px 8px' }}
                      title={rak === 'musik'
                        ? t('sisipan.ke_efek')
                        : t('sisipan.ke_musik')}
                      onClick={() => pindahRak(a, rak === 'musik' ? 'efek' : 'musik')}>
                → {rak === 'musik' ? t('sisipan.efek') : t('rak.musik')}
              </button>
            )}
            <button className="btn-secondary" style={{ fontSize: '0.7rem', padding: '3px 8px' }}
                    onClick={() => tambah(a)}>{t('sisipan.tambah')}</button>
            <button className="btn-secondary studio-icon" onClick={() => hapusAset(a)}
                    title={t('sisipan.hapus_pustaka')}><Trash2 size={12} /></button>
          </div>
        );
      })}

      {/* Musik latar yang dipakai pembuat klip di TikTok dan YouTube hampir
          seluruhnya berhak cipta, jadi ia tidak bisa ikut di dalam aplikasi ini.
          Dikatakan di tempat berkasnya dicari, bukan di halaman bantuan. */}
      {rak === 'musik' && (
        <p style={{ ...kecil, margin: '10px 0 0', lineHeight: 1.6 }}>
          {t('sisipan.tanpa_lagu')}
        </p>
      )}

      {/* Bagian ini hanya muncul kalau memang ada isinya. Pustaka efek bawaan
          dikosongkan 25 September 2026 atas keputusan pemiliknya, dan judul
          bagian yang berdiri di atas daftar kosong lebih buruk daripada tidak
          ada bagian sama sekali. */}
      {efek.length > 0 && (
        <>
          <div style={{ ...judul, marginTop: '16px' }}>{t('sisipan.efek_bawaan')}</div>
          <p style={{ ...kecil, margin: '0 0 7px' }}>
            {t('sisipan.efek_bawaan_ket')}
          </p>
        </>
      )}
      {efek.map((a) => (
        <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: '7px',
                                 padding: '6px 0', borderBottom: '1px solid var(--border-color)' }}>
          <button className="btn-secondary studio-icon" onClick={() => putar(a)} title={t('sisipan.dengarkan')}>
            {dengar === a.id ? <Square size={12} /> : <Play size={12} />}
          </button>
          <span style={{ flex: 1, minWidth: 0 }}>
            <span style={{ fontSize: '0.78rem', fontWeight: 700, display: 'block' }}>{a.nama}</span>
            <span style={kecil}>{a.catatan}</span>
          </span>
          <button className="btn-secondary" style={{ fontSize: '0.7rem', padding: '3px 8px' }}
                  onClick={() => tambah(a)}>{t('sisipan.tambah')}</button>
        </div>
      ))}
    </div>
  );
}
