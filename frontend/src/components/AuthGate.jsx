import React, { useCallback, useEffect, useState } from 'react';
import { KeyRound, Loader2, Lock, ShieldCheck, Eye, EyeOff, AlertTriangle } from 'lucide-react';
import { apiGet, apiPost } from '../lib/api';

/**
 * Pintu di depan seluruh aplikasi.
 *
 * Tiga keadaan yang mungkin, dan ketiganya sengaja terlihat berbeda:
 *
 *   - gerbang mati        -> tidak ada yang ditampilkan, aplikasi langsung jalan
 *   - belum ada kata sandi -> layar PEMASANGAN, sekali seumur hidup instalasi
 *   - ada kata sandi       -> layar masuk
 *
 * Layar pemasangan penting justru karena ia mudah dilewatkan: tanpa itu, cara
 * memasang kata sandi pertama adalah menyunting basis data, dan orang yang
 * tidak bisa melakukannya akan menerbitkan aplikasi tanpa kata sandi.
 */
export default function AuthGate({ children }) {
  const [state, setState] = useState(null); // null = belum tahu
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    try {
      setState(await apiGet('/auth/status'));
      setError(null);
    } catch (err) {
      // Backend mati bukan urusan gerbang. Biarkan aplikasi memuat dan
      // menampilkan pesan "backend tidak terhubung" seperti biasa.
      setError(err.message);
      setState({ required: false, authenticated: true, offline: true });
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  // Sesi bisa berakhir di tengah pemakaian — cookie kedaluwarsa, atau kata
  // sandi diganti dari perangkat lain. Saat itu terjadi, kembali ke layar masuk
  // alih-alih membiarkan setiap tombol gagal tanpa penjelasan.
  useEffect(() => {
    const onExpired = () => setState((s) => (s ? { ...s, authenticated: false } : s));
    window.addEventListener('omniclip:auth-required', onExpired);
    return () => window.removeEventListener('omniclip:auth-required', onExpired);
  }, []);

  if (state === null) return <Splash />;
  if (!state.required || state.authenticated) return children;
  return (
    <Gate
      mode={state.has_password ? 'login' : 'setup'}
      minLength={state.min_length || 8}
      statusError={error}
      onDone={refresh}
    />
  );
}

function Splash() {
  return (
    <div style={wrap}>
      <Loader2 size={22} className="animate-spin" style={{ color: 'var(--text-muted)' }} />
    </div>
  );
}

function Gate({ mode, minLength, statusError, onDone }) {
  const setup = mode === 'setup';
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(statusError || null);

  const tooShort = setup && password.length > 0 && password.length < minLength;
  const mismatch = setup && confirm.length > 0 && confirm !== password;
  const ready = setup
    ? password.length >= minLength && confirm === password
    : password.length > 0;

  const submit = async (e) => {
    e?.preventDefault();
    if (!ready || busy) return;
    setBusy(true);
    setError(null);
    try {
      if (setup) await apiPost('/auth/setup', { new_password: password });
      else await apiPost('/auth/login', { password });
      setPassword('');
      setConfirm('');
      await onDone();
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  };

  return (
    <div style={wrap}>
      <form onSubmit={submit} style={panel}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
          {setup
            ? <ShieldCheck size={20} style={{ color: 'var(--reh)' }} />
            : <Lock size={20} style={{ color: 'var(--reh)' }} />}
          <h1 style={{ fontSize: '1.05rem', fontWeight: 800, margin: 0, color: 'var(--text-primary)' }}>
            {setup ? 'Pasang kata sandi' : 'OmniClip terkunci'}
          </h1>
        </div>

        <p style={help}>
          {setup
            ? `Kata sandi ini menjaga seluruh aplikasi: unduhan, klip, API key, dan akses ke kanal YouTube yang tersambung. Minimal ${minLength} karakter.`
            : 'Masukkan kata sandi untuk membuka aplikasi di perangkat ini.'}
        </p>

        <div style={{ position: 'relative', marginTop: '16px' }}>
          <input
            type={show ? 'text' : 'password'}
            value={password}
            autoFocus
            autoComplete={setup ? 'new-password' : 'current-password'}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={setup ? 'Kata sandi baru' : 'Kata sandi'}
            style={input}
          />
          <button type="button" onClick={() => setShow((v) => !v)}
                  aria-label={show ? 'Sembunyikan kata sandi' : 'Tampilkan kata sandi'}
                  style={eye}>
            {show ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>

        {setup && (
          <input
            type={show ? 'text' : 'password'}
            value={confirm}
            autoComplete="new-password"
            onChange={(e) => setConfirm(e.target.value)}
            placeholder="Ulangi kata sandi"
            style={{ ...input, marginTop: '10px' }}
          />
        )}

        {(tooShort || mismatch) && (
          <p style={{ ...help, marginTop: '10px', color: 'var(--text-muted)' }}>
            {tooShort ? `Masih kurang ${minLength - password.length} karakter.` : 'Ulangannya belum sama.'}
          </p>
        )}

        {error && (
          <div style={{ ...help, marginTop: '12px', color: 'var(--accent-red, var(--danger))',
                        display: 'flex', gap: '7px', alignItems: 'flex-start' }}>
            <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: '2px' }} />
            <span>{error}</span>
          </div>
        )}

        <button type="submit" className="btn-primary" disabled={!ready || busy}
                style={{ width: '100%', marginTop: '18px', justifyContent: 'center',
                         opacity: !ready || busy ? 0.5 : 1 }}>
          {busy ? <Loader2 size={15} className="animate-spin" />
                : <><KeyRound size={15} /> {setup ? 'Pasang dan masuk' : 'Masuk'}</>}
        </button>

        {setup && (
          <p style={{ ...help, marginTop: '14px' }}>
            Lupa kata sandi tidak bisa dipulihkan lewat email — tidak ada email di
            sini. Pemulihannya lewat terminal komputer ini; caranya ada di
            <code> PANDUAN-AKSES-JARAK-JAUH.md</code>.
          </p>
        )}
      </form>
    </div>
  );
}

const wrap = {
  minHeight: '100vh',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: '24px',
  background: 'var(--bg-page, var(--bg-primary))',
};

const panel = {
  width: '100%',
  maxWidth: '380px',
  padding: '26px 24px',
  borderRadius: 'var(--radius-lg, 14px)',
  border: '1px solid var(--border-color)',
  background: 'var(--bg-glass)',
};

const help = {
  fontSize: '0.78rem',
  color: 'var(--text-secondary)',
  lineHeight: 1.6,
  margin: 0,
};

const input = {
  width: '100%',
  padding: '12px 40px 12px 14px',
  borderRadius: 'var(--radius-md)',
  border: '1px solid var(--border-color)',
  background: 'var(--bg-primary, transparent)',
  color: 'var(--text-primary)',
  fontSize: '0.9rem',
  fontFamily: 'inherit',
};

const eye = {
  position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)',
  background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)',
  display: 'flex', alignItems: 'center',
};
