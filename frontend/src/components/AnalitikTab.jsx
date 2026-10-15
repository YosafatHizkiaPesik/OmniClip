import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle, BarChart3, ExternalLink, Eye, Loader2, RefreshCw, ThumbsUp,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { apiGet } from '../lib/api';
import { useT } from '../lib/i18n';
import GrafikHarian from './GrafikHarian';

/**
 * Analitik: bagaimana klip yang sudah diunggah berjalan, dan apa artinya.
 *
 * Dilaporkan pemiliknya 6 Oktober 2026: "pada fitur analytic mengapa tidak ada
 * tampilan apa apa padahal sudah saya masukkan api key youtube data v3,
 * OmniClip hanya menunjukkan kunci terpasang saja".
 *
 * Ia benar, dan yang kurang bukan datanya. Angkanya memang sudah terbaca, tapi
 * ia hanya muncul sebagai angka kecil di kartu Klip jadi, dan daftar periksa
 * isinya cuma terlihat saat satu klip disiapkan untuk diunggah. Tidak ada satu
 * tempat pun yang menjawab pertanyaan yang sebenarnya: klip mana yang jalan,
 * dan apa yang harus diubah.
 *
 * Halaman ini tidak pernah mengarang sebab. Dengan klip terunggah yang masih
 * sedikit, ia mengatakan apa adanya bahwa belum ada yang bisa dibandingkan,
 * lalu menunjukkan daftar periksa sebagai daftar periksa, bukan sebagai
 * penjelasan kenapa sebuah video sepi.
 */

const card = {
  padding: '18px 20px', border: '1px solid var(--rule-2)',
  borderRadius: 'var(--radius-md)', background: 'var(--plate-2)',
};
const sectionTitle = {
  display: 'flex', alignItems: 'center', gap: '10px', fontSize: '0.95rem',
  fontWeight: 800, color: 'var(--text-primary)', marginBottom: '6px',
};
const helpText = { fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.6 };

const warnaBerat = (b) => (b === 'berat' ? 'var(--accent-red)'
  : b === 'sedang' ? 'var(--reh)' : 'var(--ink-2)');

function Angka({ label, nilai, nota }) {
  return (
    <div style={{ ...card, flex: '1 1 180px', minWidth: 0 }}>
      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontWeight: 700,
                    textTransform: 'uppercase', letterSpacing: '0.04em' }}>{label}</div>
      <div style={{ fontSize: '1.6rem', fontWeight: 800, marginTop: '4px',
                    fontVariantNumeric: 'tabular-nums' }}>{nilai}</div>
      {nota && <div style={{ ...helpText, fontSize: '0.72rem', marginTop: '2px' }}>{nota}</div>}
    </div>
  );
}

function Temuan({ temuan: tm }) {
  const t = useT();
  return (
    <li style={{ padding: '10px 0', borderTop: '1px solid var(--border-color)' }}>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'baseline', flexWrap: 'wrap' }}>
        <b style={{ fontSize: '0.82rem', color: warnaBerat(tm.berat) }}>{tm.judul}</b>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          {t('analitik.dari_klip', { n: tm.berapa, dari: tm.dari })}
        </span>
        {tm.dasar === 'kanal' && (
          <span className="chip is-on" style={{ fontSize: '0.66rem' }}>{t('analitik.terukur_chip')}</span>
        )}
      </div>
      {tm.dasar === 'kanal' && (
        <div style={{ ...helpText, fontSize: '0.74rem', marginTop: '3px' }}>
          {t('analitik.median_kena', { kena: tm.median_kena, bersih: tm.median_bersih })}
        </div>
      )}
      <div style={{ ...helpText, fontSize: '0.76rem', marginTop: '3px' }}>{tm.saran}</div>
    </li>
  );
}

export default function AnalitikTab() {
  const t = useT();
  const [data, setData] = useState(null);
  const [galat, setGalat] = useState(null);
  const [sibuk, setSibuk] = useState(false);

  const muat = useCallback(async () => {
    setSibuk(true);
    setGalat(null);
    try {
      setData(await apiGet('/uploads/analitik'));
    } catch (e) {
      setGalat(e.message);
    } finally {
      setSibuk(false);
    }
  }, []);
  useEffect(() => { muat(); }, [muat]);

  const r = data?.ringkasan;
  const belumTerbaca = data ? data.terunggah - data.terbaca : 0;

  return (
    <div className="page" style={{ maxWidth: '1280px' }}>
      <div className="work-block" style={{ alignItems: 'center' }}>
        <div style={{ minWidth: 0 }}>
          <h1 className="work-title">{t('analitik.judul')}</h1>
          <div className="sub">
            {t('analitik.sub')}
          </div>
        </div>
        <button className="btn-secondary" onClick={muat} disabled={sibuk}
                style={{ display: 'inline-flex', gap: '7px', alignItems: 'center' }}>
          {sibuk ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          {t('umum.muat_ulang')}
        </button>
      </div>

      {galat && (
        <div style={{ ...card, display: 'flex', gap: '9px', alignItems: 'flex-start',
                      color: 'var(--accent-red)' }}>
          <AlertTriangle size={16} style={{ flex: 'none', marginTop: '2px' }} />
          <span style={{ fontSize: '0.8rem' }}>{galat}</span>
        </div>
      )}

      {!data && !galat && (
        <div style={{ ...helpText, display: 'flex', gap: '8px', alignItems: 'center' }}>
          <Loader2 size={16} className="animate-spin" /> {t('analitik.membaca')}
        </div>
      )}

      {data && !data.kunci_terpasang && (
        <div style={card}>
          <div style={sectionTitle}>
            <BarChart3 size={18} style={{ color: 'var(--reh)' }} />{t('analitik.tanpa_kunci')}
          </div>
          <p className="bantu" style={helpText}>
            {t('analitik.tanpa_kunci_a')}{' '}
            <Link to="/profil" style={{ color: 'var(--reh)' }}>{t('nav.akun')}</Link>
            {t('analitik.tanpa_kunci_b')}
          </p>
        </div>
      )}

      {data && data.kunci_terpasang && data.terunggah === 0 && (
        <div style={card}>
          <div style={sectionTitle}>
            <BarChart3 size={18} style={{ color: 'var(--reh)' }} />{t('analitik.belum_unggah')}
          </div>
          <p className="bantu" style={helpText}>
            {t('analitik.belum_unggah_a')}{' '}
            <Link to="/clips" style={{ color: 'var(--reh)' }}>{t('klip.judul')}</Link>
            {t('analitik.belum_unggah_b')}
          </p>
        </div>
      )}

      {data && data.terunggah > 0 && (
        <>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <Angka label={t('analitik.total')} nilai={r?.total ?? 0}
                   nota={t('analitik.dari_terbaca', { n: data.terbaca })} />
            <Angka label={t('analitik.median')} nilai={r?.median ?? '-'}
                   nota={t('analitik.median_nota')} />
            <Angka label={t('analitik.terunggah')} nilai={data.terunggah}
                   nota={belumTerbaca > 0 ? t('analitik.belum_terbaca', { n: belumTerbaca }) : t('analitik.semua_terbaca')} />
          </div>

          {/* Ringkasan kanal, dan dari mana tiap video datang.

              Sampai 9 Oktober 2026 halaman ini hanya memuat video yang
              diunggah LEWAT OmniClip, karena sumbernya tabel `uploads`. Di
              kanal pemiliknya itu 1 dari 4 video. Yang dilaporkannya: "disana
              tidak memuat seluruh video yang kita upload". */}
          {data.kanal_terbaca && data.kanal && (
            <div style={{ ...card, marginTop: '12px' }}>
              <div style={sectionTitle}>
                <BarChart3 size={18} style={{ color: 'var(--reh)' }} />
                {t('analitik.kanal', { nama: data.kanal.nama })}
              </div>
              <div style={{ display: 'flex', gap: '22px', flexWrap: 'wrap',
                            margin: '8px 0 4px' }}>
                <Angka label={t('analitik.video_kanal')} nilai={data.kanal.jumlah_video ?? '-'}
                       nota={data.dari_omniclip !== undefined
                         ? t('analitik.lewat_omniclip_n', { n: data.dari_omniclip })
                         : ''} />
                <Angka label={t('analitik.total_kanal')}
                       nilai={data.kanal.total_tayangan ?? '-'}
                       nota={t('analitik.total_kanal_nota')} />
                <Angka label={t('analitik.pelanggan')}
                       nilai={data.kanal.pelanggan_disembunyikan ? t('analitik.disembunyikan')
                         : (data.kanal.pelanggan ?? '-')}
                       nota={t('analitik.menurut_yt')} />
              </div>
              <div style={{ marginTop: '14px', paddingTop: '12px',
                            borderTop: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '0.82rem', fontWeight: 800,
                              marginBottom: '8px' }}>
                  {t('analitik.per_hari')}
                </div>
                <GrafikHarian harian={data.harian} helpText={helpText} />
              </div>
            </div>
          )}

          {belumTerbaca > 0 && (
            <div style={{ ...card, marginTop: '12px', display: 'flex', gap: '9px',
                          alignItems: 'flex-start' }}>
              <AlertTriangle size={16} style={{ flex: 'none', marginTop: '2px',
                                                color: 'var(--reh)' }} />
              <div style={{ ...helpText, fontSize: '0.78rem' }}>
                <b>{t('analitik.tak_terbaca_judul', { n: belumTerbaca })}</b>{' '}
                {t('analitik.tak_terbaca_isi')}
              </div>
            </div>
          )}

          {/* JOB-2 F3-2: apakah komentar pemilik kanal membuat klip lebih
              ditonton DI KANAL INI. Tanpa angka yang cukup, ia hanya
              menyebut berapa klip lagi yang dibutuhkan. */}
          {data.banding_komentar && (
            <div style={{ ...card, marginTop: '12px' }}>
              <div style={sectionTitle}>
                <BarChart3 size={18} style={{ color: 'var(--reh)' }} />
                {t('analitik.banding')}
              </div>
              <p className="bantu" style={helpText}>{data.banding_komentar.kalimat}</p>
              <div style={{ ...helpText, fontSize: '0.74rem' }}>
                {t('analitik.banding_ket', data.banding_komentar)}
              </div>
            </div>
          )}

          <div style={{ ...card, marginTop: '12px' }}>
            <div style={sectionTitle}>
              <BarChart3 size={18} style={{ color: 'var(--reh)' }} />
              {data.cukup_data ? t('analitik.terukur') : t('analitik.kurang')}
            </div>
            <p className="bantu" style={helpText}>
              {data.cukup_data
                ? t('analitik.terukur_ket')
                : t('analitik.kurang_ket', { n: data.terbaca, ambang: data.ambang })}
            </p>
            {data.temuan.length === 0 ? (
              <p style={{ ...helpText, marginTop: '10px' }}>
                {t('analitik.tanpa_temuan')}
              </p>
            ) : (
              <ul style={{ listStyle: 'none', padding: 0, margin: '10px 0 0' }}>
                {data.temuan.map((tm) => <Temuan key={tm.kode} temuan={tm} />)}
              </ul>
            )}
            <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)',
                        margin: '12px 0 0', lineHeight: 1.55 }}>
              {data.catatan_kaki} {t('analitik.bukan_ramalan')}
            </p>
          </div>

          <div style={{ ...card, marginTop: '12px' }}>
            <div style={sectionTitle}>
              <Eye size={18} style={{ color: 'var(--reh)' }} />{t('analitik.per_klip')}
            </div>
            <div style={{ overflowX: 'auto', marginTop: '8px' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse',
                              fontSize: '0.78rem' }}>
                <thead>
                  <tr style={{ textAlign: 'left', color: 'var(--text-muted)',
                               fontSize: '0.7rem', textTransform: 'uppercase',
                               letterSpacing: '0.04em' }}>
                    <th style={{ padding: '6px 8px 6px 0' }}>{t('analitik.kol_klip')}</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right' }}>{t('analitik.kol_tayangan')}</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right' }}>{t('analitik.kol_suka')}</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right' }}>{t('analitik.kol_panjang')}</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right' }}>{t('analitik.kol_periksa')}</th>
                    <th style={{ padding: '6px 0 6px 8px' }} />
                  </tr>
                </thead>
                <tbody>
                  {data.klip.map((k) => (
                    <tr key={k.remote_id} style={{ borderTop: '1px solid var(--border-color)' }}>
                      <td style={{ padding: '9px 8px 9px 0', maxWidth: '380px' }}>
                        <div style={{ fontWeight: 700, overflow: 'hidden',
                                      textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {k.judul || k.clip_name}
                        </div>
                        {/* Dari mana video ini datang. Penting karena hanya
                            untuk yang lewat OmniClip kita punya keterangan
                            isinya; untuk yang lain yang ada cuma angkanya, dan
                            itu dikatakan apa adanya alih-alih dikarang. */}
                        <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)',
                                      marginTop: 2 }}>
                          {k.dari_omniclip === false
                            ? t('analitik.luar_omniclip')
                            : t('analitik.lewat_omniclip')}
                          {k.waktu ? ` · ${String(k.waktu).slice(0, 10)}` : ''}
                        </div>
                        {!k.terbaca && (
                          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                            {t('analitik.tak_terbaca')}
                            {k.privasi && k.privasi !== 'public'
                              ? t(k.privasi === 'private' ? 'analitik.sebagai_pribadi' : 'analitik.sebagai_tidak_publik')
                              : ''}
                          </div>
                        )}
                      </td>
                      <td style={{ padding: '9px 8px', textAlign: 'right',
                                   fontVariantNumeric: 'tabular-nums', fontWeight: 800 }}>
                        {k.terbaca ? k.tayangan : '-'}
                      </td>
                      <td style={{ padding: '9px 8px', textAlign: 'right',
                                   fontVariantNumeric: 'tabular-nums',
                                   color: 'var(--text-secondary)' }}>
                        {k.terbaca ? (
                          <span style={{ display: 'inline-flex', gap: '5px',
                                         alignItems: 'center' }}>
                            <ThumbsUp size={12} />{k.suka ?? '-'}
                          </span>
                        ) : '-'}
                      </td>
                      <td style={{ padding: '9px 8px', textAlign: 'right',
                                   color: 'var(--text-secondary)',
                                   fontVariantNumeric: 'tabular-nums' }}>
                        {k.durasi ? t('analitik.detik', { n: Math.round(k.durasi) }) : '-'}
                      </td>
                      <td style={{ padding: '9px 8px', textAlign: 'right',
                                   fontVariantNumeric: 'tabular-nums' }}>
                        {k.skor === null || k.skor === undefined ? '-' : (
                          <span style={{ color: k.skor >= 85 ? 'var(--entry)'
                            : k.skor >= 60 ? 'var(--reh)' : 'var(--accent-red)',
                                         fontWeight: 800 }}>
                            {k.skor}/100
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '9px 0 9px 8px' }}>
                        <a href={k.url} target="_blank" rel="noreferrer"
                           title={t('analitik.buka_yt')}
                           style={{ color: 'var(--reh)', display: 'inline-flex' }}>
                          <ExternalLink size={14} />
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)',
                        margin: '12px 0 0', lineHeight: 1.55 }}>
              {t('analitik.cache')}
            </p>
          </div>
        </>
      )}
    </div>
  );
}
