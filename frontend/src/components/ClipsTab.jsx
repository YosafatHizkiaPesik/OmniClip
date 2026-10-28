import React, { useEffect, useRef, useState } from 'react';
import {
  Film, Download, Trash2, RefreshCw, Loader2, AlertTriangle, Layers, X, UploadCloud,
  Send, Check, Eye, FolderOpen, Search, Play, ExternalLink, MessageSquarePlus,
} from 'lucide-react';
import {
  apiGet, apiPost, apiDelete, dijalankanDiKomputerIni, downloadToDisk, mediaUrl, kategoriKlip,
} from '../lib/api';
import { formatTime } from '../utils/timeFormat';
import { angka, lokal, useT } from '../lib/i18n';
import UploadModal from './UploadModal';
import SiapkanTerbit from './SiapkanTerbit';

// Cermin dari PLATFORM di backend/app/services/keterangan.py. Hanya labelnya;
// aturan tiap platform tetap tinggal di sana.
const LABEL_PLATFORM = {
  tiktok: 'TikTok', instagram: 'Instagram', shorts: 'Shorts', facebook: 'Facebook',
};

/** "12 Okt" untuk waktu epoch detik, dalam bahasa antarmuka. */
function tanggalPendek(detik) {
  return new Date(detik * 1000).toLocaleDateString(lokal(), { day: 'numeric', month: 'short' });
}

function formatBytes(bytes) {
  if (!bytes) return '';
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

// Berapa pratinjau boleh mengambil data dari jaringan pada saat yang sama.
//
// Angkanya kecil dengan sengaja. Peramban hanya membuka enam sambungan ke satu
// alamat, dan sambungan itu DIBAGI oleh seluruh tab. Terukur di komputer
// pemiliknya: dengan 55 pratinjau memuat serentak, permintaan biasa dari tab
// Pengaturan naik dari 250 milidetik menjadi 7,3 detik, dan kartu "Ruang
// cakram" tampak menggantung selamanya. Berkasnya sendiri ada di cakram NTFS
// 67 MB/detik, jadi tiap pratinjau memegang sambungannya cukup lama.
const MUAT_BERSAMAAN = 3;
let _sedangMuat = 0;
const _antre = [];

function _ambilGiliran(lanjut) {
  if (_sedangMuat < MUAT_BERSAMAAN) {
    _sedangMuat += 1;
    lanjut();
  } else {
    _antre.push(lanjut);
  }
}

function _lepasGiliran() {
  _sedangMuat = Math.max(0, _sedangMuat - 1);
  const berikut = _antre.shift();
  if (berikut) {
    _sedangMuat += 1;
    berikut();
  }
}

/**
 * Pratinjau satu klip yang baru menyentuh jaringan saat benar-benar dilihat.
 *
 * Tiga syarat sebelum videonya dimuat: kartunya masuk layar, tabnya sedang
 * ditampilkan, dan gilirannya tiba. Syarat kedua yang paling penting: tab
 * "Klip jadi" yang ditinggal terbuka di belakang tetap memuat lima puluh lima
 * video pada versi sebelumnya, dan itu memperlambat SELURUH tab OmniClip yang
 * lain tanpa satu pun tanda dari mana asalnya.
 */
function PratinjauKlip({ src, onClick, children, lepas = false }) {
  const wadah = useRef(null);
  const [muat, setMuat] = useState(false);
  // `lepas` dinyalakan tepat sebelum klipnya dihapus. Lihat catatan di
  // `deleteClip`: selama <video> ini masih memegang berkasnya, Windows menolak
  // menghapusnya.
  const tampil = muat && !lepas;

  useEffect(() => {
    if (muat) return undefined;
    const el = wadah.current;
    if (!el) return undefined;

    let terlihat = false;
    let dibatalkan = false;

    const coba = () => {
      if (dibatalkan || !terlihat || document.hidden) return;
      _ambilGiliran(() => { if (!dibatalkan) setMuat(true); else _lepasGiliran(); });
    };

    const io = new IntersectionObserver((entri) => {
      terlihat = entri.some((e) => e.isIntersecting);
      coba();
    }, { rootMargin: '250px' });
    io.observe(el);
    document.addEventListener('visibilitychange', coba);

    return () => {
      dibatalkan = true;
      io.disconnect();
      document.removeEventListener('visibilitychange', coba);
    };
  }, [muat]);

  const gaya = { width: '100%', height: '100%', objectFit: 'cover' };
  return (
    <div ref={wadah} onClick={onClick} className="pratinjau-klip">
      {tampil ? (
        <video src={src} preload="metadata" muted style={gaya}
               onLoadedMetadata={_lepasGiliran} onError={_lepasGiliran} />
      ) : (
        <Film size={26} style={{ color: '#5B6678' }} />
      )}
      {children}
    </div>
  );
}

function PlayerModal({ clip, onClose }) {
  const t = useT();
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={{
        background: '#000', borderRadius: '16px', overflow: 'hidden',
        maxHeight: '86vh', position: 'relative', display: 'flex',
      }}>
        <button onClick={onClose} aria-label={t('umum.tutup')} style={{
          position: 'absolute', top: '10px', right: '10px', zIndex: 2,
          background: 'rgba(0,0,0,0.6)', border: 'none', borderRadius: '50%',
          width: '32px', height: '32px', cursor: 'pointer', color: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}><X size={17} /></button>
        <video
          src={mediaUrl(kategoriKlip(), clip.file_name)}
          controls autoPlay playsInline
          style={{ maxHeight: '86vh', maxWidth: '92vw', display: 'block' }}
        />
      </div>
    </div>
  );
}

export default function ClipsTab() {
  const t = useT();
  const [clips, setClips] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [playing, setPlaying] = useState(null);
  const [selected, setSelected] = useState(() => new Set());
  const [working, setWorking] = useState(false);
  // Terpisah dari `error`: kegagalan menghapus satu klip tidak boleh mengganti
  // seluruh daftar dengan layar error.
  const [actionError, setActionError] = useState(null);
  // Klip yang sedang dibuka jendela unggahnya. Satu per satu — tidak ada
  // bentuk jamaknya, dan itu disengaja.
  const [uploading, setUploading] = useState(null);
  const [siapkan, setSiapkan] = useState(null);
  // Klip mana yang sudah pernah naik ke mana, dibaca dari riwayat server.
  const [sent, setSent] = useState({});
  const [cari, setCari] = useState('');
  const [saring, setSaring] = useState('semua');

  // Menandai terbit tanpa membuka jendela apa pun. Sidecar klipnya yang jadi
  // sumber kebenaran, sama seperti di dalam "Siapkan terbit", jadi kedua tempat
  // tidak pernah bisa menunjukkan hal yang berbeda.
  const tandaiTerbit = async (clip, platform, sudah) => {
    try {
      const r = await apiPost('/clip-terbit', {
        clip_name: clip.file_name, platform, sudah,
      });
      setClips((daftar) => daftar.map((c) => (c.file_name === clip.file_name
        ? { ...c, metadata: { ...(c.metadata || {}), terbit: r.terbit || [] } }
        : c)));
    } catch (e) {
      setError(new Error(e.message));
    }
  };

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiGet('/clips');
      setClips(data.local_clips || []);
    } catch (err) {
      setError(err);
      setClips([]);
    } finally {
      setLoading(false);
    }
  };

  const loadUploads = async () => {
    try {
      // `statistik=true`: tayangan ikut diminta. Server mengambilnya di utas
      // lain dan mengembalikan daftar yang sama tanpa angka bila kuncinya
      // belum disetel, jadi halaman ini tidak perlu tahu apakah kuncinya ada.
      const { uploads } = await apiGet('/uploads?limit=200&statistik=true');
      const map = {};
      for (const u of uploads) {
        // Yang GAGAL ikut, dan itu perbaikan, bukan kelalaian.
        //
        // Unggahan yang diantrekan dari Studio berjalan di server sesudah
        // render selesai, jadi kegagalannya datang ketika tidak ada satu pun
        // layar yang menunggunya. Sebelum ini baris 'done' saja yang disimpan,
        // sehingga kegagalan hilang tanpa bekas di mana pun. Terlapor 25
        // September 2026: kotak YouTube dicentang, klipnya sampai di Drive,
        // dan tidak ada apa pun yang menyebutkan bahwa unggahan YouTube-nya
        // ditolak dengan alasan yang jelas ("akun ini belum punya kanal").
        // Yang masih berjalan ikut juga (15 Oktober 2026), dengan kemajuannya:
        // unggahan dari Studio berjalan di server, dan tanpa ini tidak ada
        // satu layar pun yang menunjukkan bahwa ia sedang dikerjakan.
        if (u.status !== 'done' && u.status !== 'failed' && !u.job) continue;
        if (u.job && u.job.status !== 'queued' && u.job.status !== 'running') continue;
        (map[u.clip_name] ??= []).push(u);
      }
      setSent(map);
    } catch { /* riwayat kosong bukan kegagalan halaman */ }
  };

  useEffect(() => { load(); loadUploads(); }, []);
  // Selama ada unggahan yang berjalan, riwayatnya dibaca ulang tiap 4 detik.
  const adaJalan = Object.values(sent).some((d) => d.some((u) => u.job));
  useEffect(() => {
    if (!adaJalan) return undefined;
    const j = setInterval(loadUploads, 4000);
    return () => clearInterval(j);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [adaJalan]);

  const toggle = (name) => setSelected((prev) => {
    const next = new Set(prev);
    if (next.has(name)) next.delete(name); else next.add(name);
    return next;
  });

  const saveSelected = async () => {
    setWorking(true);
    for (const name of selected) {
      try {
        // eslint-disable-next-line no-await-in-loop
        await downloadToDisk(kategoriKlip(), name);
      } catch { /* lanjut ke berikutnya */ }
    }
    setWorking(false);
  };

  // Nama klip yang sedang dihapus atau diunduh, supaya barisnya bisa
  // menunjukkan bahwa perintahnya SEDANG dikerjakan. Tanpa ini, menekan
  // tombolnya tidak mengubah apa pun di layar sampai daftarnya dimuat ulang.
  const [sibukBaris, setSibukBaris] = useState(null);

  const diKomputerIni = dijalankanDiKomputerIni();

  /**
   * Membuka pengelola berkas dengan klip ini SUDAH TERSOROT.
   *
   * Dilaporkan pemiliknya 9 Oktober 2026: "saat mengklik klip yang jadi
   * disana hanya ada simpan berkas bukan membuka folder dan menunjuk video
   * itu dimana, karena sering saat upload saya harus cari foldernya dahulu,
   * jika tidak maka saya mendownload ulang hasil klip". Mengunduh ulang
   * melahirkan salinan kedua dengan nama berbeda, dan dari situlah video
   * tertukar saat diunggah.
   */
  const tunjukBerkas = async (name) => {
    setSibukBaris({ nama: name, apa: 'tunjuk' });
    try {
      await apiPost('/berkas/tunjuk', { kategori: kategoriKlip(), nama: name });
    } catch (e) {
      setActionError?.(e.message);
    } finally {
      setSibukBaris(null);
    }
  };

  const deleteClip = async (name) => {
    if (!window.confirm(t('klip.yakin_hapus', { nama: name }))) return;
    // PEMUTARNYA DILEPAS DULU, baru berkasnya dihapus.
    //
    // Tiap kartu memasang <video> yang menarik berkasnya lewat /api/media, dan
    // selama itu berkasnya terbuka. Di Windows, berkas yang terbuka tidak bisa
    // dihapus sama sekali. Dilaporkan pemiliknya 7 Oktober 2026: menghapus
    // klip jadi menjawab "tidak bisa terhubung ke server" di komputernya,
    // sementara di laptop ini tidak pernah terjadi.
    setSibukBaris({ nama: name, apa: 'hapus' });
    await new Promise((lanjut) => { setTimeout(lanjut, 120); });
    try {
      await apiDelete(`/clips/${encodeURIComponent(name)}`);
      setSelected((prev) => { const n = new Set(prev); n.delete(name); return n; });
      load();
    } catch (err) {
      setActionError(t('klip.gagal_hapus', { nama: name, pesan: err.message }));
    } finally {
      setSibukBaris(null);
    }
  };

  /** Menyimpan satu klip ke komputer, dengan tanda sedang berjalan. */
  const simpanSatu = async (name) => {
    setSibukBaris({ nama: name, apa: 'unduh' });
    try {
      await downloadToDisk(kategoriKlip(), name);
    } catch (err) {
      setActionError(t('klip.gagal_simpan', { nama: name, pesan: err.message }));
    } finally {
      setSibukBaris(null);
    }
  };

  // Ringkasan dan saring. "Terunggah" berarti pernah naik ke mana pun, lewat
  // unggahan OmniClip maupun tanda terbit yang dipasang tangan.
  const terunggah = (c) => (sent[c.file_name] || []).some((u) => u.status === 'done')
    || (c.metadata?.terbit?.length > 0);
  const judulKlip = (c) => {
    const m = c.metadata || {};
    return (m.title || m.hook_text || c.file_name.replace(/\.mp4$/i, '').replace(/[-_]+/g, ' ')).trim();
  };
  const jumlah = {
    semua: clips.length,
    belum: clips.filter((c) => !terunggah(c)).length,
    terunggah: clips.filter(terunggah).length,
  };
  const ukuranTotal = clips.reduce((n, c) => n + (c.file_size || 0), 0);
  const kata = cari.trim().toLowerCase();
  const tampil = clips.filter((c) => (saring === 'semua' || (saring === 'terunggah') === terunggah(c))
    && (!kata || judulKlip(c).toLowerCase().includes(kata) || c.file_name.toLowerCase().includes(kata)));

  const hapusTerpilih = async () => {
    const nama = [...selected];
    if (!nama.length || !window.confirm(t('klip.yakin_hapus_n', { n: nama.length }))) return;
    setWorking(true);
    for (const n of nama) {
      setSibukBaris({ nama: n, apa: 'hapus' });
      // eslint-disable-next-line no-await-in-loop
      await new Promise((lanjut) => { setTimeout(lanjut, 120); });
      try {
        // eslint-disable-next-line no-await-in-loop
        await apiDelete(`/clips/${encodeURIComponent(n)}`);
      } catch (err) {
        setActionError(t('klip.gagal_hapus', { nama: n, pesan: err.message }));
      }
    }
    setSibukBaris(null);
    setSelected(new Set());
    setWorking(false);
    load();
  };

  return (
    <div className="rak">
      {actionError && (
        <div className="rak-galat" role="alert">
          <AlertTriangle size={15} />
          <span>{actionError}</span>
          <button className="btn-secondary" onClick={() => setActionError(null)}>{t('umum.tutup')}</button>
        </div>
      )}
      <header className="rak-kepala">
        <div className="rak-kepala-teks">
          <h1 className="work-title rak-judul">{t('klip.judul')}</h1>
          <p className="rak-angka">
            {loading ? <span>{t('rak.memuat')}</span> : (
              <>
                <span><b>{jumlah.semua}</b>{t('rak.klip')}</span>
                <span><b>{formatBytes(ukuranTotal)}</b>{t('rak.di_cakram')}</span>
                <span className="is-entry"><b>{jumlah.terunggah}</b>{t('rak.terunggah')}</span>
                {jumlah.belum > 0 && <span className="is-reh"><b>{jumlah.belum}</b>{t('rak.belum_unggah')}</span>}
              </>
            )}
          </p>
        </div>
        <div className="rak-aksi">
          <button className="btn-secondary" onClick={() => { load(); loadUploads(); }}>
            <RefreshCw size={14} /> {t('umum.muat_ulang')}
          </button>
        </div>
      </header>

      {clips.length > 0 && (
        <div className="rak-alat">
          <label className="rak-cari">
            <Search size={15} />
            <input className="field" type="search" value={cari} onChange={(e) => setCari(e.target.value)}
                   placeholder={t('rak.cari_klip')} aria-label={t('rak.cari_klip')} />
          </label>
          <div className="seg" role="tablist" aria-label={t('rak.saring')}>
            {[['semua', 'rak.s_semua'], ['belum', 'rak.s_belum'], ['terunggah', 'rak.s_terunggah']].map(([k, kunci]) => (
              <button key={k} role="tab" aria-selected={saring === k}
                      className={saring === k ? 'is-on' : undefined} onClick={() => setSaring(k)}>
                {t(kunci)} <span className="seg-n">{jumlah[k]}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {selected.size > 0 && (
        <div className="bilah-pilih">
          <span><b>{selected.size}</b> {t('rak.dipilih')}</span>
          <span className="pengisi" />
          <button className="btn-secondary" onClick={saveSelected} disabled={working}>
            {working ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            {t('klip.simpan_n', { n: selected.size })}
          </button>
          <button className="btn-secondary" onClick={hapusTerpilih} disabled={working}
                  style={{ color: 'var(--danger)' }}>
            <Trash2 size={14} /> {t('rak.hapus_n', { n: selected.size })}
          </button>
          <button className="ikon-btn" onClick={() => setSelected(new Set())}
                  title={t('rak.batal_pilih')} aria-label={t('rak.batal_pilih')}>
            <X size={15} />
          </button>
        </div>
      )}

      {loading ? (
        <div className="rak-grid rak-grid--tegak" aria-busy="true">
          {[0, 1, 2, 3, 4].map((n) => (
            <div key={n} className="lembar lembar-kerangka">
              <div className="kerangka" style={{ aspectRatio: '9 / 16', borderRadius: '3px 3px 0 0' }} />
              <div className="lembar-badan">
                <div className="kerangka" style={{ height: 13, width: '80%' }} />
                <div className="kerangka" style={{ height: 10, width: '50%' }} />
              </div>
            </div>
          ))}
        </div>
      ) : error ? (
        <div className="rak-kosong">
          <AlertTriangle size={34} style={{ color: 'var(--danger)' }} />
          <h3>{t('klip.gagal_muat')}</h3>
          <p>{error.message}</p>
          <button className="btn-secondary" onClick={load} style={{ marginTop: 16 }}>
            <RefreshCw size={14} /> {t('umum.coba_lagi')}
          </button>
        </div>
      ) : clips.length === 0 ? (
        <div className="rak-kosong">
          <Film size={38} />
          <h3>{t('klip.kosong')}</h3>
          <p>{t('klip.kosong_saran')}</p>
        </div>
      ) : tampil.length === 0 ? (
        <div className="rak-kosong">
          <Search size={32} />
          <h3>{t('rak.tak_cocok')}</h3>
          <button className="btn-secondary" style={{ marginTop: 12 }}
                  onClick={() => { setCari(''); setSaring('semua'); }}>{t('rak.hapus_saring')}</button>
        </div>
      ) : (
        <div className="rak-grid rak-grid--tegak">
          {tampil.map((clip) => {
            const meta = clip.metadata || {};
            const segCount = meta.segments?.length ?? 1;
            const dipilih = selected.has(clip.file_name);
            const sibuk = sibukBaris?.nama === clip.file_name;
            const judul = judulKlip(clip);
            const unggahan = sent[clip.file_name] || [];
            const stat = unggahan.map((u) => u.statistik).find((x) => x && x.tayangan != null);
            const gagalTerbaru = unggahan.find((u) => u.status === 'failed')?.error;
            return (
              <article key={clip.file_name} className={`lembar${dipilih ? ' is-pilih' : ''}`}>
                <div className="lembar-gambar">
                  <PratinjauKlip
                    src={mediaUrl(kategoriKlip(), clip.file_name)}
                    lepas={sibuk && sibukBaris.apa === 'hapus'}
                    onClick={() => setPlaying(clip)}
                  >
                    <span className="lembar-putar" aria-hidden="true"><Play size={22} fill="currentColor" /></span>
                    <span className="lencana lencana--kb">{formatTime(meta.duration || 0)}</span>
                    {segCount > 1 && (
                      <span className="lencana lencana--ka lencana--hl" title={t('rak.n_potongan', { n: segCount })}>
                        <Layers size={10} /> {segCount}
                      </span>
                    )}
                    {/* Kotak pilih di pojok gambar, bukan di baris tombol: tujuh
                        tombol dalam satu baris kartu selebar 190 px mendorong
                        tombol hapus keluar kartu dan terpotong. Dilaporkan
                        pemiliknya 28 Oktober 2026: "di klip jadi tidak ada
                        button untuk menghapus klip". */}
                    <label className="pilih-gambar" onClick={(e) => e.stopPropagation()} title={t('umum.pilih')}>
                      <input type="checkbox" checked={dipilih}
                             onChange={() => toggle(clip.file_name)} aria-label={t('umum.pilih')} />
                    </label>
                  </PratinjauKlip>
                </div>

                <div className="lembar-badan">
                  <h2 className="lembar-judul" title={judul}>{judul}</h2>
                  <div className="lembar-meta">
                    <span>{meta.aspect_ratio || '9:16'}</span>
                    <span>{formatBytes(clip.file_size)}</span>
                    {clip.created_at ? <span>{tanggalPendek(clip.created_at)}</span> : null}
                  </div>
                  {/* Nilai tambah (JOB-2 F3-1): berapa banyak klip ini berisi
                      komentar atau tambahan dari pemiliknya sendiri. Klip lama
                      yang dirender sebelum skornya ada tidak diberi angka.
                      Kuning, bukan merah: ini saran, bukan galat. */}
                  {meta.nilai_tambah && (
                    <span className={`tanda ${meta.nilai_tambah.cukup ? 'tanda--siap' : 'tanda--warn'}`}
                          title={(meta.nilai_tambah.rincian || []).join(' · ') || t('klip.nilai_kosong')}>
                      {meta.nilai_tambah.cukup ? <Check size={12} /> : <MessageSquarePlus size={12} />}
                      {t('klip.nilai_tambah', { n: meta.nilai_tambah.persen })}
                      {meta.nilai_tambah.cukup ? '' : t('klip.belum_komentar')}
                    </span>
                  )}
                  {/* Tayangan, kalau kuncinya disetel dan videonya publik.
                      Tidak ditampilkan sebagai nol saat tidak terbaca: nol pada
                      klip yang sebenarnya ditonton ribuan orang adalah angka
                      yang langsung dipakai orang untuk mengambil keputusan. */}
                  {stat && (
                    <span className="tanda" title={t('klip.tayangan_yt')}>
                      <Eye size={12} />
                      <b style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--ink)' }}>{angka(stat.tayangan)}</b>
                      {stat.suka != null && (
                        <span style={{ color: 'var(--ink-3)', fontWeight: 500 }}>{t('klip.suka', { n: angka(stat.suka) })}</span>
                      )}
                    </span>
                  )}

                  {/* Sudah diterbitkan ke mana: ditandai tangan (bisa dicabut
                      kalau salah tekan) atau lewat unggahan OmniClip. Ini yang
                      mencegah klip yang sama dikirim dua kali ke kanal yang sama. */}
                  {(meta.terbit?.length > 0 || unggahan.length > 0) && (
                    <div className="lembar-tujuan">
                      {(meta.terbit || []).map((nama) => (
                        <button key={nama} type="button" className="tujuan is-ok"
                                title={t('klip.sudah_terbit')}
                                onClick={() => tandaiTerbit(clip, nama, false)}>
                          <Check size={10} /> {LABEL_PLATFORM[nama] || nama}
                        </button>
                      ))}
                      {unggahan.map((u) => {
                        const target = u.target === 'youtube' ? 'YouTube' : 'Drive';
                        if (u.job) {
                          return (
                            <span key={u.id} className="tujuan is-jalan" title={u.job.message || ''}>
                              <Loader2 size={10} className="animate-spin" />
                              {u.job.status === 'running'
                                ? t('klip.mengunggah_ke', { target, n: Math.round((u.job.progress || 0) * 100) })
                                : t('klip.antre_unggah', { target })}
                            </span>
                          );
                        }
                        if (u.status === 'done') {
                          return (
                            <a key={u.id} href={u.remote_url} target="_blank" rel="noreferrer" className="tujuan is-ok">
                              <ExternalLink size={10} /> {target}
                            </a>
                          );
                        }
                        /* Alasannya ditulis lengkap di bawah, bukan cuma
                           "gagal": yang menghalangi biasanya bisa dibereskan
                           sendiri dalam semenit. */
                        return (
                          <span key={u.id} className="tujuan is-gagal" title={u.error || t('klip.unggah_gagal')}>
                            <X size={10} /> {t('klip.target_gagal', { target })}
                          </span>
                        );
                      })}
                    </div>
                  )}
                  {gagalTerbaru && <div className="lembar-catatan" style={{ color: 'var(--ink-3)' }}>{gagalTerbaru}</div>}

                  <div className="lembar-kaki">
                    <button className="btn-garis" onClick={() => setUploading(clip)} title={t('klip.unggah')}>
                      <UploadCloud size={14} /> {t('rak.unggah')}
                    </button>
                    <button className="ikon-btn" onClick={() => setSiapkan(clip)}
                            aria-label={t('klip.siapkan')} title={t('klip.siapkan_judul')}>
                      <Send size={15} />
                    </button>
                    {diKomputerIni && (
                      <button className="ikon-btn" onClick={() => tunjukBerkas(clip.file_name)} disabled={sibuk}
                              aria-label={t('klip.tunjuk')} title={t('klip.tunjuk_judul')}>
                        {sibuk && sibukBaris.apa === 'tunjuk'
                          ? <Loader2 size={15} className="animate-spin" /> : <FolderOpen size={15} />}
                      </button>
                    )}
                    <button className="ikon-btn" onClick={() => simpanSatu(clip.file_name)} disabled={sibuk}
                            aria-label={t('klip.simpan_salinan')} title={t('klip.simpan_salinan_judul')}>
                      {sibuk && sibukBaris.apa === 'unduh'
                        ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />}
                    </button>
                    {clip.srt && (
                      <button className="ikon-btn" onClick={() => simpanSatu(clip.file_name.replace(/\.mp4$/, '.srt'))}
                              disabled={sibuk} aria-label={t('klip.srt')} title={t('klip.srt_judul')}>
                        SRT
                      </button>
                    )}
                    <button className="ikon-btn is-bahaya" onClick={() => deleteClip(clip.file_name)} disabled={sibuk}
                            aria-label={t('umum.hapus')} title={t('umum.hapus')}>
                      {sibuk && sibukBaris.apa === 'hapus'
                        ? <Loader2 size={15} className="animate-spin" /> : <Trash2 size={15} />}
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {playing && <PlayerModal clip={playing} onClose={() => setPlaying(null)} />}
      {uploading && (
        <UploadModal clip={uploading} onClose={() => setUploading(null)}
                     onDone={loadUploads} />
      )}
      {siapkan && (
        <SiapkanTerbit clip={siapkan} onClose={() => setSiapkan(null)} onSelesai={load} />
      )}
    </div>
  );
}

