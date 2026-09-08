import React, { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Search, Download, Scissors, SlidersHorizontal, Film, Music4 } from 'lucide-react';
import ErrorBoundary from './components/ErrorBoundary';
import { apiGet } from './lib/api';

// Metafora partitur memberi bentuk pada layar kerjanya, tapi tidak boleh
// menutupi tugasnya: nama bagian di sini menyebut apa yang ada di dalamnya.
// "Partitur suara" terdengar bagus dan tidak memberi tahu apa pun.
const NAV = [
  { to: '/', label: 'Cari video', Icon: Search, end: true },
  { to: '/studio', label: 'Partitur', Icon: Music4 },
  { to: '/clips', label: 'Klip jadi', Icon: Film },
  { to: '/downloads', label: 'Unduhan', Icon: Download },
  { to: '/settings', label: 'Pengaturan', Icon: SlidersHorizontal },
];

/**
 * Kerangka aplikasi.
 *
 * Navigasi duduk di KIRI pada layar lebar, di tempat partitur menuliskan nama
 * instrumen tiap balok — bukan sebagai bilah di bawah halaman, yang memakan
 * tinggi layar justru pada satu-satunya layar yang membutuhkannya (editor).
 * Di bawah 900px ia turun jadi bilah jempol, karena di sanalah ibu jari sampai.
 */
export default function App() {
  const [engine, setEngine] = useState(null);
  const navigate = useNavigate();
  // Kunci penahan galat: berpindah halaman harus menghapus galat sebelumnya,
  // bukan menyisakan pesan rusak dari rute yang sudah ditinggalkan.
  const location = useLocation();

  useEffect(() => {
    const savedTheme = localStorage.getItem('omniclip_theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
  }, []);

  // Label mesin dibaca dari pengaturan sungguhan, bukan ditulis permanen.
  useEffect(() => {
    apiGet('/settings')
      .then((s) => setEngine(s.gemini_api_key_set ? 'gemini' : 'lokal'))
      .catch(() => setEngine('lokal'));
  }, []);

  return (
    <div className="app-viewport">
      <header className="top-header">
        <div className="brand-logo" onClick={() => navigate('/')}
             style={{ cursor: 'pointer' }}>
          <span>OMNI<em>CLIP</em></span>
        </div>
        <span className="brand-badge">Auto-clipper</span>

        <div className="header-meta">
          <span>
            Mesin{' '}
            <b>
              {engine === 'gemini' ? 'Gemini + heuristik'
                : engine === 'lokal' ? 'heuristik lokal' : '…'}
            </b>
          </span>
        </div>
      </header>

      <nav className="side-rail">
        <div className="rail-label">Bagian</div>
        {NAV.map(({ to, label, Icon, end }) => (
          <NavLink key={to} to={to} end={end}
                   className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
            <Icon className="nav-icon" size={17} strokeWidth={1.9} />
            <span>{label}</span>
          </NavLink>
        ))}
      </nav>

      <main className="main-content">
        <ErrorBoundary key={location.pathname}><Outlet /></ErrorBoundary>
      </main>
    </div>
  );
}
