import React, { useState, useEffect } from 'react';
import {
  KeyRound, Loader2, Sun, Moon, Settings, Eye, EyeOff, Info,
  CheckCircle2, AlertTriangle, Cookie,
} from 'lucide-react';
import { apiGet, apiPost } from '../lib/api';

const card = {
  background: 'var(--bg-card)',
  border: '1px solid var(--border-color)',
  borderRadius: 'var(--radius-lg)',
  padding: '20px',
  boxShadow: 'var(--shadow-card)',
};

const sectionTitle = {
  display: 'flex',
  alignItems: 'center',
  gap: '10px',
  fontSize: '0.95rem',
  fontWeight: 800,
  color: 'var(--text-primary)',
  marginBottom: '6px',
};

const helpText = {
  fontSize: '0.78rem',
  color: 'var(--text-secondary)',
  lineHeight: 1.6,
};

export default function ProfileTab() {
  const [theme, setTheme] = useState(() => localStorage.getItem('omniclip_theme') || 'dark');
  const [apiKey, setApiKey] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [savingKey, setSavingKey] = useState(false);
  const [feedback, setFeedback] = useState(null); // {kind:'ok'|'error', text}
  const [settings, setSettings] = useState(null);
  const [settingsError, setSettingsError] = useState(null);

  const loadSettings = async () => {
    try {
      setSettings(await apiGet('/settings'));
      setSettingsError(null);
    } catch (err) {
      setSettingsError(err.message);
    }
  };

  useEffect(() => { loadSettings(); }, []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('omniclip_theme', theme);
  }, [theme]);

  const handleSaveApiKey = async () => {
    if (!apiKey.trim()) return;
    setSavingKey(true);
    setFeedback(null);
    try {
      await apiPost('/settings/api-key', { api_key: apiKey.trim() });
      setApiKey('');
      setFeedback({ kind: 'ok', text: 'API Key Gemini tersimpan untuk sesi ini.' });
      loadSettings();
    } catch (err) {
      setFeedback({ kind: 'error', text: err.message });
    } finally {
      setSavingKey(false);
    }
  };

  return (
    <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '18px', maxWidth: '760px', margin: '0 auto' }}>
      <div style={{ ...sectionTitle, fontSize: '1.2rem', marginBottom: 0 }}>
        <Settings size={22} style={{ color: 'var(--accent-cyan)' }} />
        Pengaturan
      </div>

      {settingsError && (
        <div style={{ ...card, borderColor: 'var(--accent-red)', display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
          <AlertTriangle size={18} style={{ color: 'var(--accent-red)', flexShrink: 0, marginTop: '2px' }} />
          <div>
            <div style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--text-primary)' }}>Backend tidak terhubung</div>
            <div style={helpText}>{settingsError}</div>
          </div>
        </div>
      )}

      {/* --- Tampilan --- */}
      <div style={card}>
        <div style={sectionTitle}>
          {theme === 'dark' ? <Moon size={18} style={{ color: 'var(--accent-cyan)' }} /> : <Sun size={18} style={{ color: 'var(--accent-cyan)' }} />}
          Tampilan
        </div>
        <p style={helpText}>Pilih tema terang atau gelap untuk seluruh aplikasi.</p>
        <div style={{ display: 'flex', gap: '10px', marginTop: '14px' }}>
          {[
            { id: 'dark', label: 'Gelap', Icon: Moon },
            { id: 'light', label: 'Terang', Icon: Sun },
          ].map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => setTheme(id)}
              style={{
                flex: 1,
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                padding: '12px',
                borderRadius: 'var(--radius-md)',
                cursor: 'pointer',
                fontWeight: 700,
                fontSize: '0.85rem',
                color: theme === id ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                background: theme === id ? 'rgba(0, 242, 254, 0.1)' : 'transparent',
                border: theme === id ? '1px solid var(--border-active)' : '1px solid var(--border-color)',
                transition: 'all 0.2s ease',
              }}
            >
              <Icon size={16} />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* --- Gemini API Key --- */}
      <div style={card}>
        <div style={sectionTitle}>
          <KeyRound size={18} style={{ color: 'var(--accent-cyan)' }} />
          Gemini API Key
        </div>
        <p style={helpText}>
          Opsional. Tanpa API key, OmniClip tetap memotong klip memakai mesin heuristik
          lokal berbasis transkrip asli. Dengan API key, Gemini ikut menyusun ulang
          peringkat dan judul klip. Ambil kunci gratis di{' '}
          <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noreferrer"
             style={{ color: 'var(--accent-cyan)' }}>
            aistudio.google.com
          </a>.
        </p>

        {settings && (
          <div style={{ ...helpText, marginTop: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            {settings.gemini_api_key_set ? (
              <>
                <CheckCircle2 size={15} style={{ color: '#10b981' }} />
                Tersimpan (berakhiran <code>{settings.gemini_api_key_last4}</code>)
              </>
            ) : (
              <>
                <Info size={15} style={{ color: 'var(--text-muted)' }} />
                Belum dikonfigurasi — mode heuristik lokal aktif.
              </>
            )}
          </div>
        )}

        <div style={{ display: 'flex', gap: '8px', marginTop: '14px' }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <input
              type={showApiKey ? 'text' : 'password'}
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSaveApiKey()}
              placeholder="Tempel API key di sini…"
              style={{
                width: '100%',
                padding: '11px 40px 11px 14px',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--border-color)',
                background: 'var(--bg-glass)',
                color: 'var(--text-primary)',
                fontSize: '0.85rem',
                fontFamily: 'inherit',
              }}
            />
            <button
              type="button"
              onClick={() => setShowApiKey((v) => !v)}
              aria-label={showApiKey ? 'Sembunyikan API key' : 'Tampilkan API key'}
              style={{
                position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)',
                background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)',
                display: 'flex', alignItems: 'center',
              }}
            >
              {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
          <button
            className="btn-primary"
            onClick={handleSaveApiKey}
            disabled={savingKey || !apiKey.trim()}
            style={{ opacity: savingKey || !apiKey.trim() ? 0.5 : 1, whiteSpace: 'nowrap' }}
          >
            {savingKey ? <Loader2 size={15} className="animate-spin" /> : 'Simpan'}
          </button>
        </div>

        {feedback && (
          <div style={{
            ...helpText,
            marginTop: '10px',
            color: feedback.kind === 'ok' ? '#10b981' : 'var(--accent-red)',
            display: 'flex', alignItems: 'center', gap: '7px',
          }}>
            {feedback.kind === 'ok' ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}
            {feedback.text}
          </div>
        )}
      </div>

      {/* --- Cookies YouTube --- */}
      <div style={card}>
        <div style={sectionTitle}>
          <Cookie size={18} style={{ color: 'var(--accent-cyan)' }} />
          Cookies YouTube
        </div>
        <p style={helpText}>
          Kalau YouTube menolak unduhan dengan pesan <em>&ldquo;Sign in to confirm you&rsquo;re not a bot&rdquo;</em>{' '}
          atau HTTP 403, ekspor cookies dari browser ke sebuah file, lalu jalankan backend
          dengan variabel <code>OMNICLIP_COOKIES_FILE=/path/ke/cookies.txt</code>.
          Langkah pertama yang lebih sering menyelesaikan masalah:{' '}
          <code>pip install -U yt-dlp</code> di venv backend.
        </p>
        {settings && (
          <div style={{ ...helpText, marginTop: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            {settings.cookies_file_set ? (
              <><CheckCircle2 size={15} style={{ color: '#10b981' }} /> File cookies terpasang.</>
            ) : (
              <><Info size={15} style={{ color: 'var(--text-muted)' }} /> Belum dipakai (tidak wajib).</>
            )}
          </div>
        )}
      </div>

      {/* --- Info --- */}
      <div style={card}>
        <div style={sectionTitle}>
          <Info size={18} style={{ color: 'var(--accent-cyan)' }} />
          Tentang
        </div>
        <div style={{ ...helpText, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '6px 16px', marginTop: '8px' }}>
          <span style={{ color: 'var(--text-muted)' }}>Versi</span><span>OmniClip AI 3.1</span>
          <span style={{ color: 'var(--text-muted)' }}>Mode</span><span>Lokal — semua file dan riwayat disimpan di komputer ini</span>
          <span style={{ color: 'var(--text-muted)' }}>Penyimpanan</span><span><code>OmniClip_Storage/</code></span>
        </div>
      </div>
    </div>
  );
}
