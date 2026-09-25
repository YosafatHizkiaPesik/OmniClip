import React, { useEffect, useRef, useState } from 'react';
import {
  Film, Download, Trash2, RefreshCw, Loader2, AlertTriangle, Layers, X, UploadCloud, Send, Check
} from 'lucide-react';
import { apiGet, apiPost, apiDelete, downloadToDisk, mediaUrl, kategoriKlip } from '../lib/api';
import { formatTime } from '../utils/timeFormat';
import UploadModal from './UploadModal';
import SiapkanTerbit from './SiapkanTerbit';

// Cermin dari PLATFORM di backend/app/services/keterangan.py. Hanya labelnya;
// aturan tiap platform tetap tinggal di sana.
const LABEL_PLATFORM = {
  tiktok: 'TikTok', instagram: 'Instagram', shorts: 'Shorts', facebook: 'Facebook',
};

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
function PratinjauKlip({ src, onClick, children }) {
  const wadah = useRef(null);
  const [muat, setMuat] = useState(false);

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
    <div ref={wadah} onClick={onClick} style={{
      position: 'relative', aspectRatio: '9 / 16', background: 'var(--stage)',
      cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      {muat ? (
        <video src={src} preload="metadata" muted style={gaya}
               onLoadedMetadata={_lepasGiliran} onError={_lepasGiliran} />
      ) : (
        <Film size={26} style={{ color: 'var(--text-muted)' }} />
      )}
      {children}
    </div>
  );
}

function PlayerModal({ clip, onClose }) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} style={{
        background: '#000', borderRadius: '16px', overflow: 'hidden',
        maxHeight: '86vh', position: 'relative', display: 'flex',
      }}>
        <button onClick={onClose} aria-label="Tutup" style={{
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
      const { uploads } = await apiGet('/uploads?limit=200');
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
        if (u.status !== 'done' && u.status !== 'failed') continue;
        (map[u.clip_name] ??= []).push(u);
      }
      setSent(map);
    } catch { /* riwayat kosong bukan kegagalan halaman */ }
  };

  useEffect(() => { load(); loadUploads(); }, []);

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

  const deleteClip = async (name) => {
    if (!window.confirm(`Hapus klip "${name}"?`)) return;
    setSibukBaris({ nama: name, apa: 'hapus' });
    try {
      await apiDelete(`/clips/${encodeURIComponent(name)}`);
      setSelected((prev) => { const n = new Set(prev); n.delete(name); return n; });
      load();
    } catch (err) {
      setActionError(`Gagal menghapus "${name}": ${err.message}`);
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
      setActionError(`Gagal menyimpan "${name}": ${err.message}`);
    } finally {
      setSibukBaris(null);
    }
  };

  return (
    <div style={{ paddingBottom: '40px' }}>
      {actionError && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap',
          padding: '11px 14px', marginBottom: '14px', fontSize: '0.83rem',
          borderRadius: 'var(--radius-md)', color: 'var(--accent-red, var(--danger))',
          background: 'color-mix(in srgb, var(--danger) 12%, transparent)', border: '1px solid color-mix(in srgb, var(--danger) 30%, transparent)',
        }}>
          <span style={{ flex: 1, minWidth: '180px' }}>{actionError}</span>
          <button className="btn-secondary" style={{ fontSize: '0.76rem', padding: '5px 11px' }}
                  onClick={() => setActionError(null)}>Tutup</button>
        </div>
      )}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap', marginBottom: '18px' }}>
        <h1 style={{ fontSize: '1.2rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '9px' }}>
          <Film size={20} style={{ color: 'var(--accent-cyan)' }} /> Klip jadi
        </h1>
        <div style={{ flex: 1 }} />
        {selected.size > 0 && (
          <button className="btn-primary" onClick={saveSelected} disabled={working} style={{ fontSize: '0.8rem' }}>
            {working ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            Simpan {selected.size} klip
          </button>
        )}
        <button className="btn-secondary" onClick={load} style={{ fontSize: '0.8rem' }}>
          <RefreshCw size={14} /> Muat ulang
        </button>
      </div>

      {loading ? (
        <div style={{ padding: '60px', textAlign: 'center' }}>
          <Loader2 size={30} className="animate-spin" style={{ color: 'var(--accent-cyan)' }} />
        </div>
      ) : error ? (
        <div style={{
          padding: '36px 20px', textAlign: 'center', background: 'var(--bg-card)',
          border: '1px solid var(--accent-red)', borderRadius: 'var(--radius-lg)',
        }}>
          <AlertTriangle size={34} style={{ color: 'var(--accent-red)', marginBottom: '10px' }} />
          <div style={{ fontWeight: 700 }}>Gagal memuat klip</div>
          <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)' }}>{error.message}</p>
        </div>
      ) : clips.length === 0 ? (
        <div style={{
          padding: '54px 20px', textAlign: 'center', background: 'var(--bg-card)',
          border: '1px dashed var(--border-color)', borderRadius: 'var(--radius-lg)',
        }}>
          <Film size={44} style={{ color: 'var(--text-muted)', marginBottom: '12px' }} />
          <h3 style={{ fontWeight: 700 }}>Belum ada klip</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            Buka sebuah video di Cari video, tekan “Potong jadi klip”, lalu render klipnya di Partitur.
          </p>
        </div>
      ) : (
        <div style={{
          display: 'grid', gap: '14px',
          gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))',
        }}>
          {clips.map((clip) => {
            const meta = clip.metadata || {};
            const segCount = meta.segments?.length ?? 1;
            return (
              <div key={clip.file_name} style={{
                background: 'var(--bg-card)', border: selected.has(clip.file_name)
                  ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                borderRadius: 'var(--radius-md)', overflow: 'hidden',
                display: 'flex', flexDirection: 'column',
              }}>
                <PratinjauKlip
                  src={mediaUrl(kategoriKlip(), clip.file_name)}
                  onClick={() => setPlaying(clip)}
                >
                  <div style={{
                    position: 'absolute', bottom: '6px', right: '6px',
                    background: 'rgba(0,0,0,0.8)', color: '#fff', fontSize: '0.7rem',
                    fontWeight: 700, padding: '2px 6px', borderRadius: '4px',
                  }}>
                    {formatTime(meta.duration || 0)}
                  </div>
                  {segCount > 1 && (
                    <div style={{
                      position: 'absolute', top: '6px', left: '6px',
                      background: 'var(--hl-wash)', color: '#000', fontSize: '0.66rem',
                      fontWeight: 800, padding: '2px 6px', borderRadius: '4px',
                      display: 'flex', alignItems: 'center', gap: '3px',
                    }}>
                      <Layers size={10} /> {segCount}
                    </div>
                  )}
                </PratinjauKlip>

                <div style={{ padding: '10px', display: 'flex', flexDirection: 'column', gap: '7px' }}>
                  <div style={{ fontSize: '0.76rem', fontWeight: 700, lineHeight: 1.3 }}>
                    {meta.hook_text ? meta.hook_text.slice(0, 46) : clip.file_name.slice(0, 26)}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                    {meta.aspect_ratio || '9:16'} · {formatBytes(clip.file_size)}
                  </div>
                  {/* Sudah diterbitkan ke platform mana, ditandai tangan.
                      Penandanya dulu hanya ada DI DALAM jendela "Siapkan
                      terbit", jadi menjawab "yang mana yang sudah naik?" berarti
                      membuka lima belas jendela satu per satu. Di sini ia
                      terlihat sekaligus, dan bisa dicabut kalau salah tekan. */}
                  {meta.terbit?.length > 0 && (
                    <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                      {(meta.terbit || []).map((nama) => (
                        <button key={nama} className="chip is-on"
                                title="Sudah diterbitkan. Klik untuk mencabut tandanya."
                                onClick={() => tandaiTerbit(clip, nama, false)}
                                style={{ fontSize: '.64rem', padding: '2px 7px',
                                         cursor: 'pointer', display: 'inline-flex',
                                         alignItems: 'center', gap: '4px' }}>
                          <Check size={10} /> {LABEL_PLATFORM[nama] || nama}
                        </button>
                      ))}
                    </div>
                  )}

                  {/* Sudah pernah naik ke mana lewat unggahan otomatis. Ini
                      yang mencegah klip yang sama dikirim dua kali ke kanal
                      yang sama. */}
                  {sent[clip.file_name]?.length > 0 && (
                    <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
                      {sent[clip.file_name].map((u) => (u.status === 'done' ? (
                        <a key={u.id} href={u.remote_url} target="_blank" rel="noreferrer"
                           className="chip" style={{
                             fontSize: '.64rem', padding: '2px 7px', textDecoration: 'none',
                           }}>
                          ↗ {u.target === 'youtube' ? 'YouTube' : 'Drive'}
                        </a>
                      ) : (
                        /* Alasannya ditulis lengkap, bukan cuma "gagal": yang
                           menghalangi biasanya bisa dibereskan sendiri dalam
                           semenit, misalnya kanal YouTube yang belum dibuat. */
                        <span key={u.id} className="chip" title={u.error || 'Unggahan gagal'}
                              style={{
                                fontSize: '.64rem', padding: '2px 7px',
                                color: 'var(--danger)',
                                borderColor: 'var(--danger)', cursor: 'help',
                              }}>
                          ✕ {u.target === 'youtube' ? 'YouTube' : 'Drive'} gagal
                        </span>
                      )))}
                    </div>
                  )}
                  {/* Alasan gagal terbaru, ditulis apa adanya. Tanda "✕" di
                      atas cuma memberi tahu ADA yang gagal; yang menentukan
                      langkah berikutnya adalah kalimat ini. */}
                  {sent[clip.file_name]?.find((u) => u.status === 'failed')?.error && (
                    <div style={{ fontSize: '.66rem', color: 'var(--text-muted)',
                                  lineHeight: 1.45 }}>
                      {sent[clip.file_name].find((u) => u.status === 'failed').error}
                    </div>
                  )}
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <label style={{ display: 'flex', alignItems: 'center', gap: '5px', cursor: 'pointer', fontSize: '0.72rem', flex: 1 }}>
                      <input type="checkbox" checked={selected.has(clip.file_name)}
                             onChange={() => toggle(clip.file_name)}
                             style={{ accentColor: 'var(--accent-cyan)' }} />
                      Pilih
                    </label>
                    <button onClick={() => setSiapkan(clip)} style={iconBtn}
                            aria-label="Siapkan untuk diterbitkan"
                            title="Siapkan caption dan tagar untuk TikTok, Reels, atau Shorts">
                      <Send size={14} />
                    </button>
                    <button onClick={() => setUploading(clip)} style={iconBtn}
                            aria-label="Unggah ke Drive atau YouTube"
                            title="Unggah ke Drive atau YouTube">
                      <UploadCloud size={14} />
                    </button>
                    <button onClick={() => simpanSatu(clip.file_name)}
                            disabled={sibukBaris?.nama === clip.file_name}
                            aria-label="Simpan" style={iconBtn}>
                      {sibukBaris?.nama === clip.file_name && sibukBaris.apa === 'unduh'
                        ? <Loader2 size={14} className="animate-spin" />
                        : <Download size={14} />}
                    </button>
                    {clip.srt && (
                      <button onClick={() => simpanSatu(clip.file_name.replace(/\.mp4$/, '.srt'))}
                              disabled={sibukBaris?.nama === clip.file_name}
                              aria-label="Simpan takarir .srt"
                              title="Simpan takarir .srt untuk diunggah terpisah ke YouTube"
                              style={{ ...iconBtn, fontSize: '0.62rem', fontWeight: 800,
                                       letterSpacing: '0.03em' }}>
                        SRT
                      </button>
                    )}
                    <button onClick={() => deleteClip(clip.file_name)} aria-label="Hapus"
                            disabled={sibukBaris?.nama === clip.file_name}
                            style={{ ...iconBtn, color: 'var(--accent-red)' }}>
                      {sibukBaris?.nama === clip.file_name && sibukBaris.apa === 'hapus'
                        ? <Loader2 size={14} className="animate-spin" />
                        : <Trash2 size={14} />}
                    </button>
                  </div>
                </div>
              </div>
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

const iconBtn = {
  background: 'none', border: 'none', cursor: 'pointer',
  color: 'var(--text-secondary)', display: 'flex', padding: '3px',
};
