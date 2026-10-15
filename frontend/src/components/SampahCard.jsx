import React, { useEffect, useState } from 'react';
import {
  AlertTriangle, Check, Loader2, Search, Trash2,
} from 'lucide-react';
import { apiGet, apiPost } from '../lib/api';

import { tebal, useT } from '../lib/i18n';
/**
 * Sampah: berkas yang tidak mungkin berguna lagi.
 *
 * Diminta pemiliknya 9 Oktober 2026: "bisa membersihkan semua sampah yang ada
 * dan juga jika bisa buat saja mesin yang mendeteksi sampah".
 *
 * Kartu ini sengaja berbeda dari kartu Ruang di sebelahnya. Di sana yang
 * didaftar BARANG BERHARGA yang mungkin sudah tidak dibutuhkan, dan yang
 * memutuskan tetap orangnya. Di sini yang didaftar hanya yang tidak mungkin
 * berguna lagi, dan tiap barisnya membawa alasannya sendiri supaya keputusan
 * mesin itu bisa diperiksa, bukan dipercaya begitu saja.
 *
 * Pemeriksaan isi berkas (ffprobe) punya tombolnya sendiri. Ia membuka tiap
 * berkas media satu per satu, dan pemiliknya sudah pernah melaporkan laptopnya
 * tidak bisa dipakai gara-gara pekerjaan latar.
 */

const mb = (b) => (b >= 1e9 ? `${(b / 1e9).toFixed(2)} GB`
  : b >= 1e6 ? `${(b / 1e6).toFixed(1)} MB`
    : b >= 1e3 ? `${(b / 1e3).toFixed(0)} KB` : `${b} B`);

export default function SampahCard({ card, sectionTitle, helpText }) {
  const t = useT();
  const [data, setData] = useState(null);
  const [rusak, setRusak] = useState(null);
  const [sibuk, setSibuk] = useState('');
  const [galat, setGalat] = useState(null);
  const [kabar, setKabar] = useState(null);

  const muat = async () => {
    setSibuk('pindai'); setGalat(null);
    try { setData(await apiGet('/settings/sampah', { timeout: 120000 })); }
    catch (e) { setGalat(e.message); }
    finally { setSibuk(''); }
  };
  useEffect(() => { muat(); }, []);

  const periksa = async () => {
    setSibuk('periksa'); setGalat(null); setKabar(null);
    try {
      // Batas waktunya panjang dengan sengaja: ini membuka tiap berkas media.
      setRusak(await apiPost('/settings/sampah/periksa', {}, { timeout: 15 * 60 * 1000 }));
    } catch (e) { setGalat(e.message); }
    finally { setSibuk(''); }
  };

  const buang = async (jalur) => {
    setSibuk('buang'); setGalat(null); setKabar(null);
    try {
      const r = await apiPost('/settings/sampah/buang',
                              jalur ? { jalur } : {}, { timeout: 120000 });
      setKabar(r.dibuang
        ? t('sampah.dibuang', { n: r.dibuang, ukuran: mb(r.lega) })
        : t('sampah.tidak_ada'));
      setRusak(null);
      await muat();
    } catch (e) { setGalat(e.message); }
    finally { setSibuk(''); }
  };

  const kelompok = [...(data?.kelompok ?? []), ...(rusak?.kelompok ?? [])];
  const total = (data?.ukuran ?? 0) + (rusak?.ukuran ?? 0);
  const jumlah = (data?.jumlah ?? 0) + (rusak?.jumlah ?? 0);

  return (
    <div style={card}>
      <div style={sectionTitle}>
        <Trash2 size={18} style={{ color: 'var(--reh)' }} />
        {t('sampah.judul')}
      </div>
      <p style={helpText}>
        {tebal(t('sampah.ket'))}
      </p>

      {!data ? (
        <div style={{ ...helpText, display: 'flex', gap: 8, alignItems: 'center' }}>
          <Loader2 size={14} className="animate-spin" /> {t('sampah.memindai')}
        </div>
      ) : jumlah === 0 ? (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center',
                      fontSize: '0.82rem', margin: '10px 0' }}>
          <Check size={16} style={{ color: 'var(--entry)' }} />
          {t('sampah.bersih')}
        </div>
      ) : (
        <>
          <div style={{ fontSize: '0.86rem', fontWeight: 800, margin: '10px 0 6px' }}>
            {t('sampah.ringkas', { n: jumlah, ukuran: mb(total) })}
          </div>
          {kelompok.map((k) => (
            <details key={k.nama} style={{ marginBottom: 7 }}>
              <summary style={{ cursor: 'pointer', fontSize: '0.8rem' }}>
                {t('sampah.kelompok', { label: k.label, n: k.jumlah, ukuran: mb(k.ukuran) })}
              </summary>
              <ul style={{ ...helpText, margin: '6px 0 0', paddingLeft: 18,
                           maxHeight: 190, overflowY: 'auto' }}>
                {k.berkas.map((b) => (
                  <li key={b.jalur} style={{ marginBottom: 3 }}>
                    <code style={{ fontSize: '0.72rem' }}>{b.nama}</code>
                    {' '}&middot; {mb(b.ukuran)} &middot; {b.alasan}
                  </li>
                ))}
              </ul>
            </details>
          ))}
        </>
      )}

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap',
                    alignItems: 'center', marginTop: 12 }}>
        <button className="btn-secondary" disabled={!!sibuk} onClick={muat}
                style={{ fontSize: '0.78rem', padding: '6px 11px' }}>
          {sibuk === 'pindai' ? <Loader2 size={13} className="animate-spin" />
            : <Search size={13} />}
          {t('sampah.pindai')}
        </button>
        <button className="btn-secondary" disabled={!!sibuk} onClick={periksa}
                title={t('sampah.periksa_judul')}
                style={{ fontSize: '0.78rem', padding: '6px 11px' }}>
          {sibuk === 'periksa' ? <Loader2 size={13} className="animate-spin" />
            : <AlertTriangle size={13} />}
          {t('sampah.periksa')}
        </button>
        {jumlah > 0 && (
          <button className="btn-primary" disabled={!!sibuk}
                  onClick={() => buang(rusak?.kelompok?.length
                    ? [...(data?.kelompok ?? []), ...rusak.kelompok]
                      .flatMap((k) => k.berkas.map((b) => b.jalur))
                    : null)}
                  style={{ fontSize: '0.78rem', padding: '6px 11px' }}>
            {sibuk === 'buang' ? <Loader2 size={13} className="animate-spin" />
              : <Trash2 size={13} />}
            {t('sampah.buang_semua', { ukuran: mb(total) })}
          </button>
        )}
        {kabar && <span style={helpText}>{kabar}</span>}
        {galat && <span style={{ ...helpText, color: 'var(--danger)' }}>{galat}</span>}
      </div>

      {rusak && rusak.diperiksa !== undefined && (
        <p style={{ ...helpText, marginTop: 9 }}>
          {t('sampah.diperiksa', { n: rusak.diperiksa, rusak: rusak.jumlah })}
          {rusak.jumlah === 0 ? t('sampah.sehat') : ''}
        </p>
      )}
    </div>
  );
}
