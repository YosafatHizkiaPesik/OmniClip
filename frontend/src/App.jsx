import React, { useEffect, useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { Search, Download, Scissors, User, Sparkles, Film } from 'lucide-react';
import { apiGet } from './lib/api';

const NAV = [
  { to: '/', label: 'YouTube Hub', Icon: Search, end: true },
  { to: '/studio', label: 'Clip Studio', Icon: Scissors },
  { to: '/clips', label: 'Klip Saya', Icon: Film },
  { to: '/downloads', label: 'Downloads', Icon: Download },
  { to: '/settings', label: 'Settings', Icon: User },
];

/**
 * Kerangka aplikasi: header, area rute, dan navigasi bawah.
 *
 * Sebelumnya seluruh aplikasi hidup di satu URL dengan state `activeTab`, jadi
 * tombol back browser keluar dari aplikasi, tidak ada halaman yang bisa
 * di-bookmark atau dibagikan, dan berpindah tab me-remount seluruh layar.
 * Sekarang tiap layar punya alamatnya sendiri.
 */
export default function App() {
  const [engine, setEngine] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const savedTheme = localStorage.getItem('omniclip_theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
  }, []);

  // Label mesin dibaca dari pengaturan sungguhan. Sebelumnya tertulis "Gemini
  // Flash Engine" secara permanen, bahkan tanpa API key.
  useEffect(() => {
    apiGet('/settings')
      .then((s) => setEngine(s.gemini_api_key_set ? 'gemini' : 'lokal'))
      .catch(() => setEngine('lokal'));
  }, []);

  return (
    <div className="app-viewport">
      <header className="top-header">
        <div className="brand-logo" onClick={() => navigate('/')} style={{ cursor: 'pointer' }}>
          <Scissors size={24} style={{ color: 'var(--accent-cyan)' }} />
          <span>OmniClip AI</span>
          <span className="brand-badge">Opus &amp; CapCut Suite</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{
            fontSize: '0.8rem', color: 'var(--text-secondary)',
            display: 'flex', alignItems: 'center', gap: '6px',
          }}>
            <Sparkles size={14} style={{ color: 'var(--accent-cyan)' }} />
            {engine === 'gemini' ? 'Gemini + heuristik lokal'
              : engine === 'lokal' ? 'Mesin heuristik lokal' : 'Memuat…'}
          </div>
        </div>
      </header>

      <main className="main-content">
        <Outlet />
      </main>

      <nav className="bottom-nav">
        {NAV.map(({ to, label, Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
          >
            <Icon className="nav-icon" />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
