import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  UploadCloud, CheckCircle2, Loader2, AlertTriangle, Info, LogOut, ExternalLink,
} from 'lucide-react';
import { apiGet, apiPost } from '../lib/api';

/**
 * Menyambungkan akun Google untuk mengunggah klip.
 *
 * Yang dipasang di sini adalah berkas OAuth client milik pengguna sendiri,
 * bukan kunci milik OmniClip: aplikasi ini berjalan di komputer satu orang,
 * dan kuota unggah YouTube dihitung per project Google Cloud. Memakai satu
 * kunci bersama berarti kuota satu orang menghabiskan kuota semua orang.
 *
 * Berkas rahasianya tidak pernah dikirim balik ke browser. Yang dijawab server
 * hanya "sudah tersambung atau belum" dan alamat surel akunnya.
 */
export default function GoogleAccountCard({ card, sectionTitle, helpText }) {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [note, setNote] = useState(null);
  const fileRef = useRef(null);

  const refresh = useCallback(async () => {
    try {
      setStatus(await apiGet('/uploads/google/status'));
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  // Setelah izin diberikan di tab lain, tab ini tidak tahu apa-apa sampai
  // seseorang memuat ulang. Memeriksa saat jendela kembali fokus menutup jarak
  // itu tanpa memaksa pengguna menekan apa pun.
  useEffect(() => {
    const onFocus = () => refresh();
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [refresh]);

  const pickFile = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setBusy(true); setError(null); setNote(null);
    try {
      const text = await file.text();
      const res = await apiPost('/uploads/google/client', text, { raw: true });
      setNote(res.redirect_uri_needed
        ? 'Berkas tersimpan. Karena ini OAuth client jenis Web, tambahkan alamat '
          + 'pengalihan di bawah ke daftar Authorized redirect URIs di Cloud Console.'
        : 'Berkas tersimpan. Sekarang sambungkan akun Anda.');
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const connect = async () => {
    setBusy(true); setError(null); setNote(null);
    try {
      const { authorization_url: url } = await apiPost('/uploads/google/connect', {});
      window.open(url, '_blank', 'noopener');
      setNote('Halaman izin Google terbuka di tab baru. Selesaikan di sana, lalu '
        + 'kembali ke sini — status di bawah akan ikut berubah.');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true); setError(null); setNote(null);
    try {
      await apiPost('/uploads/google/disconnect', {});
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div style={card}>
      <div style={sectionTitle}>
        <UploadCloud size={18} style={{ color: 'var(--reh)' }} />
        Unggah ke Google Drive &amp; YouTube
      </div>
      <p style={helpText}>
        Klip yang sudah jadi bisa dikirim langsung ke Drive atau naik sebagai
        video di kanal Anda — satu per satu, tidak pernah berombongan.
      </p>

      {!status ? (
        <div style={{ ...helpText, display: 'flex', gap: '8px', alignItems: 'center', marginTop: '12px' }}>
          <Loader2 size={15} className="animate-spin" /> Membaca status…
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '14px' }}>
          <StatusLine
            ok={status.client_configured}
            okText="Berkas OAuth client terpasang."
            offText="Belum ada berkas OAuth client." />
          <StatusLine
            ok={status.connected}
            okText={`Tersambung${status.email ? ` sebagai ${status.email}` : ''}.`}
            offText="Akun Google belum tersambung." />

          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            <input ref={fileRef} type="file" accept="application/json,.json"
                   onChange={pickFile} style={{ display: 'none' }} />
            <button className="btn-secondary" disabled={busy}
                    onClick={() => fileRef.current?.click()}>
              {busy ? <Loader2 size={14} className="animate-spin" /> : null}
              {status.client_configured ? 'Ganti berkas client' : 'Pasang berkas client'}
            </button>
            {status.client_configured && !status.connected && (
              <button className="btn-primary" disabled={busy} onClick={connect}>
                <ExternalLink size={14} /> Sambungkan akun Google
              </button>
            )}
            {status.connected && (
              <button className="btn-secondary" disabled={busy} onClick={disconnect}>
                <LogOut size={14} /> Putuskan sambungan
              </button>
            )}
          </div>

          {note && (
            <div style={{ ...helpText, display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
              <Info size={15} style={{ color: 'var(--cue)', flexShrink: 0, marginTop: '2px' }} />
              <span>{note}</span>
            </div>
          )}
          {error && (
            <div style={{ ...helpText, display: 'flex', gap: '8px', alignItems: 'flex-start',
                          color: 'var(--danger)' }}>
              <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: '2px' }} />
              <span>{error}</span>
            </div>
          )}

          <details style={{ fontSize: '.8rem', color: 'var(--ink-2)' }}>
            <summary style={{ cursor: 'pointer', fontWeight: 650, color: 'var(--ink)' }}>
              Cara mendapatkan berkas OAuth client
            </summary>
            <ol style={{ margin: '10px 0 0', paddingLeft: '20px', lineHeight: 1.7 }}>
              <li>Buka <b>console.cloud.google.com</b>, buat satu project.</li>
              <li>APIs &amp; Services → Library → aktifkan <b>YouTube Data API v3</b>
                {' '}dan <b>Google Drive API</b>.</li>
              <li>OAuth consent screen: pilih External, isi seadanya, lalu tambahkan
                akun Google Anda sendiri sebagai <b>Test user</b>. Selama aplikasinya
                masih berstatus Testing, hanya akun yang terdaftar di situ yang bisa
                memberi izin.</li>
              <li>Credentials → Create credentials → OAuth client ID → jenis
                <b> Desktop app</b> (paling sederhana), lalu unduh JSON-nya.</li>
              <li>Kalau Anda memilih jenis <b>Web application</b>, tambahkan alamat
                ini ke Authorized redirect URIs:</li>
            </ol>
            <code style={{
              display: 'block', marginTop: '8px', padding: '8px 10px', fontSize: '.74rem',
              background: 'var(--plate-2)', border: '1px solid var(--rule-2)',
              borderRadius: 'var(--r-sm)', wordBreak: 'break-all',
            }}>{status.redirect_uri}</code>
            <p style={{ marginTop: '10px', lineHeight: 1.6 }}>
              Kuota unggah YouTube lewat API terbatas per hari dan per project —
              biasanya cukup untuk beberapa video sehari, bukan puluhan. Karena
              itu OmniClip mengunggah satu per satu
              {status.gap_seconds > 0 && `, dengan jeda ${status.gap_seconds} detik antar video`}.
            </p>
          </details>
        </div>
      )}
    </div>
  );
}

function StatusLine({ ok, okText, offText }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '0.84rem' }}>
      {ok
        ? <CheckCircle2 size={15} style={{ color: 'var(--entry)', flexShrink: 0 }} />
        : <Info size={15} style={{ color: 'var(--ink-3)', flexShrink: 0 }} />}
      <span style={{ color: ok ? 'var(--ink)' : 'var(--ink-2)' }}>{ok ? okText : offText}</span>
    </div>
  );
}
