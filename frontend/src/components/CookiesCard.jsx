import React, { useEffect, useRef, useState } from 'react';
import {
  AlertTriangle, CheckCircle2, Cookie, Info, Loader2, Upload,
} from 'lucide-react';
import { apiDelete, apiGet, apiPost } from '../lib/api';

const NAMA_BROWSER = {
  firefox: 'Firefox', chrome: 'Google Chrome', chromium: 'Chromium',
  brave: 'Brave', edge: 'Microsoft Edge', opera: 'Opera',
  vivaldi: 'Vivaldi', whale: 'Whale', safari: 'Safari',
};

/**
 * Cookies YouTube, diatur dari dalam aplikasi.
 *
 * Versi sebelumnya kartu ini hanya teks: ia menyuruh menyetel variabel
 * lingkungan `OMNICLIP_COOKIES_FILE`. Itu tidak bisa dituruti dari tempat
 * pesannya muncul — variabel lingkungan disetel SEBELUM aplikasi menyala, dan
 * exe yang diklik dua kali tidak pernah melewati terminal.
 *
 * Tombol "Uji sekarang" bukan hiasan. Cookies yang terbaca sempurna tetap bisa
 * menghasilkan nol format yang bisa diunduh, dan satu-satunya cara mengetahuinya
 * adalah meminta YouTube dua kali berdampingan — dengan dan tanpa cookies —
 * saat tombolnya ditekan.
 */
export default function CookiesCard({ card, sectionTitle, helpText }) {
  const [info, setInfo] = useState(null);
  const [sibuk, setSibuk] = useState('');
  const [galat, setGalat] = useState(null);
  const [hasil, setHasil] = useState(null);
  const berkasRef = useRef(null);

  // `periksa=1`: tiap browser DIUJI, bukan sekadar didaftar namanya.
  //
  // Bedanya nyata di Windows. yt-dlp 2026.08.19 belum mengerti app-bound
  // encryption yang dipakai Chrome dan Edge sejak versi 127, jadi browser itu
  // bisa terpasang, pemakainya login, dan pembacaan cookie-nya tetap gagal.
  // Daftar tanpa pengujian menawarkan tombol yang pasti tidak bekerja, lalu
  // membiarkan orangnya menyangka cookies-nya sudah menyala.
  const muat = async () => {
    try { setInfo(await apiGet('/settings/cookies?periksa=1')); }
    catch (err) { setGalat(err.message); }
  };
  useEffect(() => { muat(); }, []);

  /**
   * Menyiapkan browser sebagai CADANGAN, bukan menyalakannya terus-menerus.
   *
   * Ini yang disarankan untuk kebanyakan orang. Terukur 9 Oktober 2026 dari
   * jaringan yang tidak ditandai: tanpa cookies 12 format, dengan cookies 7.
   * Jadi memakainya terus justru mengurangi pilihan resolusi. Yang
   * menyalakannya adalah penolakan pertama dari YouTube.
   */
  const siapkanCadangan = async (nama) => {
    setSibuk('simpan'); setGalat(null); setHasil(null);
    try {
      await apiPost('/settings/cookies/siapkan', { mode: 'browser', browser: nama });
      await muat();
    } catch (err) { setGalat(err.message); } finally { setSibuk(''); }
  };

  const pilihBrowser = async (nama) => {
    setSibuk('simpan'); setGalat(null); setHasil(null);
    try {
      setInfo({ ...(await apiPost('/settings/cookies', { mode: 'browser', browser: nama })),
                browser_tersedia: info.browser_tersedia });
    } catch (err) { setGalat(err.message); } finally { setSibuk(''); }
  };

  const matikan = async () => {
    setSibuk('simpan'); setGalat(null); setHasil(null);
    try {
      setInfo({ ...(await apiDelete('/settings/cookies')),
                browser_tersedia: info.browser_tersedia });
    } catch (err) { setGalat(err.message); } finally { setSibuk(''); }
  };

  const unggah = async (e) => {
    const f = e.target.files?.[0];
    e.target.value = '';
    if (!f) return;
    setSibuk('unggah'); setGalat(null); setHasil(null);
    try {
      const data = new FormData();
      data.append('berkas', f);
      setInfo({ ...(await apiPost('/settings/cookies/berkas', data)),
                browser_tersedia: info.browser_tersedia });
    } catch (err) { setGalat(err.message); } finally { setSibuk(''); }
  };

  const uji = async () => {
    setSibuk('uji'); setGalat(null); setHasil(null);
    try { setHasil(await apiPost('/settings/cookies/uji', {}, { timeout: 120000 })); }
    catch (err) { setGalat(err.message); } finally { setSibuk(''); }
  };

  if (!info) return null;

  const daftar = info.browser_tersedia || [];
  const bagus = hasil && hasil.dengan !== null && hasil.dengan >= hasil.polos && hasil.dengan > 0;

  return (
    <div style={card}>
      <div style={sectionTitle}>
        <Cookie size={18} style={{ color: 'var(--reh)' }} />
        Cookies YouTube
      </div>
      <p className="bantu" style={helpText}>
        Biasanya tidak perlu. Nyalakan bila YouTube terus meminta &ldquo;confirm
        you&rsquo;re not a bot&rdquo; untuk banyak video. Tandanya jaringan Anda
        sedang ditandai, dan sesi login adalah jalan keluarnya.
      </p>

      {/* Peringatan ini ditulis dari pengukuran, bukan dari dugaan, dan
          sengaja berada di ATAS tombolnya, bukan di bawah sebagai catatan
          kaki yang dibaca setelah terlanjur dinyalakan. */}
      <div style={{
        display: 'flex', gap: '9px', alignItems: 'flex-start', margin: '10px 0',
        padding: '10px 12px', borderRadius: 'var(--radius-sm, 8px)', fontSize: '0.76rem',
        lineHeight: 1.55,
        background: 'color-mix(in srgb, var(--warning, #e0a500) 12%, transparent)',
        border: '1px solid color-mix(in srgb, var(--warning, #e0a500) 30%, transparent)',
      }}>
        <Info size={15} style={{ flexShrink: 0, marginTop: '2px' }} />
        <span>
          Pakai browser yang login dengan <strong>akun Google cadangan</strong>,
          bukan akun utama: akun yang dipakai mengunduh bisa ikut ditandai YouTube.
          Cookies tidak pernah keluar dari komputer ini. Tekan &ldquo;Uji
          sekarang&rdquo; untuk membandingkan dengan dan tanpa cookies hari ini.
        </span>
      </div>

      {/* Mode cadangan didahulukan karena ia yang disarankan. Sebelumnya kartu
          ini cuma menawarkan "tanpa cookies" atau "pakai terus", dan yang
          membacanya wajar memilih "pakai terus" lalu kehilangan resolusi. */}
      {daftar.some((b) => !info.diperiksa || b.login) && (
        <div style={{ display: 'flex', gap: '7px', flexWrap: 'wrap',
                      alignItems: 'center', marginBottom: '9px' }}>
          {daftar.filter((b) => !info.diperiksa || b.login).map((b) => (
            <button key={b.nama} className="btn-secondary" disabled={!!sibuk}
                    onClick={() => siapkanCadangan(b.nama)}
                    title="Disimpan sekarang, dikirim hanya saat YouTube menuduh bot"
                    style={{ fontSize: '0.78rem', padding: '6px 11px',
                             borderColor: info.mode === 'mati' && info.siaga === b.nama
                               ? 'var(--accent-cyan)' : undefined,
                             color: info.mode === 'mati' && info.siaga === b.nama
                               ? 'var(--accent-cyan)' : undefined }}>
              Cadangan: {NAMA_BROWSER[b.nama] || b.nama} (disarankan)
            </button>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', gap: '7px', flexWrap: 'wrap', alignItems: 'center' }}>
        <button className="btn-secondary" disabled={!!sibuk} onClick={matikan}
                style={{ fontSize: '0.78rem', padding: '6px 11px',
                         borderColor: info.mode === 'mati' ? 'var(--accent-cyan)' : undefined,
                         color: info.mode === 'mati' ? 'var(--accent-cyan)' : undefined }}>
          Tanpa cookies
        </button>
        {daftar.map((b) => (
          <button key={b.nama} className="btn-secondary"
                  disabled={!!sibuk || (info.diperiksa && !b.login)}
                  title={info.diperiksa && !b.login
                    ? (b.galat || 'Cookies browser ini tidak bisa dibaca.')
                    : 'Pakai sesi dari browser ini pada SETIAP permintaan'}
                  onClick={() => pilihBrowser(b.nama)}
                  style={{ fontSize: '0.78rem', padding: '6px 11px',
                           borderColor: info.mode === 'browser' && info.browser === b.nama
                             ? 'var(--accent-cyan)' : undefined,
                           color: info.mode === 'browser' && info.browser === b.nama
                             ? 'var(--accent-cyan)' : undefined }}>
            {info.diperiksa && b.login
              ? <CheckCircle2 size={12} style={{ color: 'var(--accent-cyan)' }} />
              : null}
            {NAMA_BROWSER[b.nama] || b.nama}
          </button>
        ))}
        <button className="btn-secondary" disabled={!!sibuk}
                onClick={() => berkasRef.current?.click()}
                style={{ fontSize: '0.78rem', padding: '6px 11px',
                         borderColor: info.mode === 'berkas' ? 'var(--accent-cyan)' : undefined,
                         color: info.mode === 'berkas' ? 'var(--accent-cyan)' : undefined }}>
          {sibuk === 'unggah' ? <Loader2 size={13} className="animate-spin" /> : <Upload size={13} />}
          cookies.txt
        </button>
        <input ref={berkasRef} type="file" accept=".txt,text/plain" hidden onChange={unggah} />
      </div>

      {!daftar.length && (
        <p style={{ ...helpText, marginTop: '9px' }}>
          Tidak ada browser yang profilnya terbaca di komputer ini, jadi hanya
          unggah <code>cookies.txt</code> yang tersedia.
        </p>
      )}

      {/* Browser yang ada tapi tidak bisa dipakai, DENGAN alasannya.
          Tombol mati tanpa keterangan hanya memindahkan kebingungannya. */}
      {info.diperiksa && daftar.some((b) => !b.login) && (
        <ul style={{ ...helpText, marginTop: '9px', paddingLeft: '18px' }}>
          {daftar.filter((b) => !b.login).map((b) => (
            <li key={b.nama}>
              {NAMA_BROWSER[b.nama] || b.nama}: {b.galat || 'tidak bisa dibaca'}
            </li>
          ))}
        </ul>
      )}

      <div style={{ display: 'flex', gap: '8px', marginTop: '11px', alignItems: 'center', flexWrap: 'wrap' }}>
        <button className="btn-secondary" disabled={!!sibuk} onClick={uji}
                style={{ fontSize: '0.78rem', padding: '6px 11px' }}>
          {sibuk === 'uji' ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />}
          Uji sekarang
        </button>
        <span style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
          {/* "Siaga" adalah keadaan ketiga, dan tanpa menyebutnya "tanpa
              cookies" terbaca sebagai "tidak ada yang siap". Padahal sesinya
              sudah tersimpan dan akan dinyalakan sendiri begitu YouTube
              menolak dengan tuduhan bot. Lihat `cookies.KUNCI_SIAGA`. */}
          {info.dari_env
            ? 'Dipaksa lewat OMNICLIP_COOKIES_FILE.'
            : info.mode === 'browser' ? `Memakai ${NAMA_BROWSER[info.browser] || info.browser}.`
            : info.mode === 'berkas' ? 'Memakai berkas cookies.txt.'
            : info.siaga ? `Cadangan siap: ${NAMA_BROWSER[info.siaga] || info.siaga}. `
              + 'Dikirim hanya saat YouTube menuduh bot.'
            : 'Sedang tidak memakai cookies.'}
        </span>
      </div>

      {sibuk === 'uji' && (
        <p style={{ ...helpText, marginTop: '9px' }}>
          Meminta dua kali ke YouTube, dengan dan tanpa cookies. Butuh belasan detik.
        </p>
      )}

      {hasil && (
        <div style={{
          marginTop: '11px', padding: '10px 12px', fontSize: '0.78rem', lineHeight: 1.6,
          borderRadius: 'var(--radius-sm, 8px)',
          background: 'var(--plate-3, rgba(255,255,255,0.04))',
          border: '1px solid var(--border-color)',
        }}>
          <div style={{ display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
            {bagus ? <CheckCircle2 size={15} style={{ flexShrink: 0, marginTop: '2px', color: 'var(--entry)' }} />
                   : <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: '2px', color: 'var(--accent-red)' }} />}
            <span>{hasil.saran}</span>
          </div>
          {hasil.dilewati && (
            <div style={{ marginTop: '7px', fontSize: '0.74rem' }}>
              OmniClip sudah <strong>melewati cookies ini sendiri</strong> untuk beberapa jam
              ke depan, karena permintaan tanpa cookies terbukti berhasil sementara yang
              dengan cookies gagal. Tidak ada yang perlu Anda lakukan.
            </div>
          )}
          <div style={{ marginTop: '7px', fontSize: '0.73rem', color: 'var(--text-muted)' }}>
            Format video pada video uji. Tanpa cookies: <strong>{hasil.polos}</strong>
            {hasil.dengan !== null && <> · dengan cookies: <strong>{hasil.dengan}</strong></>}
            {hasil.terbaca > 0 && <> · {hasil.terbaca} butir cookie terbaca</>}
          </div>
        </div>
      )}

      {galat && (
        <div style={{
          display: 'flex', gap: '8px', alignItems: 'center', marginTop: '10px',
          fontSize: '0.78rem', color: 'var(--accent-red)',
        }}>
          <AlertTriangle size={15} style={{ flexShrink: 0 }} /> {galat}
        </div>
      )}
    </div>
  );
}
