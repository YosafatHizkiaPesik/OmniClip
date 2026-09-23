import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Eye, EyeOff, Info, Loader2, LifeBuoy, Trash2 } from 'lucide-react';
import { apiDelete, apiGet, apiPost } from '../lib/api';

/**
 * Kunci cadangan OpenRouter.
 *
 * Kuota gratis Gemini habis pada sore hari kalau dipakai serius, dan saat itu
 * sutradara AI berhenti sama sekali. Kunci di sini membuatnya tetap jalan
 * dengan model gratis dari penyedia lain — bukan menggantikan Gemini, hanya
 * menangkapnya saat jatuh.
 */
export default function OpenRouterCard({ card, sectionTitle, helpText }) {
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
      setKabar({ ok: true, teks: r.message || 'Tersimpan.' });
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
      setKabar({ ok: true, teks: 'Kunci OpenRouter dihapus.' });
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

  const daftar = info?.tersedia || [];
  return (
    <div style={card}>
      <div style={sectionTitle}>
        <LifeBuoy size={18} style={{ color: 'var(--reh)' }} />
        Sutradara bingkai: cadangan dan otomatis
      </div>
      <p style={helpText}>
        Opsional. Kuota gratis Gemini terbatas per hari, dan begitu habis sutradara
        bingkai berhenti sampai besok. Dengan kunci{' '}
        <a href="https://openrouter.ai/keys" target="_blank" rel="noreferrer"
           style={{ color: 'var(--reh)' }}>openrouter.ai</a>{' '}
        OmniClip pindah sendiri ke model gratis di sana dan pekerjaannya jalan terus.
        Gemini tetap yang dipakai lebih dulu selama masih bisa.
      </p>

      {info && (
        <div style={{ ...helpText, marginTop: '10px', display: 'flex', alignItems: 'center', gap: '8px' }}>
          {info.openrouter_key_set ? (
            <>
              <CheckCircle2 size={15} style={{ color: 'var(--entry)' }} />
              Tersimpan (berakhiran <code>{info.openrouter_key_last4}</code>)
            </>
          ) : (
            <>
              <Info size={15} style={{ color: 'var(--text-muted)' }} />
              Belum diisi — saat kuota Gemini habis, bingkai disusun mesin lokal.
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
            placeholder="Tempel kunci OpenRouter di sini…"
            style={{
              width: '100%', padding: '11px 40px 11px 14px',
              borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)',
              background: 'var(--bg-glass)', color: 'var(--text-primary)',
              fontSize: '0.85rem', fontFamily: 'inherit',
            }}
          />
          <button type="button" onClick={() => setLihat((v) => !v)}
                  aria-label={lihat ? 'Sembunyikan kunci' : 'Tampilkan kunci'}
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
          {simpan ? <Loader2 size={15} className="animate-spin" /> : 'Simpan'}
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
          Hapus kunci ini
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
              Otomatis — yang paling cocok{info?.terkuat ? ` (sekarang ${info.terkuat})` : ''}
            </option>
            {daftar.map((m) => (
              <option key={m.id} value={m.id}>
                {m.id}{m.video ? ' — bisa menonton video' : ' — hanya gambar'}{m.suara ? ' + suara' : ''}
              </option>
            ))}
          </select>
          <p style={{ ...helpText, marginTop: '10px' }}>
            Hanya model <strong>gratis</strong> yang ditampilkan, diurutkan dari yang
            paling cocok: yang bisa menonton video dan mendengar suaranya lebih dulu,
            karena tawa lebih jelas terdengar daripada terlihat. Model berbayar tidak
            pernah dipilih sendiri.
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
        <span style={helpText}>
          <strong style={{ color: 'var(--text-primary)' }}>Susun bingkai sendiri sesudah mengklip.</strong>{' '}
          Tanpa ini, bingkai reaksi baru disusun saat Anda menekan tombolnya di Studio.
          Dengan ini, 6 klip pertama tiap video sudah berbingkai saat dibuka. Sengaja
          mati sejak awal: tiap klip memakai satu panggilan model, dari kuota harian
          yang sama dengan yang dipakai untuk memilih klip video berikutnya.
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
