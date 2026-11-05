/**
 * Daftar proyek Montase (/montase, JOB-4 M1.5).
 *
 * Kartu tiap proyek: sampul (bahan gambar pertama di linimasa), nama, ukuran
 * kanvas, durasi, dan kapan terakhir diubah. "Proyek baru" memilih ukuran
 * kanvas lewat preset (bagian M1.5) atau ukuran sendiri, plus fps.
 *
 * Halaman ini juga bekerja di HP (T-6): yang butuh layar lebar hanya editornya.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  CircleHelp, Clapperboard, Copy, Film, Loader2, Plus, RefreshCw, Trash2, X,
} from 'lucide-react';
import { lokal, useT } from '../../lib/i18n';
import { IsiBantuan } from './BantuanMontase.jsx';
import { formatTime } from '../../utils/timeFormat';
import {
  alamatBahan, ambilToken, buatProyek, daftarProyek, gandakanProyek, hapusProyek,
} from './api.js';

export const PRESET = [
  { id: 'shorts', kunci: 'montase.preset.shorts', lebar: 1080, tinggi: 1920, rasio: '9:16' },
  { id: 'youtube', kunci: 'montase.preset.youtube', lebar: 1920, tinggi: 1080, rasio: '16:9' },
  { id: 'persegi', kunci: 'montase.preset.persegi', lebar: 1080, tinggi: 1080, rasio: '1:1' },
  { id: 'potret', kunci: 'montase.preset.potret', lebar: 1080, tinggi: 1350, rasio: '4:5' },
];
const FPS = [24, 25, 30, 60];

function rasioDari(lebar, tinggi) {
  const p = PRESET.find((x) => x.lebar === lebar && x.tinggi === tinggi);
  return p ? p.rasio : `${lebar}×${tinggi}`;
}

function FormProyekBaru({ onBatal, onJadi }) {
  const t = useT();
  const [nama, setNama] = useState('');
  const [preset, setPreset] = useState('shorts');
  const [lebar, setLebar] = useState(1080);
  const [tinggi, setTinggi] = useState(1920);
  const [fps, setFps] = useState(30);
  const [sibuk, setSibuk] = useState(false);
  const [galat, setGalat] = useState(null);

  const kirim = async (e) => {
    e.preventDefault();
    setSibuk(true);
    setGalat(null);
    try {
      const isi = { nama: nama.trim() || t('montase.home.tanpa_judul'), fps };
      if (preset === 'sendiri') Object.assign(isi, { lebar: Number(lebar), tinggi: Number(tinggi) });
      else isi.preset = preset;
      onJadi(await buatProyek(isi));
    } catch (err) {
      setGalat(err.message);
      setSibuk(false);
    }
  };

  return (
    <form className="plate montase-baru" onSubmit={kirim}>
      <div className="plate-head">
        <h2>{t('montase.home.baru')}</h2>
        <button type="button" className="btn-secondary montase-ikon" onClick={onBatal}
                aria-label={t('umum.tutup')}
        >
          <X size={14} />
        </button>
      </div>
      <div className="panel-isi">
        <label className="montase-kolom">
          <span>{t('montase.home.nama')}</span>
          <input value={nama} maxLength={120} autoFocus placeholder={t('montase.home.tanpa_judul')}
                 onChange={(e) => setNama(e.target.value)} />
        </label>
        <div className="montase-kolom">
          <span>{t('montase.home.ukuran')}</span>
          <div className="montase-preset" role="radiogroup">
            {[...PRESET, { id: 'sendiri', kunci: 'montase.preset.sendiri', rasio: '' }].map((p) => (
              <button key={p.id} type="button" role="radio" aria-checked={preset === p.id}
                      className={`montase-preset-pil ${preset === p.id ? 'aktif' : ''}`}
                      onClick={() => setPreset(p.id)}
              >
                {p.rasio && (
                  <i className="montase-preset-bentuk"
                     style={{ aspectRatio: `${p.lebar} / ${p.tinggi}` }} aria-hidden />
                )}
                <b>{t(p.kunci)}</b>
                {p.lebar && <small>{p.lebar}×{p.tinggi}</small>}
              </button>
            ))}
          </div>
        </div>
        {preset === 'sendiri' && (
          <div className="montase-baris-isian">
            <label className="montase-kolom">
              <span>{t('montase.home.lebar')}</span>
              <input type="number" min={16} max={7680} step={2} value={lebar}
                     onChange={(e) => setLebar(e.target.value)} />
            </label>
            <label className="montase-kolom">
              <span>{t('montase.home.tinggi')}</span>
              <input type="number" min={16} max={7680} step={2} value={tinggi}
                     onChange={(e) => setTinggi(e.target.value)} />
            </label>
          </div>
        )}
        <label className="montase-kolom">
          <span>{t('montase.home.fps')}</span>
          <select value={fps} onChange={(e) => setFps(Number(e.target.value))}>
            {FPS.map((f) => <option key={f} value={f}>{f} fps</option>)}
          </select>
        </label>
        {galat && <p className="montase-galat" role="alert">{galat}</p>}
        <button type="submit" className="btn-primary" disabled={sibuk}>
          {sibuk ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
          {t('montase.home.buat')}
        </button>
      </div>
    </form>
  );
}

function KartuProyek({ proyek, token, onBuka, onGandakan, onHapus }) {
  const t = useT();
  const k = proyek.kanvas ?? {};
  const diubah = new Date(proyek.updated_at * 1000).toLocaleDateString(lokal(),
    { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  return (
    <article className="montase-kartu">
      <button type="button" className="montase-kartu-sampul" onClick={onBuka}
              style={{ aspectRatio: `${k.lebar || 9} / ${k.tinggi || 16}` }}
              aria-label={t('montase.home.buka', { nama: proyek.nama })}
      >
        {proyek.sampul && token
          ? <img src={alamatBahan(token, proyek.sampul, { turunan: 'sampul' })} alt="" loading="lazy" />
          : <Film size={28} aria-hidden />}
        <span className="montase-kartu-durasi">{formatTime(proyek.durasi_detik || 0)}</span>
      </button>
      <div className="montase-kartu-isi">
        <h3 title={proyek.nama}>{proyek.nama}</h3>
        <p>{rasioDari(k.lebar, k.tinggi)} · {k.fps} fps · {t('montase.home.diubah', { waktu: diubah })}</p>
        <div className="montase-kartu-aksi">
          <button type="button" className="btn-secondary" onClick={onBuka}>
            <Clapperboard size={13} />{t('montase.home.sunting')}
          </button>
          <button type="button" className="btn-secondary montase-ikon" onClick={onGandakan}
                  title={t('montase.home.gandakan')} aria-label={t('montase.home.gandakan')}
          >
            <Copy size={13} />
          </button>
          <button type="button" className="btn-secondary montase-ikon" onClick={onHapus}
                  title={t('montase.home.hapus')} aria-label={t('montase.home.hapus')}
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>
    </article>
  );
}

export default function MontaseHome() {
  const t = useT();
  const navigate = useNavigate();
  const [proyek, setProyek] = useState(null);
  const [token, setToken] = useState(null);
  const [galat, setGalat] = useState(null);
  const [formBaru, setFormBaru] = useState(false);
  const [bantuan, setBantuan] = useState(false);

  const muat = useCallback(() => {
    setGalat(null);
    daftarProyek().then(setProyek).catch((e) => { setGalat(e.message); setProyek([]); });
    ambilToken().then(setToken).catch(() => {});
  }, []);
  useEffect(() => { muat(); }, [muat]);

  const hapus = async (p) => {
    // eslint-disable-next-line no-alert
    if (!window.confirm(t('montase.home.hapus_tanya', { nama: p.nama }))) return;
    try { await hapusProyek(p.id); muat(); } catch (e) { setGalat(e.message); }
  };
  const gandakan = async (p) => {
    try { await gandakanProyek(p.id); muat(); } catch (e) { setGalat(e.message); }
  };

  return (
    <div className="page rak montase-home" style={{ maxWidth: '1280px' }}>
      <header className="rak-kepala">
        <div className="rak-kepala-teks">
          <h1 className="work-title rak-judul">
            {t('montase.home.judul')}
          </h1>
          <p className="rak-sub">{t('montase.home.sub')}</p>
        </div>
        <div className="rak-aksi">
          <button type="button" className="btn-secondary" onClick={() => setBantuan((v) => !v)}
                  aria-expanded={bantuan}
          >
            <CircleHelp size={14} />{t('montase.bantuan.tombol')}
          </button>
          <button type="button" className="btn-secondary" onClick={muat}>
            <RefreshCw size={14} />{t('umum.muat_ulang')}
          </button>
          <button type="button" className="btn-primary" onClick={() => setFormBaru(true)}>
            <Plus size={14} />{t('montase.home.baru')}
          </button>
        </div>
      </header>

      {galat && <p className="montase-galat" role="alert">{galat}</p>}
      {bantuan && (
        <section className="plate montase-bantuan" aria-label={t('montase.bantuan.judul')}>
          <h2>{t('montase.bantuan.judul')}</h2>
          <IsiBantuan />
        </section>
      )}
      {formBaru && (
        <FormProyekBaru onBatal={() => setFormBaru(false)}
                        onJadi={(p) => navigate(`/montase/${p.id}`)} />
      )}

      {proyek === null && <Loader2 size={18} className="animate-spin" />}
      {proyek?.length === 0 && !formBaru && (
        <div className="plate montase-kosong">
          <Clapperboard size={30} aria-hidden />
          <h2>{t('montase.home.kosong')}</h2>
          <p>{t('montase.home.kosong_ket')}</p>
          <button type="button" className="btn-primary" onClick={() => setFormBaru(true)}>
            <Plus size={14} />{t('montase.home.baru')}
          </button>
        </div>
      )}
      {proyek?.length > 0 && (
        <div className="montase-kisi">
          {proyek.map((p) => (
            <KartuProyek key={p.id} proyek={p} token={token}
                         onBuka={() => navigate(`/montase/${p.id}`)}
                         onGandakan={() => gandakan(p)} onHapus={() => hapus(p)} />
          ))}
        </div>
      )}
    </div>
  );
}
