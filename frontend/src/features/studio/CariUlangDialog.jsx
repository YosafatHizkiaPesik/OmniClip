import React, { useEffect, useState } from 'react';
import { Loader2, RotateCcw, Sparkles, X, Cpu } from 'lucide-react';
import { apiGet, apiPost } from '../../lib/api';
import BilahProses from '../../components/BilahProses';

const kecil = { fontSize: '0.72rem', color: 'var(--text-secondary)', lineHeight: 1.5 };
const label = { fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-secondary)' };
const kontrol = {
  padding: '6px 8px', fontSize: '0.78rem', fontFamily: 'inherit',
  borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)',
  background: 'var(--bg-card)', color: 'var(--text-primary)',
};

function namaMesin(engine, model) {
  if (engine === 'gemini') return `Gemini${model ? ` (${model})` : ''}`;
  return 'mesin lokal (heuristik)';
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
  const [mesin, setMesin] = useState('gemini');
  const [model, setModel] = useState(() => {
    try { return localStorage.getItem('omniclip_gemini_model') || ''; } catch { return ''; }
  });
  const [daftarModel, setDaftarModel] = useState([]);
  const [infoModel, setInfoModel] = useState({ terkuat: null, tanpaKuota: [] });
  const [adaKunci, setAdaKunci] = useState(null);
  const [jumlah, setJumlah] = useState(0);
  const [sibuk, setSibuk] = useState(false);
  const [pesan, setPesan] = useState('');
  const [galat, setGalat] = useState(null);
  const [job, setJob] = useState(null);

  useEffect(() => {
    apiGet('/settings/models').then((r) => {
      setAdaKunci(r.configured !== false);
      const daftar = r.cocok?.length ? r.cocok : (r.available || []);
      setDaftarModel(daftar);
      // Pilihan lama yang tidak cocok lagi (atau sudah tidak ada) kembali ke
      // Otomatis, bukan diam-diam dikirim ke server.
      setModel((m) => (m && !daftar.includes(m) ? '' : m));
      setInfoModel({ terkuat: r.terkuat || null, tanpaKuota: r.tanpa_kuota || [] });
      if (r.configured === false) setMesin('heuristik');
    }).catch(() => setAdaKunci(null));
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
    setSibuk(true); setGalat(null); setPesan('Memulai…'); setJob(null);
    try {
      // Suntingan yang belum tersimpan disimpan dulu, supaya "Kembalikan
      // sebelumnya" mengembalikan susunan yang benar-benar terakhir dilihat.
      if (dirty) {
        setPesan('Menyimpan suntingan sekarang…');
        await onSimpanDulu();
      }
      const { job_id: jobId } = await apiPost(`/projects/${videoId}/cari-ulang`, {
        mesin, gemini_model: mesin === 'gemini' && model ? model : null,
        max_clips: Number(jumlah) || 0,
      });
      const job = await pantau(jobId);
      if (job.status !== 'done') throw new Error(job.error || 'Pencarian ulang gagal.');
      setPesan('Memuat klip baru…');
      await muatUlang();
      setPesan(`${job.message || 'Selesai.'} Daftar klip sudah diperbarui.`);
    } catch (e) {
      setGalat(e.message);
    } finally {
      setSibuk(false);
    }
  };

  const pulihkan = async () => {
    setSibuk(true); setGalat(null); setPesan('Mengembalikan susunan sebelumnya…');
    try {
      await apiPost(`/projects/${videoId}/pulihkan`, {});
      await muatUlang();
      setPesan('Susunan sebelumnya dikembalikan.');
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
    <div role="dialog" aria-modal="true" aria-label="Cari ulang klip"
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
          <b style={{ fontSize: '0.98rem' }}>Cari ulang klip</b>
          <button onClick={onTutup} disabled={sibuk} aria-label="Tutup"
                  style={{ marginLeft: 'auto', background: 'none', border: 'none',
                           cursor: sibuk ? 'default' : 'pointer', color: 'var(--text-secondary)' }}>
            <X size={18} />
          </button>
        </div>

        <p style={{ ...kecil, margin: 0 }}>
          Klip sekarang: <b>{(data?.clips || []).length} klip</b> dari{' '}
          <b>{namaMesin(data?.engine, data?.model)}</b>. Pencarian ulang memilih
          momen, hook, dan judul yang baru. Video dan transkrip tidak diunduh
          ulang, dan penanda narasumber tetap sama.
        </p>

        <div style={{ display: 'grid', gap: '7px' }}>
          {pilihan('gemini', <Sparkles size={16} style={{ color: 'var(--accent-cyan)', marginTop: 2 }} />,
                   'Gemini', adaKunci === false
                     ? 'Butuh kunci API — isi di Pengaturan → Model AI.'
                     : 'Membaca seluruh transkrip dan menilai momen seperti penyunting.',
                   adaKunci === false)}
          {pilihan('heuristik', <Cpu size={16} style={{ color: 'var(--text-secondary)', marginTop: 2 }} />,
                   'Mesin lokal', 'Tanpa internet dan tanpa kuota, dari pola bicara dan energi suara.')}
        </div>

        {mesin === 'gemini' && daftarModel.length > 0 && (
          <label style={label}>Model
            <select value={model} onChange={(e) => setModel(e.target.value)} disabled={sibuk}
                    style={{ ...kontrol, width: '100%', marginTop: '5px' }}>
              <option value="">
                Otomatis — terkuat yang tersedia{infoModel.terkuat ? ` (${infoModel.terkuat})` : ''}
              </option>
              {daftarModel.map((m) => (
                <option key={m} value={m} disabled={infoModel.tanpaKuota.includes(m)}>
                  {m}{infoModel.tanpaKuota.includes(m) ? ' — tidak tersedia untuk kunci ini' : ''}
                </option>
              ))}
            </select>
          </label>
        )}

        <label style={label}>Jumlah klip
          <select value={jumlah} onChange={(e) => setJumlah(e.target.value)} disabled={sibuk}
                  style={{ ...kontrol, width: '100%', marginTop: '5px' }}>
            <option value={0}>Otomatis, sesuai panjang video</option>
            {[5, 8, 10, 15, 20, 30].map((n) => <option key={n} value={n}>{n} klip</option>)}
          </select>
        </label>

        <p style={{ ...kecil, margin: 0, padding: '8px 10px', borderRadius: 'var(--radius-sm)',
                    background: 'var(--bg-glass)', border: '1px solid var(--border-color)' }}>
          Daftar klip di Studio akan diganti{dirty ? ', dan suntingan yang belum disimpan disimpan dulu' : ''}.
          Klip yang sudah dirender tidak tersentuh, dan susunan sekarang bisa
          dikembalikan kapan saja.
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
            {sibuk ? 'Mencari…' : 'Cari ulang'}
          </button>
          {sebelumnya && (
            <button className="btn-secondary" onClick={pulihkan} disabled={sibuk}
                    title={`Kembali ke ${sebelumnya.clip_count} klip dari ${namaMesin(sebelumnya.engine, sebelumnya.model)}`}
                    style={{ display: 'inline-flex', gap: '6px', alignItems: 'center' }}>
              <RotateCcw size={14} />
              Kembalikan sebelumnya ({sebelumnya.clip_count} klip)
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
