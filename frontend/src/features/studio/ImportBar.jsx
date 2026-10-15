import React, { useEffect, useRef, useState } from 'react';
import { AlertTriangle, ChevronDown, FolderOpen, Link2, Loader2, Smartphone, Sparkles, Upload, X } from 'lucide-react';
import { apiGet, apiPost, apiUnggah } from '../../lib/api';
import FolderPicker from '../../components/FolderPicker';
import { useT } from '../../lib/i18n';

/**
 * Memasukkan video baru ke Partitur, dari tautan atau dari komputer sendiri.
 *
 * Dua tombol kecil di kepala halaman, bukan kartu selebar layar (diminta
 * pemilik 15 Oktober 2026: "link ini dan upload berkas diberikan button kecil
 * saja agar lebih rapih"). Tautan YouTube sudah bisa ditempel di kotak cari
 * Beranda, jadi kotak tautan di sini menerima video dari situs MANA PUN yang
 * dikenal yt-dlp: TikTok, Instagram, X, Facebook, Vimeo, Twitch, dan YouTube.
 */
export default function ImportBar({ onDone }) {
  const t = useT();
  const [tautan, setTautan] = useState('');
  // Panjang klip milik VIDEO INI, bukan milik aplikasi. Nilai di Pengaturan
  // hanya jadi titik awalnya.
  const [sibuk, setSibuk] = useState('');
  const [galat, setGalat] = useState(null);
  const [kabar, setKabar] = useState(null);
  const berkasRef = useRef(null);
  // Jalur audio video yang ditempel. Hanya ditampilkan bila lebih dari satu:
  // video bersulih suara (MrBeast punya tiga belas) — dan tanpa pilihan,
  // yang terunduh pernah suara Indonesia hasil sulih, bukan suara aslinya.
  const [jalur, setJalur] = useState([]);
  const [audio, setAudio] = useState('');       // '' = suara asli
  const [periksa, setPeriksa] = useState(false);
  // Panel yang terbuka: 'tautan' | 'berkas' | null.
  const [panel, setPanel] = useState(null);
  const wadahRef = useRef(null);
  useEffect(() => {
    if (!panel) return undefined;
    const tutup = (e) => {
      if (!wadahRef.current?.contains(e.target) && !sibuk) setPanel(null);
    };
    const esc = (e) => { if (e.key === 'Escape' && !sibuk) setPanel(null); };
    document.addEventListener('mousedown', tutup);
    document.addEventListener('keydown', esc);
    return () => {
      document.removeEventListener('mousedown', tutup);
      document.removeEventListener('keydown', esc);
    };
  }, [panel, sibuk]);

  useEffect(() => {
    const nilai = tautan.trim();
    setJalur([]);
    setAudio('');
    if (!/(youtu\.?be|^[\w-]{11}$)/.test(nilai)) return undefined;
    let batal = false;
    const jeda = setTimeout(() => {
      setPeriksa(true);
      apiGet(`/video-info?url=${encodeURIComponent(nilai)}`)
        .then((info) => { if (!batal) setJalur(info?.audio_tracks ?? []); })
        .catch(() => { /* tanpa daftar jalur: tetap suara asli */ })
        .finally(() => { if (!batal) setPeriksa(false); });
    }, 700);
    return () => { batal = true; clearTimeout(jeda); };
  }, [tautan]);

  const mulaiKlip = async (videoId, judul, audioLang = null) => {
    const res = await apiPost('/auto-clip', {
      video_id: videoId,
      audio_lang: audioLang,
      max_clips: Number(localStorage.getItem('omniclip_max_clips') || 0),
      whisper_model: localStorage.getItem('omniclip_whisper_model') || 'base',
      gemini_model: localStorage.getItem('omniclip_gemini_model') || null,
    });
    setKabar(res.cached
      ? t('impor.sudah', { judul })
      : t('impor.antre', { judul }));
    onDone?.();
  };

  const kirimTautan = async (e) => {
    e.preventDefault();
    const nilai = tautan.trim();
    if (!nilai) return;
    setSibuk('tautan'); setGalat(null); setKabar(null);
    try {
      // Tautan situs lain dicatat dulu sebagai video impor (judulnya dibaca
      // dari situsnya); tautan YouTube langsung diteruskan seperti biasa.
      const r = await apiPost('/impor/tautan', { url: nilai }, { timeout: 60000 });
      await mulaiKlip(r.video_id, r.youtube ? nilai.slice(0, 40) : r.title,
        r.youtube ? (audio || null) : null);
      setTautan('');
    } catch (err) {
      setGalat(err.message);
    } finally {
      setSibuk('');
    }
  };

  // Video di komputer ini: dibaca DI TEMPATNYA, tidak disalin. Unggah lewat
  // peramban (di bawah) hanya untuk perangkat lain — peramban tidak boleh
  // memberi tahu jalur berkas, jadi di sana berkasnya harus dikirim utuh.
  const [jelajah, setJelajah] = useState(false);
  const pakaiJalur = async (jalur) => {
    setJelajah(false);
    setPanel('berkas');
    try {
      const folder = jalur.replace(/[\\/][^\\/]*$/, '');
      localStorage.setItem('omniclip.folderImpor', folder);
    } catch { /* mode privat */ }
    setSibuk('berkas'); setGalat(null); setKabar(null);
    try {
      const hasil = await apiPost('/impor/jalur', { jalur });
      await mulaiKlip(hasil.video_id, hasil.title);
    } catch (err) {
      setGalat(err.message);
    } finally {
      setSibuk('');
    }
  };

  const kirimBerkas = async (e) => {
    const f = e.target.files?.[0];
    e.target.value = '';           // supaya berkas yang sama bisa dipilih lagi
    if (!f) return;
    setSibuk('berkas'); setGalat(null); setKabar(null);
    try {
      const data = new FormData();
      data.append('berkas', f);
      const mb = Math.round(f.size / 1e6);
      setKabar(t('impor.mengirim', { nama: f.name, mb, n: 0 }));
      const hasil = await apiUnggah('/impor/berkas', data, (frac) => {
        setKabar(frac < 1
          ? t('impor.mengirim', { nama: f.name, mb, n: Math.round(frac * 100) })
          : t('impor.terkirim'));
      });
      setKabar(null);
      await mulaiKlip(hasil.video_id, hasil.title);
    } catch (err) {
      setGalat(err.message);
    } finally {
      setSibuk('');
    }
  };

  // Kabar "masuk antrean" cukup terbaca sebentar; panelnya lalu menutup sendiri.
  useEffect(() => {
    if (!kabar || sibuk || galat) return undefined;
    const j = setTimeout(() => { setPanel(null); setKabar(null); }, 3500);
    return () => clearTimeout(j);
  }, [kabar, sibuk, galat]);

  const tombol = (nama, Ikon, label, judul) => (
    <button type="button" className={`btn-secondary${panel === nama ? ' is-on' : ''}`}
            aria-expanded={panel === nama} title={judul}
            onClick={() => { setGalat(null); setKabar(null); setPanel(panel === nama ? null : nama); }}
            style={{ fontSize: '0.8rem', whiteSpace: 'nowrap' }}>
      {sibuk === nama ? <Loader2 size={14} className="animate-spin" /> : <Ikon size={14} />}
      {label}
      <ChevronDown size={13} style={{ opacity: 0.6, marginLeft: '-2px' }} />
    </button>
  );

  const kabarGalat = (
    <>
      {sibuk === 'berkas' && (
        <p className="impor-kabar">{t('impor.menyalin')}</p>
      )}
      {kabar && <p className="impor-kabar" style={{ color: 'var(--accent-cyan)' }}>{kabar}</p>}
      {galat && (
        <p className="impor-kabar" style={{ color: 'var(--danger)', display: 'flex', gap: '7px' }}>
          <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: '1px' }} /> {galat}
        </p>
      )}
    </>
  );

  return (
    <div ref={wadahRef} className="impor-ringkas">
      {tombol('tautan', Link2, t('impor.tempel'), t('impor.tempel_judul'))}
      {tombol('berkas', Upload, t('impor.dari_komputer'), t('impor.dari_komputer_judul'))}
      <input ref={berkasRef} type="file" accept="video/*" hidden onChange={kirimBerkas} />

      {panel === 'tautan' && (
        <div className="impor-panel" role="dialog" aria-label={t('impor.tempel')}>
          <div className="impor-panel-kepala">
            <strong>{t('impor.tempel')}</strong>
            <button type="button" className="ikon-tutup" aria-label={t('umum.tutup')}
                    onClick={() => setPanel(null)} disabled={!!sibuk}><X size={15} /></button>
          </div>
          <p className="impor-ket">{t('impor.ket_tautan')}</p>
          <form onSubmit={kirimTautan} style={{ display: 'flex', gap: '8px' }}>
            <input autoFocus value={tautan} onChange={(e) => setTautan(e.target.value)}
                   placeholder="https://…" className="impor-input" />
            <button type="submit" className="btn-primary" disabled={!tautan.trim() || !!sibuk}
                    style={{ fontSize: '0.8rem', whiteSpace: 'nowrap' }}>
              {sibuk === 'tautan' ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
              {t('tonton.potong')}
            </button>
          </form>
          {(jalur.length > 1 || periksa) && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '9px',
                          fontSize: '0.78rem', color: 'var(--text-secondary)', flexWrap: 'wrap' }}>
              {periksa ? (
                <><Loader2 size={13} className="animate-spin" /> {t('impor.periksa_audio')}</>
              ) : (
                <>
                  <span>{t('impor.n_jalur', { n: jalur.length })}</span>
                  <select value={audio} onChange={(e) => setAudio(e.target.value)}
                          style={{ padding: '5px 8px', fontSize: '0.78rem', borderRadius: '6px',
                                   background: 'var(--plate-3, transparent)', color: 'var(--ink)',
                                   border: '1px solid var(--border-color)' }}>
                    {jalur.map((j) => (
                      <option key={j.lang} value={j.asli ? '' : j.lang}>
                        {j.nama}{j.asli ? t('impor.suara_asli') : ''}
                      </option>
                    ))}
                  </select>
                </>
              )}
            </div>
          )}
          {kabarGalat}
        </div>
      )}

      {panel === 'berkas' && (
        <div className="impor-panel impor-menu" role="menu">
          <button type="button" role="menuitem" disabled={!!sibuk} onClick={() => setJelajah(true)}>
            <FolderOpen size={16} />
            <span><b>{t('impor.pilih_folder')}</b><small>{t('impor.dari_komputer_judul')}</small></span>
          </button>
          <button type="button" role="menuitem" disabled={!!sibuk} onClick={() => berkasRef.current?.click()}>
            <Smartphone size={16} />
            <span><b>{t('impor.kirim_perangkat')}</b><small>{t('impor.dari_hp_ket')}</small></span>
          </button>
          {kabarGalat}
        </div>
      )}

      {jelajah && (
        <FolderPicker modeVideo judul={t('impor.pilih_video')}
                      awal={(() => { try { return localStorage.getItem('omniclip.folderImpor') || ''; } catch { return ''; } })()}
                      onTutup={() => setJelajah(false)}
                      onPilih={pakaiJalur} />
      )}
    </div>
  );
}
