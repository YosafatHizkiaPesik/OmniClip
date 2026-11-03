import { lazy, StrictMode, Suspense } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import './index.css';
import App from './App.jsx';
import { selaraskanProfil } from './lib/api';
import AuthGate from './components/AuthGate.jsx';
import Home from './routes/Home.jsx';
import Watch from './routes/Watch.jsx';
import Studio from './routes/Studio.jsx';
import EditorRoute from './routes/EditorRoute.jsx';
import Profil from './routes/Profil.jsx';
import ClipsTab from './components/ClipsTab.jsx';
import AnalitikTab from './components/AnalitikTab.jsx';
import DownloadsTab from './components/DownloadsTab.jsx';
import ProfileTab from './components/ProfileTab.jsx';
import MesinTab from './components/MesinTab';
import Channel from './routes/Channel.jsx';
import Langganan from './routes/Langganan.jsx';
import Riwayat from './routes/Riwayat.jsx';

// Montase dimuat hanya saat dibuka: Remotion menambah ratusan kilobita yang
// tidak perlu dibayar halaman lain.
const MontaseUji = lazy(() => import('./features/montase/uji/MontaseUji.jsx'));

// Profil terakhir diambil dari server SEBELUM apa pun digambar. Setiap
// permintaan membawa nomor profil di headernya, jadi menggambar dulu lalu
// membetulkan kemudian berarti permintaan pertama berangkat atas nama profil
// yang salah — dan yang terlihat pengguna adalah daftar video akun lain.
selaraskanProfil().finally(() => {
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthGate>
      <Routes>
        <Route path="/" element={<App />}>
          <Route index element={<Home />} />
          <Route path="watch/:videoId" element={<Watch />} />
          <Route path="channel/:ref" element={<Channel />} />
          <Route path="langganan" element={<Langganan />} />
          <Route path="riwayat" element={<Riwayat />} />
          <Route path="studio" element={<Studio />} />
          {/* Editor punya alamat sendiri, jadi sebuah project bisa dibuka
              langsung lewat tautan dan tombol back kembali ke daftar kartu. */}
          <Route path="studio/:videoId" element={<EditorRoute />} />
          <Route path="clips" element={<ClipsTab />} />
          <Route path="analitik" element={<AnalitikTab />} />
          <Route path="downloads" element={<DownloadsTab />} />
          <Route path="profil" element={<Profil />} />
          <Route path="settings" element={<ProfileTab />} />
          <Route path="mesin" element={<MesinTab />} />
          {/* Halaman uji Tahap 0 (JOB-4.md); diganti menu Montase di Tahap 1. */}
          <Route path="montase-uji" element={<Suspense fallback={null}><MontaseUji /></Suspense>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
      </AuthGate>
    </BrowserRouter>
  </StrictMode>,
);
});
