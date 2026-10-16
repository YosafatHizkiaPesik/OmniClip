import React, { useState, useEffect } from 'react';
import {
  Sun, Moon, Info, AlertTriangle, Sparkles, Scissors, Mic,
  Languages, UploadCloud, ShieldAlert, Captions, Volume2, Palette, Globe,
} from 'lucide-react';
import { BAHASA, NEGARA, bahasa, namaNegara, setBahasa, setWilayah, tebal, useT, wilayahOtomatis, wilayahPilihan } from '../lib/i18n';
import HalamanSetelan from './HalamanSetelan';
import KunciGeminiCard from './KunciGeminiCard';
import { apiGet, apiPost, apiPut } from '../lib/api';
import { Link } from 'react-router-dom';
import SakelarSensor from './SakelarSensor';
import SakelarGumam from './SakelarGumam';
import SuaraCard from './SuaraCard';
import CookiesCard from './CookiesCard';
import TerjemahOtomatisCard from './TerjemahOtomatisCard';
import OpenRouterCard from './OpenRouterCard';
import LajuRenderCard from './LajuRenderCard';
import WarnaPenuturCard from './WarnaPenuturCard';

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

/**
 * Satu kelompok setelan: judul kecil, lalu kartunya mengalir di bawahnya.
 *
 * Tiga belas kartu berderet tanpa kelompok menuntut orang membaca semuanya
 * untuk menemukan satu. Dikelompokkan, matanya berhenti di satu judul dulu.
 * Keterangan kelompok ikut tersembunyi di mode Ringkas, seperti keterangan
 * setelan lainnya.
 */
export default function ProfileTab() {
  const t = useT();
  const [theme, setTheme] = useState(() => localStorage.getItem('omniclip_theme') || 'light');
  const [, setSettings] = useState(null);
  const [settingsError, setSettingsError] = useState(null);
  // Model AI yang dipakai untuk memilih klip. Disimpan di browser dan dikirim
  // bersama setiap permintaan auto-clip.
  const [models, setModels] = useState(null);
  // Berapa model disembunyikan karena kunci ini tidak punya aksesnya.
  const [modelTersembunyi, setModelTersembunyi] = useState(0);
  const [modelInfo, setModelInfo] = useState({
    terkuat: null, tanpaKuota: [], habisHarian: [], jamKePutaran: null,
  });
  const [model, setModel] = useState(() => localStorage.getItem('omniclip_gemini_model') || '');
  // Versi datang dari backend: satu sumber, bukan angka yang ditulis ulang
  // di sini dan diam-diam tertinggal saat versinya naik.
  const [versiApp, setVersiApp] = useState('');
  const [modelsError, setModelsError] = useState(null);
  // Preferensi pengklipan. Dulu tinggal di halaman tonton, yang membuat layar
  // itu penuh pilihan yang harus dibaca ulang setiap membuka video padahal
  // jarang diubah.
  const [maxClips, setMaxClips] = useState(
    () => Number(localStorage.getItem('omniclip_max_clips') || 0));
  const [whisperModel, setWhisperModel] = useState(
    () => localStorage.getItem('omniclip_whisper_model') || 'base');
  // Bahasa teks yang ditulis AI (JOB-3 J3-12): judul, alasan, caption, draf
  // komentar. 'ui' = ikut bahasa antarmuka.
  const [bahasaAi, setBahasaAi] = useState('ui');

  // Setelan milik akun aktif, dibaca sekali. Server yang menang atas salinan
  // peramban: salinan itu satu untuk semua akun, dan justru itu masalahnya.
  useEffect(() => {
    let batal = false;
    apiGet('/profil/setelan')
      .then((r) => {
        const k = r?.setelan?.klip;
        if (batal || !k) return;
        if (k.max_clips !== undefined) setMaxClips(Number(k.max_clips) || 0);
        if (k.whisper_model) setWhisperModel(String(k.whisper_model));
        if (k.bahasa_ai) setBahasaAi(String(k.bahasa_ai));
      })
      .catch(() => {});
    return () => { batal = true; };
  }, []);

  // Bahasa subtitle. Tinggal di SERVER, bukan di localStorage: yang memakainya
  // adalah pengambil caption di backend, dan pilihan yang cuma ada di peramban
  // tidak akan pernah sampai ke sana.
  const [langs, setLangs] = useState([]);
  const [bahasaUmum, setBahasaUmum] = useState(null);
  const [negara, setNegara] = useState(wilayahPilihan);
  const [langDraft, setLangDraft] = useState('');
  const [langError, setLangError] = useState(null);

  useEffect(() => {
    apiGet('/settings/languages')
      .then((r) => { setLangs(r.langs || []); setBahasaUmum(r.common || []); })
      .catch((e) => setLangError(e.message));
  }, []);

  const simpanLangs = async (next) => {
    setLangError(null);
    try {
      const r = await apiPost('/settings/languages', { langs: next });
      setLangs(r.langs || []);
    } catch (e) {
      setLangError(e.message);
    }
  };

  // Klik menambah ke AKHIR daftar, bukan menyisipkan di tempat acak: urutannya
  // adalah urutan pilihan, dan itu harus terbaca dari urutan menekannya.
  const toggleLang = (code) => simpanLangs(
    langs.includes(code) ? langs.filter((x) => x !== code) : [...langs, code]);

  const tambahLang = () => {
    const kode = langDraft.trim();
    if (!kode) return;
    setLangDraft('');
    if (!langs.includes(kode)) simpanLangs([...langs, kode]);
  };

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
        // Hanya model yang layak memilih klip, dari yang terkuat. Agen, Gemma,
        // dan varian lite ikut terdaftar di kunci tapi tidak cocok untuk ini.
        // Model yang kunci ini TIDAK punya aksesnya sama sekali tidak
        // ditampilkan. Dulu ia muncul sebagai pilihan mati bertuliskan "tidak
        // tersedia untuk kunci ini", dan yang terbaca dari situ adalah daftar
        // penuh pilihan yang tidak satu pun bisa dipakai. Jumlahnya tetap
        // disebut di bawah daftar, supaya tidak ada yang hilang diam-diam.
        const tak = new Set(res.tanpa_kuota || []);
        const semua = res.cocok?.length ? res.cocok : (res.available || []);
        setModels(semua.filter((m) => !tak.has(m)));
        setModelTersembunyi((res.tanpa_kuota || []).length);
        setModelInfo({
          terkuat: res.terkuat || null,
          tanpaKuota: res.tanpa_kuota || [],
          habisHarian: res.habis_harian || [],
          jamKePutaran: res.jam_ke_putaran ?? null,
        });
        if (res.error) setModelsError(res.error);
      })
      .catch((err) => setModelsError(err.message));
  }, []);

  /**
   * Preferensi pengklipan disimpan KE AKUN, bukan ke peramban.
   *
   * Dulu keduanya hanya di localStorage dengan satu nilai untuk semua akun,
   * jadi mengubahnya untuk satu kanal mengubahnya untuk semua kanal.
   * Dilaporkan 9 Oktober 2026: "tiap akun tidak memiliki settingnya masing
   * masing". Nilai di peramban tetap ditulis sebagai salinan cepat supaya
   * halaman ini tidak berkedip ke bawaan saat dibuka.
   */
  const simpanKlip = (nilai) => {
    apiPut('/profil/setelan', { kelompok: 'klip', nilai }).catch(() => {});
  };

  const chooseMaxClips = (v) => {
    setMaxClips(v);
    localStorage.setItem('omniclip_max_clips', String(v));
    simpanKlip({ max_clips: v });
  };

  const chooseWhisper = (v) => {
    setWhisperModel(v);
    localStorage.setItem('omniclip_whisper_model', v);
    simpanKlip({ whisper_model: v });
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

  // Keterangan panjang dilipat secara BAWAAN.
  //
  // Halaman ini punya 2018 kata saat semuanya terbuka, dan hampir semuanya
  // penjelasan yang hanya perlu dibaca sekali. Yang dipakai tiap hari cuma
  // sakelar dan kotak isiannya. Pilihannya diingat, jadi yang memang ingin
  // membaca tidak perlu menekannya berulang kali.
  const [ringkas, setRingkas] = useState(
    () => localStorage.getItem('omniclip_setelan_ringkas') !== '0');
  const ubahRingkas = () => setRingkas((r) => {
    const n = !r;
    try { localStorage.setItem('omniclip_setelan_ringkas', n ? '1' : '0'); } catch { /* mode privat */ }
    return n;
  });

  const pilihan = (on) => ({
    textAlign: 'center', padding: '11px 6px', cursor: 'pointer',
    borderRadius: 'var(--radius-md)',
    border: on ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
    background: on ? 'var(--hl-wash)' : 'transparent',
  });

  const tombolRingkas = (
    <button className="tombol-ringkas" onClick={ubahRingkas}
            title={ringkas ? t('setelan.penjelasan_judul') : t('setelan.ringkas_judul')}>
      {ringkas ? t('setelan.tampil_penjelasan') : t('setelan.ringkas')}
    </button>
  );

  const galatBackend = settingsError && (
    <div style={{ ...card, borderColor: 'var(--accent-red)', display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
      <AlertTriangle size={18} style={{ color: 'var(--danger)', flexShrink: 0, marginTop: '2px' }} />
      <div>
        <div style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--text-primary)' }}>{t('set.backend')}</div>
        <div className="bantu" style={helpText}>{settingsError}</div>
      </div>
    </div>
  );

  const klipIsi = (
    <>
      {galatBackend}
      <div style={card}>
        <div style={sectionTitle}>
          <Scissors size={18} style={{ color: 'var(--reh)' }} />
          {t('set.jumlah')}
        </div>
        <p className="bantu" style={helpText}>{t('set.jumlah_ket')}</p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px', marginTop: '13px' }}>
          {[
            [0, t('set.otomatis'), t('set.ikut_durasi')],
            [8, t('set.n_klip', { n: 8 }), t('set.ringkas')],
            [16, t('set.n_klip', { n: 16 }), t('set.banyak')],
            [30, t('set.n_klip', { n: 30 }), t('set.maksimal')],
          ].map(([v, judul, ket]) => (
            <button key={v} onClick={() => chooseMaxClips(v)} style={pilihan(maxClips === v)}>
              <div style={{
                fontSize: '0.84rem', fontWeight: 800, marginBottom: '2px',
                color: maxClips === v ? 'var(--accent-cyan)' : 'var(--text-primary)',
              }}>{judul}</div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{ket}</div>
            </button>
          ))}
        </div>
        <p className="bantu" style={{ ...helpText, marginTop: '11px' }}>{t('set.jumlah_ulang')}</p>
      </div>

      <div style={card}>
        <div style={sectionTitle}>
          <Languages size={18} style={{ color: 'var(--reh)' }} />
          {t('set.bahasa_ai')}
        </div>
        <p className="bantu" style={helpText}>{t('set.bahasa_ai_ket')}</p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '8px', marginTop: '13px' }}>
          {[
            ['ui', t('set.bahasa_ai_ui'), t('set.bahasa_ai_ui_ket')],
            ['video', t('set.bahasa_ai_video'), t('set.bahasa_ai_video_ket')],
            ['id', 'Bahasa Indonesia', t('set.bahasa_ai_selalu')],
            ['en', 'English', t('set.bahasa_ai_selalu')],
          ].map(([v, judul, ket]) => (
            <button key={v} onClick={() => { setBahasaAi(v); simpanKlip({ bahasa_ai: v }); }}
                    style={pilihan(bahasaAi === v)}>
              <div style={{
                fontSize: '0.84rem', fontWeight: 800, marginBottom: '2px',
                color: bahasaAi === v ? 'var(--accent-cyan)' : 'var(--text-primary)',
              }}>{judul}</div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>{ket}</div>
            </button>
          ))}
        </div>
      </div>

      <div style={card}>
        <div style={sectionTitle}>
          <Mic size={18} style={{ color: 'var(--reh)' }} />
          {t('set.teliti')}
        </div>
        <p className="bantu" style={helpText}>{t('set.teliti_ket')}</p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '13px' }}>
          {[
            ['base', t('set.cepat'), t('set.cepat_laju'), t('set.cepat_ket')],
            ['small', t('set.akurat'), t('set.akurat_laju'), t('set.akurat_ket')],
          ].map(([v, judul, laju, ket]) => (
            <button key={v} onClick={() => chooseWhisper(v)}
                    style={{ ...pilihan(whisperModel === v), textAlign: 'left', padding: '11px 13px' }}>
              <div style={{
                fontSize: '0.88rem', fontWeight: 800, marginBottom: '3px',
                color: whisperModel === v ? 'var(--accent-cyan)' : 'var(--text-primary)',
              }}>{judul}</div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginBottom: '3px' }}>{laju}</div>
              <div style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>{ket}</div>
            </button>
          ))}
        </div>
      </div>

      <div style={card}>
        <div style={sectionTitle}>
          <Languages size={18} style={{ color: 'var(--reh)' }} />
          {t('set.bahasa_sub')}
        </div>
        <p className="bantu" style={helpText}>{tebal(t('set.bahasa_sub_ket'))}</p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '13px' }}>
          {(bahasaUmum ?? []).map(({ code, label: nama }) => {
            const urutan = langs.indexOf(code);
            const on = urutan >= 0;
            return (
              <button key={code} onClick={() => toggleLang(code)} style={{
                display: 'inline-flex', alignItems: 'center', gap: '6px',
                padding: '7px 11px', fontSize: '0.76rem', fontWeight: 700,
                cursor: 'pointer', borderRadius: 'var(--radius-sm)',
                border: on ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                background: on ? 'var(--hl-wash)' : 'transparent',
                color: on ? 'var(--accent-cyan)' : 'var(--text-secondary)',
              }}>
                {on && (
                  <span style={{
                    minWidth: '17px', height: '17px', borderRadius: '50%',
                    background: 'var(--accent-cyan)', color: '#04121a',
                    fontSize: '0.66rem', fontWeight: 900,
                    display: 'grid', placeItems: 'center',
                  }}>{urutan + 1}</span>
                )}
                {nama}
              </button>
            );
          })}
        </div>
        <div style={{ display: 'flex', gap: '7px', marginTop: '11px', flexWrap: 'wrap' }}>
          <input value={langDraft} onChange={(e) => setLangDraft(e.target.value)}
                 placeholder={t('set.kode_lain')}
                 onKeyDown={(e) => { if (e.key === 'Enter') tambahLang(); }}
                 style={{
                   flex: '1 1 150px', padding: '8px 10px', fontSize: '0.78rem',
                   fontFamily: 'inherit', borderRadius: 'var(--radius-sm)',
                   border: '1px solid var(--border-color)', background: 'transparent',
                   color: 'var(--text-primary)',
                 }} />
          <button onClick={tambahLang} className="btn-secondary"
                  style={{ fontSize: '0.78rem' }}>{t('set.tambah')}</button>
          <button onClick={() => simpanLangs([])} className="btn-secondary"
                  style={{ fontSize: '0.78rem' }}>{t('set.bawaan')}</button>
        </div>
        {langError && (
          <p style={{ fontSize: '0.75rem', color: 'var(--danger)', margin: '9px 0 0' }}>{langError}</p>
        )}
        <p style={{ ...helpText, marginTop: '11px' }}>
          {t('set.urutan')} <strong>{langs.join(' → ') || t('set.urutan_bawaan')}</strong>
        </p>
      </div>

      <CookiesCard card={card} sectionTitle={sectionTitle} helpText={helpText} />
    </>
  );

  const subtitleIsi = (
    <>
      <div style={card}>
        <div style={sectionTitle}>
          <ShieldAlert size={18} style={{ color: 'var(--reh)' }} />
          {t('set.kata')}
        </div>
        <SakelarSensor />
        <SakelarGumam helpText={helpText} />
      </div>
      <WarnaPenuturCard card={card} sectionTitle={sectionTitle} helpText={helpText} />
      <TerjemahOtomatisCard card={card} sectionTitle={sectionTitle} helpText={helpText} />
    </>
  );

  const suaraIsi = (
    <>
      <SuaraCard card={card} sectionTitle={sectionTitle} helpText={helpText} />
      <LajuRenderCard card={card} sectionTitle={sectionTitle} helpText={helpText} />
    </>
  );

  const tampilanIsi = (
    <>
      <div style={card}>
        <div style={sectionTitle}>
          {theme === 'dark' ? <Moon size={18} style={{ color: 'var(--reh)' }} /> : <Sun size={18} style={{ color: 'var(--reh)' }} />}
          {t('set.tema')}
        </div>
        <p className="bantu" style={helpText}>{t('set.tema_ket')}</p>
        <div style={{ display: 'flex', gap: '10px', marginTop: '14px' }}>
          {[
            { id: 'dark', label: t('set.gelap'), Icon: Moon },
            { id: 'light', label: t('set.terang'), Icon: Sun },
          ].map(({ id, label, Icon }) => (
            <button key={id} onClick={() => setTheme(id)} style={{
              flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
              padding: '12px', borderRadius: 'var(--radius-md)', cursor: 'pointer',
              fontWeight: 700, fontSize: '0.85rem', fontFamily: 'inherit',
              color: theme === id ? 'var(--accent-cyan)' : 'var(--text-secondary)',
              background: theme === id ? 'var(--hl-wash)' : 'transparent',
              border: theme === id ? '1px solid var(--border-active)' : '1px solid var(--border-color)',
              transition: 'all 0.2s ease',
            }}>
              <Icon size={16} />
              {label}
            </button>
          ))}
        </div>
      </div>

      <div style={card}>
        <div style={sectionTitle}>
          <Globe size={18} style={{ color: 'var(--reh)' }} />
          {t('set.bahasa')}
        </div>
        <p className="bantu" style={helpText}>{t('set.bahasa_ket')}</p>
        <div style={{ display: 'flex', gap: '10px', marginTop: '14px', flexWrap: 'wrap' }}>
          {BAHASA.map(({ kode, nama }) => (
            <button key={kode} onClick={() => setBahasa(kode)} lang={kode} style={{
              flex: '1 1 160px', padding: '12px', borderRadius: 'var(--radius-md)', cursor: 'pointer',
              fontWeight: 700, fontSize: '0.85rem', fontFamily: 'inherit',
              color: bahasa() === kode ? 'var(--accent-cyan)' : 'var(--text-secondary)',
              background: bahasa() === kode ? 'var(--hl-wash)' : 'transparent',
              border: bahasa() === kode ? '1px solid var(--border-active)' : '1px solid var(--border-color)',
            }}>
              {nama}
            </button>
          ))}
        </div>
        <label style={{ display: 'block', marginTop: '18px', fontWeight: 700, fontSize: '0.85rem' }}
               htmlFor="pilih-negara">
          {t('set.negara')}
        </label>
        <p className="bantu" style={helpText}>{t('set.negara_ket')}</p>
        <select id="pilih-negara" value={negara}
                onChange={(e) => { setWilayah(e.target.value); setNegara(e.target.value); }}
                style={{
                  width: '100%', maxWidth: '320px', marginTop: '8px', padding: '11px 12px',
                  borderRadius: 'var(--radius-md)', fontSize: '0.86rem',
                  border: '1px solid var(--border-color)',
                  background: 'var(--bg-glass)', color: 'var(--text-primary)',
                }}>
          <option value="">{t('set.negara_otomatis', { negara: namaNegara(wilayahOtomatis()) })}</option>
          {(!negara || NEGARA.includes(negara) ? NEGARA : [negara, ...NEGARA]).map((k) => (
            <option key={k} value={k}>{namaNegara(k)}</option>
          ))}
        </select>
      </div>
    </>
  );

  const aiIsi = (
    <>
      <div style={card}>
        <div style={sectionTitle}>
          <Sparkles size={18} style={{ color: 'var(--reh)' }} />
          {t('set.model')}
        </div>
        <p className="bantu" style={helpText}>{t('set.model_ket')}</p>
        {models === null && !modelsError && (
          <p style={{ ...helpText, marginTop: '10px' }}>{t('set.memuat_model')}</p>
        )}
        {modelsError && (
          <p style={{ ...helpText, marginTop: '10px', color: 'var(--accent-red, var(--danger))' }}>
            {t('set.gagal_model', { pesan: modelsError })}
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
              <option value="">
                {t('ulang.otomatis')}{modelInfo.terkuat ? t('ulang.mencoba', { model: modelInfo.terkuat }) : ''}
              </option>
              {models.map((m) => (
                <option key={m} value={m}>
                  {m}{modelInfo.habisHarian.includes(m) ? t('ulang.jatah_habis') : ''}
                </option>
              ))}
            </select>
            <p className="bantu" style={{ ...helpText, marginTop: '10px' }}>{tebal(t('set.model_urut'))}</p>
            {modelInfo.habisHarian.length > 0 && (
              <p style={{ ...helpText, marginTop: '8px' }}>
                {t('set.habis_n', { n: modelInfo.habisHarian.length })}
                {modelInfo.jamKePutaran !== null
                  ? t('set.habis_jam', { n: modelInfo.jamKePutaran }) : t('set.habis_putar')}
                : {modelInfo.habisHarian.join(', ')}.
              </p>
            )}
            {modelTersembunyi > 0 && (
              <p className="bantu" style={{ ...helpText, marginTop: '8px' }}>
                {tebal(t('set.tersembunyi', { n: modelTersembunyi }))}
              </p>
            )}
          </>
        )}
      </div>

      <KunciGeminiCard card={card} sectionTitle={sectionTitle} helpText={helpText}
                       onBerubah={loadSettings} />
      <OpenRouterCard card={card} sectionTitle={sectionTitle} helpText={helpText} />
    </>
  );

  // Akun Google milik TIAP akun OmniClip, jadi di sini hanya tautan ke sana.
  const lainIsi = (
    <>
      <div style={card}>
        <div style={sectionTitle}>
          <UploadCloud size={18} style={{ color: 'var(--reh)' }} />
          {t('set.google')}
        </div>
        <p style={helpText}>
          <span className="bantu">{t('set.google_ket')}{' '}</span>
          {t('set.atur_di')}{' '}
          <Link to="/profil" style={{ color: 'var(--reh)', fontWeight: 700 }}>{t('set.halaman_akun')}</Link>.
        </p>
      </div>
      <div style={card}>
        <div style={sectionTitle}>
          <Info size={18} style={{ color: 'var(--reh)' }} />
          {t('set.tentang')}
        </div>
        <div style={{ ...helpText, display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '6px 16px', marginTop: '8px' }}>
          <span style={{ color: 'var(--text-muted)' }}>{t('set.versi')}</span><span>OmniClip {versiApp || '…'}</span>
          <span style={{ color: 'var(--text-muted)' }}>{t('set.mode')}</span><span>{t('set.mode_ket')}</span>
          <span style={{ color: 'var(--text-muted)' }}>{t('set.penyimpanan')}</span><span><code>OmniClip_Storage/</code></span>
        </div>
      </div>
    </>
  );

  return (
    <HalamanSetelan
      kelas={ringkas ? 'ringkas' : ''}
      judul={t('set.judul')}
      sub={t('set.sub')}
      aksi={tombolRingkas}
      bagian={[
        { id: 'klip', judul: t('set.b_klip'), nota: t('set.b_klip_nota'), Ikon: Scissors, isi: klipIsi },
        { id: 'subtitle', judul: t('set.b_subtitle'), nota: t('set.b_subtitle_nota'), Ikon: Captions, isi: subtitleIsi },
        { id: 'suara', judul: t('set.b_suara'), nota: t('set.b_suara_nota'), Ikon: Volume2, isi: suaraIsi },
        { id: 'tampilan', judul: t('set.b_tampilan'), nota: t('set.b_tampilan_nota'), Ikon: Palette, isi: tampilanIsi },
        { id: 'ai', judul: t('set.b_ai'), nota: t('set.b_ai_nota'), Ikon: Sparkles, isi: aiIsi },
        { id: 'lain', judul: t('set.b_lain'), nota: t('set.b_lain_nota'), Ikon: Info, isi: lainIsi },
      ]}
    />
  );
}
