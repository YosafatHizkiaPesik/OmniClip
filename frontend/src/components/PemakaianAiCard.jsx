import React, { useCallback, useEffect, useState } from 'react';
import { Activity, Gauge, Loader2, RefreshCw } from 'lucide-react';
import { apiGet } from '../lib/api';

import { t as tr, tebal, useT, angka } from '../lib/i18n';
/**
 * Berapa jatah AI yang sudah terpakai hari ini, dan untuk apa.
 *
 * Ada karena satu pertanyaan yang sebelumnya tidak bisa dijawab: "jatah saya
 * masih sisa berapa?" Jawabannya dulu selalu sama, yaitu menunggu sampai gagal
 * lalu menebak sebabnya. Jatah gratis Gemini hanya 20 permintaan per model per
 * hari, jadi pertanyaan itu syarat untuk bisa merencanakan hari, bukan rasa
 * ingin tahu.
 *
 * Yang ditampilkan angka NYATA dari tiap panggilan, bukan perkiraan. Sisa
 * jatahnya perkiraan, dan dikatakan begitu: yang menghitung sebenarnya Google.
 */
/** Nama pekerjaan AI dari server, diterjemahkan bila dikenal. */
function namaPekerjaan(nama) {
  const kunci = `pekerjaan_ai.${String(nama).toLowerCase().replace(/[^a-z]+/g, '_')}`;
  const hasil = tr(kunci);
  return hasil === kunci ? nama : hasil;
}

export default function PemakaianAiCard({ card, sectionTitle, helpText }) {
  const t = useT();
  const [data, setData] = useState(null);
  const [sibuk, setSibuk] = useState(false);

  const muat = useCallback(() => {
    setSibuk(true);
    apiGet('/settings/pemakaian-ai')
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setSibuk(false));
  }, []);
  useEffect(() => { muat(); }, [muat]);

  const hari = data?.hari_ini;
  const sisaTotal = (hari?.sisa ?? []).reduce((n, s) => n + s.sisa, 0);
  const belumTersentuh = Math.max(0, 10 - (hari?.sisa?.length ?? 0));

  return (
    <div style={card}>
      <div style={{ ...sectionTitle, justifyContent: 'space-between' }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
          <Gauge size={18} style={{ color: 'var(--reh)' }} />
          {t('ai.judul')}
        </span>
        <button onClick={muat} disabled={sibuk} aria-label={t('ai.hitung_ulang')}
                style={{ background: 'none', border: 'none', cursor: 'pointer',
                         color: 'var(--text-secondary)', display: 'flex', padding: '3px' }}>
          {sibuk ? <Loader2 size={15} className="animate-spin" />
                 : <RefreshCw size={15} />}
        </button>
      </div>

      {!data ? (
        <p className="bantu" style={helpText}>{t('ai.menghitung')}</p>
      ) : (
        <>
          <p className="bantu" style={helpText}>
            {tebal(t('ai.hari_ini', { n: hari.panggilan }))}
            {hari.token > 0 && tebal(t('ai.token', { n: angka(hari.token) }))}
            {tebal(t('ai.jatah', { n: data.jatah_per_model }))}
          </p>

          {hari.sisa.length > 0 && (
            <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column',
                          gap: '7px' }}>
              {hari.sisa.map((s) => {
                const pakai = Math.min(1, s.terpakai / Math.max(1, s.jatah));
                return (
                  <div key={s.model}>
                    <div style={{ display: 'flex', justifyContent: 'space-between',
                                  fontSize: '0.74rem', marginBottom: '3px' }}>
                      <span>{s.model}</span>
                      <span style={{ color: s.pasti ? 'var(--accent-red)' : 'var(--text-muted)',
                                     fontVariantNumeric: 'tabular-nums' }}>
                        {s.terpakai}/{s.jatah}{s.pasti ? t('ai.penuh') : ''}
                      </span>
                    </div>
                    <div style={{ height: '5px', borderRadius: '3px',
                                  background: 'var(--rule-2)', overflow: 'hidden' }}>
                      <div style={{
                        width: `${pakai * 100}%`, height: '100%',
                        background: pakai >= 1 ? 'var(--accent-red)'
                          : pakai > 0.7 ? 'var(--hl)' : 'var(--entry)',
                      }} />
                    </div>
                  </div>
                );
              })}
              <p style={{ ...helpText, marginTop: '2px' }}>
                {tebal(t('ai.sisa', { n: sisaTotal }))}
                {belumTersentuh > 0 && t('ai.sisa_lain')}.{' '}
                {hari.sisa.some((s) => s.pasti) ? t('ai.pasti') : t('ai.perkiraan')}
              </p>
            </div>
          )}

          {data.per_pekerjaan?.length > 0 && (
            <>
              <div style={{ ...helpText, marginTop: '14px', fontWeight: 800,
                            color: 'var(--text-secondary)' }}>
                {t('ai.untuk_apa', { n: data.rentang_hari })}
              </div>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap',
                            marginTop: '6px' }}>
                {data.per_pekerjaan.map((p) => (
                  <span key={p.pekerjaan} className="chip" style={{ fontSize: '0.7rem' }}>
                    {namaPekerjaan(p.pekerjaan)} · {p.panggilan}×
                  </span>
                ))}
              </div>
            </>
          )}

          {data.rata_per_video?.video > 0 && (
            <p style={{ ...helpText, marginTop: '12px', display: 'flex',
                        alignItems: 'center', gap: '7px' }}>
              <Activity size={14} style={{ flexShrink: 0 }} />
              {tebal(t('ai.rata', { n: data.rata_per_video.panggilan, video: data.rata_per_video.video }))}
            </p>
          )}
        </>
      )}
    </div>
  );
}
