import React, { useState, useEffect } from 'react';
import {
  KeyRound, Loader2, Sun, Moon, Eye, EyeOff, Info,
  CheckCircle2, AlertTriangle, Cookie, Sparkles, Scissors, Mic,
  Trash2,
} from 'lucide-react';
import { apiDelete, apiGet, apiPost } from '../lib/api';
import GoogleAccountCard from './GoogleAccountCard';
import SecurityCard from './SecurityCard';
import StorageCard from './StorageCard';
import UpdateCard from './UpdateCard';

// Bagian pada satu lembar bergaris, bukan kartu di atas kartu. Tumpukan kartu
// ikon+judul+teks sebagai struktur halaman adalah wadah paling malas yang ada,
// dan menaruh kartu pilihan DI DALAMNYA menggandakan kesalahannya.
const card = {
  padding: '18px 20px',
  borderBottom: '1px solid var(--rule-2)',
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
  const [theme, setTheme] = useState(() => localStorage.getItem('omniclip_theme') || 'light');
  const [apiKey, setApiKey] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [savingKey, setSavingKey] = useState(false);
  const [feedback, setFeedback] = useState(null); // {kind:'ok'|'error', text}
  const [settings, setSettings] = useState(null);
  const [settingsError, setSettingsError] = useState(null);
  // Model AI yang dipakai untuk memilih klip. Disimpan di browser dan dikirim
  // bersama setiap permintaan auto-clip.
  const [models, setModels] = useState(null);
  const [model, setModel] = useState(() => localStorage.getItem('omniclip_gemini_model') || '');
  const [deletingKey, setDeletingKey] = useState(false);
  // Versi datang dari backend: satu sumber, bukan angka yang ditulis ulang
  // di sini dan diam-diam tertinggal saat versinya naik.
  const [versiApp, setVersiApp] = useState('');
  const [modelsError, setModelsError] = useState(null);
  // Preferensi pengklipan. Dulu tinggal di halaman tonton, yang membuat layar
  // itu penuh pilihan yang harus dibaca ulang setiap membuka video padahal
  // jarang diubah.
  const [clipLength, setClipLength] = useState(
    () => localStorage.getItem('omniclip_clip_length') || 'medium');
  const [maxClips, setMaxClips] = useState(
    () => Number(localStorage.getItem('omniclip_max_clips') || 0));
  const [whisperModel, setWhisperModel] = useState(
    () => localStorage.getItem('omniclip_whisper_model') || 'base');

  const loadSettings = async () => {
    try {
      const next = await apiGet('/settings');
      setSettings(next);
      setSettingsError(null);
      // Pilihan model tinggal di server sekarang. Dulu ia hanya di localStorage,
      // yang berarti memilih model di laptop tidak berpengaruh apa pun saat
      // aplikasi yang sama dibuka dari HP.
      if (next.ai_model !== undefined) {
        setModel(next.ai_model || '');
        if (next.ai_model) localStorage.setItem('omniclip_gemini_model', next.ai_model);
        else localStorage.removeItem('omniclip_gemini_model');
      }
    } catch (err) {
      setSettingsError(err.message);
    }
  };

  useEffect(() => { loadSettings(); }, []);

  useEffect(() => {
    apiGet('/health').then((r) => setVersiApp(r.versi || '')).catch(() => {});
  }, []);

  // Daftar model diambil dari API, bukan dari daftar tetap: model dipensiunkan
  // tanpa pemberitahuan, dan itu persis yang membuat penajaman AI diam-diam
  // gagal selama berminggu-minggu.
  useEffect(() => {
    apiGet('/settings/models')
      .then((res) => {
        setModels(res.available || []);
        if (res.error) setModelsError(res.error);
      })
      .catch((err) => setModelsError(err.message));
  }, []);

  const chooseClipLength = (v) => {
    setClipLength(v);
    localStorage.setItem('omniclip_clip_length', v);
  };

  const chooseMaxClips = (v) => {
    setMaxClips(v);
    localStorage.setItem('omniclip_max_clips', String(v));
  };

  const chooseWhisper = (v) => {
    setWhisperModel(v);
    localStorage.setItem('omniclip_whisper_model', v);
  };

  const chooseModel = (value) => {
    setModel(value);
    if (value) localStorage.setItem('omniclip_gemini_model', value);
    else localStorage.removeItem('omniclip_gemini_model');
    // Disimpan juga di server supaya berlaku di semua perangkat. Kegagalannya
    // tidak perlu mengganggu: salinan di peramban ini sudah cukup untuk
    // permintaan yang dikirim dari sini.
    apiPost('/settings/model', { model: value }).catch(() => {});
  };

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('omniclip_theme', theme);
  }, [theme]);

  const handleSaveApiKey = async () => {
    if (!apiKey.trim()) return;
    setSavingKey(true);
    setFeedback(null);
    try {
      const res = await apiPost('/settings/api-key',
        { api_key: apiKey.trim(), provider: settings?.ai_provider || 'gemini' });
      setApiKey('');
      setFeedback({ kind: 'ok', text: res.message || 'API key tersimpan.' });
      loadSettings();
    } catch (err) {
      setFeedback({ kind: 'error', text: err.message });
    } finally {
      setSavingKey(false);
    }
  };

  const handleDeleteApiKey = async () => {
    setDeletingKey(true);
    setFeedback(null);
    try {
      const res = await apiDelete('/settings/api-key');
      setFeedback({ kind: 'ok', text: res.message || 'API key dihapus.' });
      loadSettings();
    } catch (err) {
      setFeedback({ kind: 'error', text: err.message });
    } finally {
      setDeletingKey(false);
    }
  };

  const provider = settings?.providers?.find((p) => p.id === settings.ai_provider)
    || settings?.providers?.[0]
    || { id: 'gemini', label: 'Google Gemini',
         key_url: 'https://aistudio.google.com/app/apikey' };

  return (
    <div className="page" style={{ maxWidth: '780px' }}>
      <div className="work-block">
        <div style={{ minWidth: 0 }}>
          <h1 className="work-title">Catatan main</h1>
          <div className="sub">Setelan yang berlaku untuk seluruh partitur.</div>
        </div>
      </div>

      <div className="plate" style={{ overflow: 'hidden' }}>

      {settingsError && (
        <div style={{ ...card, borderColor: 'var(--accent-red)', display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
          <AlertTriangle size={18} style={{ color: 'var(--danger)', flexShrink: 0, marginTop: '2px' }} />
          <div>
            <div style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--text-primary)' }}>Backend tidak terhubung</div>
            <div style={helpText}>{settingsError}</div>
          </div>
        </div>
      )}

      {/* --- Tampilan --- */}
      <div style={card}>
        <div style={sectionTitle}>
          {theme === 'dark' ? <Moon size={18} style={{ color: 'var(--reh)' }} /> : <Sun size={18} style={{ color: 'var(--reh)' }} />}
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
                background: theme === id ? 'var(--hl-wash)' : 'transparent',
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

      {/* --- Jumlah klip --- */}
      <div style={card}>
        <div style={sectionTitle}>
          <Scissors size={18} style={{ color: 'var(--reh)' }} />
          Jumlah klip per video
        </div>
        <p style={helpText}>
          Berapa banyak momen yang ditawarkan dari satu video. Pada mode otomatis
          jatahnya tumbuh mengikuti durasi — kira-kira satu klip tiap empat menit —
          sehingga podcast dua jam tidak lagi diperlakukan sama dengan video
          sepuluh menit.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px', marginTop: '13px' }}>
          {[
            [0, 'Otomatis', 'ikut durasi'],
            [8, '8 klip', 'ringkas'],
            [16, '16 klip', 'banyak'],
            [30, '30 klip', 'maksimal'],
          ].map(([v, title, hint]) => (
            <button key={v} onClick={() => chooseMaxClips(v)} style={{
              textAlign: 'center', padding: '11px 6px', cursor: 'pointer',
              borderRadius: 'var(--radius-md)',
              border: maxClips === v ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
              background: maxClips === v ? 'var(--hl-wash)' : 'transparent',
            }}>
              <div style={{
                fontSize: '0.84rem', fontWeight: 800, marginBottom: '2px',
                color: maxClips === v ? 'var(--accent-cyan)' : 'var(--text-primary)',
              }}>{title}</div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{hint}</div>
            </button>
          ))}
        </div>
        <p style={{ ...helpText, marginTop: '11px' }}>
          Video yang sudah pernah dianalisis dengan jatah lebih kecil akan
          dianalisis ulang saat jatahnya dinaikkan.
        </p>
      </div>

      {/* --- Preferensi klip --- */}
      <div style={card}>
        <div style={sectionTitle}>
          <Scissors size={18} style={{ color: 'var(--reh)' }} />
          Panjang klip
        </div>
        <p style={helpText}>
          Batas durasi yang dicari saat menyusun klip otomatis. Batas atas inilah
          yang menentukan apakah sebuah pembahasan tertangkap utuh atau hanya
          bagian pembukanya.
        </p>
        <div style={{ display: 'grid', gap: '8px', marginTop: '13px' }}>
          {[
            ['short', 'Pendek', '15–40 detik', 'Untuk potongan singkat yang langsung ke inti.'],
            ['medium', 'Sedang', '20–60 detik', 'Pilihan aman untuk kebanyakan konten.'],
            ['long', 'Panjang', '35–110 detik', 'Menangkap pembahasan utuh: pertanyaan beserta jawabannya.'],
          ].map(([v, title, range, hint]) => (
            <button key={v} onClick={() => chooseClipLength(v)} style={{
              textAlign: 'left', padding: '11px 13px', cursor: 'pointer',
              borderRadius: 'var(--radius-md)',
              border: clipLength === v ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
              background: clipLength === v ? 'var(--hl-wash)' : 'transparent',
            }}>
              <div style={{
                fontSize: '0.88rem', fontWeight: 800, marginBottom: '3px',
                color: clipLength === v ? 'var(--accent-cyan)' : 'var(--text-primary)',
              }}>
                {title} <span style={{ fontWeight: 600, color: 'var(--text-muted)' }}>{range}</span>
              </div>
              <div style={{ fontSize: '0.76rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                {hint}
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* --- Ketelitian transkrip --- */}
      <div style={card}>
        <div style={sectionTitle}>
          <Mic size={18} style={{ color: 'var(--reh)' }} />
          Ketelitian transkrip
        </div>
        <p style={helpText}>
          Hanya berlaku untuk video yang belum punya subtitle di YouTube dan harus
          disalin ucapannya di komputer ini. Video yang sudah bersubtitle tidak
          terpengaruh dan tetap selesai dalam hitungan detik.
        </p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '13px' }}>
          {[
            ['base', 'Cepat', '± 5x lebih cepat', 'Cukup untuk bicara jelas dan pelan.'],
            ['small', 'Akurat', '± 5x lebih lama', 'Jauh lebih baik untuk percakapan cepat dan bahasa gaul.'],
          ].map(([v, title, speed, hint]) => (
            <button key={v} onClick={() => chooseWhisper(v)} style={{
              textAlign: 'left', padding: '11px 13px', cursor: 'pointer',
              borderRadius: 'var(--radius-md)',
              border: whisperModel === v ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
              background: whisperModel === v ? 'var(--hl-wash)' : 'transparent',
            }}>
              <div style={{
                fontSize: '0.88rem', fontWeight: 800, marginBottom: '3px',
                color: whisperModel === v ? 'var(--accent-cyan)' : 'var(--text-primary)',
              }}>{title}</div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '3px' }}>{speed}</div>
              <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>{hint}</div>
            </button>
          ))}
        </div>
      </div>

      {/* --- Model AI --- */}
      <div style={card}>
        <div style={sectionTitle}>
          <Sparkles size={18} style={{ color: 'var(--reh)' }} />
          Model AI pemilih klip
        </div>
        <p style={helpText}>
          Model yang membaca transkrip lalu memutuskan bagian mana yang layak jadi
          klip. Model yang lebih besar biasanya lebih paham konteks pembahasan,
          tapi lebih lambat dan memakai lebih banyak kuota.
        </p>
        {models === null && !modelsError && (
          <p style={{ ...helpText, marginTop: '10px' }}>Memuat daftar model…</p>
        )}
        {modelsError && (
          <p style={{ ...helpText, marginTop: '10px', color: 'var(--accent-red, var(--danger))' }}>
            Tidak bisa mengambil daftar model: {modelsError}
          </p>
        )}
        {models?.length > 0 && (
          <>
            <select value={model} onChange={(e) => chooseModel(e.target.value)}
                    style={{
                      width: '100%', marginTop: '12px', padding: '11px 12px',
                      borderRadius: 'var(--radius-md)', fontSize: '0.86rem',
                      border: '1px solid var(--border-color)',
                      background: 'var(--bg-glass)', color: 'var(--text-primary)',
                    }}>
              <option value="">Otomatis (coba berurutan dari yang tercepat)</option>
              {models.map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
            <p style={{ ...helpText, marginTop: '10px' }}>
              {models.length} model tersedia untuk API key ini. Untuk podcast panjang
              yang pembahasannya berlapis, model <strong>pro</strong> memberi
              pemilihan yang jauh lebih nyambung daripada <strong>flash</strong>.
            </p>
          </>
        )}
      </div>

      {/* --- Gemini API Key --- */}
      <div style={card}>
        <div style={sectionTitle}>
          <KeyRound size={18} style={{ color: 'var(--reh)' }} />
          API key AI
        </div>
        <p style={helpText}>
          Opsional. Tanpa API key, OmniClip tetap memotong klip memakai mesin heuristik
          lokal berbasis transkrip asli. Dengan API key, {provider.label} ikut menyusun
          ulang peringkat dan judul klip. Ambil kunci gratis di{' '}
          <a href={provider.key_url} target="_blank" rel="noreferrer"
             style={{ color: 'var(--reh)' }}>
            {new URL(provider.key_url).host}
          </a>.
        </p>
        <p style={{ ...helpText, marginTop: '8px' }}>
          Kunci disimpan di basis data komputer ini dan tetap ada setelah backend
          dimulai ulang — jadi tidak perlu lagi menyunting <code>backend/.env</code>
          lewat terminal, yang memang tidak bisa dilakukan dari HP. Kunci tidak
          pernah dikirim ke mana pun selain {provider.label}.
        </p>

        {settings && (
          <div style={{ ...helpText, marginTop: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            {settings.gemini_api_key_set ? (
              <>
                <CheckCircle2 size={15} style={{ color: 'var(--entry)' }} />
                Tersimpan (berakhiran <code>{settings.gemini_api_key_last4}</code>)
                {settings.gemini_api_key_source === 'env' && (
                  <span style={{ color: 'var(--text-muted)' }}>
                    — dari <code>backend/.env</code>
                  </span>
                )}
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

        {settings?.gemini_api_key_set && settings.gemini_api_key_source !== 'env' && (
          <button
            onClick={handleDeleteApiKey}
            disabled={deletingKey}
            style={{
              marginTop: '10px', display: 'flex', alignItems: 'center', gap: '7px',
              background: 'none', border: 'none', padding: '4px 0', cursor: 'pointer',
              fontSize: '0.78rem', fontWeight: 700, fontFamily: 'inherit',
              color: 'var(--danger)', opacity: deletingKey ? 0.5 : 1,
            }}
          >
            {deletingKey ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
            Hapus kunci ini
          </button>
        )}

        {feedback && (
          <div style={{
            ...helpText,
            marginTop: '10px',
            color: feedback.kind === 'ok' ? 'var(--entry)' : 'var(--accent-red)',
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
          <Cookie size={18} style={{ color: 'var(--reh)' }} />
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
              <><CheckCircle2 size={15} style={{ color: 'var(--entry)' }} /> File cookies terpasang.</>
            ) : (
              <><Info size={15} style={{ color: 'var(--text-muted)' }} /> Belum dipakai (tidak wajib).</>
            )}
          </div>
        )}
      </div>

      <UpdateCard card={card} sectionTitle={sectionTitle} helpText={helpText} />

      <StorageCard card={card} sectionTitle={sectionTitle} helpText={helpText} />

      <SecurityCard card={card} sectionTitle={sectionTitle} helpText={helpText} />

      <GoogleAccountCard card={card} sectionTitle={sectionTitle} helpText={helpText} />

      {/* --- Info --- */}
      <div style={card}>
        <div style={sectionTitle}>
          <Info size={18} style={{ color: 'var(--reh)' }} />
          Tentang
        </div>
        <div style={{ ...helpText, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '6px 16px', marginTop: '8px' }}>
          <span style={{ color: 'var(--text-muted)' }}>Versi</span><span>OmniClip {versiApp || '…'}</span>
          <span style={{ color: 'var(--text-muted)' }}>Mode</span><span>Lokal — semua file dan riwayat disimpan di komputer ini</span>
          <span style={{ color: 'var(--text-muted)' }}>Penyimpanan</span><span><code>OmniClip_Storage/</code></span>
        </div>
      </div>
      </div>
    </div>
  );
}
