/**
 * Meter orisinalitas di kepala editor Montase (JOB-5 O1).
 *
 * Lencana kecil yang selalu terlihat (persen + warna), dan panel yang
 * menerangkan angkanya: dari mana nilainya, apa yang kurang, dan bagian mana
 * dari video yang masih berupa potongan polos video orang lain, dengan tombol
 * untuk melompat ke sana. Dihitung di peramban dari dokumen (model/orisinalitas.js)
 * dengan rumus yang sama dengan gerbang tinjau di server.
 */
import React, { useEffect, useRef, useState } from 'react';
import { Copy, Loader2, ShieldAlert, ShieldCheck, ShieldHalf } from 'lucide-react';
import { useT } from '../../../lib/i18n';
import { formatTime } from '../../../utils/timeFormat';

const IKON = { baik: ShieldCheck, sedang: ShieldHalf, kurang: ShieldAlert };

/**
 * Kemiripan dengan ekspor sebelumnya (JOB-5 O3): dihitung server dari sidik
 * ekspor lama, jadi hanya saat diminta.
 */
function Kemiripan({ onPeriksa }) {
  const t = useT();
  const [hasil, setHasil] = useState(null);
  const [sibuk, setSibuk] = useState(false);
  const [galat, setGalat] = useState(null);
  const periksa = async () => {
    setSibuk(true);
    setGalat(null);
    try { setHasil(await onPeriksa()); } catch (e) { setGalat(e.message); } finally { setSibuk(false); }
  };
  return (
    <section className="montase-orisinal-mirip">
      <h4>{t('montase.mirip.judul')}</h4>
      <p className="montase-petunjuk">{t('montase.mirip.ket')}</p>
      <button type="button" className="btn-secondary" onClick={periksa} disabled={sibuk}>
        {sibuk ? <Loader2 size={13} className="animate-spin" /> : <Copy size={13} />}{t('montase.mirip.periksa')}
      </button>
      {galat && <p className="montase-galat" role="alert">{galat}</p>}
      {hasil && (
        <div className={`montase-mirip-hasil ${hasil.tingkat}`}>
          <p><b>{t(`montase.mirip.tingkat_${hasil.tingkat}`, { n: hasil.mirip.length, total: hasil.jumlah_banding })}</b></p>
          {hasil.mirip.length > 0 && (
            <ul>
              {hasil.mirip.slice(0, 5).map((m) => (
                <li key={m.berkas}>
                  {t('montase.mirip.baris', { persen: Math.round(m.skor * 100), judul: m.judul || m.berkas })}
                  {m.sama.length > 0 && <small> · {m.sama.map((k) => t(`montase.mirip.dimensi_${k}`)).join(', ')}</small>}
                </li>
              ))}
            </ul>
          )}
          {hasil.saran.length > 0 && <ul className="montase-orisinal-saran">{hasil.saran.map((s) => <li key={s}>{s}</li>)}</ul>}
        </div>
      )}
    </section>
  );
}

export default function MeterOrisinalitas({ hasil, onKe, onRekamNarasi, onPeriksaKemiripan }) {
  const t = useT();
  const [buka, setBuka] = useState(false);
  const wadah = useRef(null);
  useEffect(() => {
    if (!buka) return undefined;
    const tutup = (e) => { if (!wadah.current?.contains(e.target)) setBuka(false); };
    document.addEventListener('pointerdown', tutup);
    return () => document.removeEventListener('pointerdown', tutup);
  }, [buka]);
  const Ikon = IKON[hasil.tingkat];
  const d = hasil.detik;
  const detik = (x) => `${x.toFixed(1)} ${t('montase.satuan.detik')}`;
  return (
    <div className="montase-orisinal" ref={wadah}>
      <button type="button" className={`montase-orisinal-lencana ${hasil.tingkat}`} aria-expanded={buka}
              onClick={() => setBuka((v) => !v)} title={t('montase.orisinal.judul')}
      >
        <Ikon size={14} />{t('montase.orisinal.lencana', { persen: hasil.persen })}
      </button>
      {buka && (
        <div className="montase-orisinal-panel plate" role="dialog" aria-label={t('montase.orisinal.judul')}>
          <h3>{t('montase.orisinal.judul')}</h3>
          <p className={`montase-orisinal-status ${hasil.tingkat}`}>{t(`montase.orisinal.tingkat_${hasil.tingkat}`)}</p>
          <dl>
            <dt>{t('montase.orisinal.suara')}</dt><dd>{detik(d.suara)}{d.sendiri > 0 ? ` (${t('montase.orisinal.sendiri', { d: detik(d.sendiri) })})` : ''}</dd>
            <dt>{t('montase.orisinal.tambahan')}</dt><dd>{detik(d.tambahan)}</dd>
            <dt>{t('montase.orisinal.lain')}</dt><dd>{detik(d.lain)} / {detik(d.total)}</dd>
          </dl>
          {hasil.saran.length > 0 && (
            <ul className="montase-orisinal-saran">
              {hasil.saran.map((s) => (
                <li key={s.kunci}>
                  {t(`montase.orisinal.saran_${s.kunci}`, { n: s.n })}
                  {s.kunci === 'suara_sendiri' && onRekamNarasi && (
                    <button type="button" className="btn-secondary montase-orisinal-aksi"
                            onClick={() => { setBuka(false); onRekamNarasi(); }}
                    >
                      {t('montase.teleprompter.buka')}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          )}
          {hasil.celah.length > 0 && (
            <>
              <h4>{t('montase.orisinal.celah_judul')}</h4>
              <ul className="montase-orisinal-celah">
                {hasil.celah.map((c) => (
                  <li key={c.dari}>
                    <span>{formatTime(c.mulai)} · {detik(c.detik)}</span>
                    <button type="button" className="btn-secondary" onClick={() => { onKe(c.dari); setBuka(false); }}>
                      {t('montase.orisinal.lompat')}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
          {onPeriksaKemiripan && <Kemiripan onPeriksa={onPeriksaKemiripan} />}
          <p className="montase-petunjuk">{t('montase.orisinal.ket')}</p>
        </div>
      )}
    </div>
  );
}
