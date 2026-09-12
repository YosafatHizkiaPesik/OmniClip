import React, { useEffect, useState } from 'react';
import {
  Lock, Loader2, LogOut, CheckCircle2, AlertTriangle, Info, Eye, EyeOff,
} from 'lucide-react';
import { apiDelete, apiGet, apiPost } from '../lib/api';

/**
 * Kata sandi dan sesi.
 *
 * Hanya berarti bila aplikasi ini dijangkau dari luar komputer ini. Selama ia
 * hanya mendengar di 127.0.0.1, kartu ini tetap ditampilkan — justru supaya
 * kata sandi bisa dipasang SEBELUM terowongan dinyalakan, bukan sesudahnya.
 */
export default function SecurityCard({ card, sectionTitle, helpText }) {
  const [status, setStatus] = useState(null);
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  const load = () => apiGet('/auth/status').then(setStatus).catch(() => setStatus(null));
  useEffect(() => { load(); }, []);

  const minLength = status?.min_length || 8;
  const has = !!status?.has_password;
  const ready = next.length >= minLength && next === confirm && (!has || current.length > 0);

  const save = async () => {
    if (!ready || busy) return;
    setBusy(true);
    setMsg(null);
    try {
      if (has) await apiPost('/auth/password', { new_password: next, current_password: current });
      else await apiPost('/auth/setup', { new_password: next });
      setCurrent(''); setNext(''); setConfirm('');
      setMsg({ kind: 'ok', text: has
        ? 'Kata sandi diganti. Semua perangkat lain harus masuk ulang.'
        : 'Kata sandi dipasang. Aplikasi ini sekarang terkunci.' });
      load();
    } catch (err) {
      setMsg({ kind: 'error', text: err.message });
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    setBusy(true);
    setMsg(null);
    try {
      await apiDelete('/auth/password');
      setMsg({ kind: 'ok', text: 'Kata sandi dilepas. Aplikasi kembali ke mode lokal.' });
      load();
    } catch (err) {
      setMsg({ kind: 'error', text: err.message });
    } finally {
      setBusy(false);
    }
  };

  const logout = async () => {
    await apiPost('/auth/logout').catch(() => {});
    window.location.reload();
  };

  return (
    <div style={card}>
      <div style={sectionTitle}>
        <Lock size={18} style={{ color: 'var(--reh)' }} />
        Kata sandi &amp; akses
      </div>
      <p style={helpText}>
        Kata sandi menjaga seluruh aplikasi: unduhan, klip, API key, dan kanal
        YouTube yang tersambung. Wajib dipasang sebelum OmniClip dibuka lewat
        Cloudflare — tanpa itu, siapa pun yang tahu alamatnya bisa memakai
        semuanya.
      </p>

      {status && (
        <div style={{ ...helpText, marginTop: '10px', display: 'flex',
                      alignItems: 'center', gap: '8px' }}>
          {has ? (
            <><CheckCircle2 size={15} style={{ color: 'var(--entry)' }} /> Terpasang — aplikasi terkunci.</>
          ) : (
            <><Info size={15} style={{ color: 'var(--text-muted)' }} /> Belum ada — mode lokal, siapa pun yang sampai ke port ini bisa masuk.</>
          )}
          {status.mode === 'on' && (
            <span style={{ color: 'var(--text-muted)' }}>· dipaksa menyala</span>
          )}
        </div>
      )}

      <div style={{ display: 'grid', gap: '9px', marginTop: '14px' }}>
        {has && (
          <input type={show ? 'text' : 'password'} value={current} autoComplete="current-password"
                 onChange={(e) => setCurrent(e.target.value)}
                 placeholder="Kata sandi sekarang" style={input} />
        )}
        <div style={{ position: 'relative' }}>
          <input type={show ? 'text' : 'password'} value={next} autoComplete="new-password"
                 onChange={(e) => setNext(e.target.value)}
                 placeholder={`Kata sandi baru (min. ${minLength} karakter)`} style={input} />
          <button type="button" onClick={() => setShow((v) => !v)}
                  aria-label={show ? 'Sembunyikan' : 'Tampilkan'}
                  style={{ position: 'absolute', right: '10px', top: '50%',
                           transform: 'translateY(-50%)', background: 'none',
                           border: 'none', cursor: 'pointer', color: 'var(--text-muted)',
                           display: 'flex', alignItems: 'center' }}>
            {show ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>
        <input type={show ? 'text' : 'password'} value={confirm} autoComplete="new-password"
               onChange={(e) => setConfirm(e.target.value)}
               placeholder="Ulangi kata sandi baru" style={input} />
      </div>

      <div style={{ display: 'flex', gap: '8px', marginTop: '12px', flexWrap: 'wrap' }}>
        <button className="btn-primary" onClick={save} disabled={!ready || busy}
                style={{ opacity: !ready || busy ? 0.5 : 1 }}>
          {busy ? <Loader2 size={15} className="animate-spin" />
                : (has ? 'Ganti kata sandi' : 'Pasang kata sandi')}
        </button>
        {has && (
          <>
            <button onClick={logout} style={ghost}>
              <LogOut size={14} /> Keluar di perangkat ini
            </button>
            {status?.mode !== 'on' && (
              <button onClick={remove} disabled={busy} style={{ ...ghost, color: 'var(--danger)' }}>
                Lepas kata sandi
              </button>
            )}
          </>
        )}
      </div>

      {msg && (
        <div style={{ ...helpText, marginTop: '11px', display: 'flex', gap: '7px',
                      alignItems: 'flex-start',
                      color: msg.kind === 'ok' ? 'var(--entry)' : 'var(--accent-red, var(--danger))' }}>
          {msg.kind === 'ok' ? <CheckCircle2 size={15} style={{ flexShrink: 0, marginTop: '2px' }} />
                             : <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: '2px' }} />}
          <span>{msg.text}</span>
        </div>
      )}

      <p style={{ ...helpText, marginTop: '12px' }}>
        Mengganti kata sandi mencabut sesi di semua perangkat lain — itulah cara
        mengeluarkan HP yang hilang atau orang yang tidak lagi perlu akses.
      </p>
    </div>
  );
}

const input = {
  width: '100%',
  padding: '11px 40px 11px 14px',
  borderRadius: 'var(--radius-md)',
  border: '1px solid var(--border-color)',
  background: 'var(--bg-glass)',
  color: 'var(--text-primary)',
  fontSize: '0.85rem',
  fontFamily: 'inherit',
};

const ghost = {
  display: 'flex', alignItems: 'center', gap: '7px',
  padding: '9px 13px', borderRadius: 'var(--radius-md)',
  border: '1px solid var(--border-color)', background: 'transparent',
  color: 'var(--text-secondary)', cursor: 'pointer',
  fontSize: '0.82rem', fontWeight: 700, fontFamily: 'inherit',
};
