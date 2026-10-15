import React, { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  Search, Download, SlidersHorizontal, Film, Music4, Menu, X, ArrowDownToLine, UserRound, Gauge,
  BarChart3, Home, TvMinimalPlay, History, Globe,
} from 'lucide-react';
import { BAHASA, bahasa, setBahasa, useT } from './lib/i18n';
import ErrorBoundary from './components/ErrorBoundary';
import ProfilPemilih from './components/ProfilPemilih';
import KotakCari from './components/KotakCari';
import { apiGet } from './lib/api';
import useBuildWatch from './hooks/useBuildWatch';

// Dikelompokkan seperti YouTube (JOB-3 J3-2): menonton dulu, lalu studio
// tempat klip dibuat, lalu channel yang diikuti, lalu urusan akun dan mesin.
// Label lewat kamus terjemahan; lihat lib/i18n.js.
const NAV_UTAMA = [
  { to: '/', kunci: 'nav.beranda', Icon: Home, end: true },
  { to: '/langganan', kunci: 'nav.langganan', Icon: TvMinimalPlay },
  { to: '/riwayat', kunci: 'nav.riwayat', Icon: History },
];
const NAV_STUDIO = [
  { to: '/studio', kunci: 'nav.partitur', Icon: Music4 },
  { to: '/clips', kunci: 'nav.klip_jadi', Icon: Film },
  { to: '/analitik', kunci: 'nav.analitik', Icon: BarChart3 },
  { to: '/downloads', kunci: 'nav.unduhan', Icon: Download },
];
const NAV_LAIN = [
  { to: '/profil', kunci: 'nav.akun', Icon: UserRound },
  { to: '/settings', kunci: 'nav.pengaturan', Icon: SlidersHorizontal },
  { to: '/mesin', kunci: 'nav.mesin', Icon: Gauge },
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
  // Memuat ulang sendiri kalau build di server sudah berganti.
  useBuildWatch();
  // Pembaruan yang tersedia harus terlihat tanpa membuka Pengaturan — orang
  // tidak membuka halaman setelan untuk memeriksa sesuatu yang tidak mereka
  // tahu ada.
  const [pembaruan, setPembaruan] = useState(null);
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

  // Sekali saat aplikasi dibuka. Jawabannya di-cache backend enam jam, jadi
  // berpindah halaman tidak berarti bertanya ulang ke GitHub.
  useEffect(() => {
    apiGet('/update')
      .then((u) => { if (u?.ada_pembaruan) setPembaruan(u); })
      .catch(() => {});
  }, []);

  const t = useT();
  // Channel yang diikuti akun ini, untuk bagian "Channel diikuti" di menu.
  const [diikuti, setDiikuti] = useState([]);
  useEffect(() => {
    const muat = () => apiGet('/channel/ikuti').then((r) => setDiikuti(r.channel ?? []))
      .catch(() => setDiikuti([]));
    muat();
    window.addEventListener('omniclip:ikuti', muat);
    return () => window.removeEventListener('omniclip:ikuti', muat);
  }, []);

  const Item = ({ to, kunci, Icon, end }) => (
    <NavLink to={to} end={end} tabIndex={railOpen ? 0 : -1}
             className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
      <Icon className="nav-icon" size={18} strokeWidth={1.9} />
      <span>{t(kunci)}</span>
    </NavLink>
  );

  return (
    <div className="app-viewport" data-rail={railOpen ? 'on' : 'off'}>
      <header className="top-header">
        <button className="rail-toggle" onClick={() => setRailOpen((v) => !v)}
                aria-label={railOpen ? t('nav.tutup_menu') : t('nav.buka_menu')}
                aria-expanded={railOpen}>
          {railOpen ? <X size={17} /> : <Menu size={17} />}
        </button>

        <div className="brand-logo" onClick={() => navigate('/')}
             style={{ cursor: 'pointer' }}>
          <span>OMNI<em>CLIP</em></span>
        </div>
        <span className="brand-badge">Auto-clipper</span>

        <KotakCari />

        <div className="header-meta">
          {pembaruan && (
            <button className="header-versi" onClick={() => navigate('/settings')}
                    title={t('header.versi_tersedia', { v: pembaruan.versi_terbaru })}>
              <ArrowDownToLine size={13} />
              {t('header.versi', { v: pembaruan.versi_terbaru })}
            </button>
          )}
          <label className="header-bahasa" title={t('bahasa.pilih')}>
            <Globe size={15} />
            <select value={bahasa()} onChange={(e) => setBahasa(e.target.value)}
                    aria-label={t('bahasa.pilih')}>
              {BAHASA.map((b) => <option key={b.kode} value={b.kode}>{b.nama}</option>)}
            </select>
          </label>
          <ProfilPemilih />
        </div>
      </header>

      <nav className="side-rail" aria-hidden={!railOpen}>
        <div className="nav-kelompok">{NAV_UTAMA.map((n) => <Item key={n.to} {...n} />)}</div>
        <div className="nav-kelompok">
          <div className="nav-judul">{t('nav.studio_anda')}</div>
          {NAV_STUDIO.map((n) => <Item key={n.to} {...n} />)}
        </div>
        <div className="nav-kelompok nav-langganan">
          <div className="nav-judul">{t('nav.channel_diikuti')}</div>
          {diikuti.length === 0 && <div className="nav-kosong">{t('nav.belum_ikuti')}</div>}
          {diikuti.map((c) => (
            <NavLink key={c.channel_id} to={`/channel/${encodeURIComponent(c.channel_id)}`}
                     tabIndex={railOpen ? 0 : -1}
                     className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}>
              {c.avatar
                ? <img className="nav-avatar" src={c.avatar} alt="" referrerPolicy="no-referrer" />
                : <span className="nav-avatar nav-avatar-huruf">{(c.nama || '?').slice(0, 1)}</span>}
              <span className="nav-nama">{c.nama}</span>
            </NavLink>
          ))}
        </div>
        <div className="nav-kelompok nav-bawah">{NAV_LAIN.map((n) => <Item key={n.to} {...n} />)}</div>
      </nav>

      <main className="main-content">
        <ErrorBoundary key={location.pathname}><Outlet /></ErrorBoundary>
      </main>
    </div>
  );
}
