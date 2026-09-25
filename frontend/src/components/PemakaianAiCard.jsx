import React, { useCallback, useEffect, useState } from 'react';
import { Activity, Gauge, Loader2, RefreshCw } from 'lucide-react';
import { apiGet } from '../lib/api';

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
export default function PemakaianAiCard({ card, sectionTitle, helpText }) {
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
          Pemakaian AI
        </span>
        <button onClick={muat} disabled={sibuk} aria-label="Hitung ulang"
                style={{ background: 'none', border: 'none', cursor: 'pointer',
                         color: 'var(--text-secondary)', display: 'flex', padding: '3px' }}>
          {sibuk ? <Loader2 size={15} className="animate-spin" />
                 : <RefreshCw size={15} />}
        </button>
      </div>

      {!data ? (
        <p style={helpText}>Menghitung…</p>
      ) : (
        <>
          <p style={helpText}>
            Hari ini <b>{hari.panggilan}</b> panggilan
            {hari.token > 0 && <> · <b>{hari.token.toLocaleString('id-ID')}</b> token</>}.
            Jatah gratis Google <b>{data.jatah_per_model} panggilan per model per hari</b>,
            dan berputar tengah malam waktu Pasifik (sekitar pukul 14.00 WIB).
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
                        {s.terpakai}/{s.jatah}{s.pasti ? ' · penuh' : ''}
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
                Sisa <b>{sisaTotal}</b> panggilan pada model yang sudah dipakai
                hari ini{belumTersentuh > 0 && <>, ditambah model lain yang belum
                tersentuh sama sekali</>}.{' '}
                {hari.sisa.some((s) => s.pasti)
                  ? 'Model yang penuh sudah ditolak Google sendiri, jadi untuk '
                    + 'yang itu angkanya pasti.'
                  : 'Perkiraan: Google tidak pernah mengirim sisa kuotanya, jadi '
                    + 'yang dihitung di sini panggilan yang keluar dari OmniClip. '
                    + 'Batasnya sendiri diambil dari jawaban Google saat jatah '
                    + 'sebuah model pertama kali habis.'}
              </p>
            </div>
          )}

          {data.per_pekerjaan?.length > 0 && (
            <>
              <div style={{ ...helpText, marginTop: '14px', fontWeight: 800,
                            color: 'var(--text-secondary)' }}>
                Terpakai untuk apa ({data.rentang_hari} hari terakhir)
              </div>
              <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap',
                            marginTop: '6px' }}>
                {data.per_pekerjaan.map((p) => (
                  <span key={p.pekerjaan} className="chip" style={{ fontSize: '0.7rem' }}>
                    {p.pekerjaan} · {p.panggilan}×
                  </span>
                ))}
              </div>
            </>
          )}

          {data.rata_per_video?.video > 0 && (
            <p style={{ ...helpText, marginTop: '12px', display: 'flex',
                        alignItems: 'center', gap: '7px' }}>
              <Activity size={14} style={{ flexShrink: 0 }} />
              Rata-rata <b>{data.rata_per_video.panggilan}</b> panggilan per video,
              dari {data.rata_per_video.video} video.
            </p>
          )}
        </>
      )}
    </div>
  );
}
