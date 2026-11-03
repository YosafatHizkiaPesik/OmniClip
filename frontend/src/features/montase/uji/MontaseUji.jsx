/**
 * Halaman uji Tahap 0 Montase (/montase-uji, JOB-4.md M0.1 sampai M0.7).
 *
 * Satu halaman untuk membuktikan semua jalur yang berisiko sebelum editor
 * dibangun, dan untuk dijalankan pemilik di komputernya sendiri (Linux dan
 * Windows):
 *   1. status mesin + tombol menyiapkannya (unduh Node dan Chrome);
 *   2. pratinjau langsung: Remotion Player di halaman ini (M0.1);
 *   3. pratinjau kotak pasir: Player yang sama di iframe tertutup (M0.6);
 *   4. render uji lewat Mesin Montase, dengan angka waktunya (M0.2, M0.5).
 *
 * Dibuang sesudah Tahap 1 menggantinya dengan menu Montase sungguhan.
 */
import React, { useCallback, useEffect, useState } from 'react';
import { Player } from '@remotion/player';
import { Clapperboard, Download, Loader2, PlayCircle, RefreshCw } from 'lucide-react';
import { apiGet } from '../../../lib/api';
import { angka, useT } from '../../../lib/i18n';
import { useJobRunner } from '../../../hooks/useJob';
import JobProgress from '../../../components/JobProgress';
import { Komposisi, ukuranDokumen } from '../komposisi/index.js';
import PratinjauKotakPasir from '../pratinjau/PratinjauKotakPasir.jsx';

function BarisStatus({ label, nilai }) {
  return (
    <div className="montase-uji-baris">
      <span>{label}</span>
      <code>{nilai || '—'}</code>
    </div>
  );
}

export default function MontaseUji() {
  const t = useT();
  const [uji, setUji] = useState(null);
  const [mesin, setMesin] = useState(null);
  const [galat, setGalat] = useState(null);
  const [galatPratinjau, setGalatPratinjau] = useState(null);
  const siapkan = useJobRunner();
  const render = useJobRunner();

  const muat = useCallback(() => {
    setGalat(null);
    apiGet('/montase/mesin').then(setMesin).catch((e) => setGalat(e.message));
    apiGet('/montase/uji', { timeout: 120000 }).then(setUji).catch((e) => setGalat(e.message));
  }, []);

  useEffect(() => { muat(); }, [muat]);
  useEffect(() => {
    if (siapkan.status === 'done') apiGet('/montase/mesin').then(setMesin).catch(() => {});
  }, [siapkan.status]);

  const u = uji ? ukuranDokumen(uji.dokumen) : null;
  const hasil = render.result;
  const alamatHasil = uji && hasil
    ? `${uji.sumber.bahan.b1.replace(/[^/]+$/, hasil.berkas)}?t=${render.job?.job_id ?? ''}`
    : null;

  return (
    <div className="page rak montase-uji" style={{ maxWidth: '1280px' }}>
      <header className="rak-kepala">
        <div className="rak-kepala-teks">
          <h1 className="work-title rak-judul">{t('montase.uji.judul')}</h1>
          <p className="rak-sub">{t('montase.uji.sub')}</p>
        </div>
        <div className="rak-aksi">
          <button className="btn-secondary" onClick={muat}>
            <RefreshCw size={14} />
            {t('umum.muat_ulang')}
          </button>
        </div>
      </header>

      {galat && <p className="montase-uji-galat" role="alert">{galat}</p>}

      <section className="plate panel-rak">
        <div className="plate-head"><h2>{t('montase.uji.mesin')}</h2></div>
        <div className="panel-isi">
          <BarisStatus label={t('montase.uji.node')} nilai={mesin?.versi_node && `${mesin.versi_node} · ${mesin.node}`} />
          <BarisStatus label={t('montase.uji.paket')} nilai={mesin?.paket} />
          <BarisStatus label={t('montase.uji.bundel')} nilai={mesin?.bundel} />
          <BarisStatus label={t('montase.uji.browser')} nilai={mesin?.browser ?? t('montase.uji.browser_remotion')} />
          <p className="montase-uji-ket" data-siap={mesin?.siap ? 'ya' : 'tidak'}>
            {mesin?.siap ? t('montase.uji.mesin_siap') : t('montase.uji.mesin_belum')}
          </p>
          <button
            className="btn-secondary"
            disabled={siapkan.active}
            onClick={() => siapkan.run('/montase/mesin/siapkan').catch(() => {})}
          >
            {siapkan.active ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
            {t('montase.uji.siapkan')}
          </button>
          {(siapkan.job || siapkan.error) && (
            <JobProgress job={siapkan.job} error={siapkan.error} onCancel={siapkan.cancel} compact />
          )}
        </div>
      </section>

      <div className="montase-uji-dua">
        <section className="plate panel-rak">
          <div className="plate-head"><h2>{t('montase.uji.langsung')}</h2></div>
          <div className="panel-isi">
            <p className="montase-uji-ket">{t('montase.uji.langsung_ket')}</p>
            {uji ? (
              <div className="montase-uji-layar" style={{ aspectRatio: `${u.lebar} / ${u.tinggi}` }}>
                <Player
                  component={Komposisi}
                  inputProps={{ dokumen: uji.dokumen, sumber: uji.sumber }}
                  durationInFrames={u.durasi}
                  compositionWidth={u.lebar}
                  compositionHeight={u.tinggi}
                  fps={u.fps}
                  controls
                  style={{ width: '100%', height: '100%' }}
                  acknowledgeRemotionLicense
                />
              </div>
            ) : <Loader2 size={18} className="animate-spin" />}
          </div>
        </section>

        <section className="plate panel-rak">
          <div className="plate-head"><h2>{t('montase.uji.kotak_pasir')}</h2></div>
          <div className="panel-isi">
            <p className="montase-uji-ket">{t('montase.uji.kotak_pasir_ket')}</p>
            {uji ? (
              <PratinjauKotakPasir dokumen={uji.dokumen} sumber={uji.sumber} onGalat={setGalatPratinjau} />
            ) : <Loader2 size={18} className="animate-spin" />}
            {galatPratinjau && <p className="montase-uji-galat" role="alert">{galatPratinjau}</p>}
          </div>
        </section>
      </div>

      <section className="plate panel-rak">
        <div className="plate-head"><h2>{t('montase.uji.render')}</h2></div>
        <div className="panel-isi">
          <p className="montase-uji-ket">{t('montase.uji.render_ket')}</p>
          {uji?.komponen && (
            <p className="montase-uji-ket" data-lolos={uji.komponen.lolos ? 'ya' : 'tidak'}>
              {uji.komponen.lolos
                ? t('montase.uji.komponen_lolos')
                : t('montase.uji.komponen_gagal', { masalah: (uji.komponen.masalah ?? []).join('; ') })}
            </p>
          )}
          <button
            className="btn-primary"
            disabled={render.active || !mesin?.siap}
            onClick={() => render.run('/montase/uji/render').catch(() => {})}
          >
            {render.active ? <Loader2 size={14} className="animate-spin" /> : <Clapperboard size={14} />}
            {t('montase.uji.render_mulai')}
          </button>
          {(render.job || render.error) && (
            <JobProgress job={render.job} error={render.error} onCancel={render.cancel} compact />
          )}
          {hasil && (
            <div className="montase-uji-hasil">
              <BarisStatus label={t('montase.uji.hasil_waktu')} nilai={t('montase.uji.hasil_waktu_isi', {
                detik: angka(hasil.detik_dinding), video: angka(hasil.detik_video),
                kali: angka(hasil.kali_durasi),
              })}
              />
              <BarisStatus label={t('montase.uji.hasil_ukuran')} nilai={`${angka(hasil.ukuran_mb)} MB · ${angka(hasil.bingkai)}`} />
              <a className="btn-secondary" href={alamatHasil} target="_blank" rel="noreferrer">
                <PlayCircle size={14} />
                {t('montase.uji.hasil_tonton')}
              </a>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
