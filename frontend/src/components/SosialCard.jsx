import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, ExternalLink, Info, Loader2, Share2 } from 'lucide-react';
import { apiGet, apiPost } from '../lib/api';

/**
 * Akun TikTok, Facebook, dan Instagram untuk profil yang sedang dipakai.
 *
 * Berbeda dari akun Google: OmniClip tidak membawa kunci aplikasi apa pun,
 * karena TikTok dan Meta mewajibkan tiap aplikasi didaftarkan atas nama yang
 * memakainya. Jadi ada dua langkah, dan urutannya tidak bisa dibalik — daftar
 * aplikasi sekali, lalu sambungkan akun per profil.
 */
export default function SosialCard({ card, sectionTitle, helpText }) {
  const [daftar, setDaftar] = useState([]);
  const [buka, setBuka] = useState(null);       // platform yang formulir kuncinya terbuka
  const [isian, setIsian] = useState({});
  const [sibuk, setSibuk] = useState(null);
  const [kabar, setKabar] = useState(null);

  const muat = () => apiGet('/uploads/sosial/status')
    .then((r) => setDaftar(r.platform || []))
    .catch((e) => setKabar({ ok: false, teks: e.message }));
  useEffect(() => { muat(); }, []);

  const simpanKunci = async (platform) => {
    setSibuk(platform);
    setKabar(null);
    try {
      const r = await apiPost('/uploads/sosial/kunci', { platform, nilai: isian });
      setDaftar(r.platform || []);
      setBuka(null);
      setIsian({});
      setKabar({ ok: true, teks: 'Kunci aplikasi tersimpan.' });
    } catch (e) {
      setKabar({ ok: false, teks: e.message });
    } finally {
      setSibuk(null);
    }
  };

  const sambung = async (platform) => {
    setSibuk(platform);
    setKabar(null);
    try {
      const r = await apiPost(`/uploads/sosial/${platform}/connect`, {});
      window.open(r.authorization_url, '_blank', 'noopener');
      setKabar({ ok: true, teks: 'Beri izin di tab yang baru terbuka, lalu kembali dan muat ulang kartu ini.' });
    } catch (e) {
      setKabar({ ok: false, teks: e.message });
    } finally {
      setSibuk(null);
    }
  };

  const putus = async (platform) => {
    if (!window.confirm('Putuskan akun ini dari profil yang sedang dipakai?')) return;
    setSibuk(platform);
    try {
      await apiPost(`/uploads/sosial/${platform}/disconnect`, {});
      muat();
    } catch (e) {
      setKabar({ ok: false, teks: e.message });
    } finally {
      setSibuk(null);
    }
  };

  const KUNCI = {
    tiktok: [['client_key', 'Client key'], ['client_secret', 'Client secret']],
    facebook: [['app_id', 'App ID'], ['app_secret', 'App secret']],
    instagram: [['app_id', 'App ID'], ['app_secret', 'App secret']],
  };

  return (
    <div style={card}>
      <div style={sectionTitle}>
        <Share2 size={18} style={{ color: 'var(--reh)' }} />
        TikTok, Facebook, dan Instagram
      </div>
      <p style={helpText}>
        Satu klip vertikal cocok untuk keempat tempat sekaligus. Bedanya dengan akun
        Google: TikTok dan Meta mewajibkan <b>aplikasi</b> didaftarkan atas nama Anda
        sendiri, jadi ada dua langkah — daftarkan aplikasinya sekali, lalu sambungkan
        akunnya per profil. Facebook dan Instagram memakai satu aplikasi Meta yang sama.
      </p>

      {daftar.map((p) => (
        <div key={p.platform} style={{
          marginTop: '12px', paddingTop: '12px', borderTop: '1px solid var(--border-color)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <b style={{ fontSize: '0.86rem' }}>{p.label}</b>
            {p.tersambung ? (
              <span style={{ ...helpText, display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                <CheckCircle2 size={14} style={{ color: 'var(--entry)' }} />
                {p.akun}
                {p.sisa_hari != null && p.sisa_hari < 7 && (
                  <b style={{ color: 'var(--accent-red)' }}>
                    — izin habis {p.sisa_hari} hari lagi
                  </b>
                )}
              </span>
            ) : (
              <span style={{ ...helpText, display: 'inline-flex', alignItems: 'center', gap: '5px' }}>
                <Info size={14} style={{ color: 'var(--text-muted)' }} />
                {p.siap ? 'Aplikasi siap — akun belum tersambung' : 'Kunci aplikasi belum diisi'}
              </span>
            )}
          </div>
          <p style={{ ...helpText, margin: '5px 0 0' }}>{p.catatan}</p>

          <div style={{ display: 'flex', gap: '7px', marginTop: '9px', flexWrap: 'wrap' }}>
            <button className="btn-secondary" style={{ fontSize: '0.76rem' }}
                    onClick={() => { setBuka(buka === p.platform ? null : p.platform); setIsian({}); }}>
              {p.siap ? 'Ganti kunci aplikasi' : 'Isi kunci aplikasi'}
            </button>
            {p.siap && !p.tersambung && (
              <button className="btn-primary" style={{ fontSize: '0.76rem' }}
                      disabled={sibuk === p.platform}
                      onClick={() => sambung(p.platform)}>
                {sibuk === p.platform ? <Loader2 size={13} className="animate-spin" /> : 'Sambungkan akun'}
              </button>
            )}
            {p.tersambung && (
              <button style={{
                background: 'none', border: 'none', cursor: 'pointer', padding: '4px 0',
                fontSize: '0.76rem', fontWeight: 700, fontFamily: 'inherit', color: 'var(--danger)',
              }} onClick={() => putus(p.platform)}>
                Putuskan
              </button>
            )}
            <a href={p.daftar} target="_blank" rel="noreferrer"
               style={{ ...helpText, display: 'inline-flex', alignItems: 'center', gap: '4px',
                        color: 'var(--reh)' }}>
              Portal pengembang <ExternalLink size={12} />
            </a>
          </div>

          {buka === p.platform && (
            <div style={{ marginTop: '10px' }}>
              {(KUNCI[p.platform] || []).map(([nama, label]) => (
                <input key={nama} placeholder={label} value={isian[nama] || ''}
                       onChange={(e) => setIsian((s) => ({ ...s, [nama]: e.target.value }))}
                       style={{
                         width: '100%', marginBottom: '7px', padding: '8px 11px',
                         borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)',
                         background: 'var(--bg-glass)', color: 'var(--text-primary)',
                         fontSize: '0.8rem', fontFamily: 'inherit',
                       }} />
              ))}
              <p style={{ ...helpText, margin: '0 0 8px' }}>
                Daftarkan alamat balik ini persis seperti tertulis di portal pengembangnya:
                <br />
                <code style={{ fontSize: '0.72rem' }}>{p.redirect_uri}</code>
              </p>
              <button className="btn-primary" style={{ fontSize: '0.76rem' }}
                      disabled={sibuk === p.platform}
                      onClick={() => simpanKunci(p.platform)}>
                {sibuk === p.platform ? <Loader2 size={13} className="animate-spin" /> : 'Simpan kunci'}
              </button>
            </div>
          )}
        </div>
      ))}

      {kabar && (
        <div style={{
          ...helpText, marginTop: '12px', display: 'flex', alignItems: 'center', gap: '7px',
          color: kabar.ok ? 'var(--entry)' : 'var(--accent-red)',
        }}>
          {kabar.ok ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}
          {kabar.teks}
        </div>
      )}
    </div>
  );
}
