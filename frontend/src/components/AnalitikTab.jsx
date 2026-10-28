import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle, BarChart3, ExternalLink, Eye, ListChecks, Loader2, MessageSquareText, RefreshCw,
  ThumbsUp, TrendingUp,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { apiGet } from '../lib/api';
import { angka, useT } from '../lib/i18n';
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

const helpText = { fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.6 };

const warnaBerat = (b) => (b === 'berat' ? 'var(--danger)'
  : b === 'sedang' ? 'var(--warn)' : 'var(--ink-2)');


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

  const maksTayangan = Math.max(1, ...(data?.klip || []).map((k) => (k.terbaca ? k.tayangan || 0 : 0)));
  const kanal = data?.kanal_terbaca && data?.kanal ? data.kanal : null;

  return (
    <div className="page rak" style={{ maxWidth: '1280px' }}>
      <header className="rak-kepala">
        <div className="rak-kepala-teks">
          <h1 className="work-title rak-judul">{t('analitik.judul')}</h1>
          <p className="rak-sub">{t('analitik.sub')}</p>
        </div>
        <div className="rak-aksi">
          <button className="btn-secondary" onClick={muat} disabled={sibuk}>
            {sibuk ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            {t('umum.muat_ulang')}
          </button>
        </div>
      </header>

      {galat && (
        <div className="rak-galat" role="alert">
          <AlertTriangle size={15} /><span>{galat}</span>
        </div>
      )}

      {!data && !galat && (
        <div aria-busy="true" style={{ display: 'grid', gap: 14 }}>
          <div className="strip-angka lembar-kerangka">
            {[0, 1, 2].map((n) => (
              <div key={n}>
                <div className="kerangka" style={{ height: 10, width: '50%' }} />
                <div className="kerangka" style={{ height: 26, width: '40%', margin: '8px 0' }} />
                <div className="kerangka" style={{ height: 10, width: '70%' }} />
              </div>
            ))}
          </div>
          <p style={{ ...helpText, display: 'flex', gap: '8px', alignItems: 'center', margin: 0 }}>
            <Loader2 size={14} className="animate-spin" /> {t('analitik.membaca')}
          </p>
        </div>
      )}

      {data && !data.kunci_terpasang && (
        <div className="rak-kosong">
          <BarChart3 size={36} />
          <h3>{t('analitik.tanpa_kunci')}</h3>
          <p>
            {t('analitik.tanpa_kunci_a')}{' '}
            <Link to="/profil" style={{ color: 'var(--reh)' }}>{t('nav.akun')}</Link>
            {t('analitik.tanpa_kunci_b')}
          </p>
        </div>
      )}

      {data && data.kunci_terpasang && data.terunggah === 0 && (
        <div className="rak-kosong">
          <BarChart3 size={36} />
          <h3>{t('analitik.belum_unggah')}</h3>
          <p>
            {t('analitik.belum_unggah_a')}{' '}
            <Link to="/clips" style={{ color: 'var(--reh)' }}>{t('klip.judul')}</Link>
            {t('analitik.belum_unggah_b')}
          </p>
        </div>
      )}

      {data && data.terunggah > 0 && (
        <div style={{ display: 'grid', gap: 14 }}>
          {/* Angka klip dan angka kanal dalam SATU strip. Dulu dua baris
              kartu, yang kedua di dalam kartu lain. */}
          <section className="strip-angka" aria-label={t('analitik.judul')}>
            <div>
              <span className="mark">{t('analitik.total')}</span>
              <span className="nilai">{angka(r?.total ?? 0)}</span>
              <span className="ket">{t('analitik.dari_terbaca', { n: data.terbaca })}</span>
            </div>
            <div>
              <span className="mark">{t('analitik.median')}</span>
              <span className="nilai">{r?.median ?? '-'}</span>
              <span className="ket">{t('analitik.median_nota')}</span>
            </div>
            <div>
              <span className="mark">{t('analitik.terunggah')}</span>
              <span className="nilai">{data.terunggah}</span>
              <span className="ket">{belumTerbaca > 0 ? t('analitik.belum_terbaca', { n: belumTerbaca }) : t('analitik.semua_terbaca')}</span>
            </div>
            {kanal && (
              <>
                <div>
                  <span className="mark">{t('analitik.video_kanal')}</span>
                  <span className="nilai">{kanal.jumlah_video ?? '-'}</span>
                  <span className="ket">{data.dari_omniclip !== undefined ? t('analitik.lewat_omniclip_n', { n: data.dari_omniclip }) : kanal.nama}</span>
                </div>
                <div>
                  <span className="mark">{t('analitik.total_kanal')}</span>
                  <span className="nilai">{kanal.total_tayangan != null ? angka(kanal.total_tayangan) : '-'}</span>
                  <span className="ket">{t('analitik.total_kanal_nota')}</span>
                </div>
                <div>
                  <span className="mark">{t('analitik.pelanggan')}</span>
                  <span className="nilai">{kanal.pelanggan_disembunyikan ? t('analitik.disembunyikan') : (kanal.pelanggan != null ? angka(kanal.pelanggan) : '-')}</span>
                  <span className="ket">{t('analitik.menurut_yt')}</span>
                </div>
              </>
            )}
          </section>

          {/* Ringkasan kanal, dan dari mana tiap video datang.

              Sampai 9 Oktober 2026 halaman ini hanya memuat video yang
              diunggah LEWAT OmniClip, karena sumbernya tabel `uploads`. Di
              kanal pemiliknya itu 1 dari 4 video. Yang dilaporkannya: "disana
              tidak memuat seluruh video yang kita upload". */}
          {kanal && (
            <section className="plate panel-rak">
              <div className="plate-head">
                <TrendingUp size={16} style={{ color: 'var(--reh)' }} />
                <h2>{t('analitik.per_hari')}</h2>
                <span className="mark" style={{ marginLeft: 'auto' }}>{t('analitik.kanal', { nama: kanal.nama })}</span>
              </div>
              <div className="panel-isi">
                <GrafikHarian harian={data.harian} helpText={helpText} />
              </div>
            </section>
          )}

          {belumTerbaca > 0 && (
            <div className="rak-galat" style={{ color: 'var(--ink-2)', background: 'color-mix(in srgb, var(--warn) 9%, transparent)',
                                                 borderColor: 'color-mix(in srgb, var(--warn) 35%, transparent)', margin: 0 }}>
              <AlertTriangle size={15} style={{ color: 'var(--warn)' }} />
              <span><b>{t('analitik.tak_terbaca_judul', { n: belumTerbaca })}</b> {t('analitik.tak_terbaca_isi')}</span>
            </div>
          )}

          <div className="analitik-dua">
            {/* JOB-2 F3-2: apakah komentar pemilik kanal membuat klip lebih
                ditonton DI KANAL INI. Tanpa angka yang cukup, ia hanya
                menyebut berapa klip lagi yang dibutuhkan. */}
            {data.banding_komentar && (
              <section className="plate panel-rak">
                <div className="plate-head">
                  <MessageSquareText size={16} style={{ color: 'var(--reh)' }} />
                  <h2>{t('analitik.banding')}</h2>
                </div>
                <div className="panel-isi">
                  <p style={{ ...helpText, margin: 0 }}>{data.banding_komentar.kalimat}</p>
                  <p style={{ ...helpText, fontSize: '0.74rem', margin: '6px 0 0', color: 'var(--ink-3)' }}>
                    {t('analitik.banding_ket', data.banding_komentar)}
                  </p>
                </div>
              </section>
            )}

            <section className="plate panel-rak">
              <div className="plate-head">
                <ListChecks size={16} style={{ color: 'var(--reh)' }} />
                <h2>{data.cukup_data ? t('analitik.terukur') : t('analitik.kurang')}</h2>
              </div>
              <div className="panel-isi">
                <p style={{ ...helpText, margin: 0 }}>
                  {data.cukup_data
                    ? t('analitik.terukur_ket')
                    : t('analitik.kurang_ket', { n: data.terbaca, ambang: data.ambang })}
                </p>
                {data.temuan.length === 0 ? (
                  <p style={{ ...helpText, marginTop: '10px' }}>{t('analitik.tanpa_temuan')}</p>
                ) : (
                  <ul style={{ listStyle: 'none', padding: 0, margin: '10px 0 0' }}>
                    {data.temuan.map((tm) => <Temuan key={tm.kode} temuan={tm} />)}
                  </ul>
                )}
                <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', margin: '12px 0 0', lineHeight: 1.55 }}>
                  {data.catatan_kaki} {t('analitik.bukan_ramalan')}
                </p>
              </div>
            </section>
          </div>

          <section className="plate panel-rak">
            <div className="plate-head">
              <Eye size={16} style={{ color: 'var(--reh)' }} />
              <h2>{t('analitik.per_klip')}</h2>
              {!data.retensi_tersambung && (
                <span style={{ marginLeft: 'auto', fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                  {t('analitik.retensi_belum')}{' '}
                  <Link to="/profil?bagian=google" style={{ color: 'var(--reh)' }}>{t('analitik.retensi_sambung')}</Link>
                </span>
              )}
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table className="tabel-rak">
                <thead>
                  <tr>
                    <th>{t('analitik.kol_klip')}</th>
                    <th className="angka">{t('analitik.kol_tayangan')}</th>
                    <th className="angka">{t('analitik.kol_suka')}</th>
                    {data.retensi_tersambung && (
                      <th className="angka" title={t('analitik.kol_retensi_judul')}>{t('analitik.kol_retensi')}</th>
                    )}
                    <th className="angka">{t('analitik.kol_panjang')}</th>
                    <th className="angka">{t('analitik.kol_periksa')}</th>
                    <th aria-label={t('analitik.buka_yt')} />
                  </tr>
                </thead>
                <tbody>
                  {data.klip.map((k) => (
                    <tr key={k.remote_id}>
                      <td style={{ maxWidth: '420px' }}>
                        <div className="tabel-judul">{k.judul || k.clip_name}</div>
                        {/* Dari mana video ini datang. Penting karena hanya
                            untuk yang lewat OmniClip kita punya keterangan
                            isinya; untuk yang lain yang ada cuma angkanya, dan
                            itu dikatakan apa adanya alih-alih dikarang. */}
                        <div className="tabel-sub">
                          {k.dari_omniclip === false ? t('analitik.luar_omniclip') : t('analitik.lewat_omniclip')}
                          {k.waktu ? ` · ${String(k.waktu).slice(0, 10)}` : ''}
                        </div>
                        {!k.terbaca && (
                          <div className="tabel-sub">
                            {t('analitik.tak_terbaca')}
                            {k.privasi && k.privasi !== 'public'
                              ? t(k.privasi === 'private' ? 'analitik.sebagai_pribadi' : 'analitik.sebagai_tidak_publik')
                              : ''}
                          </div>
                        )}
                      </td>
                      <td className="angka">
                        {k.terbaca ? (
                          <div className="tayangan-sel">
                            <b>{angka(k.tayangan)}</b>
                            {/* Bilah data: tayangan klip ini dibanding yang terbanyak. */}
                            <span className="tayangan-bilah" aria-hidden="true">
                              <span style={{ width: `${Math.max(3, ((k.tayangan || 0) / maksTayangan) * 100)}%` }} />
                            </span>
                          </div>
                        ) : '-'}
                      </td>
                      <td className="angka redup">
                        {k.terbaca ? (
                          <span style={{ display: 'inline-flex', gap: '5px', alignItems: 'center' }}>
                            <ThumbsUp size={12} />{k.suka ?? '-'}
                          </span>
                        ) : '-'}
                      </td>
                      {data.retensi_tersambung && (
                        <td className="angka" title={k.retensi ? t('analitik.retensi_rinci', { detik: Math.round(k.retensi.detik) }) : ''}>
                          {k.retensi ? (
                            <b style={{ color: k.retensi.persen >= 70 ? 'var(--entry)'
                              : k.retensi.persen >= 40 ? 'var(--warn)' : 'var(--danger)' }}>
                              {Math.round(k.retensi.persen)}%
                            </b>
                          ) : '-'}
                        </td>
                      )}
                      <td className="angka redup">
                        {k.durasi ? t('analitik.detik', { n: Math.round(k.durasi) }) : '-'}
                      </td>
                      <td className="angka">
                        {k.skor === null || k.skor === undefined ? <span className="redup">-</span> : (
                          <b style={{ color: k.skor >= 85 ? 'var(--entry)' : k.skor >= 60 ? 'var(--warn)' : 'var(--danger)' }}>
                            {k.skor}/100
                          </b>
                        )}
                      </td>
                      <td style={{ width: 40 }}>
                        <a href={k.url} target="_blank" rel="noreferrer" className="ikon-btn"
                           title={t('analitik.buka_yt')} aria-label={t('analitik.buka_yt')}>
                          <ExternalLink size={14} />
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', margin: 0, padding: '10px 16px 12px', lineHeight: 1.55 }}>
              {t('analitik.cache')}
            </p>
          </section>
        </div>
      )}
    </div>
  );
}
