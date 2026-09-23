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
export default function TambahAkun({ card, sectionTitle, helpText, onSelesai }) {
  const [status, setStatus] = useState(null);
  const [buka, setBuka] = useState(false);
  const [sibuk, setSibuk] = useState(false);
  const [galat, setGalat] = useState(null);
  const [menunggu, setMenunggu] = useState(false);   // tab izin Google terbuka
  const [salin, setSalin] = useState(false);
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
          <UserPlus size={18} style={{ color: 'var(--reh)' }} />
          Selesaikan di tab Google
        </div>
        <p style={helpText}>
          Pilih akun Google yang ingin Anda tambahkan, lalu izinkan OmniClip
          mengunggah. Setelah halaman Google mengatakan berhasil, kembali ke sini
          dan tekan tombol di bawah — akunnya akan muncul dengan nama surelnya
          sendiri.
        </p>
        <button className="btn-primary" style={{ marginTop: '12px' }}
                onClick={() => (onSelesai ? onSelesai() : window.location.reload())}>
          Saya sudah selesai
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
            Aplikasi Google Anda sudah terdaftar, jadi langkah ini tinggal diulang
            untuk tiap akun baru.
          </p>
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
              unggah YouTube dihitung per aplikasi — itulah sebabnya OmniClip
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
                Di <b>OAuth consent screen</b>, pilih <b>External</b>, isi nama aplikasi
                dan surel Anda. Pada bagian <b>Test users</b>, tambahkan setiap alamat
                Gmail yang akan Anda pakai di OmniClip — tanpa itu Google menolak
                akun tersebut saat login.
              </li>
              <li>
                Di <b>Credentials → Create credentials → OAuth client ID</b>, pilih
                jenis <b>Desktop app</b>. Kalau Anda memilih <b>Web application</b>,
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

      {galat && (
        <div style={{ ...helpText, marginTop: '10px', color: 'var(--accent-red)',
                      display: 'flex', alignItems: 'center', gap: '7px' }}>
          <AlertTriangle size={15} />{galat}
        </div>
      )}
    </div>
  );
}
