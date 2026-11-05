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
import { ShieldAlert, ShieldCheck, ShieldHalf } from 'lucide-react';
import { useT } from '../../../lib/i18n';
import { formatTime } from '../../../utils/timeFormat';

const IKON = { baik: ShieldCheck, sedang: ShieldHalf, kurang: ShieldAlert };

export default function MeterOrisinalitas({ hasil, onKe, onRekamNarasi }) {
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
          <p className="montase-petunjuk">{t('montase.orisinal.ket')}</p>
        </div>
      )}
    </div>
  );
}
