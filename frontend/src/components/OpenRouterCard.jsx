import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Eye, EyeOff, Info, Loader2, LifeBuoy, Trash2 } from 'lucide-react';
import { apiDelete, apiGet, apiPost } from '../lib/api';
import { tebal, useT } from '../lib/i18n';

/**
 * Kunci cadangan OpenRouter.
 *
 * Kuota gratis Gemini habis pada sore hari kalau dipakai serius, dan saat itu
 * sutradara AI berhenti sama sekali. Kunci di sini membuatnya tetap jalan
 * dengan model gratis dari penyedia lain — bukan menggantikan Gemini, hanya
 * menangkapnya saat jatuh.
 */
export default function OpenRouterCard({ card, sectionTitle, helpText }) {
  const t = useT();
  const [info, setInfo] = useState(null);
  const [kunci, setKunci] = useState('');
  const [lihat, setLihat] = useState(false);
  const [simpan, setSimpan] = useState(false);
  const [hapus, setHapus] = useState(false);
  const [kabar, setKabar] = useState(null);

  const muat = () => apiGet('/settings/openrouter-models').then(setInfo).catch(() => setInfo({ tersedia: [] }));
  useEffect(() => { muat(); }, []);

  const simpanKunci = async () => {
    const nilai = kunci.trim();
    if (!nilai) return;
    setSimpan(true);
    setKabar(null);
    try {
      const r = await apiPost('/settings/openrouter-key', { api_key: nilai, provider: 'gemini' });
      setKunci('');
      setKabar({ ok: true, teks: r.message || t('akun.tersimpan') });
      muat();
    } catch (e) {
      setKabar({ ok: false, teks: e.message });
    } finally {
      setSimpan(false);
    }
  };

  const hapusKunci = async () => {
    setHapus(true);
    try {
      await apiDelete('/settings/openrouter-key');
      setKabar({ ok: true, teks: t('or.dihapus') });
      muat();
    } catch (e) {
      setKabar({ ok: false, teks: e.message });
    } finally {
      setHapus(false);
    }
  };

  const pilihModel = async (v) => {
    setInfo((s) => ({ ...s, openrouter_model: v }));
    try {
      await apiPost('/settings/openrouter-model', { model: v });
    } catch (e) {
      setKabar({ ok: false, teks: e.message });
    }
  };

  const sakelarBingkai = async (aktif) => {
    setInfo((s) => ({ ...s, bingkai_otomatis: aktif }));
    try {
      await apiPost('/settings/bingkai-otomatis', { aktif });
    } catch (e) {
      setInfo((s) => ({ ...s, bingkai_otomatis: !aktif }));
      setKabar({ ok: false, teks: e.message });
    }
  };

  // Daftar model hanya muncul setelah kuncinya ada. Memilih model tanpa kunci
  // tidak mengubah apa pun, dan menu yang tidak berpengaruh membuat orang
  // mengira cadangannya sudah menyala.
  const daftar = info?.openrouter_key_set ? (info?.tersedia || []) : [];
  return (
    <div style={card}>
      <div style={sectionTitle}>
        <LifeBuoy size={18} style={{ color: 'var(--reh)' }} />
        {t('or.judul')}
      </div>
      <p className="bantu" style={helpText}>
        {tebal(t('or.ket_a'))}{' '}
        <a href="https://openrouter.ai/keys" target="_blank" rel="noreferrer"
           style={{ color: 'var(--reh)' }}>openrouter.ai</a>{' '}
        {t('or.ket_b')}
      </p>

      {info && (
        <div style={{ ...helpText, marginTop: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          {info.openrouter_key_set ? (
            <>
              <CheckCircle2 size={15} style={{ color: 'var(--entry)' }} />
              {t('set.tersimpan_akhiran')} <code>{info.openrouter_key_last4}</code>)
            </>
          ) : (
            <>
              <Info size={15} style={{ color: 'var(--text-muted)' }} />
              {t('or.belum')}
            </>
          )}
        </div>
      )}

      <div style={{ display: 'flex', gap: '8px', marginTop: '14px' }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <input
            type={lihat ? 'text' : 'password'}
            value={kunci}
            onChange={(e) => setKunci(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && simpanKunci()}
            placeholder={t('or.placeholder')}
            style={{
              width: '100%', padding: '11px 40px 11px 14px',
              borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)',
              background: 'var(--bg-glass)', color: 'var(--text-primary)',
              fontSize: '0.85rem', fontFamily: 'inherit',
            }}
          />
          <button type="button" onClick={() => setLihat((v) => !v)}
                  aria-label={lihat ? t('or.sembunyi') : t('or.tampil')}
                  style={{
                    position: 'absolute', right: '10px', top: '50%', transform: 'translateY(-50%)',
                    background: 'none', border: 'none', cursor: 'pointer',
                    color: 'var(--text-muted)', display: 'flex', alignItems: 'center',
                  }}>
            {lihat ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>
        <button className="btn-primary" onClick={simpanKunci}
                disabled={simpan || !kunci.trim()}
                style={{ opacity: simpan || !kunci.trim() ? 0.5 : 1, whiteSpace: 'nowrap' }}>
          {simpan ? <Loader2 size={15} className="animate-spin" /> : t('umum.simpan')}
        </button>
      </div>

      {info?.openrouter_key_set && (
        <button onClick={hapusKunci} disabled={hapus}
                style={{
                  marginTop: '10px', display: 'flex', alignItems: 'center', gap: '7px',
                  background: 'none', border: 'none', padding: '4px 0', cursor: 'pointer',
                  fontSize: '0.78rem', fontWeight: 700, fontFamily: 'inherit',
                  color: 'var(--danger)', opacity: hapus ? 0.5 : 1,
                }}>
          {hapus ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
          {t('set.hapus_kunci')}
        </button>
      )}

      {daftar.length > 0 && (
        <div style={{ marginTop: '14px' }}>
          <select value={info?.openrouter_model || ''} onChange={(e) => pilihModel(e.target.value)}
                  style={{
                    width: '100%', padding: '9px 11px', fontSize: '0.8rem', fontFamily: 'inherit',
                    borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)',
                    background: 'transparent', color: 'var(--ink)',
                  }}>
            <option value="">
              {t('or.otomatis')}{info?.terkuat ? t('or.sekarang', { model: info.terkuat }) : ''}
            </option>
            {daftar.map((m) => (
              <option key={m.id} value={m.id}>
                {m.id}{m.video ? t('or.video') : t('or.gambar')}{m.suara ? t('or.suara') : ''}
              </option>
            ))}
          </select>
          <p style={{ ...helpText, marginTop: '10px' }}>
            {tebal(t('or.gratis'))}
          </p>
        </div>
      )}

      <label style={{
        display: 'flex', alignItems: 'flex-start', gap: '10px', marginTop: '16px',
        paddingTop: '14px', borderTop: '1px solid var(--border-color)', cursor: 'pointer',
      }}>
        <input type="checkbox" checked={!!info?.bingkai_otomatis}
               onChange={(e) => sakelarBingkai(e.target.checked)}
               style={{ marginTop: '3px', width: '16px', height: '16px', accentColor: 'var(--reh)' }} />
        <span style={{ ...helpText, color: 'var(--text-primary)' }}>
          <strong>{t('or.bingkai')}</strong>
          <span className="bantu">{' '}
          {t('or.bingkai_ket')}
          </span>
        </span>
      </label>

      {kabar && (
        <div style={{
          ...helpText, marginTop: '10px',
          color: kabar.ok ? 'var(--entry)' : 'var(--accent-red)',
          display: 'flex', alignItems: 'center', gap: '7px',
        }}>
          {kabar.ok ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}
          {kabar.teks}
        </div>
      )}
    </div>
  );
}
