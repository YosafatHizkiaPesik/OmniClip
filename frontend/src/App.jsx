import React, { useState, useEffect } from 'react';
import { Search, Download, Scissors, User, Sparkles, LogIn, ShieldCheck, CheckCircle2, Zap, Flame } from 'lucide-react';
import SearchTab from './components/SearchTab';
import StudioEditor from './components/StudioEditor';
import DownloadsTab from './components/DownloadsTab';
import OpusClipsTab from './components/OpusClipsTab';
import ProfileTab from './components/ProfileTab';

// ==================== LOGIN SCREEN (Fullscreen, Mandatory) ====================
function LoginScreen({ onLogin }) {
  const [isAnimating, setIsAnimating] = useState(false);

  const handleLogin = (acc) => {
    setIsAnimating(true);
    setTimeout(() => {
      onLogin(acc);
    }, 600);
  };

  return (
    <div style={{
      position: 'fixed',
      inset: 0,
      background: 'linear-gradient(135deg, #0a0e1a 0%, #0d1b2e 40%, #0a0e1a 100%)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 9999,
      opacity: isAnimating ? 0 : 1,
      transition: 'opacity 0.5s ease',
    }}>
      {/* Background glow effects */}
      <div style={{
        position: 'absolute',
        top: '20%',
        left: '50%',
        transform: 'translateX(-50%)',
        width: '600px',
        height: '600px',
        background: 'radial-gradient(circle, rgba(0, 242, 254, 0.08) 0%, transparent 70%)',
        pointerEvents: 'none'
      }} />
      <div style={{
        position: 'absolute',
        bottom: '10%',
        right: '10%',
        width: '400px',
        height: '400px',
        background: 'radial-gradient(circle, rgba(127, 0, 255, 0.06) 0%, transparent 70%)',
        pointerEvents: 'none'
      }} />

      {/* Login Card */}
      <div style={{
        position: 'relative',
        width: '100%',
        maxWidth: '460px',
        padding: '0 24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '32px',
        alignItems: 'center',
      }}>
        {/* Logo & Brand */}
        <div style={{ textAlign: 'center' }}>
          <div style={{
            width: '80px',
            height: '80px',
            borderRadius: '24px',
            background: 'linear-gradient(135deg, var(--accent-cyan), var(--accent-blue))',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 16px',
            boxShadow: '0 0 40px rgba(0, 242, 254, 0.3)',
          }}>
            <Scissors size={42} style={{ color: '#000' }} />
          </div>
          <h1 style={{ fontSize: '2rem', fontWeight: 900, tracking: '-0.02em', marginBottom: '8px' }}>
            OmniClip <span style={{ color: 'var(--accent-cyan)' }}>AI Studio</span>
          </h1>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', maxWidth: '340px', margin: '0 auto' }}>
            Platform Clipper & Video Shortener AI Otomatis dengan Standar Opus Clip & CapCut Studio
          </p>
        </div>

        {/* Account Options */}
        <div style={{
          width: '100%',
          background: 'var(--bg-card)',
          borderRadius: '20px',
          padding: '24px',
          border: '1px solid var(--border-color)',
          boxShadow: 'var(--shadow-card)',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}>
          <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <LogIn size={16} style={{ color: 'var(--accent-cyan)' }} />
            Pilih Akun Google untuk Masuk:
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {[
              { id: 'acc_1', name: 'Alberth Ynot', email: 'alberth.ynot@gmail.com', avatar: 'A' },
              { id: 'acc_2', name: 'OmniClip Team', email: 'creator@omniclip.ai', avatar: 'O' }
            ].map(acc => (
              <div
                key={acc.id}
                onClick={() => handleLogin(acc)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '14px',
                  padding: '12px 16px',
                  background: 'rgba(255, 255, 255, 0.03)',
                  border: '1px solid var(--border-color)',
                  borderRadius: '12px',
                  cursor: 'pointer',
                  transition: 'all 0.2s ease',
                }}
              >
                <div style={{
                  width: '36px', height: '36px', borderRadius: '50%',
                  background: 'linear-gradient(135deg, var(--accent-cyan), var(--accent-purple))',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontWeight: 800, color: '#fff', fontSize: '0.9rem'
                }}>
                  {acc.avatar}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>{acc.name}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {acc.email}
                  </div>
                </div>
                <ShieldCheck size={18} style={{ color: 'var(--accent-cyan)' }} />
              </div>
            ))}
          </div>

          <div style={{ marginTop: '8px', padding: '10px', background: 'rgba(255,255,255,0.03)', borderRadius: '8px', display: 'flex', gap: '8px', alignItems: 'flex-start' }}>
            <Zap size={14} style={{ color: 'var(--accent-cyan)', marginTop: '2px', flexShrink: 0 }} />
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              Sistem menggunakan Google OAuth 2.0 untuk autentikasi aman. Data akun disimpan di server lokal Anda.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ==================== MAIN APP ====================
export default function App() {
  const [activeTab, setActiveTab] = useState('search');
  const [user, setUser] = useState(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [editingVideo, setEditingVideo] = useState(null);
  const [editingAiData, setEditingAiData] = useState(null);

  // Apply saved theme on startup
  useEffect(() => {
    const savedTheme = localStorage.getItem('omniclip_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
  }, []);

  // Check login on load
  useEffect(() => {
    checkExistingLogin();
  }, []);

  const checkExistingLogin = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/accounts');
      const accounts = await res.json();
      const active = accounts.find(a => a.active);
      if (active) {
        setUser(active);
      }
    } catch (err) {
      console.warn('Backend offline, menampilkan login screen');
    } finally {
      setAuthChecked(true);
    }
  };

  const handleLogin = (acc) => {
    setUser(acc);
  };

  const handleLogout = () => {
    setUser(null);
  };

  // Open Opus Clips Dashboard from Search
  const handleOpenOpusClips = (video, aiData) => {
    setEditingVideo(video);
    setEditingAiData(aiData);
    setActiveTab('opus');
  };

  // Open Studio Editor with specific Clip
  const handleOpenStudioWithClip = (video, clip) => {
    setEditingVideo(video);
    if (editingAiData) {
      setEditingAiData(editingAiData);
    } else if (clip) {
      setEditingAiData({ clips: [clip] });
    }
    setActiveTab('studio');
  };

  if (!authChecked) {
    return (
      <div style={{
        position: 'fixed', inset: 0,
        background: '#0a0e1a',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexDirection: 'column', gap: '16px'
      }}>
        <Scissors size={40} style={{ color: 'var(--accent-cyan)', animation: 'pulse 1.5s ease-in-out infinite' }} />
        <span style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Memuat OmniClip AI...</span>
      </div>
    );
  }

  if (!user) {
    return <LoginScreen onLogin={handleLogin} />;
  }

  return (
    <div className="app-viewport">
      {/* Top Bar Header */}
      <header className="top-header">
        <div className="brand-logo" onClick={() => setActiveTab('search')} style={{ cursor: 'pointer' }}>
          <Scissors size={24} style={{ color: 'var(--accent-cyan)' }} />
          <span>OmniClip AI</span>
          <span className="brand-badge">Opus & CapCut Suite</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Sparkles size={14} style={{ color: 'var(--accent-cyan)' }} />
            Gemini Pro/Flash Engine
          </div>

          {/* User Badge - Klik untuk ke Profile */}
          <div
            onClick={() => setActiveTab('profile')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '6px 12px',
              background: 'rgba(0, 242, 254, 0.1)',
              border: '1px solid var(--border-active)',
              borderRadius: '20px',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
            }}
          >
            <div style={{
              width: '24px', height: '24px', borderRadius: '50%',
              background: 'linear-gradient(135deg, var(--accent-cyan), var(--accent-blue))',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#000', fontWeight: 800, fontSize: '0.75rem'
            }}>
              {user.name ? user.name.charAt(0) : 'U'}
            </div>
            <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>{user.name}</span>
            <CheckCircle2 size={14} style={{ color: '#10b981' }} />
          </div>
        </div>
      </header>

      {/* Main View Area */}
      <main className="main-content">
        {activeTab === 'search' && (
          <SearchTab onOpenClipEditor={handleOpenOpusClips} />
        )}
        {activeTab === 'opus' && (
          <OpusClipsTab
            currentVideo={editingVideo}
            currentAiData={editingAiData}
            onOpenStudioWithClip={handleOpenStudioWithClip}
          />
        )}
        {activeTab === 'studio' && (
          <StudioEditor video={editingVideo} aiData={editingAiData} />
        )}
        {activeTab === 'downloads' && (
          <DownloadsTab />
        )}
        {activeTab === 'profile' && (
          <ProfileTab user={user} onLogout={handleLogout} />
        )}
      </main>

      {/* Bottom Navigation Bar (Modular Separation) */}
      <nav className="bottom-nav">
        <button
          className={`nav-item ${activeTab === 'search' ? 'active' : ''}`}
          onClick={() => setActiveTab('search')}
        >
          <Search className="nav-icon" />
          <span>YouTube Hub</span>
        </button>

        <button
          className={`nav-item ${activeTab === 'opus' ? 'active' : ''}`}
          onClick={() => setActiveTab('opus')}
        >
          <Flame className="nav-icon" style={{ color: activeTab === 'opus' ? '#10b981' : undefined }} />
          <span>Opus Clips</span>
        </button>

        <button
          className={`nav-item ${activeTab === 'studio' ? 'active' : ''}`}
          onClick={() => setActiveTab('studio')}
        >
          <Scissors className="nav-icon" />
          <span>CapCut Studio</span>
        </button>

        <button
          className={`nav-item ${activeTab === 'downloads' ? 'active' : ''}`}
          onClick={() => setActiveTab('downloads')}
        >
          <Download className="nav-icon" />
          <span>Downloads</span>
        </button>

        <button
          className={`nav-item ${activeTab === 'profile' ? 'active' : ''}`}
          onClick={() => setActiveTab('profile')}
        >
          <User className="nav-icon" />
          <span>Settings</span>
        </button>
      </nav>
    </div>
  );
}
