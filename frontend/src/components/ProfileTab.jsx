import React, { useState, useEffect } from 'react';
import { User, CheckCircle2, UserPlus, ShieldCheck, HardDrive, KeyRound, Loader2, Sun, Moon, Settings, Trash2, Eye, EyeOff, Info } from 'lucide-react';

export default function ProfileTab({ user, onLogout }) {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newName, setNewName] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [adding, setAdding] = useState(false);

  // Settings state
  const [theme, setTheme] = useState(localStorage.getItem('omniclip_theme') || 'dark');
  const [apiKey, setApiKey] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [apiKeyStatus, setApiKeyStatus] = useState(null); // null | 'ok' | 'error'
  const [savingKey, setSavingKey] = useState(false);
  const [settingsInfo, setSettingsInfo] = useState(null);
  const [activeSection, setActiveSection] = useState('accounts'); // 'accounts' | 'settings'

  const fetchAccounts = async () => {
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/api/accounts');
      const data = await res.json();
      setAccounts(Array.isArray(data) ? data : []);
    } catch { setAccounts([]); }
    finally { setLoading(false); }
  };

  const fetchSettings = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/settings');
      const data = await res.json();
      setSettingsInfo(data);
    } catch {}
  };

  useEffect(() => { fetchAccounts(); fetchSettings(); }, []);

  // Apply theme
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('omniclip_theme', theme);
  }, [theme]);

  const handleSwitchAccount = async (accountId) => {
    try {
      const res = await fetch('http://localhost:8000/api/accounts/switch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: accountId })
      });
      const data = await res.json();
      if (res.ok) setAccounts(data.accounts);
    } catch { alert('Gagal berganti akun'); }
  };

  const handleAddAccount = async (e) => {
    e.preventDefault();
    if (!newName || !newEmail) return;
    setAdding(true);
    try {
      const res = await fetch('http://localhost:8000/api/accounts/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newName, email: newEmail })
      });
      const data = await res.json();
      if (res.ok) {
        setAccounts(data.accounts);
        setShowAddModal(false);
        setNewName(''); setNewEmail('');
      }
    } catch { alert('Gagal menambahkan akun'); }
    finally { setAdding(false); }
  };

  const handleSaveApiKey = async () => {
    if (!apiKey.trim()) return;
    setSavingKey(true);
    setApiKeyStatus(null);
    try {
      const res = await fetch('http://localhost:8000/api/settings/api-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey.trim() })
      });
      if (res.ok) {
        setApiKeyStatus('ok');
        fetchSettings();
        setTimeout(() => setApiKeyStatus(null), 3000);
      } else { setApiKeyStatus('error'); }
    } catch { setApiKeyStatus('error'); }
    finally { setSavingKey(false); }
  };

  const activeAccount = accounts.find(a => a.active) || accounts[0] || user;

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px', flexWrap: 'wrap', gap: '12px' }}>
        <h2 style={{ fontSize: '1.4rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '10px' }}>
          <User size={24} style={{ color: 'var(--accent-cyan)' }} />
          Profil & Pengaturan
        </h2>
        <button onClick={onLogout} className="btn-secondary" style={{ color: '#ef4444', borderColor: 'rgba(239,68,68,0.3)', fontSize: '0.82rem' }}>
          Keluar (Logout)
        </button>
      </div>

      {/* Active Account Card */}
      {activeAccount && (
        <div style={{
          background: 'linear-gradient(135deg, rgba(0,242,254,0.1), rgba(127,0,255,0.1))',
          border: '1px solid rgba(0,242,254,0.25)',
          borderRadius: '16px', padding: '20px', marginBottom: '24px',
          display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap',
        }}>
          <div style={{
            width: '56px', height: '56px', borderRadius: '50%',
            background: 'linear-gradient(135deg, var(--accent-cyan), var(--accent-blue))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#000', fontWeight: 900, fontSize: '1.4rem', flexShrink: 0,
          }}>{(activeAccount.name || 'U').charAt(0)}</div>
          <div style={{ flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '2px' }}>
              <h3 style={{ fontWeight: 800, fontSize: '1.1rem' }}>{activeAccount.name}</h3>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, padding: '2px 8px', borderRadius: '12px', background: 'rgba(16,185,129,0.2)', border: '1px solid #10b981', color: '#10b981' }}>
                ✓ Aktif
              </span>
            </div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{activeAccount.email}</div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.78rem', color: 'var(--text-secondary)', background: 'rgba(0,0,0,0.3)', padding: '8px 12px', borderRadius: '8px' }}>
            <ShieldCheck size={14} style={{ color: 'var(--accent-cyan)' }} />
            OAuth 2.0 Verified
          </div>
        </div>
      )}

      {/* Section Tabs */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
        {[['accounts', <User size={15} />, 'Akun Google'], ['settings', <Settings size={15} />, 'Pengaturan App']].map(([id, icon, label]) => (
          <button key={id} onClick={() => setActiveSection(id)}
            className={activeSection === id ? 'btn-primary' : 'btn-secondary'}
            style={{ fontSize: '0.85rem' }}
          >{icon}{label}</button>
        ))}
      </div>

      {/* === ACCOUNTS SECTION === */}
      {activeSection === 'accounts' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-secondary)' }}>
              Multi-Account Manager ({accounts.length} akun)
            </h3>
            <button className="btn-primary" onClick={() => setShowAddModal(true)} style={{ fontSize: '0.82rem' }}>
              <UserPlus size={14} /> Tambah Akun
            </button>
          </div>

          {loading ? (
            <div style={{ padding: '40px', textAlign: 'center' }}>
              <Loader2 size={28} className="animate-spin" style={{ color: 'var(--accent-cyan)' }} />
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '12px' }}>
              {accounts.map(acc => (
                <div key={acc.id} onClick={() => handleSwitchAccount(acc.id)}
                  style={{
                    background: acc.active ? 'rgba(0,242,254,0.08)' : 'var(--bg-card)',
                    border: acc.active ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                    borderRadius: '12px', padding: '14px', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    transition: 'all 0.2s ease',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ width: '38px', height: '38px', borderRadius: '50%', background: 'rgba(255,255,255,0.1)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700 }}>
                      {acc.name.charAt(0)}
                    </div>
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '0.88rem' }}>{acc.name}</div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>{acc.email}</div>
                    </div>
                  </div>
                  {acc.active
                    ? <CheckCircle2 size={18} style={{ color: 'var(--accent-cyan)' }} />
                    : <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Klik untuk aktifkan</span>}
                </div>
              ))}
            </div>
          )}

          {/* Add Account Modal */}
          {showAddModal && (
            <div className="modal-overlay">
              <div className="modal-box">
                <h3 style={{ fontWeight: 700, borderBottom: '1px solid var(--border-color)', paddingBottom: '10px' }}>
                  🔑 Tambah Akun Google
                </h3>
                <form onSubmit={handleAddAccount} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <div>
                    <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>Nama Channel / Niche</label>
                    <input type="text" required value={newName} onChange={e => setNewName(e.target.value)}
                      placeholder="Contoh: Niche Edukasi Shorts"
                      style={{ width: '100%', padding: '10px', background: 'rgba(30,41,59,0.8)', border: '1px solid var(--border-color)', borderRadius: '8px', color: '#fff' }} />
                  </div>
                  <div>
                    <label style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>Email Google</label>
                    <input type="email" required value={newEmail} onChange={e => setNewEmail(e.target.value)}
                      placeholder="email@gmail.com"
                      style={{ width: '100%', padding: '10px', background: 'rgba(30,41,59,0.8)', border: '1px solid var(--border-color)', borderRadius: '8px', color: '#fff' }} />
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                    <button type="button" className="btn-secondary" onClick={() => setShowAddModal(false)}>Batal</button>
                    <button type="submit" className="btn-primary" disabled={adding}>
                      {adding ? <Loader2 size={15} className="animate-spin" /> : <UserPlus size={15} />} Simpan
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </div>
      )}

      {/* === SETTINGS SECTION === */}
      {activeSection === 'settings' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>

          {/* Theme Toggle */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '14px', padding: '20px' }}>
            <div style={{ fontWeight: 700, fontSize: '1rem', marginBottom: '14px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              {theme === 'dark' ? <Moon size={18} style={{ color: 'var(--accent-cyan)' }} /> : <Sun size={18} style={{ color: '#f59e0b' }} />}
              Tampilan Aplikasi
            </div>
            <div style={{ display: 'flex', gap: '10px' }}>
              {[['dark', <Moon size={16} />, 'Dark Mode', '#0b0f19'], ['light', <Sun size={16} />, 'Light Mode', '#f0f4f8']].map(([val, icon, label]) => (
                <button key={val} onClick={() => setTheme(val)}
                  style={{
                    flex: 1, padding: '14px', borderRadius: '10px', cursor: 'pointer', fontWeight: 700, fontSize: '0.88rem',
                    border: theme === val ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                    background: theme === val ? 'rgba(0,242,254,0.1)' : 'rgba(255,255,255,0.04)',
                    color: theme === val ? 'var(--accent-cyan)' : 'var(--text-primary)',
                    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px',
                  }}>
                  {icon} {label}
                  {theme === val && <CheckCircle2 size={14} />}
                </button>
              ))}
            </div>
          </div>

          {/* Gemini API Key */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '14px', padding: '20px' }}>
            <div style={{ fontWeight: 700, fontSize: '1rem', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '8px' }}>
              <KeyRound size={18} style={{ color: 'var(--accent-cyan)' }} />
              Gemini API Key
            </div>

            {settingsInfo && (
              <div style={{
                padding: '8px 12px', borderRadius: '8px', marginBottom: '14px', fontSize: '0.8rem',
                background: settingsInfo.gemini_api_key_set ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.1)',
                border: `1px solid ${settingsInfo.gemini_api_key_set ? '#10b981' : '#ef4444'}`,
                color: settingsInfo.gemini_api_key_set ? '#10b981' : '#ef4444',
                display: 'flex', alignItems: 'center', gap: '8px',
              }}>
                {settingsInfo.gemini_api_key_set
                  ? <><CheckCircle2 size={14} /> API Key aktif: {settingsInfo.gemini_api_key_preview}</>
                  : <><Info size={14} /> API Key belum dikonfigurasi — AI menggunakan mode heuristik</>}
              </div>
            )}

            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '12px', lineHeight: 1.6 }}>
              Masukkan Gemini API Key dari <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noreferrer" style={{ color: 'var(--accent-cyan)' }}>Google AI Studio</a> untuk mengaktifkan AI clipping yang lebih akurat sesuai konten video.
            </p>

            <div style={{ display: 'flex', gap: '8px' }}>
              <div style={{ flex: 1, position: 'relative', display: 'flex', alignItems: 'center' }}>
                <input
                  type={showApiKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={e => setApiKey(e.target.value)}
                  placeholder="AIza..."
                  style={{
                    width: '100%', padding: '10px 40px 10px 12px',
                    background: 'rgba(30,41,59,0.8)', border: '1px solid var(--border-color)',
                    borderRadius: '8px', color: '#fff', fontSize: '0.9rem', fontFamily: 'monospace',
                  }}
                />
                <button onClick={() => setShowApiKey(!showApiKey)} style={{
                  position: 'absolute', right: '10px', background: 'none', border: 'none',
                  color: 'var(--text-muted)', cursor: 'pointer',
                }}>{showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}</button>
              </div>
              <button onClick={handleSaveApiKey} disabled={savingKey || !apiKey.trim()} className="btn-primary" style={{ flexShrink: 0 }}>
                {savingKey ? <Loader2 size={15} className="animate-spin" /> : <KeyRound size={15} />}
                Simpan
              </button>
            </div>

            {apiKeyStatus === 'ok' && (
              <div style={{ marginTop: '8px', fontSize: '0.8rem', color: '#10b981', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <CheckCircle2 size={13} /> API Key berhasil disimpan untuk sesi ini!
              </div>
            )}
            {apiKeyStatus === 'error' && (
              <div style={{ marginTop: '8px', fontSize: '0.8rem', color: '#ef4444' }}>
                ✗ Gagal menyimpan API Key. Periksa koneksi backend.
              </div>
            )}
          </div>

          {/* App Info */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-color)', borderRadius: '14px', padding: '20px' }}>
            <div style={{ fontWeight: 700, fontSize: '1rem', marginBottom: '12px' }}>ℹ️ Informasi Aplikasi</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
              {[
                ['Versi', 'OmniClip AI v3.0'],
                ['Backend', 'FastAPI + yt-dlp + FFmpeg'],
                ['AI Engine', 'Google Gemini 2.0 Flash'],
                ['Storage', 'Lokal (OmniClip_Storage/)'],
                ['Pertanyaan', 'Tidak perlu deploy — berjalan 100% lokal'],
              ].map(([k, v]) => (
                <div key={k} style={{ display: 'flex', gap: '12px' }}>
                  <span style={{ minWidth: '100px', color: 'var(--text-muted)' }}>{k}</span>
                  <span style={{ color: '#fff', fontWeight: 600 }}>{v}</span>
                </div>
              ))}
            </div>
            <div style={{ marginTop: '14px', padding: '10px', background: 'rgba(0,242,254,0.06)', borderRadius: '8px', fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              💡 <strong style={{ color: 'var(--accent-cyan)' }}>Tidak perlu deploy ke internet.</strong> Semua fitur (search, download, AI clip, rendering) berjalan sepenuhnya di server lokal Anda. Deploy ke internet hanya dibutuhkan jika ingin akses dari perangkat lain.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
