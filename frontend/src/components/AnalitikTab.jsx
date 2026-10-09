import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle, BarChart3, ExternalLink, Eye, Loader2, RefreshCw, ThumbsUp,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { apiGet } from '../lib/api';
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

function Temuan({ t }) {
  return (
    <li style={{ padding: '10px 0', borderTop: '1px solid var(--border-color)' }}>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'baseline', flexWrap: 'wrap' }}>
        <b style={{ fontSize: '0.82rem', color: warnaBerat(t.berat) }}>{t.judul}</b>
        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          {t.berapa} dari {t.dari} klip
        </span>
        {t.dasar === 'kanal' && (
          <span className="chip is-on" style={{ fontSize: '0.66rem' }}>terukur di kanal ini</span>
        )}
      </div>
      {t.dasar === 'kanal' && (
        <div style={{ ...helpText, fontSize: '0.74rem', marginTop: '3px' }}>
          Median tayangan klip yang kena: <b>{t.median_kena}</b>, yang tidak kena:{' '}
          <b>{t.median_bersih}</b>.
        </div>
      )}
      <div style={{ ...helpText, fontSize: '0.76rem', marginTop: '3px' }}>{t.saran}</div>
    </li>
  );
}

export default function AnalitikTab() {
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
          <h1 className="work-title">Analitik</h1>
          <div className="sub">
            Klip yang sudah diunggah ke YouTube, berapa kali ditonton, dan apa
            yang bisa dibaca dari angkanya.
          </div>
        </div>
        <button className="btn-secondary" onClick={muat} disabled={sibuk}
                style={{ display: 'inline-flex', gap: '7px', alignItems: 'center' }}>
          {sibuk ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
          Muat ulang
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
          <Loader2 size={16} className="animate-spin" /> Membaca tayangan dari YouTube…
        </div>
      )}

      {data && !data.kunci_terpasang && (
        <div style={card}>
          <div style={sectionTitle}>
            <BarChart3 size={18} style={{ color: 'var(--reh)' }} />Kunci belum terpasang
          </div>
          <p className="bantu" style={helpText}>
            Tayangan dibaca dengan kunci YouTube Data API. Tanpa kunci itu,
            OmniClip tahu video mana yang ia unggah tapi tidak boleh menanyakan
            angkanya. Kuncinya dipasang sekali di halaman{' '}
            <Link to="/profil" style={{ color: 'var(--reh)' }}>Akun</Link>, dan
            hanya bisa membaca: ia tidak mengubah apa pun di kanal Anda.
          </p>
        </div>
      )}

      {data && data.kunci_terpasang && data.terunggah === 0 && (
        <div style={card}>
          <div style={sectionTitle}>
            <BarChart3 size={18} style={{ color: 'var(--reh)' }} />Belum ada yang diunggah
          </div>
          <p className="bantu" style={helpText}>
            Kuncinya terpasang dan siap, tapi profil ini belum pernah mengunggah
            klip ke YouTube lewat OmniClip. Begitu klip pertama naik dari{' '}
            <Link to="/clips" style={{ color: 'var(--reh)' }}>Klip jadi</Link>,
            angkanya muncul di sini sendiri.
          </p>
        </div>
      )}

      {data && data.terunggah > 0 && (
        <>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <Angka label="Total tayangan" nilai={r?.total ?? 0}
                   nota={`dari ${data.terbaca} klip yang terbaca`} />
            <Angka label="Median per klip" nilai={r?.median ?? '-'}
                   nota="setengah klip di atas angka ini, setengahnya di bawah" />
            <Angka label="Terunggah" nilai={data.terunggah}
                   nota={belumTerbaca > 0 ? `${belumTerbaca} belum terbaca` : 'semuanya terbaca'} />
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
                Kanal {data.kanal.nama}
              </div>
              <div style={{ display: 'flex', gap: '22px', flexWrap: 'wrap',
                            margin: '8px 0 4px' }}>
                <Angka label="Video di kanal" nilai={data.kanal.jumlah_video ?? '-'}
                       nota={data.dari_omniclip !== undefined
                         ? `${data.dari_omniclip} diunggah lewat OmniClip`
                         : ''} />
                <Angka label="Total tayangan kanal"
                       nilai={data.kanal.total_tayangan ?? '-'}
                       nota="seluruh video, sejak kanal dibuat" />
                <Angka label="Pelanggan"
                       nilai={data.kanal.pelanggan_disembunyikan ? 'disembunyikan'
                         : (data.kanal.pelanggan ?? '-')}
                       nota="menurut YouTube" />
              </div>
              <div style={{ marginTop: '14px', paddingTop: '12px',
                            borderTop: '1px solid var(--border-color)' }}>
                <div style={{ fontSize: '0.82rem', fontWeight: 800,
                              marginBottom: '8px' }}>
                  Tambahan tayangan per hari
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
                <b>{belumTerbaca} video belum terbaca angkanya.</b> Kunci API hanya
                bisa membaca video <b>publik</b>. Video yang masih Pribadi atau Tidak
                publik tidak dijawab YouTube sama sekali, dan OmniClip tidak akan
                menampilkannya sebagai nol tayangan. Ubah statusnya jadi publik di
                YouTube Studio, lalu muat ulang halaman ini.
              </div>
            </div>
          )}

          <div style={{ ...card, marginTop: '12px' }}>
            <div style={sectionTitle}>
              <BarChart3 size={18} style={{ color: 'var(--reh)' }} />
              {data.cukup_data ? 'Yang terukur di kanal ini' : 'Yang masih kurang'}
            </div>
            <p className="bantu" style={helpText}>
              {data.cukup_data
                ? 'Tiap temuan di bawah ini dibandingkan antara klip yang kena dan '
                  + 'yang tidak, memakai median tayangan klip Anda sendiri.'
                : `Dengan ${data.terbaca} klip terbaca, belum ada yang bisa `
                  + `dibandingkan. Di bawah ${data.ambang} klip, perbedaan tayangan `
                  + 'antara dua video bisa seluruhnya kebetulan, dan menyajikannya '
                  + 'sebagai sebab akan membuat Anda mengubah hal yang salah. Jadi '
                  + 'yang di bawah ini daftar periksa, bukan penjelasan kenapa '
                  + 'sebuah klip sepi.'}
            </p>
            {data.temuan.length === 0 ? (
              <p style={{ ...helpText, marginTop: '10px' }}>
                Tidak ada satu pun temuan di klip yang sudah diunggah. Yang
                tersisa ada di luar berkas videonya: judul, jam tayang, dan
                seberapa sering kanal ini mengunggah.
              </p>
            ) : (
              <ul style={{ listStyle: 'none', padding: 0, margin: '10px 0 0' }}>
                {data.temuan.map((t) => <Temuan key={t.kode} t={t} />)}
              </ul>
            )}
            <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)',
                        margin: '12px 0 0', lineHeight: 1.55 }}>
              {data.catatan_kaki} Daftar periksa, bukan ramalan: tidak ada yang
              bisa menjamin jangkauan, yang bisa dijaga hanya hal-hal yang
              diketahui membuat penonton pergi.
            </p>
          </div>

          <div style={{ ...card, marginTop: '12px' }}>
            <div style={sectionTitle}>
              <Eye size={18} style={{ color: 'var(--reh)' }} />Klip per klip
            </div>
            <div style={{ overflowX: 'auto', marginTop: '8px' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse',
                              fontSize: '0.78rem' }}>
                <thead>
                  <tr style={{ textAlign: 'left', color: 'var(--text-muted)',
                               fontSize: '0.7rem', textTransform: 'uppercase',
                               letterSpacing: '0.04em' }}>
                    <th style={{ padding: '6px 8px 6px 0' }}>Klip</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right' }}>Tayangan</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right' }}>Suka</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right' }}>Panjang</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right' }}>Daftar periksa</th>
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
                            ? 'diunggah di luar OmniClip'
                            : 'lewat OmniClip'}
                          {k.waktu ? ` · ${String(k.waktu).slice(0, 10)}` : ''}
                        </div>
                        {!k.terbaca && (
                          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                            angkanya tidak terbaca
                            {k.privasi && k.privasi !== 'public'
                              ? `, diunggah sebagai ${k.privasi === 'private' ? 'Pribadi' : 'Tidak publik'}`
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
                        {k.durasi ? `${Math.round(k.durasi)} dtk` : '-'}
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
                           title="Buka di YouTube"
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
              Angka tayangan disimpan lima belas menit sebelum ditanyakan ulang,
              supaya jatah harian kunci API tidak habis hanya karena halaman ini
              dibuka berkali-kali.
            </p>
          </div>
        </>
      )}
    </div>
  );
}
