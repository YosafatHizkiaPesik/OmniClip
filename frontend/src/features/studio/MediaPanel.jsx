import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  Film, Image as ImageIcon, Music, Upload, Loader2, Trash2, Wand2, Play, Square,
  Crosshair, Sparkles, X, ChevronUp, ChevronDown,
} from 'lucide-react';
import { apiDelete, apiGet, apiPatch, apiPost } from '../../lib/api';
import { formatTime } from '../../utils/timeFormat';

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
  { id: 'musik', label: 'Musik',
    kosong: 'Belum ada musik latar. Impor berkas mp3 atau wav milik Anda sendiri.' },
  { id: 'efek', label: 'Efek suara',
    kosong: 'Belum ada efek suara. Berkas suara pendek masuk ke sini sendiri.' },
  { id: 'media', label: 'Video & foto',
    kosong: 'Belum ada. Contohnya cuplikan pertandingan untuk podcast bola, atau logo kanal.' },
];

const IKON = { video: Film, gambar: ImageIcon, audio: Music };

export const POSISI = [
  ['penuh', 'Penuh'],
  ['atas', 'Separuh atas'],
  ['bawah', 'Separuh bawah'],
  ['tengah', 'Tengah'],
  ['sudut', 'Pojok'],
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
    const t = Math.max(0, Math.min(waktuSekarang, Math.max(0, durasiKlip - 0.2)));
    const sisa = Math.max(0.2, durasiKlip - t);
    const id = idBaru();
    // Langsung terpilih: kotaknya muncul di pratinjau tanpa harus dicari dan
    // diklik dulu, dan menaruh sesuatu lalu langsung menggesernya adalah urutan
    // yang dilakukan orang setiap kali.
    onSorot?.(id);
    onLayers([...lapisan, {
      id, aset: a.id, jenis: a.jenis, nama: a.nama, t: Number(t.toFixed(2)),
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
    if (!window.confirm(`Hapus "${a.nama}" dari pustaka? Klip yang memakainya kehilangan sisipan ini.`)) return;
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


  if (!clip) return <p style={kecil}>Pilih klip dulu.</p>;

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
      <div style={judul}>Di klip ini ({urut.length})</div>
      {!urut.length && (
        <p style={{ ...kecil, margin: '0 0 12px' }}>
          Belum ada sisipan. Tambahkan dari pustaka di bawah, dan ia ditaruh di posisi
          garis main sekarang ({formatTime(waktuSekarang)}).
        </p>
      )}
      {urut.map((l) => {
        const a = asetById[l.aset];
        // Indeks di daftar ASLI, bukan di daftar yang sudah diurut waktu:
        // yang menentukan tumpukan adalah urutan daftarnya.
        const indeks = lapisan.findIndex((x) => x.id === l.id);
        const Ikon = IKON[a?.jenis] ?? Music;
        const visual = a?.jenis === 'video' || a?.jenis === 'gambar';
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
                {a?.nama ?? 'Aset hilang'}
              </b>
              {l.asal === 'otomatis' && (
                <span style={{ fontSize: '0.62rem', fontWeight: 800, padding: '1px 6px',
                               borderRadius: '99px', background: 'var(--hl-wash)',
                               color: 'var(--accent-cyan)' }}>otomatis</span>
              )}
              {/* Urutan tumpuk. Yang di BAWAH daftar digambar paling akhir,
                  jadi ia yang menutupi. Urutan daftar itu sendiri yang dipakai
                  render, jadi tombol ini benar-benar memindahkan lapisannya,
                  bukan menyimpan angka z tersendiri yang bisa berbeda. */}
              {visual && (
                <>
                  <button className="btn-secondary studio-icon"
                          title="Pindahkan ke belakang (tertutup sisipan lain)"
                          disabled={indeks <= 0}
                          onClick={() => geser(l.id, -1)}><ChevronDown size={13} /></button>
                  <button className="btn-secondary studio-icon"
                          title="Pindahkan ke depan (menutupi sisipan lain)"
                          disabled={indeks >= lapisan.length - 1}
                          onClick={() => geser(l.id, 1)}><ChevronUp size={13} /></button>
                </>
              )}
              <button className="btn-secondary studio-icon" title="Hapus sisipan ini"
                      onClick={() => hapus(l.id)}><X size={13} /></button>
            </div>
            {l.alasan && <p style={{ ...kecil, margin: '4px 0 0' }}>{l.alasan}</p>}
            {!a && (
              <p style={{ ...kecil, color: 'var(--danger)', margin: '4px 0 0' }}>
                Berkasnya sudah dihapus dari pustaka. Sisipan ini akan dilewati saat render.
              </p>
            )}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center',
                          marginTop: '7px', fontSize: '0.72rem' }}>
              <label>Mulai <input type="number" step="0.1" min="0" style={angka}
                                  value={l.t ?? 0}
                                  onChange={(e) => ubah(l.id, { t: Math.max(0, Number(e.target.value) || 0) })} /></label>
              <button className="btn-secondary" style={{ fontSize: '0.68rem', padding: '3px 7px' }}
                      title="Pindahkan awalnya ke garis main"
                      onClick={() => ubah(l.id, { t: Number(waktuSekarang.toFixed(2)) })}>
                <Crosshair size={11} /> ke sini
              </button>
              <label>Lama <input type="number" step="0.1" min="0.1" style={angka}
                                 value={l.dur ?? ''}
                                 onChange={(e) => ubah(l.id, { dur: Math.max(0.1, Number(e.target.value) || 0.1) })} /></label>
              {a?.jenis === 'video' && (
                <label title="Detik keberapa di dalam berkasnya cuplikan ini dimulai">
                  Dari detik <input type="number" step="0.1" min="0" style={angka}
                                    value={l.mulai_sumber ?? 0}
                                    onChange={(e) => ubah(l.id, { mulai_sumber: Math.max(0, Number(e.target.value) || 0) })} />
                </label>
              )}
              {bersuara && (
                <label style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                  Volume
                  <input type="range" min="0" max="2" step="0.05" value={l.volume ?? 1}
                         onChange={(e) => ubah(l.id, { volume: Number(e.target.value) })} />
                  <span style={{ width: '32px' }}>{Math.round((l.volume ?? 1) * 100)}%</span>
                </label>
              )}
              {bersuara && (
                <label title="Suara ini mengecil sendiri saat ada orang bicara"
                       style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <input type="checkbox" checked={!!l.redam}
                         onChange={(e) => ubah(l.id, { redam: e.target.checked })} />
                  Kecilkan saat orang bicara
                </label>
              )}
              {a?.jenis !== 'gambar' && (
                <label title="Berkas yang lebih pendek daripada petaknya diputar berulang sampai penuh"
                       style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                  <input type="checkbox" checked={!!l.ulang}
                         onChange={(e) => ubah(l.id, { ulang: e.target.checked })} />
                  Putar berulang
                </label>
              )}
            </div>

            {/* Lembut masuk dan keluar. Berlaku untuk gambar, cuplikan, dan
                suara sekaligus, jadi ia berdiri di luar cabang jenis. Pada
                visual ia bekerja di saluran alfa: yang memudar sisipannya,
                bukan gambar di bawahnya. */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center',
                          marginTop: '6px', fontSize: '0.72rem' }}>
              <label title="Detik untuk muncul berangsur di awalnya">
                Lembut masuk <input type="number" step="0.1" min="0" max="10" style={angka}
                                    value={l.fade_masuk ?? 0}
                                    onChange={(e) => ubah(l.id, { fade_masuk: Math.max(0, Number(e.target.value) || 0) })} />
              </label>
              <label title="Detik untuk menghilang berangsur di akhirnya">
                Lembut keluar <input type="number" step="0.1" min="0" max="10" style={angka}
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
                    <b style={{ color: 'var(--text-primary)' }}>Petak di layar.</b>{' '}
                    Seret kotaknya langsung di pratinjau, atau mulai dari salah satu
                    bentuk di bawah lalu geser sendiri.
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px', marginBottom: '7px' }}>
                    {POSISI.map(([v, t]) => (
                      <button key={v} className="btn-secondary"
                              style={{ fontSize: '0.68rem', padding: '3px 8px' }}
                              onClick={() => ubah(l.id, { posisi: v, rect: rectDariPreset(v, aspectRatio) })}>
                        {t}
                      </button>
                    ))}
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center',
                                fontSize: '0.72rem' }}>
                    <label>Kiri % <input type="number" step="1" style={angka} value={petak.x}
                                         onChange={(e) => setPetak({ x: Number(e.target.value) || 0 })} /></label>
                    <label>Atas % <input type="number" step="1" style={angka} value={petak.y}
                                         onChange={(e) => setPetak({ y: Number(e.target.value) || 0 })} /></label>
                    <label>Lebar % <input type="number" step="1" style={angka} value={petak.w}
                                          onChange={(e) => setPetak({ w: Number(e.target.value) || 2 })} /></label>
                    <label>Tinggi % <input type="number" step="1" style={angka} value={petak.h}
                                           onChange={(e) => setPetak({ h: Number(e.target.value) || 2 })} /></label>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', alignItems: 'center',
                                marginTop: '7px', fontSize: '0.72rem' }}>
                    <label title="Penuh memotong sisi yang kelebihan; Muat memuat semuanya dengan ruang kosong di sisanya">
                      Isi petak{' '}
                      <select value={l.isi ?? (a?.jenis === 'gambar' ? 'muat' : 'penuh')}
                              onChange={(e) => ubah(l.id, { isi: e.target.value })}
                              style={{ ...angka, width: 'auto' }}>
                        <option value="penuh">Penuhi, potong sisanya</option>
                        <option value="muat">Muat utuh</option>
                      </select>
                    </label>
                    <label style={{ display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                      Ketembusan
                      <input type="range" min="0.05" max="1" step="0.05"
                             value={l.opasitas ?? 1}
                             onChange={(e) => ubah(l.id, { opasitas: Number(e.target.value) })} />
                      <span style={{ width: '32px' }}>{Math.round((l.opasitas ?? 1) * 100)}%</span>
                    </label>
                    {bebas && (
                      <button className="btn-secondary"
                              style={{ fontSize: '0.68rem', padding: '3px 8px' }}
                              title="Kembali memakai bentuk baku, membuang petak yang Anda geser"
                              onClick={() => ubah(l.id, { rect: null })}>
                        Kembalikan
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
      <div style={{ ...judul, marginTop: '16px' }}>Berkas Anda</div>
      <button className="btn-secondary" onClick={() => berkasRef.current?.click()} disabled={unggah}
              style={{ fontSize: '0.8rem', display: 'inline-flex', gap: '6px', alignItems: 'center',
                       marginBottom: '9px' }}>
        {unggah ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
        {unggah ? 'Mengunggah…' : 'Impor video, gambar, atau musik'}
      </button>
      <input ref={berkasRef} type="file" hidden onChange={kirimBerkas}
             accept="video/*,audio/*,image/png,image/jpeg,image/webp,image/gif" />
      {aset === null && <p style={kecil}><Loader2 size={12} className="animate-spin" /> Memuat…</p>}

      {/* Tiga rak. Selalu tergambar, juga saat kosong: rak yang hilang karena
          belum ada isinya menyembunyikan tempat berkas itu nanti mendarat. */}
      <div style={{ display: 'flex', gap: '5px', marginBottom: '9px' }}>
        {RAK.map((r) => (
          <button key={r.id} onClick={() => setRak(r.id)}
                  className={`chip${rak === r.id ? ' is-on' : ''}`}
                  style={{ flex: 1, justifyContent: 'center' }}>
            {r.label}{jumlahRak[r.id] ? ` (${jumlahRak[r.id]})` : ''}
          </button>
        ))}
      </div>

      {aset && !diRak.length && (
        <p style={{ ...kecil, margin: '0 0 12px' }}>
          {RAK.find((r) => r.id === rak)?.kosong}
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
            <span style={kecil}>{a.jenis === 'gambar' ? 'gambar' : formatTime(a.durasi)}</span>
            {a.jenis === 'audio' && (
              <button className="btn-secondary studio-icon" onClick={() => putar(a)}
                      title="Dengarkan">{dengar === a.id ? <Square size={12} /> : <Play size={12} />}</button>
            )}
            {/* Berkas suara ditaruh di raknya dengan menebak dari durasi, dan
                durasi tidak tahu apa-apa soal maksud: jingle lima detik itu
                musik, rekaman tawa satu menit itu efek. Jadi raknya bisa
                dipindahkan, dan hanya untuk suara — video dan foto tidak
                punya rak lain untuk dituju. */}
            {a.jenis === 'audio' && (
              <button className="btn-secondary" style={{ fontSize: '0.7rem', padding: '3px 8px' }}
                      title={rak === 'musik'
                        ? 'Pindahkan ke rak Efek suara'
                        : 'Pindahkan ke rak Musik'}
                      onClick={() => pindahRak(a, rak === 'musik' ? 'efek' : 'musik')}>
                → {rak === 'musik' ? 'Efek' : 'Musik'}
              </button>
            )}
            <button className="btn-secondary" style={{ fontSize: '0.7rem', padding: '3px 8px' }}
                    onClick={() => tambah(a)}>+ Tambah</button>
            <button className="btn-secondary studio-icon" onClick={() => hapusAset(a)}
                    title="Hapus dari pustaka"><Trash2 size={12} /></button>
          </div>
        );
      })}

      {/* Musik latar yang dipakai pembuat klip di TikTok dan YouTube hampir
          seluruhnya berhak cipta, jadi ia tidak bisa ikut di dalam aplikasi ini.
          Dikatakan di tempat berkasnya dicari, bukan di halaman bantuan. */}
      {rak === 'musik' && (
        <p style={{ ...kecil, margin: '10px 0 0', lineHeight: 1.6 }}>
          OmniClip tidak membawa lagu apa pun. Lagu yang biasa dipakai pembuat
          klip hampir semuanya berhak cipta, dan menyalinkannya ke sini berarti
          menaruh masalah hak cipta di kanal Anda, bukan di aplikasinya. Impor
          berkas milik Anda sendiri, atau ambil dari pustaka bebas royalti
          seperti YouTube Audio Library, Pixabay Music, atau Free Music Archive.
        </p>
      )}

      {/* Bagian ini hanya muncul kalau memang ada isinya. Pustaka efek bawaan
          dikosongkan 25 September 2026 atas keputusan pemiliknya, dan judul
          bagian yang berdiri di atas daftar kosong lebih buruk daripada tidak
          ada bagian sama sekali. */}
      {efek.length > 0 && (
        <>
          <div style={{ ...judul, marginTop: '16px' }}>Efek suara bawaan</div>
          <p style={{ ...kecil, margin: '0 0 7px' }}>
            Dibuat sendiri oleh sistem, jadi bebas dipakai dan tidak butuh internet.
          </p>
        </>
      )}
      {efek.map((a) => (
        <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: '7px',
                                 padding: '6px 0', borderBottom: '1px solid var(--border-color)' }}>
          <button className="btn-secondary studio-icon" onClick={() => putar(a)} title="Dengarkan">
            {dengar === a.id ? <Square size={12} /> : <Play size={12} />}
          </button>
          <span style={{ flex: 1, minWidth: 0 }}>
            <span style={{ fontSize: '0.78rem', fontWeight: 700, display: 'block' }}>{a.nama}</span>
            <span style={kecil}>{a.catatan}</span>
          </span>
          <button className="btn-secondary" style={{ fontSize: '0.7rem', padding: '3px 8px' }}
                  onClick={() => tambah(a)}>+ Tambah</button>
        </div>
      ))}
    </div>
  );
}
