import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import './index.css';
import App from './App.jsx';
import AuthGate from './components/AuthGate.jsx';
import Home from './routes/Home.jsx';
import Watch from './routes/Watch.jsx';
import Studio from './routes/Studio.jsx';
import EditorRoute from './routes/EditorRoute.jsx';
import ClipsTab from './components/ClipsTab.jsx';
import DownloadsTab from './components/DownloadsTab.jsx';
import ProfileTab from './components/ProfileTab.jsx';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthGate>
      <Routes>
        <Route path="/" element={<App />}>
          <Route index element={<Home />} />
          <Route path="watch/:videoId" element={<Watch />} />
          <Route path="studio" element={<Studio />} />
          {/* Editor punya alamat sendiri, jadi sebuah project bisa dibuka
              langsung lewat tautan dan tombol back kembali ke daftar kartu. */}
          <Route path="studio/:videoId" element={<EditorRoute />} />
          <Route path="clips" element={<ClipsTab />} />
          <Route path="downloads" element={<DownloadsTab />} />
          <Route path="settings" element={<ProfileTab />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
      </AuthGate>
    </BrowserRouter>
  </StrictMode>,
);
