import React, { useEffect, useState } from 'react';
import { namaMesin as namaMesinUmum } from '../../lib/mesin';
import { Loader2, RotateCcw, Sparkles, X, Cpu } from 'lucide-react';
import { apiGet, apiPost } from '../../lib/api';
import BilahProses from '../../components/BilahProses';
import { useT } from '../../lib/i18n';

const kecil = { fontSize: '0.72rem', color: 'var(--text-secondary)', lineHeight: 1.5 };
const label = { fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-secondary)' };
const kontrol = {
  padding: '6px 8px', fontSize: '0.78rem', fontFamily: 'inherit',
  borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)',
  background: 'var(--bg-card)', color: 'var(--text-primary)',
};

function namaMesin(engine, model, t) {
  if (!engine || engine === 'heuristic') return t('ulang.mesin_lokal_heuristik');
  return namaMesinUmum(engine, model);
}

/**
 * Mencari ulang rekomendasi klip, hook, dan judul untuk video yang sudah ada.
 *
 * Dulu beralih dari mesin lokal ke Gemini — atau sekadar mencoba model lain —
 * berarti menghapus proyek dan mengunduh videonya lagi. Di sini yang diulang
 * hanya pemilihan momen: video, transkrip, dan penanda narasumber dipakai apa
 * adanya, dan susunan klip sebelumnya bisa dikembalikan.
 */
export default function CariUlangDialog({ videoId, data, dirty, onSimpanDulu, onSelesai, onTutup }) {
  const t = useT();
  const [mesin, setMesin] = useState('gemini');
  const [model, setModel] = useState(() => {
    try { return localStorage.getItem('omniclip_gemini_model') || ''; } catch { return ''; }
  });
  const [daftarModel, setDaftarModel] = useState([]);
  const [infoModel, setInfoModel] = useState({ terkuat: null, habisHarian: [] });
  const [adaKunci, setAdaKunci] = useState(null);
  const [jumlah, setJumlah] = useState(0);
  const [sibuk, setSibuk] = useState(false);
  const [pesan, setPesan] = useState('');
  const [galat, setGalat] = useState(null);
  const [job, setJob] = useState(null);

  useEffect(() => {
    // AI tersedia bila ADA koneksi aktif (Gemini, Claude, AI lokal, ...),
    // bukan hanya kunci Gemini (17 Oktober 2026).
    apiGet('/settings/koneksi-ai').then((r) => {
      const ada = (r.koneksi || []).some((k) => k.aktif);
      setAdaKunci(ada);
      if (!ada) setMesin('heuristik');
    }).catch(() => setAdaKunci(null));
    apiGet('/settings/models').then((r) => {
      // Model yang kunci ini tidak punya aksesnya dibuang dari daftar, bukan
      // ditampilkan sebagai pilihan yang mati.
      const tak = new Set(r.tanpa_kuota || []);
      const daftar = (r.cocok?.length ? r.cocok : (r.available || []))
        .filter((m) => !tak.has(m));
      setDaftarModel(daftar);
      // Pilihan lama yang tidak cocok lagi (atau sudah tidak ada) kembali ke
      // Otomatis, bukan diam-diam dikirim ke server.
      setModel((m) => (m && !daftar.includes(m) ? '' : m));
      setInfoModel({ terkuat: r.terkuat || null, habisHarian: r.habis_harian || [] });
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!sibuk) return undefined;
    const tahan = (e) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', tahan);
    return () => window.removeEventListener('beforeunload', tahan);
  }, [sibuk]);

  const pantau = async (jobId) => {
    for (;;) {
      // eslint-disable-next-line no-await-in-loop
      const job = await apiGet(`/jobs/${jobId}`);
      setJob(job);
      if (['done', 'failed', 'cancelled'].includes(job.status)) return job;
      // Pesan akhir ("… klip siap ditinjau") baru ditampilkan setelah daftar
      // klip dimuat ulang — sebelum itu, Studio masih memperlihatkan yang lama.
      if (job.message) setPesan(job.message);
      // eslint-disable-next-line no-await-in-loop
      await new Promise((r) => setTimeout(r, 1200));
    }
  };

  const muatUlang = async () => {
    const segar = await apiGet(`/projects/${videoId}`);
    onSelesai(segar);
  };

  const mulai = async () => {
    setSibuk(true); setGalat(null); setPesan(t('sutradara.memulai')); setJob(null);
    try {
      // Suntingan yang belum tersimpan disimpan dulu, supaya "Kembalikan
      // sebelumnya" mengembalikan susunan yang benar-benar terakhir dilihat.
      if (dirty) {
        setPesan(t('ulang.menyimpan'));
        await onSimpanDulu();
      }
      const { job_id: jobId } = await apiPost(`/projects/${videoId}/cari-ulang`, {
        mesin, gemini_model: mesin === 'gemini' && model ? model : null,
        max_clips: Number(jumlah) || 0,
      });
      const job = await pantau(jobId);
      if (job.status !== 'done') throw new Error(job.error || t('ulang.gagal'));
      setPesan(t('ulang.memuat'));
      await muatUlang();
      setPesan(t('ulang.selesai', { pesan: job.message || t('ulang.selesai_bawaan') }));
    } catch (e) {
      setGalat(e.message);
    } finally {
      setSibuk(false);
    }
  };

  const pulihkan = async () => {
    setSibuk(true); setGalat(null); setPesan(t('ulang.mengembalikan'));
    try {
      await apiPost(`/projects/${videoId}/pulihkan`, {});
      await muatUlang();
      setPesan(t('ulang.dikembalikan'));
    } catch (e) {
      setGalat(e.message);
    } finally {
      setSibuk(false);
    }
  };

  const sebelumnya = data?.sebelumnya;
  const pilihan = (nilai, ikon, judul, ket, mati) => (
    <button type="button" onClick={() => !mati && setMesin(nilai)} disabled={sibuk || mati}
            style={{
              display: 'flex', gap: '9px', alignItems: 'flex-start', textAlign: 'left',
              padding: '10px 11px', borderRadius: 'var(--radius-md)', cursor: mati ? 'not-allowed' : 'pointer',
              fontFamily: 'inherit', color: 'var(--text-primary)', opacity: mati ? 0.5 : 1,
              background: mesin === nilai ? 'var(--hl-wash)' : 'transparent',
              border: mesin === nilai ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
            }}>
      {ikon}
      <span>
        <b style={{ fontSize: '0.82rem', display: 'block' }}>{judul}</b>
        <span style={kecil}>{ket}</span>
      </span>
    </button>
  );

  return (
    <div role="dialog" aria-modal="true" aria-label={t('ulang.judul')}
         onClick={(e) => { if (e.target === e.currentTarget && !sibuk) onTutup(); }}
         style={{
           position: 'fixed', inset: 0, zIndex: 80, background: 'rgba(0,0,0,0.55)',
           display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '16px',
         }}>
      <div style={{
        width: 'min(480px, 100%)', maxHeight: '90vh', overflowY: 'auto',
        background: 'var(--bg-card)', border: '1px solid var(--border-color)',
        borderRadius: 'var(--radius-lg, 12px)', padding: '18px', display: 'grid', gap: '13px',
        boxShadow: '0 20px 60px rgba(0,0,0,0.45)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Sparkles size={17} style={{ color: 'var(--accent-cyan)' }} />
          <b style={{ fontSize: '0.98rem' }}>{t('ulang.judul')}</b>
          <button onClick={onTutup} disabled={sibuk} aria-label={t('umum.tutup')}
                  style={{ marginLeft: 'auto', background: 'none', border: 'none',
                           cursor: sibuk ? 'default' : 'pointer', color: 'var(--text-secondary)' }}>
            <X size={18} />
          </button>
        </div>

        <p style={{ ...kecil, margin: 0 }}>
          {t('ulang.sekarang_a')} <b>{t('ulang.n_klip', { n: (data?.clips || []).length })}</b> {t('ulang.dari')}{' '}
          <b>{namaMesin(data?.engine, data?.model, t)}</b>{t('ulang.sekarang_b')}
        </p>

        <div style={{ display: 'grid', gap: '7px' }}>
          {pilihan('gemini', <Sparkles size={16} style={{ color: 'var(--accent-cyan)', marginTop: 2 }} />,
                   t('ulang.ai'), adaKunci === false
                     ? t('ulang.butuh_kunci')
                     : t('ulang.gemini_ket'),
                   adaKunci === false)}
          {pilihan('heuristik', <Cpu size={16} style={{ color: 'var(--text-secondary)', marginTop: 2 }} />,
                   t('sutradara.lokal'), t('ulang.lokal_ket'))}
        </div>

        {mesin === 'gemini' && daftarModel.length > 0 && (
          <label style={label}>{t('ulang.model')}
            <select value={model} onChange={(e) => setModel(e.target.value)} disabled={sibuk}
                    style={{ ...kontrol, width: '100%', marginTop: '5px' }}>
              <option value="">
                {t('ulang.otomatis')}{infoModel.terkuat ? t('ulang.mencoba', { model: infoModel.terkuat }) : ''}
              </option>
              {daftarModel.map((m) => (
                <option key={m} value={m}>
                  {m}{infoModel.habisHarian.includes(m) ? t('ulang.jatah_habis') : ''}
                </option>
              ))}
            </select>
          </label>
        )}

        <label style={label}>{t('ulang.jumlah')}
          <select value={jumlah} onChange={(e) => setJumlah(e.target.value)} disabled={sibuk}
                  style={{ ...kontrol, width: '100%', marginTop: '5px' }}>
            <option value={0}>{t('ulang.jumlah_otomatis')}</option>
            {[5, 8, 10, 15, 20, 30].map((n) => <option key={n} value={n}>{t('ulang.n_klip', { n })}</option>)}
          </select>
        </label>

        <p style={{ ...kecil, margin: 0, padding: '8px 10px', borderRadius: 'var(--radius-sm)',
                    background: 'var(--bg-glass)', border: '1px solid var(--border-color)' }}>
          {t('ulang.diganti')}{dirty ? t('ulang.diganti_simpan') : ''}{t('ulang.diganti_b')}
        </p>

        {sibuk && job && <BilahProses job={job} />}

        {(pesan || galat) && !(sibuk && job) && (
          <div style={{ display: 'flex', gap: '7px', alignItems: 'center', fontSize: '0.78rem',
                        color: galat ? 'var(--danger)' : 'var(--text-primary)' }}>
            {sibuk && <Loader2 size={14} className="animate-spin" />}
            {galat || pesan}
          </div>
        )}

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <button className="btn-primary" onClick={mulai} disabled={sibuk}
                  style={{ display: 'inline-flex', gap: '6px', alignItems: 'center' }}>
            {sibuk ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
            {sibuk ? t('ulang.mencari') : t('ulang.cari_ulang')}
          </button>
          {sebelumnya && (
            <button className="btn-secondary" onClick={pulihkan} disabled={sibuk}
                    title={t('ulang.kembali_judul', { n: sebelumnya.clip_count, mesin: namaMesin(sebelumnya.engine, sebelumnya.model, t) })}
                    style={{ display: 'inline-flex', gap: '6px', alignItems: 'center' }}>
              <RotateCcw size={14} />
              {t('ulang.kembalikan', { n: sebelumnya.clip_count })}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
