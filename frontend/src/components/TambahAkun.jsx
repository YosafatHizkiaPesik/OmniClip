import React, { useEffect, useRef, useState } from 'react';
import {
  AlertTriangle, Check, ChevronRight, Copy, ExternalLink, Loader2, Plus, UserPlus,
} from 'lucide-react';
import { apiGet, apiPost, setProfilAktif } from '../lib/api';

/**
 * Menambah akun: masuk dengan Google, sekali jalan.
 *
 * Sebelum ini yang ada di halaman ini adalah "tambah profil" — sebuah kotak
 * nama dan sebuah tombol. Pemiliknya menanyakan hal yang benar: di mana
 * menambahkan AKUN? Sebuah profil tanpa akun tidak bisa mengunggah apa pun,
 * jadi memisahkan keduanya hanya memindahkan pekerjaan ke orangnya.
 *
 * Sekarang satu tombol mengerjakan keduanya: akunnya dibuat, izin Google
 * diminta atas nama akun itu, dan namanya diambil dari alamat surelnya
 * sendiri. Yang tersisa untuk pemiliknya cuma memilih akun di halaman Google.
 *
 * Yang TIDAK bisa dihilangkan adalah pendaftaran aplikasi di Google Cloud.
 * Google hanya menerima unggahan dari aplikasi terdaftar, dan kuota unggah
 * YouTube dihitung per aplikasi — memakai kunci bersama berarti kuota satu
 * orang menghabiskan kuota semua orang. Itu sekali seumur hidup, dan
 * langkahnya ditulis di sini apa adanya, bukan ditunjuk ke dokumentasi.
 */
// Tiga izin yang diminta OmniClip, dalam bentuk yang bisa ditempel apa adanya
// ke kotak "Manually add scopes" di Google Cloud Console. Cermin dari `SCOPES`
// di backend/app/services/google_upload.py; `openid` tidak ikut karena Google
// memberikannya sendiri dan kotak itu hanya menerima alamat https.
const SCOPES_TEKS = [
  'https://www.googleapis.com/auth/youtube.upload',
  'https://www.googleapis.com/auth/drive.file',
  'https://www.googleapis.com/auth/userinfo.email',
].join('\n');

export default function TambahAkun({ card, sectionTitle, helpText, onSelesai }) {
  const [status, setStatus] = useState(null);
  const [buka, setBuka] = useState(false);
  const [sibuk, setSibuk] = useState(false);
  const [galat, setGalat] = useState(null);
  const [menunggu, setMenunggu] = useState(false);   // tab izin Google terbuka

  // Tab izin Google mengabarkan dirinya selesai lalu menutup sendiri (lihat
  // `_page` di backend/app/routers/uploads.py). Tanpa ini, satu-satunya cara
  // melanjutkan adalah menekan tombol "Saya sudah selesai", dan pertanyaan
  // "kenapa saya yang harus menekannya?" tidak punya jawaban yang memuaskan.
  useEffect(() => {
    const dengar = (e) => {
      if (e.origin !== window.location.origin) return;
      if (e.data !== 'omniclip:google-tersambung') return;
      if (onSelesai) onSelesai(); else window.location.reload();
    };
    window.addEventListener('message', dengar);
    return () => window.removeEventListener('message', dengar);
  }, [onSelesai]);
  const [salin, setSalin] = useState(false);
  const [salinS, setSalinS] = useState(false);
  const berkasRef = useRef(null);

  const muat = () => apiGet('/uploads/google/status').then(setStatus).catch(() => setStatus({}));
  useEffect(() => { muat(); }, []);

  const pasangBerkas = async (e) => {
    const f = e.target.files?.[0];
    e.target.value = '';
    if (!f) return;
    setSibuk(true);
    setGalat(null);
    try {
      await apiPost('/uploads/google/client', await f.text(), { raw: true });
      await muat();
    } catch (err) {
      setGalat(err.message);
    } finally {
      setSibuk(false);
    }
  };

  /** Membuat akun baru lalu langsung meminta izin Google atas namanya. */
  const masuk = async () => {
    setSibuk(true);
    setGalat(null);
    try {
      const p = await apiPost('/profil', { nama: 'Akun baru', minat: [] });
      // Sejak baris ini, semua permintaan berjalan atas nama akun yang baru —
      // termasuk permintaan izin di bawahnya, yang membuat tokennya tersimpan
      // ke akun yang benar.
      setProfilAktif(p.id);
      const r = await apiPost('/uploads/google/connect', {});
      window.open(r.authorization_url, '_blank', 'noopener');
      setMenunggu(true);
    } catch (err) {
      setGalat(err.message);
    } finally {
      setSibuk(false);
    }
  };

  const salinScopes = async () => {
    try {
      await navigator.clipboard.writeText(SCOPES_TEKS);
      setSalinS(true);
      setTimeout(() => setSalinS(false), 1800);
    } catch {
      setGalat('Peramban tidak mengizinkan menyalin. Tandai teksnya dan salin sendiri.');
    }
  };

  const salinAlamat = async () => {
    try {
      await navigator.clipboard.writeText(status?.redirect_uri || '');
      setSalin(true);
      setTimeout(() => setSalin(false), 1800);
    } catch {
      setGalat('Peramban tidak mengizinkan menyalin. Tandai teksnya dan salin sendiri.');
    }
  };

  const siap = !!status?.client_configured;

  if (menunggu) {
    return (
      <div style={card}>
        <div style={sectionTitle}>
          <Loader2 size={18} className="animate-spin" style={{ color: 'var(--reh)' }} />
          Menunggu izin dari Google
        </div>
        <p style={helpText}>
          Pilih akun Google yang ingin Anda tambahkan di tab sebelah, lalu
          izinkan OmniClip mengunggah. Halaman ini akan memperbarui dirinya
          sendiri begitu Google selesai, dan akunnya muncul dengan nama surelnya.
        </p>
        {/* Tombolnya tetap ada, tapi sebagai jalan keluar, bukan sebagai
            langkah. Tab izin bisa saja dibuka di jendela lain atau ditutup
            sebelum sempat mengabarkan, dan dalam keadaan itu satu-satunya cara
            maju adalah menekan sesuatu. */}
        <button className="btn-secondary" style={{ marginTop: '12px' }}
                onClick={() => (onSelesai ? onSelesai() : window.location.reload())}>
          Tidak berpindah sendiri? Segarkan sekarang
        </button>
      </div>
    );
  }

  return (
    <div style={card}>
      <div style={sectionTitle}>
        <UserPlus size={18} style={{ color: 'var(--reh)' }} />
        Tambah akun
      </div>
      <p style={helpText}>
        Tiap akun punya folder klip, riwayat pencarian, beranda, dan kanal
        YouTube-nya sendiri. Menambah akun berarti masuk dengan akun Google lain.
      </p>

      {siap ? (
        <>
          <button className="btn-primary" onClick={masuk} disabled={sibuk}
                  style={{ marginTop: '12px', display: 'inline-flex', gap: '7px',
                           alignItems: 'center' }}>
            {sibuk ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
            Masuk dengan Google
          </button>
          <p style={{ ...helpText, marginTop: '10px' }}>
            {status?.client_bawaan
              ? 'OmniClip sudah membawa identitas aplikasinya sendiri, jadi tidak '
                + 'ada yang perlu didaftarkan. Langkah ini tinggal diulang untuk '
                + 'tiap akun baru.'
              : 'Aplikasi Google Anda sudah terdaftar, jadi langkah ini tinggal '
                + 'diulang untuk tiap akun baru.'}
          </p>
          {/* Jalan memakai project sendiri tetap ada, dan bukan sekadar
              kelengkapan: kuota Google dihitung per project, jadi pemilik yang
              mendaftarkan projectnya sendiri berhenti berbagi jatah dengan
              semua pemakai OmniClip yang lain. */}
          {status?.client_bawaan && (
            <p style={{ ...helpText, marginTop: '6px' }}>
              Punya project Google sendiri dan ingin jatah unggah terpisah?{' '}
              <button onClick={() => setBuka((v) => !v)}
                      style={{ background: 'none', border: 0, padding: 0,
                               cursor: 'pointer', color: 'var(--reh)',
                               font: 'inherit' }}>
                Pasang berkas OAuth sendiri
              </button>.
            </p>
          )}
        </>
      ) : (
        <>
          <div style={{
            marginTop: '12px', padding: '10px 12px', borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-color)', background: 'var(--hl-wash)',
          }}>
            <div style={{ fontSize: '0.8rem', fontWeight: 800, marginBottom: '4px' }}>
              Sebelum akun pertama: daftarkan aplikasinya
            </div>
            <p style={{ ...helpText, margin: 0 }}>
              Google hanya menerima unggahan dari aplikasi terdaftar, dan kuota
              unggah YouTube dihitung per aplikasi. Itulah sebabnya OmniClip
              tidak membawa kunci bawaan. Dikerjakan <b>sekali saja</b>, gratis,
              sekitar sepuluh menit. Sesudah itu Anda tinggal menekan "Masuk
              dengan Google" untuk akun kedua, ketiga, dan seterusnya.
            </p>
          </div>

          <button onClick={() => setBuka((v) => !v)}
                  style={{
                    marginTop: '10px', display: 'flex', alignItems: 'center', gap: '6px',
                    background: 'none', border: 'none', padding: '4px 0', cursor: 'pointer',
                    fontSize: '0.78rem', fontWeight: 800, fontFamily: 'inherit',
                    color: 'var(--reh)',
                  }}>
            <ChevronRight size={14} style={{
              transform: buka ? 'rotate(90deg)' : 'none', transition: 'transform 120ms' }} />
            {buka ? 'Sembunyikan langkahnya' : 'Tunjukkan langkahnya'}
          </button>

          {buka && (
            <ol style={{ ...helpText, margin: '8px 0 0', paddingLeft: '18px', lineHeight: 1.75 }}>
              <li>
                Buka{' '}
                <a href="https://console.cloud.google.com/projectcreate" target="_blank"
                   rel="noreferrer" style={{ color: 'var(--reh)' }}>
                  console.cloud.google.com <ExternalLink size={11} style={{ verticalAlign: '-1px' }} />
                </a>{' '}
                dan buat satu project. Namanya bebas, misalnya <b>OmniClip</b>.
              </li>
              <li>
                Di menu <b>APIs &amp; Services → Library</b>, cari dan nyalakan{' '}
                <b>YouTube Data API v3</b> dan <b>Google Drive API</b>.
              </li>
              <li>
                Buka <b>Google Auth Platform</b> (nama baru "OAuth consent
                screen"), lalu isi tiga bagiannya:
                <ul style={{ paddingLeft: '16px', margin: '4px 0 0' }}>
                  <li><b>Branding</b>: nama aplikasi dan surel dukungan.</li>
                  <li><b>Audience</b>: pilih <b>External</b>. Di halaman yang
                    sama, bagian <b>Test users → Add users</b>, tambahkan setiap
                    alamat Gmail yang akan Anda pakai di OmniClip. Tanpa itu
                    Google menolak akun tersebut saat login, dengan pesan yang
                    tidak menyebut sebabnya.</li>
                  <li><b>Data access → Add or remove scopes</b>. Daftarnya
                    panjang dan tidak punya kotak cari, jadi jangan dicari satu
                    per satu: gulir ke bawah sampai <b>Manually add scopes</b>,
                    lalu tempel tiga baris ini sekaligus dan tekan{' '}
                    <b>Add to table</b>:
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '7px',
                                  marginTop: '5px' }}>
                      <code style={{ fontSize: '0.67rem', lineHeight: 1.6,
                                     wordBreak: 'break-all' }}>{SCOPES_TEKS}</code>
                      <button onClick={salinScopes} title="Salin ketiganya"
                              style={{ background: 'none', border: 'none', cursor: 'pointer',
                                       color: 'var(--text-secondary)', display: 'flex' }}>
                        {salinS ? <Check size={13} style={{ color: 'var(--entry)' }} />
                                : <Copy size={13} />}
                      </button>
                    </div>
                  </li>
                </ul>
              </li>
              <li>
                Di <b>Clients → Create client</b> (dulu "Credentials → OAuth
                client ID"), pilih jenis <b>Desktop app</b>. Kalau Anda memilih{' '}
                <b>Web application</b>,
                tambahkan alamat ini ke <b>Authorized redirect URIs</b>:
                <div style={{ display: 'flex', alignItems: 'center', gap: '7px', marginTop: '5px' }}>
                  <code style={{ fontSize: '0.7rem', wordBreak: 'break-all' }}>
                    {status?.redirect_uri || '…'}
                  </code>
                  <button onClick={salinAlamat} title="Salin alamat"
                          style={{ background: 'none', border: 'none', cursor: 'pointer',
                                   color: 'var(--text-secondary)', display: 'flex' }}>
                    {salin ? <Check size={13} style={{ color: 'var(--entry)' }} /> : <Copy size={13} />}
                  </button>
                </div>
              </li>
              <li>
                Unduh berkas JSON-nya, lalu pasang di bawah ini.
              </li>
            </ol>
          )}

          <div style={{ marginTop: '12px' }}>
            <input ref={berkasRef} type="file" accept="application/json,.json"
                   onChange={pasangBerkas} style={{ display: 'none' }} />
            <button className="btn-primary" disabled={sibuk}
                    onClick={() => berkasRef.current?.click()}
                    style={{ display: 'inline-flex', gap: '7px', alignItems: 'center' }}>
              {sibuk ? <Loader2 size={15} className="animate-spin" /> : null}
              Pasang berkas OAuth client
            </button>
          </div>
        </>
      )}

      {/* Jalur project sendiri, saat identitas bawaan sedang dipakai. Sama
          persis dengan yang di atas, hanya dibuka atas permintaan: yang
          membukanya orang yang memang ingin jatah unggahnya terpisah. */}
      {siap && status?.client_bawaan && buka && (
        <div style={{ marginTop: '12px' }}>
          <p style={{ ...helpText, margin: '0 0 8px' }}>
            Kuota unggah YouTube dihitung per project Google. Dengan project
            sendiri, jatah Anda tidak dibagi dengan pemakai OmniClip yang lain.
            Langkahnya ada di{' '}
            <a href="https://console.cloud.google.com/auth/clients" target="_blank"
               rel="noreferrer" style={{ color: 'var(--reh)' }}>
              Google Cloud Console <ExternalLink size={11} style={{ verticalAlign: '-1px' }} />
            </a>{' '}
            (jenis <b>Desktop app</b>), lalu pasang JSON-nya di sini.
          </p>
          <input ref={berkasRef} type="file" accept="application/json,.json"
                 onChange={pasangBerkas} style={{ display: 'none' }} />
          <button className="btn-secondary" disabled={sibuk}
                  onClick={() => berkasRef.current?.click()}
                  style={{ display: 'inline-flex', gap: '7px', alignItems: 'center' }}>
            {sibuk ? <Loader2 size={15} className="animate-spin" /> : null}
            Pasang berkas OAuth client
          </button>
        </div>
      )}

      {galat && (
        <div style={{ ...helpText, marginTop: '10px', color: 'var(--accent-red)',
                      display: 'flex', alignItems: 'center', gap: '7px' }}>
          <AlertTriangle size={15} />{galat}
        </div>
      )}
    </div>
  );
}
