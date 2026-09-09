import React, { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  Search, Download, SlidersHorizontal, Film, Music4, Menu, X,
} from 'lucide-react';
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

/** Editor satu project: /studio/<videoId>. Bukan /studio yang berisi kartu. */
function isEditorPath(pathname) {
  return /^\/studio\/[^/]+/.test(pathname);
}

/**
 * Kerangka aplikasi.
 *
 * Navigasi duduk di KIRI pada layar lebar, di tempat partitur menuliskan nama
 * instrumen tiap balok. Di bawah 900px ia turun jadi bilah jempol, karena di
 * sanalah ibu jari sampai.
 *
 * Di dalam editor ia MENUTUP SENDIRI. Mencari video, membuka unduhan, atau
 * mengganti pengaturan bukan pekerjaan yang dilakukan sambil memotong klip;
 * yang dibutuhkan editor adalah lebar, dan kolom 188px itu diambil dari
 * satu-satunya layar yang benar-benar kekurangannya. Tombol burger di kepala
 * halaman tetap membukanya kapan saja — keadaannya diingat per-jenis-layar,
 * jadi menutupnya di editor tidak ikut menutupnya di beranda.
 */
export default function App() {
  const [engine, setEngine] = useState(null);
  const navigate = useNavigate();
  // Kunci penahan galat: berpindah halaman harus menghapus galat sebelumnya,
  // bukan menyisakan pesan rusak dari rute yang sudah ditinggalkan.
  const location = useLocation();
  const editor = isEditorPath(location.pathname);
  const [railOpen, setRailOpen] = useState(() => !isEditorPath(window.location.pathname));

  // Berpindah masuk atau keluar editor menyetel ulang bilahnya ke bawaan layar
  // itu. Tanpa ini, menutup bilah di editor lalu kembali ke beranda memberi
  // halaman tanpa navigasi sama sekali.
  useEffect(() => { setRailOpen(!editor); }, [editor]);

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
    <div className="app-viewport" data-rail={railOpen ? 'on' : 'off'}>
      <header className="top-header">
        <button className="rail-toggle" onClick={() => setRailOpen((v) => !v)}
                aria-label={railOpen ? 'Tutup menu' : 'Buka menu'}
                aria-expanded={railOpen}>
          {railOpen ? <X size={17} /> : <Menu size={17} />}
        </button>

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

      <nav className="side-rail" aria-hidden={!railOpen}>
        {NAV.map(({ to, label, Icon, end }) => (
          <NavLink key={to} to={to} end={end}
                   tabIndex={railOpen ? 0 : -1}
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
