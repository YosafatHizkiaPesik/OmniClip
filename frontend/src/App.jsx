import React, { useState, useEffect } from 'react';
import { Search, Download, Scissors, User, Sparkles, Film } from 'lucide-react';
import SearchTab from './components/SearchTab';
import StudioHome from './features/studio/StudioHome';
import Editor from './features/studio/Editor';
import { apiGet } from './lib/api';
import DownloadsTab from './components/DownloadsTab';
import ClipsTab from './components/ClipsTab';
import ProfileTab from './components/ProfileTab';

export default function App() {
  const [activeTab, setActiveTab] = useState('search');
  // Project yang sedang dibuka di editor. Null berarti Studio menampilkan
  // daftar kartu — pekerjaan klip berjalan di antrean, bukan di layar ini.
  const [openProject, setOpenProject] = useState(null);
  const [engine, setEngine] = useState(null);

  // Terapkan tema tersimpan saat startup
  useEffect(() => {
    const savedTheme = localStorage.getItem('omniclip_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
  }, []);

  // Label mesin di header dibaca dari pengaturan sungguhan. Sebelumnya tertulis
  // "Gemini Flash Engine" secara permanen, bahkan ketika tidak ada API key dan
  // seluruh pemilihan klip dikerjakan heuristik lokal.
  useEffect(() => {
    apiGet('/settings')
      .then((s) => setEngine(s.gemini_api_key_set ? 'gemini' : 'lokal'))
      .catch(() => setEngine('lokal'));
  }, []);

  const goToStudio = () => {
    setOpenProject(null);
    setActiveTab('studio');
  };

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
            {engine === 'gemini' ? 'Gemini + heuristik lokal'
              : engine === 'lokal' ? 'Mesin heuristik lokal' : 'Memuat…'}
          </div>
        </div>
      </header>

      {/* Main View Area */}
      <main className="main-content">
        {activeTab === 'search' && (
          <SearchTab onOpenStudio={goToStudio} />
        )}
        {activeTab === 'studio' && (
          openProject ? (
            <Editor project={openProject} onBack={() => setOpenProject(null)} />
          ) : (
            <StudioHome onOpen={setOpenProject}
                        onFindVideos={() => setActiveTab('search')} />
          )
        )}
        {activeTab === 'clips' && (
          <ClipsTab />
        )}
        {activeTab === 'downloads' && (
          <DownloadsTab />
        )}
        {activeTab === 'profile' && (
          <ProfileTab />
        )}
      </main>

      {/* Bottom Navigation Bar */}
      <nav className="bottom-nav">
        <button
          className={`nav-item ${activeTab === 'search' ? 'active' : ''}`}
          onClick={() => setActiveTab('search')}
        >
          <Search className="nav-icon" />
          <span>YouTube Hub</span>
        </button>

        <button
          className={`nav-item ${activeTab === 'studio' ? 'active' : ''}`}
          onClick={goToStudio}
        >
          <Scissors className="nav-icon" />
          <span>Clip Studio</span>
        </button>

        <button
          className={`nav-item ${activeTab === 'clips' ? 'active' : ''}`}
          onClick={() => setActiveTab('clips')}
        >
          <Film className="nav-icon" />
          <span>Klip Saya</span>
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
