import React, { useEffect, useState } from 'react';
import { Cpu, Loader2, Download, Trash2, CheckCircle2, AlertTriangle, Star } from 'lucide-react';
import { apiDelete, apiGet, apiPost } from '../lib/api';
import { useJobRunner } from '../hooks/useJob';
import { tebal, useT } from '../lib/i18n';

/**
 * AI lokal OmniClip (diminta pemilik 17 Oktober 2026): model bahasa kecil
 * yang berjalan di komputer ini, tanpa kunci dan tanpa kuota. Backend:
 * services/ai_lokal.py (llama.cpp + model GGUF yang dipatok sha256-nya).
 */
export default function AiLokalCard({ card, sectionTitle, helpText, onBerubah }) {
  const t = useT();
  const [st, setSt] = useState(null);
  const [pilih, setPilih] = useState('');
  const [kabar, setKabar] = useState(null);
  const [sibuk, setSibuk] = useState(false);
  const [tautan, setTautan] = useState('');
  const pasang = useJobRunner();

  const muat = () => apiGet('/settings/ai-lokal').then((r) => {
    setSt(r);
    setPilih((p) => p || r.bawaan);
  }).catch((e) => setKabar({ ok: false, teks: e.message }));
  useEffect(() => { muat(); }, []);
  useEffect(() => { if (pasang.status === 'done') muat(); }, [pasang.status]);

  if (!st) return null;
  const m = st.model.find((x) => x.id === pilih) || st.model[0];
  const ramCukup = !st.ram_bebas_mb || st.ram_bebas_mb >= m.ram_mb + 400;

  const pakaiUtama = async () => {
    setSibuk(true); setKabar(null);
    try {
      const r = await apiPost('/settings/koneksi-ai', { penyedia: 'lokal', model: m.id, nama: `${t('koneksi.p_lokal')} (${m.nama})` },
        { timeout: 300000 });
      await apiPost(`/settings/koneksi-ai/${r.id}/utama`, {});
      setKabar({ ok: true, teks: t('lokal.jadi_utama') });
      onBerubah?.();
    } catch (e) {
      setKabar({ ok: false, teks: e.message });
    } finally {
      setSibuk(false);
    }
  };

  return (
    <div style={card}>
      <div style={sectionTitle}>
        <Cpu size={18} style={{ color: 'var(--reh)' }} />
        {t('lokal.judul')}
      </div>
      <p className="bantu" style={helpText}>{tebal(t('lokal.ket'))}</p>
      <p className="bantu" style={{ ...helpText, marginTop: 6 }}>{tebal(t('lokal.ket_model'))}</p>
      {!st.didukung && <p style={{ ...helpText, color: 'var(--danger)' }}>{t('lokal.tidak_didukung')}</p>}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 8, marginTop: 12 }}>
        {st.model.map((x) => (
          <button key={x.id} onClick={() => setPilih(x.id)} style={{
            textAlign: 'left', padding: '10px 12px', borderRadius: 'var(--radius-md)', cursor: 'pointer', fontFamily: 'inherit',
            border: `1px solid ${pilih === x.id ? 'var(--border-active, var(--reh))' : 'var(--border-color)'}`,
            background: pilih === x.id ? 'var(--hl-wash)' : 'transparent', color: 'var(--text-primary)',
          }}>
            <div style={{ fontWeight: 800, fontSize: '.84rem' }}>
              {x.nama} {x.id === st.bawaan && <span style={{ color: 'var(--reh)', fontSize: '.7rem' }}>· {t('lokal.disarankan')}</span>}
            </div>
            <div style={{ fontSize: '.72rem', color: 'var(--text-secondary)', marginTop: 3 }}>
              {t('lokal.ukuran', { gb: (x.ukuran_mb / 1000).toFixed(1), ram: (x.ram_mb / 1000).toFixed(1) })}
            </div>
            <div style={{ fontSize: '.7rem', marginTop: 3, color: x.terpasang ? 'var(--entry)' : 'var(--text-muted)' }}>
              {x.terpasang ? t('lokal.terpasang') : t('lokal.belum')}
              {x.kustom ? ` · ${t('lokal.dari_hf')}` : ''}
            </div>
          </button>
        ))}
      </div>

      <p style={{ ...helpText, marginTop: 8, color: ramCukup ? 'var(--text-muted)' : 'var(--reh)' }}>
        {t('lokal.ram', { bebas: (st.ram_bebas_mb / 1000).toFixed(1), perlu: ((m.ram_mb + 400) / 1000).toFixed(1) })}
        {!ramCukup && ` ${t('lokal.ram_kurang')}`}
      </p>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 10 }}>
        {!m.terpasang && (
          <button className="btn-primary" disabled={pasang.active || !st.didukung}
                  onClick={() => { setKabar(null); pasang.run('/settings/ai-lokal/pasang', { model: m.id }).catch(() => {}); }}>
            {pasang.active ? <Loader2 size={15} className="animate-spin" /> : <Download size={15} />}
            {t('lokal.pasang', { gb: (m.ukuran_mb / 1000).toFixed(1) })}
          </button>
        )}
        {m.terpasang && (
          <>
            <button className="btn-primary" disabled={sibuk} onClick={pakaiUtama}>
              {sibuk ? <Loader2 size={15} className="animate-spin" /> : <Star size={15} />}
              {sibuk ? t('lokal.menguji') : t('lokal.pakai_utama')}
            </button>
            <button className="btn-secondary" disabled={sibuk || pasang.active}
                    onClick={() => window.confirm(t('lokal.yakin_hapus', { nama: m.nama }))
                      && apiDelete(`/settings/ai-lokal/model/${m.id}`).then(setSt).catch((e) => setKabar({ ok: false, teks: e.message }))}>
              <Trash2 size={14} /> {t('lokal.hapus')}
            </button>
          </>
        )}
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 14 }}>
        <input value={tautan} onChange={(e) => setTautan(e.target.value)} spellCheck={false}
               placeholder={t('lokal.hf_placeholder')}
               style={{ flex: '1 1 320px', padding: '9px 11px', borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--border-color)', background: 'var(--bg-glass)',
                        color: 'var(--text-primary)', fontSize: '0.8rem', fontFamily: 'inherit' }} />
        <button className="btn-secondary" disabled={!tautan.trim() || sibuk}
                onClick={() => {
                  setSibuk(true); setKabar(null);
                  apiPost('/settings/ai-lokal/kustom', { url: tautan.trim() }, { timeout: 60000 })
                    .then((r) => { setSt(r); setTautan(''); setKabar({ ok: true, teks: t('lokal.hf_ok') }); })
                    .catch((e) => setKabar({ ok: false, teks: e.message }))
                    .finally(() => setSibuk(false));
                }}>
          {t('lokal.hf_tambah')}
        </button>
      </div>

      {pasang.active && (
        <div style={{ marginTop: 10 }}>
          <div style={{ fontSize: '.76rem', color: 'var(--text-secondary)' }}>{pasang.message}</div>
          <div style={{ height: 5, marginTop: 5, borderRadius: 99, background: 'var(--bg-glass)', border: '1px solid var(--border-color)', overflow: 'hidden' }}>
            <div style={{ width: `${Math.max(2, Math.round((pasang.progress || 0) * 100))}%`, height: '100%', background: 'var(--reh)', transition: 'width .5s' }} />
          </div>
        </div>
      )}
      {pasang.error && <p style={{ ...helpText, color: 'var(--danger)', marginTop: 8 }}>{pasang.error.message}</p>}
      {kabar && (
        <div style={{ ...helpText, marginTop: '10px', display: 'flex', gap: '7px', alignItems: 'flex-start',
                      color: kabar.ok ? 'var(--entry)' : 'var(--accent-red, var(--danger))' }}>
          {kabar.ok ? <CheckCircle2 size={15} style={{ flex: 'none' }} /> : <AlertTriangle size={15} style={{ flex: 'none' }} />}
          {kabar.teks}
        </div>
      )}
    </div>
  );
}
