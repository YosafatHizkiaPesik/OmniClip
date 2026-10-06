import React, { useEffect, useState } from 'react';
import {
  AlertTriangle, BarChart3, CheckCircle2, ExternalLink, Eye, EyeOff, Loader2, Trash2,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { apiGet, apiPost } from '../lib/api';

/**
 * Kunci YouTube Data API, untuk membaca tayangan klip yang sudah diunggah.
 *
 * Clipper menagih berdasarkan tayangan, dan sampai sekarang angkanya harus
 * dicari sendiri satu per satu di YouTube Studio — padahal OmniClip sudah tahu
 * persis video mana yang ia unggah.
 *
 * Kunci API, bukan izin akun. Izin unggah yang dipegang OmniClip tidak bisa
 * membaca statistik (diuji 2 Oktober 2026: 403), dan menambah izin BACA ke
 * akun akan menuntut setiap akun yang sudah tersambung menyambung ulang —
 * termasuk akun yang sedang dipakai orang lain. Kunci API tidak menyentuh izin
 * siapa pun. Harganya: hanya video publik yang terbaca, dan itu dikatakan di
 * sini apa adanya.
 */
export default function StatistikCard({ card, sectionTitle, helpText }) {
  const [adaKunci, setAdaKunci] = useState(null);
  const [kunci, setKunci] = useState('');
  const [lihat, setLihat] = useState(false);
  const [sibuk, setSibuk] = useState(false);
  const [kabar, setKabar] = useState(null);

  const muat = () => apiGet('/settings')
    .then((s) => setAdaKunci(!!s?.youtube_api_key_set))
    .catch(() => setAdaKunci(false));
  useEffect(() => { muat(); }, []);

  const kirim = async (nilai) => {
    setSibuk(true);
    setKabar(null);
    try {
      const r = await apiPost('/settings/youtube-key', { api_key: nilai });
      setKunci('');
      setAdaKunci(!!r?.terpasang);
      setKabar({ ok: true, teks: r?.terpasang ? 'Kunci tersimpan dan terbaca.' : 'Kunci dihapus.' });
    } catch (e) {
      setKabar({ ok: false, teks: e.message });
    } finally {
      setSibuk(false);
    }
  };

  return (
    <div style={card}>
      <div style={sectionTitle}>
        <BarChart3 size={18} style={{ color: 'var(--reh)' }} />
        Tayangan klip
      </div>
      <p className="bantu" style={helpText}>
        Dengan kunci ini, Klip jadi menampilkan berapa kali tiap klip yang sudah
        diunggah ditonton. Kuncinya hanya bisa MEMBACA angka video publik: ia
        tidak bisa mengunggah, mengubah, atau melihat apa pun yang privat, dan
        tidak menyentuh izin akun Google Anda sama sekali.
      </p>

      {adaKunci === null ? null : adaKunci ? (
        <>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '10px',
                      fontSize: '0.8rem' }}>
          <CheckCircle2 size={15} style={{ color: 'var(--entry)' }} />
          <span>Kunci terpasang.</span>
          <button className="btn-secondary" disabled={sibuk} onClick={() => kirim('')}
                  style={{ marginLeft: 'auto', display: 'inline-flex', gap: '6px',
                           alignItems: 'center' }}>
            {sibuk ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
            Hapus
          </button>
        </div>
        {/* Kunci yang terpasang tanpa tempat melihat hasilnya adalah persis
            keluhan pemiliknya: "OmniClip hanya menunjukkan kunci terpasang
            saja". Tautannya ada di sini supaya jalannya terlihat dari tempat
            kuncinya dipasang. */}
        <p className="bantu" style={{ ...helpText, marginTop: '8px' }}>
          Angkanya terbaca di{' '}
          <Link to="/analitik" style={{ color: 'var(--reh)' }}>Analitik</Link>:
          tayangan tiap klip, mana yang paling jalan, dan apa yang masih kurang
          dari klip yang sudah naik.
        </p>
        </>
      ) : (
        <>
          <ol style={{ ...helpText, margin: '10px 0 0', paddingLeft: '18px', lineHeight: 1.75 }}>
            <li>
              Buka{' '}
              <a href="https://console.cloud.google.com/apis/credentials" target="_blank"
                 rel="noreferrer" style={{ color: 'var(--reh)' }}>
                Credentials <ExternalLink size={11} style={{ verticalAlign: '-1px' }} />
              </a>{' '}
              di project Google yang sama dengan yang Anda pakai untuk unggah.
            </li>
            <li>
              <b>Create credentials &rarr; API key</b>. Tidak perlu disetel apa-apa
              lagi; kalau Anda membatasinya, sertakan <b>YouTube Data API v3</b>.
            </li>
            <li>Salin kuncinya, tempel di bawah ini.</li>
          </ol>
          <div style={{ display: 'flex', gap: '8px', marginTop: '12px' }}>
            <div style={{ position: 'relative', flex: 1 }}>
              <input
                type={lihat ? 'text' : 'password'}
                value={kunci}
                onChange={(e) => setKunci(e.target.value)}
                placeholder="AIza…"
                style={{
                  width: '100%', padding: '8px 34px 8px 10px', fontSize: '0.8rem',
                  fontFamily: 'inherit', borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--border-color)', background: 'transparent',
                  color: 'var(--ink)',
                }} />
              <button type="button" onClick={() => setLihat((v) => !v)}
                      aria-label={lihat ? 'Sembunyikan' : 'Tampilkan'}
                      style={{ position: 'absolute', right: '6px', top: '50%',
                               transform: 'translateY(-50%)', background: 'none',
                               border: 0, cursor: 'pointer', display: 'flex',
                               color: 'var(--text-secondary)' }}>
                {lihat ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
            <button className="btn-primary" disabled={sibuk || !kunci.trim()}
                    onClick={() => kirim(kunci.trim())}
                    style={{ display: 'inline-flex', gap: '7px', alignItems: 'center' }}>
              {sibuk ? <Loader2 size={15} className="animate-spin" /> : null}
              Simpan
            </button>
          </div>
        </>
      )}

      {kabar && (
        <div style={{ ...helpText, marginTop: '10px', display: 'flex', gap: '7px',
                      alignItems: 'flex-start',
                      color: kabar.ok ? 'var(--entry)' : 'var(--accent-red)' }}>
          {kabar.ok ? <CheckCircle2 size={15} style={{ flex: 'none', marginTop: '1px' }} />
                    : <AlertTriangle size={15} style={{ flex: 'none', marginTop: '1px' }} />}
          <span>{kabar.teks}</span>
        </div>
      )}
    </div>
  );
}
