import React, { useEffect, useState } from 'react';
import { CheckCircle2, ChevronDown, ChevronRight, Loader2, Recycle } from 'lucide-react';
import { apiGet, apiPost } from '../lib/api';
import { tebal, useT, lokal } from '../lib/i18n';

const gb = (n) => (n >= 1e9 ? `${(n / 1e9).toFixed(2)} GB` : `${Math.round(n / 1e6)} MB`);

/**
 * Pembersihan penyimpanan otomatis (diminta pemiliknya 28 Oktober 2026).
 *
 * Video mentah hasil unduhan dibuang bila proyeknya diam 30 hari atau sudah
 * selesai; klip jadi dibuang bila diam 30 hari. Putaran otomatis baru jalan
 * sesudah disetujui sekali di sini, karena putaran pertama bisa membuang
 * puluhan gigabita sekaligus. Aturannya di backend/app/services/bersih_otomatis.py.
 */
export default function BersihOtomatisCard({ card, sectionTitle, helpText }) {
  const t = useT();
  const [r, setR] = useState(null);
  const [galat, setGalat] = useState(null);
  const [sibuk, setSibuk] = useState(false);
  const [kabar, setKabar] = useState(null);
  const [buka, setBuka] = useState(false);

  const muat = () => apiGet('/settings/bersih-otomatis', { timeout: 120000 })
    .then((x) => { setR(x); setGalat(null); })
    .catch((e) => setGalat(e.message));
  useEffect(() => { muat(); }, []);

  const atur = async (ubah) => {
    try {
      await apiPost('/settings/bersih-otomatis', ubah);
      await muat();
    } catch (e) {
      setGalat(e.message);
    }
  };

  const bersihkan = async () => {
    if (!r?.jumlah) return;
    if (!window.confirm(t('bersih.yakin', { n: r.jumlah, ukuran: gb(r.ukuran) }))) return;
    setSibuk(true); setKabar(null);
    try {
      const h = await apiPost('/settings/bersih-otomatis/jalankan', {}, { timeout: 600000 });
      setKabar(t('bersih.selesai', { n: h.dibuang, ukuran: gb(h.bita) }));
      await muat();
    } catch (e) {
      setGalat(e.message);
    } finally {
      setSibuk(false);
    }
  };

  if (!r && !galat) {
    return (
      <div style={card}>
        <div style={sectionTitle}><Recycle size={18} style={{ color: 'var(--reh)' }} />{t('bersih.judul')}</div>
        <p style={helpText}><Loader2 size={13} className="animate-spin" /> {t('bersih.menghitung')}</p>
      </div>
    );
  }
  const st = r?.setelan ?? {};
  const berjalan = st.aktif && st.disetujui;
  const kontrol = {
    padding: '5px 8px', fontSize: '0.78rem', fontFamily: 'inherit', width: 70,
    borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)',
    background: 'transparent', color: 'var(--ink)',
  };

  return (
    <div style={card}>
      <div style={sectionTitle}>
        <Recycle size={18} style={{ color: 'var(--reh)' }} />
        {t('bersih.judul')}
      </div>
      <p className="bantu" style={helpText}>{tebal(t('bersih.ket', { hari: st.hari ?? 30, selesai: st.selesai_hari ?? 7 }))}</p>
      {galat && <p style={{ ...helpText, color: 'var(--danger)' }}>{galat}</p>}

      {r && (
        <>
          <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginTop: 10, fontSize: '0.84rem', fontWeight: 700, cursor: 'pointer' }}>
            <input type="checkbox" checked={!!berjalan}
                   onChange={(e) => atur({ aktif: e.target.checked })} />
            {t('bersih.sakelar')}
          </label>
          {st.aktif && !st.disetujui && (
            <p style={{ ...helpText, color: 'var(--reh)', marginTop: 6 }}>{t('bersih.belum_disetujui')}</p>
          )}

          <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', marginTop: 10, fontSize: '0.78rem', alignItems: 'center' }}>
            <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
              <input type="checkbox" checked={!!st.sumber} onChange={(e) => atur({ sumber: e.target.checked })} />
              {t('bersih.opsi_sumber')}
            </label>
            <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
              <input type="checkbox" checked={!!st.klip} onChange={(e) => atur({ klip: e.target.checked })} />
              {t('bersih.opsi_klip')}
            </label>
            <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
              {t('bersih.hari')}
              <input type="number" min={7} max={365} defaultValue={st.hari} style={kontrol}
                     onBlur={(e) => Number(e.target.value) !== st.hari && atur({ hari: Number(e.target.value) })} />
            </label>
            <label style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}>
              {t('bersih.selesai_hari')}
              <input type="number" min={1} max={365} defaultValue={st.selesai_hari} style={kontrol}
                     onBlur={(e) => Number(e.target.value) !== st.selesai_hari && atur({ selesai_hari: Number(e.target.value) })} />
            </label>
          </div>

          <div style={{ marginTop: 12, padding: '10px 12px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
            <button type="button" onClick={() => setBuka((b) => !b)} disabled={!r.jumlah}
                    style={{ background: 'none', border: 0, padding: 0, color: 'var(--ink)', cursor: r.jumlah ? 'pointer' : 'default',
                             display: 'flex', gap: 6, alignItems: 'center', fontFamily: 'inherit', fontSize: '0.82rem', fontWeight: 700 }}>
              {r.jumlah ? (buka ? <ChevronDown size={15} /> : <ChevronRight size={15} />) : <CheckCircle2 size={15} style={{ color: 'var(--entry)' }} />}
              {r.jumlah
                ? t('bersih.akan', { n: r.jumlah, ukuran: gb(r.ukuran), sumber: r.sumber.length, klip: r.klip.length })
                : t('bersih.kosong')}
            </button>
            {buka && r.jumlah > 0 && (
              <ul style={{ margin: '8px 0 0', padding: 0, listStyle: 'none', maxHeight: 260, overflowY: 'auto', fontSize: '0.74rem' }}>
                {[...r.sumber.map((s) => ({ ...s, jenis: t(s.alasan === 'selesai' ? 'bersih.alasan_selesai' : 'bersih.alasan_diam', { hari: s.diam_hari }) })),
                  ...r.klip.map((k) => ({ ...k, jenis: t('bersih.alasan_klip', { hari: k.diam_hari, profil: k.profil }) }))]
                  .map((x) => (
                    <li key={x.berkas} style={{ display: 'flex', gap: 8, padding: '4px 0', borderTop: '1px solid var(--rule-2, var(--border-color))' }}>
                      <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={x.berkas}>{x.berkas}</span>
                      <span style={{ color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{x.jenis}</span>
                      <span style={{ fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>{gb(x.ukuran)}</span>
                    </li>
                  ))}
              </ul>
            )}
          </div>

          <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap', marginTop: 10 }}>
            <button className="btn-primary" disabled={sibuk || !r.jumlah} onClick={bersihkan}>
              {sibuk ? <Loader2 size={14} className="animate-spin" /> : <Recycle size={14} />}
              {t('bersih.sekarang')}
            </button>
            {st.terakhir > 0 && (
              <span style={{ ...helpText, fontSize: '0.72rem' }}>
                {t('bersih.terakhir', {
                  waktu: new Date(st.terakhir * 1000).toLocaleString(lokal(), { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }),
                  hasil: st.hasil_terakhir || t('bersih.tidak_ada'),
                })}
              </span>
            )}
          </div>
          {kabar && <p style={{ ...helpText, color: 'var(--entry)', marginTop: 8 }}>{kabar}</p>}
        </>
      )}
    </div>
  );
}
