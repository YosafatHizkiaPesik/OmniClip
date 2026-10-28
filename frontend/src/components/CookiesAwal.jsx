import React, { useEffect, useState } from 'react';
import { Cookie, Loader2, X, CheckCircle2, AlertTriangle } from 'lucide-react';
import { apiGet, apiPost } from '../lib/api';
import { tebal, useT } from '../lib/i18n';

/**
 * Pertanyaan cookies, sekali saja, di tempat orangnya memang berada.
 *
 * Kenapa ada: sampai 9 Oktober 2026 cookies bawaannya MATI dan satu-satunya
 * cara menyalakannya ada di Pengaturan, di kartu yang harus ditemukan sendiri.
 * Seorang pengguna Windows mengklip sebulan penuh tanpa pernah membukanya,
 * lalu YouTube menandai jaringannya sebagai bot. Sepanjang bulan itu OmniClip
 * memang mengirim permintaan tanpa sesi login sama sekali.
 *
 * Kartu ini MEMINTA IZIN, dan itu bukan formalitas. Membaca basis data cookie
 * sebuah browser berarti memegang sesi Google seseorang, dan mengirimnya ke
 * YouTube berarti permintaan OmniClip berjalan atas nama akun itu. Versi
 * sebelum ini menyimpannya diam-diam begitu menemukan browser yang login, dan
 * itu salah: ditanyakan pemiliknya 9 Oktober 2026, "apakah diawal menjalankan
 * sistem ada pemberitahuan persetujuan untuk menggunakan cookies atau tidak".
 *
 * Jadi tidak ada yang tersimpan sebelum tombol di kartu ini ditekan. Kartunya
 * muncul sekali, dan jawaban apa pun, termasuk "Nanti saja", menutupnya untuk
 * selamanya.
 *
 * Nama browser TIDAK dipakai untuk menebak. Daftar di sini hasil pengujian
 * sungguhan per browser, karena di Windows yt-dlp belum mengerti app-bound
 * encryption milik Chrome dan Edge sejak versi 127: browsernya terpasang,
 * pemakainya login, dan pembacaan cookie-nya tetap gagal. Browser seperti itu
 * ditampilkan dengan alasannya, bukan ditawarkan lalu gagal diam-diam.
 */

const NAMA = {
  firefox: 'Firefox', chrome: 'Chrome', chromium: 'Chromium', brave: 'Brave',
  edge: 'Edge', opera: 'Opera', vivaldi: 'Vivaldi', safari: 'Safari',
};

export default function CookiesAwal() {
  const t = useT();
  const [info, setInfo] = useState(null);
  const [sibuk, setSibuk] = useState('');
  const [galat, setGalat] = useState('');
  const [tutup, setTutup] = useState(false);
  const [memeriksa, setMemeriksa] = useState(true);

  useEffect(() => {
    let batal = false;
    // Dua langkah. Daftar nama browser dulu (seketika), supaya kartunya
    // langsung tampil; pengujian tiap browser (`periksa=1`) menyusul.
    //
    // Dulu hanya langkah kedua, dengan batas 30 detik, dan galatnya ditelan.
    // Di Windows menguji Chrome dan Edge bisa jauh lebih lama dari itu, jadi
    // pada pemasangan baru kartunya bisa TIDAK PERNAH muncul. Dilaporkan
    // pemiliknya 28 Oktober 2026: "saat pertama kali menggunakan app mengapa
    // tidak ada alert atau apapun yang meminta cookies".
    apiGet('/settings/cookies')
      .then((r) => { if (!batal) setInfo((lama) => lama ?? r); })
      .catch(() => {});
    apiGet('/settings/cookies?periksa=1', { timeout: 180000 })
      .then((r) => { if (!batal) setInfo(r); })
      .catch(() => {})
      .finally(() => { if (!batal) setMemeriksa(false); });
    return () => { batal = true; };
  }, []);

  if (!info || tutup || info.sudah_ditanya || info.mode !== 'mati') return null;

  const daftar = info.browser_tersedia || [];
  // Sebelum hasil pengujian datang, browser yang terpasang ditawarkan apa
  // adanya; pengujian sesungguhnya tetap terjadi saat tombolnya ditekan
  // (`/cookies/siapkan` menolak browser yang tidak login).
  const bisa = info.diperiksa ? daftar.filter((b) => b.login)
    : daftar.filter((b) => b.terpasang !== false);
  const tidak = info.diperiksa ? daftar.filter((b) => !b.login && b.terpasang) : [];

  const pakai = async (nama) => {
    setSibuk(nama); setGalat('');
    try {
      // Disimpan sebagai SIAGA, bukan dinyalakan. Lihat keterangan di atas
      // dan `cookies.KUNCI_SIAGA` di backend untuk angkanya.
      await apiPost('/settings/cookies/siapkan', { browser: nama });
      setTutup(true);
    } catch (e) {
      setGalat(e?.message || t('ca.gagal'));
    } finally { setSibuk(''); }
  };

  const nanti = async () => {
    setSibuk('nanti');
    try { await apiPost('/settings/cookies/lewati', {}); } catch { /* diabaikan */ }
    setTutup(true);
  };

  return (
    <div className="card" style={{ marginBottom: 16, borderColor: 'var(--accent-cyan)' }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
        <Cookie size={18} style={{ color: 'var(--accent-cyan)', flexShrink: 0, marginTop: 2 }} />
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>
            {t('ca.tanya')}
          </div>
          <p style={{ fontSize: '.8rem', color: 'var(--ink-2)', lineHeight: 1.6, margin: '0 0 10px' }}>
            {tebal(t('ca.ket'))}
          </p>
          <ul style={{ fontSize: '.76rem', color: 'var(--ink-2)', lineHeight: 1.6,
                       margin: '0 0 10px', paddingLeft: 18 }}>
            {['ca.p1', 'ca.p2', 'ca.p3', 'ca.p4'].map((k) => <li key={k}>{tebal(t(k))}</li>)}
          </ul>

          {memeriksa && (
            <p style={{ fontSize: '.74rem', color: 'var(--ink-3)', margin: '0 0 8px',
                        display: 'flex', gap: 6, alignItems: 'center' }}>
              <Loader2 size={12} className="animate-spin" /> {t('ca.memeriksa')}
            </p>
          )}
          {bisa.length > 0 ? (
            <>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
                {bisa.map((b) => (
                  <button key={b.nama} className="btn-primary" disabled={!!sibuk}
                          style={{ fontSize: '.78rem' }}
                          onClick={() => pakai(b.nama)}>
                    {sibuk === b.nama
                      ? <Loader2 size={13} className="animate-spin" />
                      : <CheckCircle2 size={13} />}
                    {t('ca.izinkan', { browser: NAMA[b.nama] || b.nama })}
                  </button>
                ))}
              </div>
              <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', margin: '0 0 8px' }}>
                {t(bisa.length === 1 ? 'ca.satu' : 'ca.banyak')}
              </p>
            </>
          ) : (
            <p style={{ fontSize: '.78rem', color: 'var(--ink-2)', lineHeight: 1.6,
                        margin: '0 0 8px' }}>
              {tebal(t('ca.belum'))}
            </p>
          )}

          {tidak.length > 0 && (
            <ul style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.55,
                         margin: '0 0 8px', paddingLeft: 18 }}>
              {tidak.map((b) => (
                <li key={b.nama}>
                  <AlertTriangle size={11} style={{ verticalAlign: '-1px', marginRight: 4 }} />
                  {NAMA[b.nama] || b.nama}: {b.galat || t('ck.tak_terbaca_pendek')}
                </li>
              ))}
            </ul>
          )}

          {galat && (
            <div style={{ fontSize: '.75rem', color: 'var(--danger)', marginBottom: 6 }}>
              {galat}
            </div>
          )}

          <button className="btn-secondary" style={{ fontSize: '.75rem' }}
                  disabled={!!sibuk} onClick={nanti}>
            <X size={13} /> {bisa.length ? t('ca.jangan') : t('ca.nanti')}
          </button>
          <p style={{ fontSize: '.7rem', color: 'var(--ink-3)', margin: '8px 0 0' }}>
            {t('ca.catatan')}
          </p>
        </div>
      </div>
    </div>
  );
}
