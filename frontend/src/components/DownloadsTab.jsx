import React, { useState, useEffect } from 'react';
import { Download, Film, Music, Trash2, RefreshCw, Search, Play, X, Loader2, AlertTriangle, Scissors, ArrowRight, Sparkles } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { apiGet, apiDelete, apiPost, downloadToDisk } from '../lib/api';
import { lokal, useT } from '../lib/i18n';

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function formatDate(timestamp) {
  if (!timestamp) return '';
  return new Date(timestamp * 1000).toLocaleDateString(lokal(), {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
  });
}

/**
 * Judul yang terbaca untuk berkas tanpa baris database.
 *
 * Unduhan lama — dibuat sebelum ada database — tidak punya judul tersimpan.
 * Nama berkasnya masih memuatnya, hanya dengan garis bawah sebagai spasi dan
 * ID YouTube menempel di ekor. Yang dibuang cuma itu; tidak ada yang dikarang.
 */
function judulDariNama(fileName) {
  return String(fileName || '')
    .replace(/\.[a-z0-9]{2,4}$/i, '')        // ekstensi
    .replace(/[_-][A-Za-z0-9_-]{11}$/, '')   // ID YouTube di ekor
    .replace(/_/g, ' ')
    .trim() || fileName;
}

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return null;
  const total = Math.round(seconds);
  const j = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const d = total % 60;
  const pad = (n) => String(n).padStart(2, '0');
  return j ? `${j}:${pad(m)}:${pad(d)}` : `${m}:${pad(d)}`;
}

/**
 * Sampul satu berkas unduhan.
 *
 * Dibuat dari bingkai berkasnya sendiri di server, jadi ia tetap muncul tanpa
 * internet — yang penting justru di halaman ini. Selama gambarnya belum
 * datang, yang tampil adalah bidang kosong dengan ikon, bukan pergeseran tata
 * letak: tinggi kartu sudah dikunci oleh aspect-ratio.
 */
function Thumb({ item }) {
  const [state, setState] = useState(item.thumb_url ? 'loading' : 'none');
  const audio = item.type === 'audio';
  const durasi = formatDuration(item.duration);

  return (
    <div className="pit-well" style={{ aspectRatio: '16 / 9', display: 'grid', placeItems: 'center' }}>
      {state !== 'ok' && (
        audio ? <Music size={28} style={{ color: 'var(--reh)' }} /> : <Film size={28} style={{ color: '#5B6678' }} />
      )}
      {item.thumb_url && state !== 'error' && (
        <img
          src={item.thumb_url}
          alt=""
          loading="lazy"
          onLoad={() => setState('ok')}
          onError={() => setState('error')}
          style={{
            position: 'absolute', inset: 0, width: '100%', height: '100%',
            objectFit: 'cover', opacity: state === 'ok' ? 1 : 0,
            transition: 'opacity 0.25s ease, transform .5s cubic-bezier(.16,1,.3,1)',
          }}
        />
      )}
      <span className="lembar-putar" aria-hidden="true"><Play size={22} fill="currentColor" /></span>
      {durasi && <span className="lencana lencana--kb">{durasi}</span>}
      {item.resolution && <span className="lencana lencana--kib">{item.resolution}</span>}
          </div>
  );
}

// Video Player Modal
function VideoPlayerModal({ item, onClose }) {
  const t = useT();
  const src = `${item.web_url}`;
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div onClick={e => e.stopPropagation()} style={{
        background: '#000', borderRadius: '16px', overflow: 'hidden',
        maxWidth: '800px', width: '100%', position: 'relative',
      }}>
        <button onClick={onClose} aria-label={t('umum.tutup')} style={{
          position: 'absolute', top: '10px', right: '10px', zIndex: 10,
          width: '32px', height: '32px', borderRadius: '50%',
          background: 'rgba(0,0,0,0.7)', border: 'none', color: '#fff',
          cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}><X size={16} /></button>
        {item.type === 'audio'
          ? <audio src={src} controls autoPlay style={{ width: '100%', padding: '40px 20px 20px' }} />
          : <video src={src} controls autoPlay style={{ width: '100%', maxHeight: '70vh', display: 'block' }} />
        }
        <div style={{ padding: '12px 16px', background: 'var(--stage)' }}>
          <div style={{ fontWeight: 700, fontSize: '0.9rem', color: '#E7EDF5', wordBreak: 'break-all' }}>{item.file_name}</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            {formatBytes(item.file_size)} • {item.type.toUpperCase()} • {formatDate(item.created_at)}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function DownloadsTab() {
  const t = useT();
  const [downloads, setDownloads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [deleting, setDeleting] = useState(null); // filename being deleted
  const [previewItem, setPreviewItem] = useState(null);
  const [selectedItems, setSelectedItems] = useState(new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [loadError, setLoadError] = useState(null);
  // Video yang sedang dikirim ke Partitur.
  const [mengirim, setMengirim] = useState(null);
  const navigate = useNavigate();

  /**
   * Mengirim satu unduhan ke Partitur, lalu membuka halamannya.
   *
   * Videonya sudah ada di komputer, jadi auto-klip melewati langkah unduh dan
   * langsung menyalin ucapan. Yang sudah pernah diklip tidak diklip lagi:
   * `/auto-clip` menjawab `cached`, dan yang perlu dilakukan hanya membuka
   * proyeknya.
   */
  const kePartitur = async (item) => {
    setMengirim(item.video_id);
    setActionError(null);
    try {
      await apiPost('/auto-clip', {
        video_id: item.video_id,
        max_clips: Number(localStorage.getItem('omniclip_max_clips') || 0),
        whisper_model: localStorage.getItem('omniclip_whisper_model') || 'base',
        gemini_model: localStorage.getItem('omniclip_gemini_model') || null,
      });
      navigate('/studio');
    } catch (e) {
      setActionError(e.message);
    } finally {
      setMengirim(null);
    }
  };
  // Kegagalan aksi (hapus / simpan) ditampilkan inline, bukan lewat window.alert
  // yang memblokir dan tidak bisa disalin teksnya.
  const [actionError, setActionError] = useState(null);
  const [filter, setFilter] = useState('all'); // 'all' | 'video' | 'audio'

  const fetchDownloads = async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await apiGet('/downloads');
      setDownloads(Array.isArray(data) ? data : []);
    } catch (err) {
      // Jangan samarkan backend mati sebagai "tidak ada unduhan".
      setLoadError(err);
      setDownloads([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDownloads(); }, []);

  const handleDelete = async (filename) => {
    if (!window.confirm(t('unduhan.yakin_hapus', { nama: filename }))) return;
    setDeleting(filename);
    setActionError(null);
    try {
      await apiDelete(`/downloads/${encodeURIComponent(filename)}`);
      setDownloads(prev => prev.filter(d => d.file_name !== filename));
      setSelectedItems(prev => { const s = new Set(prev); s.delete(filename); return s; });
    } catch (err) {
      setActionError(t('klip.gagal_hapus', { nama: filename, pesan: err.message }));
    } finally {
      setDeleting(null);
    }
  };

  const handleBulkDelete = async () => {
    if (selectedItems.size === 0) return;
    if (!window.confirm(t('unduhan.yakin_hapus_n', { n: selectedItems.size }))) return;
    setBulkDeleting(true);
    setActionError(null);
    const failed = [];
    for (const fname of selectedItems) {
      try {
        // eslint-disable-next-line no-await-in-loop
        await apiDelete(`/downloads/${encodeURIComponent(fname)}`);
      } catch {
        // Kegagalan per file dikumpulkan, bukan ditelan diam-diam seperti dulu.
        failed.push(fname);
      }
    }
    if (failed.length) {
      setActionError(t('unduhan.gagal_n', { n: failed.length, daftar: failed.join(', ') }));
    }
    setSelectedItems(new Set());
    await fetchDownloads();
    setBulkDeleting(false);
  };

  const handleProxyDownload = async (fileName) => {
    setActionError(null);
    try {
      await downloadToDisk('local_downloads', fileName);
    } catch (err) {
      setActionError(t('tonton.gagal_simpan', { pesan: err.message }));
    }
  };

  const toggleSelect = (fname) => {
    setSelectedItems(prev => {
      const s = new Set(prev);
      if (s.has(fname)) s.delete(fname); else s.add(fname);
      return s;
    });
  };

  // Filter + Search
  const filtered = downloads.filter(d => {
    const matchFilter = filter === 'all' || d.type === filter;
    // Judul dan kanal ikut dicari, bukan hanya nama berkas: sejak kartunya
    // menampilkan judul asli, mencari kata yang terbaca di layar tapi tidak
    // ada di nama berkas akan terasa seperti pencarian yang rusak.
    const q = searchQuery.toLowerCase();
    const matchSearch = !q || [d.file_name, d.title, d.channel]
      .some((v) => (v || '').toLowerCase().includes(q));
    return matchFilter && matchSearch;
  });

  const totalSize = downloads.reduce((acc, d) => acc + d.file_size, 0);

  const jumlah = {
    all: downloads.length,
    video: downloads.filter((d) => d.type === 'video').length,
    audio: downloads.filter((d) => d.type === 'audio').length,
  };
  const diPartitur = downloads.filter((d) => d.ada_partitur).length;

  return (
    <div className="rak">
      <header className="rak-kepala">
        <div className="rak-kepala-teks">
          <h1 className="work-title rak-judul">{t('unduhan.judul')}</h1>
          <p className="rak-angka">
            {loading ? <span>{t('rak.memuat')}</span> : (
              <>
                <span><b>{downloads.length}</b>{t('rak.berkas')}</span>
                <span><b>{formatBytes(totalSize)}</b>{t('rak.di_cakram')}</span>
                {diPartitur > 0 && <span className="is-entry"><b>{diPartitur}</b>{t('rak.sudah_partitur')}</span>}
              </>
            )}
          </p>
        </div>
        <div className="rak-aksi">
          <button className="btn-secondary" onClick={fetchDownloads}>
            <RefreshCw size={14} /> {t('umum.muat_ulang')}
          </button>
        </div>
      </header>

      {downloads.length > 0 && (
        <div className="rak-alat">
          <label className="rak-cari">
            <Search size={15} />
            <input className="field" type="search" placeholder={t('unduhan.cari')} aria-label={t('unduhan.cari')}
                   value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
          </label>
          <div className="seg" role="tablist" aria-label={t('rak.saring')}>
            {[['all', t('umum.semua'), null], ['video', 'Video', Film], ['audio', 'Audio', Music]]
              .filter(([val]) => val === 'all' || jumlah[val] > 0)
              .map(([val, label, Ikon]) => (
                <button key={val} role="tab" aria-selected={filter === val}
                        className={filter === val ? 'is-on' : undefined} onClick={() => setFilter(val)}>
                  {Ikon && <Ikon size={13} />}{label} <span className="seg-n">{jumlah[val]}</span>
                </button>
              ))}
          </div>
        </div>
      )}

      {selectedItems.size > 0 && (
        <div className="bilah-pilih">
          <span><b>{selectedItems.size}</b> {t('rak.dipilih')}</span>
          <span className="pengisi" />
          <button onClick={handleBulkDelete} disabled={bulkDeleting} className="btn-secondary"
                  style={{ color: 'var(--danger)' }}>
            {bulkDeleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
            {t('unduhan.hapus_n', { n: selectedItems.size })}
          </button>
          <button className="ikon-btn" onClick={() => setSelectedItems(new Set())}
                  title={t('rak.batal_pilih')} aria-label={t('rak.batal_pilih')}>
            <X size={15} />
          </button>
        </div>
      )}

      {actionError && (
        <div className="rak-galat" role="alert">
          <AlertTriangle size={15} />
          <span>{actionError}</span>
          <button className="btn-secondary" onClick={() => setActionError(null)}>{t('umum.tutup')}</button>
        </div>
      )}

      {loading ? (
        <div className="rak-grid" aria-busy="true">
          {[0, 1, 2, 3].map((n) => (
            <div key={n} className="lembar lembar-kerangka">
              <div className="pit-frame"><div className="pit-well" style={{ aspectRatio: '16/9' }} /></div>
              <div className="lembar-badan">
                <div className="kerangka" style={{ height: 14, width: '85%' }} />
                <div className="kerangka" style={{ height: 11, width: '55%' }} />
                <div className="kerangka" style={{ height: 32, marginTop: 12 }} />
              </div>
            </div>
          ))}
        </div>
      ) : loadError ? (
        <div className="rak-kosong">
          <AlertTriangle size={36} style={{ color: 'var(--danger)' }} />
          <h3>{t('unduhan.gagal_muat')}</h3>
          <p>{loadError.message}</p>
          <button className="btn-secondary" onClick={fetchDownloads} style={{ marginTop: '14px' }}>
            <RefreshCw size={14} /> {t('umum.coba_lagi')}
          </button>
        </div>
      ) : filtered.length === 0 ? (
        <div className="rak-kosong">
          {downloads.length === 0 ? <Download size={38} /> : <Search size={32} />}
          <h3>{downloads.length === 0 ? t('unduhan.kosong') : t('unduhan.tanpa_hasil')}</h3>
          <p>
            {downloads.length === 0
              ? t('unduhan.kosong_saran')
              : t('unduhan.tidak_cocok', { q: searchQuery })}
          </p>
          {downloads.length > 0 && (
            <button className="btn-secondary" style={{ marginTop: 14 }}
                    onClick={() => { setSearchQuery(''); setFilter('all'); }}>{t('rak.hapus_saring')}</button>
          )}
        </div>
      ) : (
        <div className="rak-grid">
          {filtered.map((item) => {
            const dipilih = selectedItems.has(item.file_name);
            const judul = item.title || judulDariNama(item.file_name);
            return (
              <article key={item.file_name} className={`lembar${dipilih ? ' is-pilih' : ''}`}>
                <div className="pit-frame lembar-sampul" onClick={() => setPreviewItem(item)}
                     role="button" tabIndex={0} aria-label={t('unduhan.putar')}
                     onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setPreviewItem(item); } }}>
                  <Thumb item={item} />
                  {/* Kotak pilih di atas sampul: kartunya digerakkan oleh
                      gambar, jadi kendali pilih ikut ke sana. */}
                  <label className="pilih-gambar" onClick={(e) => e.stopPropagation()}
                         title={dipilih ? t('unduhan.batal_pilih') : t('umum.pilih')}
                         style={{ left: 12, top: 12 }}>
                    <input type="checkbox" checked={dipilih} onChange={() => toggleSelect(item.file_name)}
                           aria-label={t('umum.pilih')} />
                  </label>
                </div>

                <div className="lembar-badan">
                  <h2 className="lembar-judul" title={item.file_name} style={{ overflowWrap: 'anywhere' }}>{judul}</h2>
                  <div className="lembar-meta">
                    {item.channel && <span style={{ maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.channel}</span>}
                  </div>
                  <div className="lembar-meta">
                    <span>{formatBytes(item.file_size)}</span>
                    {item.type === 'audio' && <span>Audio</span>}
                    <span>{formatDate(item.created_at)}</span>
                  </div>

                  <div className="lembar-kaki">
                    {/* Dari unduhan langsung ke Partitur. Sebelumnya video yang
                        sudah ada di komputer tetap harus dicari ulang lewat
                        halaman Cari video. Diminta pemiliknya. */}
                    {item.video_id && item.type !== 'audio' ? (
                      <button className="btn-garis" onClick={() => kePartitur(item)}
                              disabled={mengirim === item.video_id}
                              title={item.ada_partitur ? t('unduhan.sudah_proyek') : t('unduhan.buat_klip')}>
                        {mengirim === item.video_id
                          ? <Loader2 size={13} className="animate-spin" />
                          : item.ada_partitur ? <Sparkles size={13} /> : <Scissors size={13} />}
                        {item.ada_partitur ? t('unduhan.buka_partitur') : t('unduhan.ke_partitur')}
                        <ArrowRight size={13} />
                      </button>
                    ) : <span style={{ flex: 1 }} />}
                    <button className="ikon-btn" onClick={() => handleProxyDownload(item.file_name)}
                            title={t('unduhan.simpan')} aria-label={t('unduhan.simpan')}>
                      <Download size={15} />
                    </button>
                    <button className="ikon-btn is-bahaya" onClick={() => handleDelete(item.file_name)}
                            disabled={deleting === item.file_name}
                            title={t('umum.hapus')} aria-label={t('umum.hapus')}>
                      {deleting === item.file_name
                        ? <Loader2 size={15} className="animate-spin" /> : <Trash2 size={15} />}
                    </button>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {/* Preview Modal */}
      {previewItem && <VideoPlayerModal item={previewItem} onClose={() => setPreviewItem(null)} />}
    </div>
  );
}
