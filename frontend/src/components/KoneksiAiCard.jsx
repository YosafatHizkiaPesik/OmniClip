import React, { useEffect, useState } from 'react';
import {
  Plug, Loader2, Trash2, FlaskConical, CheckCircle2, AlertTriangle, Eye, EyeOff, Pencil,
  ArrowUp, ArrowDown, Star,
} from 'lucide-react';
import { apiDelete, apiGet, apiPost, apiPut } from '../lib/api';
import { lokal, tebal, useT } from '../lib/i18n';

/**
 * Koneksi AI universal (diminta pemilik 17 Oktober 2026).
 *
 * Satu daftar untuk semua penyedia: Gemini, OpenRouter, Claude, OpenAI, Groq,
 * Mistral, DeepSeek, Cerebras, server bergaya OpenAI (Ollama, LM Studio), dan
 * AI lokal OmniClip. Urutannya urutan dicoba; yang teratas dan aktif adalah
 * UTAMA, sisanya cadangan bila yang di atasnya gagal. Backend:
 * services/koneksi_ai.py.
 */
const WARNA = {
  bekerja: 'var(--entry)', kuota: 'var(--reh)', sibuk: 'var(--reh)', pilih_model: 'var(--reh)',
  saldo: 'var(--reh)', ditolak: 'var(--accent-red, var(--danger))',
  tidak_sah: 'var(--accent-red, var(--danger))', tidak_ada: 'var(--accent-red, var(--danger))',
  galat: 'var(--accent-red, var(--danger))',
};
const WARNA_MODEL = {
  ok: 'var(--entry)', kuota_harian: 'var(--reh)', kuota_menit: 'var(--reh)', kuota: 'var(--reh)',
  sibuk: 'var(--reh)', tanpa_jatah: 'var(--text-muted)', tidak_ada: 'var(--text-muted)',
};

export default function KoneksiAiCard({ card, sectionTitle, helpText, onBerubah, segarkan }) {
  const t = useT();
  const [daftar, setDaftar] = useState(null);
  const [penyedia, setPenyedia] = useState([]);
  const [pilih, setPilih] = useState('gemini');
  const [nama, setNama] = useState('');
  const [kunci, setKunci] = useState('');
  const [model, setModel] = useState('');
  const [alamat, setAlamat] = useState('');
  const [lihat, setLihat] = useState(false);
  const [sibuk, setSibuk] = useState('');
  const [kabar, setKabar] = useState(null);
  const [ubahNama, setUbahNama] = useState(null);

  const pakai = (r, teks) => {
    setDaftar(r.koneksi || []);
    if (r.penyedia) setPenyedia(r.penyedia);
    if (teks) setKabar({ ok: true, teks });
    onBerubah?.();
  };
  const muat = () => apiGet('/settings/koneksi-ai')
    .then((r) => pakai(r))
    .catch((e) => setKabar({ ok: false, teks: e.message }));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { muat(); }, [segarkan]);

  const p = penyedia.find((x) => x.id === pilih) || {};

  const kerjakan = async (id, fn, teksOk) => {
    setSibuk(id); setKabar(null);
    try {
      const r = await fn();
      pakai(r, typeof teksOk === 'function' ? teksOk(r) : teksOk);
    } catch (e) {
      setKabar({ ok: false, teks: e.message });
    } finally {
      setSibuk('');
    }
  };

  const tambah = () => kerjakan('tambah', async () => {
    const r = await apiPost('/settings/koneksi-ai', {
      penyedia: pilih, api_key: kunci.trim(), nama: nama.trim(), model: model.trim(), alamat: alamat.trim(),
    }, { timeout: 300000 });
    setKunci(''); setNama(''); setModel('');
    return r;
  }, (r) => (r.uji?.status === 'bekerja' ? t('kunci.tambah_ok') : t('kunci.tambah_catat')));

  const geser = (i, arah) => {
    const ids = daftar.map((k) => k.id);
    const j = i + arah;
    if (j < 0 || j >= ids.length) return;
    [ids[i], ids[j]] = [ids[j], ids[i]];
    kerjakan('urut', () => apiPut('/settings/koneksi-ai-urutan', { ids }));
  };

  const simpanNama = () => {
    if (!ubahNama) return;
    const u = ubahNama;
    setUbahNama(null);
    kerjakan(u.id, () => apiPut(`/settings/koneksi-ai/${u.id}`, { nama: u.nama }));
  };

  const labelModel = (m) => {
    switch (m.status) {
      case 'ok': return t('kunci.m_ok', { s: m.detik ?? '?' });
      case 'kuota_harian': return m.tunggu ? t('kunci.m_harian_jam', { n: Math.max(1, Math.round(m.tunggu / 3600)) }) : t('kunci.m_harian');
      case 'kuota_menit': case 'kuota': return t('kunci.m_menit');
      case 'tanpa_jatah': return t('kunci.m_tanpa_jatah');
      case 'ditolak': return t('kunci.m_ditolak');
      case 'tidak_ada': return t('kunci.m_tidak_ada');
      case 'tidak_sah': return t('kunci.m_tidak_sah');
      case 'saldo': return t('koneksi.m_saldo');
      case 'sibuk': return t('kunci.m_sibuk');
      default: return t('kunci.m_galat');
    }
  };

  const input = {
    padding: '9px 11px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)',
    background: 'var(--bg-glass)', color: 'var(--text-primary)', fontSize: '0.83rem', fontFamily: 'inherit',
  };
  const ikon = {
    background: 'none', border: 0, cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', padding: 4,
  };

  return (
    <div style={card}>
      <div style={sectionTitle}>
        <Plug size={18} style={{ color: 'var(--reh)' }} />
        {t('koneksi.judul')}
      </div>
      <p className="bantu" style={helpText}>{tebal(t('koneksi.ket'))}</p>
      <p className="bantu" style={{ ...helpText, marginTop: '6px' }}>{tebal(t('kunci.ket_uji'))}</p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '14px' }}>
        {daftar === null && <Loader2 size={16} className="animate-spin" />}
        {daftar?.length === 0 && <p style={{ ...helpText, margin: 0 }}>{t('koneksi.kosong')}</p>}
        {daftar?.map((k, i) => {
          const st = k.uji?.status;
          const pilihanModel = k.uji?.daftar_model || [];
          return (
            <div key={k.id} style={{
              border: `1px solid ${k.utama ? 'var(--border-active, var(--reh))' : 'var(--border-color)'}`,
              borderRadius: 'var(--radius-md)', padding: '10px 12px', background: 'var(--bg-glass)',
              opacity: k.aktif ? 1 : 0.6,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                <span style={{ display: 'flex', flexDirection: 'column' }}>
                  <button style={ikon} disabled={i === 0 || !!sibuk} onClick={() => geser(i, -1)}
                          aria-label={t('koneksi.naik')} title={t('koneksi.naik')}><ArrowUp size={13} /></button>
                  <button style={ikon} disabled={i === daftar.length - 1 || !!sibuk} onClick={() => geser(i, 1)}
                          aria-label={t('koneksi.turun')} title={t('koneksi.turun')}><ArrowDown size={13} /></button>
                </span>
                <input type="checkbox" checked={k.aktif} disabled={!!sibuk} title={t('koneksi.aktif')}
                       onChange={(e) => kerjakan(k.id, () => apiPut(`/settings/koneksi-ai/${k.id}`, { aktif: e.target.checked }))}
                       style={{ accentColor: 'var(--accent-cyan)' }} />
                {ubahNama?.id === k.id ? (
                  <input autoFocus value={ubahNama.nama} maxLength={60}
                         onChange={(e) => setUbahNama({ ...ubahNama, nama: e.target.value })}
                         onBlur={simpanNama}
                         onKeyDown={(e) => { if (e.key === 'Enter') simpanNama(); if (e.key === 'Escape') setUbahNama(null); }}
                         style={{ ...input, padding: '4px 8px', fontWeight: 700 }} />
                ) : (
                  <button type="button" onClick={() => setUbahNama({ id: k.id, nama: k.nama })} title={t('kunci.ubah_nama')}
                          style={{ background: 'none', border: 0, padding: 0, cursor: 'pointer', color: 'var(--text-primary)',
                                   font: 'inherit', fontWeight: 800, fontSize: '0.86rem', display: 'inline-flex', gap: '6px', alignItems: 'center' }}>
                    {k.nama} <Pencil size={11} style={{ opacity: 0.5 }} />
                  </button>
                )}
                <span style={{ fontSize: '.68rem', color: 'var(--text-muted)', border: '1px solid var(--border-color)',
                               borderRadius: 99, padding: '1px 7px' }}>
                  {k.penyedia_nama}{k.sumber === 'env' ? ' · .env' : ''}
                </span>
                {k.utama && (
                  <span style={{ fontSize: '.66rem', fontWeight: 800, color: 'var(--reh)', display: 'inline-flex', gap: 3, alignItems: 'center' }}>
                    <Star size={11} /> {t('koneksi.utama')}
                  </span>
                )}
                <span style={{ flex: 1 }} />
                <span style={{ fontSize: '0.74rem', fontWeight: 800, color: WARNA[st] || 'var(--text-muted)' }}>
                  {st ? t(`koneksi.s_${st}`) : t('kunci.s_belum')}
                </span>
                {!k.utama && k.aktif && (
                  <button className="btn-secondary" disabled={!!sibuk} style={{ fontSize: '0.72rem', padding: '4px 9px' }}
                          onClick={() => kerjakan(k.id, () => apiPost(`/settings/koneksi-ai/${k.id}/utama`, {}))}>
                    {t('koneksi.jadikan_utama')}
                  </button>
                )}
                <button className="btn-secondary" onClick={() => kerjakan(k.id, () => apiPost(`/settings/koneksi-ai/${k.id}/uji`, {}, { timeout: 300000 }))}
                        disabled={!!sibuk} style={{ fontSize: '0.74rem', padding: '4px 9px' }}>
                  {sibuk === k.id ? <Loader2 size={13} className="animate-spin" /> : <FlaskConical size={13} />}
                  {sibuk === k.id ? t('kunci.menguji') : t('kunci.uji')}
                </button>
                {k.sumber !== 'env' && (
                  <button onClick={() => window.confirm(t('kunci.yakin_hapus', { nama: k.nama }))
                                  && kerjakan(k.id, () => apiDelete(`/settings/koneksi-ai/${k.id}`), t('kunci.terhapus', { nama: k.nama }))}
                          disabled={!!sibuk} aria-label={t('kunci.hapus')} title={t('kunci.hapus')}
                          style={{ ...ikon, color: 'var(--danger)' }}>
                    <Trash2 size={15} />
                  </button>
                )}
              </div>

              {k.penyedia !== 'gemini' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8, fontSize: '.76rem', color: 'var(--text-secondary)' }}>
                  <span>{t('koneksi.model')}</span>
                  <input list={`model-${k.id}`} defaultValue={k.model} key={`${k.id}-${k.model}`}
                         placeholder={k.model_bawaan || (k.penyedia === 'openrouter' ? t('koneksi.model_otomatis') : t('koneksi.model_pilih'))}
                         onBlur={(e) => e.target.value.trim() !== k.model
                           && kerjakan(k.id, () => apiPut(`/settings/koneksi-ai/${k.id}`, { model: e.target.value.trim() }))}
                         style={{ ...input, padding: '4px 8px', flex: 1, maxWidth: 360 }} />
                  <datalist id={`model-${k.id}`}>
                    {pilihanModel.map((m) => <option key={m} value={m} />)}
                  </datalist>
                </div>
              )}

              {k.uji && (
                <>
                  {(k.uji.model || []).length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '8px' }}>
                      {k.uji.model.map((m) => (
                        <span key={m.model} className="chip" title={m.pesan || ''}
                              style={{ fontSize: '.68rem', padding: '2px 8px', cursor: 'default',
                                       color: WARNA_MODEL[m.status] || 'var(--accent-red, var(--danger))' }}>
                          <b style={{ color: 'var(--text-primary)', fontWeight: 700 }}>{m.model}</b>&nbsp;· {labelModel(m)}
                        </span>
                      ))}
                    </div>
                  )}
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '6px', lineHeight: 1.5 }}>
                    {t('kunci.diuji', {
                      waktu: new Date(k.uji.waktu * 1000).toLocaleString(lokal(), { dateStyle: 'medium', timeStyle: 'short' }),
                      n: k.uji.model_tersedia ?? 0,
                    })}
                    {st === 'ditolak' && k.penyedia === 'gemini' && (
                      <div style={{ color: WARNA.ditolak, marginTop: 3 }}>{t('kunci.saran_ditolak')}</div>
                    )}
                    {st === 'kuota' && <div style={{ marginTop: 3 }}>{t('kunci.saran_kuota')}</div>}
                    {st === 'pilih_model' && <div style={{ marginTop: 3 }}>{t('koneksi.saran_model')}</div>}
                    {k.uji.pesan && st !== 'bekerja' && k.penyedia !== 'gemini' && (
                      <div style={{ marginTop: 3 }}>{k.uji.pesan}</div>
                    )}
                  </div>
                </>
              )}
            </div>
          );
        })}
      </div>

      <div style={{ marginTop: '16px', paddingTop: '12px', borderTop: '1px solid var(--border-color)' }}>
        <div style={{ fontSize: '.8rem', fontWeight: 800, marginBottom: 8 }}>{t('koneksi.tambah_judul')}</div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <select value={pilih} onChange={(e) => { setPilih(e.target.value); setModel(''); setAlamat(''); }}
                  style={{ ...input, flex: '1 1 200px' }}>
            {penyedia.map((x) => <option key={x.id} value={x.id}>{x.nama}</option>)}
          </select>
          <input value={nama} onChange={(e) => setNama(e.target.value)} maxLength={60}
                 placeholder={t('kunci.nama_placeholder')} style={{ ...input, flex: '1 1 180px' }} />
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: 8 }}>
          {p.butuh_kunci !== false && (
            <div style={{ position: 'relative', flex: '2 1 260px' }}>
              <input value={kunci} onChange={(e) => setKunci(e.target.value)} spellCheck={false}
                     type={lihat ? 'text' : 'password'} autoComplete="off"
                     placeholder={t('kunci.kunci_placeholder')} style={{ ...input, width: '100%', paddingRight: 36 }} />
              <button type="button" onClick={() => setLihat((v) => !v)} style={{ ...ikon, position: 'absolute', right: 8, top: '50%', transform: 'translateY(-50%)' }}
                      aria-label={lihat ? t('set.sembunyi_kunci') : t('set.tampil_kunci')}>
                {lihat ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          )}
          {pilih === 'kustom' && (
            <input value={alamat} onChange={(e) => setAlamat(e.target.value)} placeholder={p.alamat || 'http://127.0.0.1:11434/v1'}
                   style={{ ...input, flex: '2 1 240px' }} />
          )}
          {pilih !== 'gemini' && pilih !== 'lokal' && (
            <input value={model} onChange={(e) => setModel(e.target.value)}
                   placeholder={p.model ? t('koneksi.model_bawaan', { m: p.model }) : t('koneksi.model_opsional')}
                   style={{ ...input, flex: '1 1 180px' }} />
          )}
          <button className="btn-primary" onClick={tambah}
                  disabled={!!sibuk || (p.butuh_kunci !== false && !kunci.trim())} style={{ whiteSpace: 'nowrap' }}>
            {sibuk === 'tambah' ? <Loader2 size={15} className="animate-spin" /> : <FlaskConical size={15} />}
            {sibuk === 'tambah' ? t('kunci.menguji') : t('kunci.tambah')}
          </button>
        </div>
        {p.kunci_url && (
          <p style={{ ...helpText, marginTop: 6 }}>
            {t('koneksi.buat_kunci')}{' '}
            <a href={p.kunci_url} target="_blank" rel="noreferrer" style={{ color: 'var(--reh)' }}>
              {new URL(p.kunci_url).host}
            </a>
          </p>
        )}
        {pilih === 'lokal' && <p style={{ ...helpText, marginTop: 6 }}>{t('koneksi.ket_lokal')}</p>}
        {pilih === 'anthropic' && <p style={{ ...helpText, marginTop: 6 }}>{t('koneksi.ket_claude')}</p>}
      </div>

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
