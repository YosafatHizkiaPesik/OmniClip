import React, { useEffect, useState } from 'react';
import { Cookie, Loader2, X, CheckCircle2, AlertTriangle } from 'lucide-react';
import { apiGet, apiPost } from '../lib/api';

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
  const [info, setInfo] = useState(null);
  const [sibuk, setSibuk] = useState('');
  const [galat, setGalat] = useState('');
  const [tutup, setTutup] = useState(false);

  useEffect(() => {
    let batal = false;
    // `periksa=1`: menguji tiap browser, bukan mendaftar namanya.
    apiGet('/settings/cookies?periksa=1')
      .then((r) => { if (!batal) setInfo(r); })
      // Pertanyaan yang gagal dimuat tidak boleh menahan halaman utama.
      .catch(() => {});
    return () => { batal = true; };
  }, []);

  if (!info || tutup || info.sudah_ditanya || info.mode !== 'mati') return null;

  const daftar = info.browser_tersedia || [];
  const bisa = daftar.filter((b) => b.login);
  const tidak = daftar.filter((b) => !b.login && b.terpasang);

  const pakai = async (nama) => {
    setSibuk(nama); setGalat('');
    try {
      // Disimpan sebagai SIAGA, bukan dinyalakan. Lihat keterangan di atas
      // dan `cookies.KUNCI_SIAGA` di backend untuk angkanya.
      await apiPost('/settings/cookies/siapkan', { browser: nama });
      setTutup(true);
    } catch (e) {
      setGalat(e?.message || 'Gagal menyimpan pilihan.');
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
            Boleh OmniClip memakai sesi YouTube Anda bila diperlukan?
          </div>
          <p style={{ fontSize: '.8rem', color: 'var(--ink-2)', lineHeight: 1.6, margin: '0 0 10px' }}>
            Suatu saat YouTube bisa menandai jaringan Anda sebagai bot, dan
            tanda itu menghentikan pengunduhan sampai ada sesi login yang bisa
            dipakai. Kalau Anda izinkan, OmniClip menyimpan nama browser Anda
            sebagai cadangan dan <b>baru membaca sesinya saat YouTube mulai
            menolak</b>, bukan setiap saat.
          </p>
          <ul style={{ fontSize: '.76rem', color: 'var(--ink-2)', lineHeight: 1.6,
                       margin: '0 0 10px', paddingLeft: 18 }}>
            <li>Cookies dibaca dari browser <b>di komputer ini</b> dan hanya
                dikirim ke YouTube. Tidak ke server kami, tidak ke mana pun.</li>
            <li>Yang terbaca adalah sesi login Google Anda, jadi sebaiknya pakai
                <b> akun cadangan</b>: akun yang dipakai mengunduh bisa ikut
                ditandai YouTube.</li>
            <li>Tidak dipakai terus-menerus, dan itu demi Anda. Diukur 9 Oktober
                2026 dari jaringan sehat: tanpa cookies 12 pilihan resolusi,
                dengan cookies hanya 7.</li>
            <li>Bisa dicabut kapan saja di Pengaturan, bagian Cookies YouTube.</li>
          </ul>

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
                    Izinkan, pakai {NAMA[b.nama] || b.nama}
                  </button>
                ))}
              </div>
              <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', margin: '0 0 8px' }}>
                {bisa.length === 1 ? 'Browser ini' : 'Browser di atas'} sedang
                login ke YouTube. Sebaiknya pakai akun Google cadangan, bukan
                akun utama: akun yang dipakai mengunduh bisa ikut ditandai.
              </p>
            </>
          ) : (
            <p style={{ fontSize: '.78rem', color: 'var(--ink-2)', lineHeight: 1.6,
                        margin: '0 0 8px' }}>
              Belum ada browser di komputer ini yang bisa dipakai. Buka YouTube
              di <b>Firefox</b> dan login di sana, lalu segarkan halaman ini.
              Firefox disebut secara khusus karena sesinya memang bisa dibaca:
              Chrome dan Edge versi baru di Windows mengunci cookie-nya dengan
              cara yang belum bisa dibuka alat yang kami pakai.
            </p>
          )}

          {tidak.length > 0 && (
            <ul style={{ fontSize: '.72rem', color: 'var(--ink-3)', lineHeight: 1.55,
                         margin: '0 0 8px', paddingLeft: 18 }}>
              {tidak.map((b) => (
                <li key={b.nama}>
                  <AlertTriangle size={11} style={{ verticalAlign: '-1px', marginRight: 4 }} />
                  {NAMA[b.nama] || b.nama}: {b.galat || 'tidak bisa dibaca'}
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
            <X size={13} /> {bisa.length ? 'Jangan, tanpa cookies saja' : 'Nanti saja'}
          </button>
          <p style={{ fontSize: '.7rem', color: 'var(--ink-3)', margin: '8px 0 0' }}>
            Sampai Anda menekan salah satu tombol di atas, tidak ada cookies
            yang dibaca maupun disimpan.
          </p>
        </div>
      </div>
    </div>
  );
}
