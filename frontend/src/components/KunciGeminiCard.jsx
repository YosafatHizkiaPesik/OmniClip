import React, { useEffect, useState } from 'react';
import {
  KeyRound, Loader2, Trash2, FlaskConical, CheckCircle2, AlertTriangle, Eye, EyeOff, Pencil,
} from 'lucide-react';
import { apiDelete, apiGet, apiPost, apiPut } from '../lib/api';
import { lokal, tebal, useT } from '../lib/i18n';

/**
 * Pengelola kunci Gemini (diminta pemilik 16 Oktober 2026).
 *
 * Tiap kunci punya nama, hasil uji terakhir, dan keadaan tiap model yang
 * diuji. Ujinya permintaan SUNGGUHAN ke Google (backend services/kunci_ai.py),
 * karena uji lama yang hanya meminta daftar model meloloskan kunci yang
 * proyeknya sudah diblokir. Kunci baru DITAMBAHKAN, tidak lagi mengganti
 * semua kunci lama.
 */
const WARNA = {
  bekerja: 'var(--entry)', kuota: 'var(--reh)', sibuk: 'var(--reh)',
  ditolak: 'var(--accent-red, var(--danger))', tidak_sah: 'var(--accent-red, var(--danger))',
  galat: 'var(--accent-red, var(--danger))',
};
const WARNA_MODEL = {
  ok: 'var(--entry)', kuota_harian: 'var(--reh)', kuota_menit: 'var(--reh)', sibuk: 'var(--reh)',
  tanpa_jatah: 'var(--text-muted)', tidak_ada: 'var(--text-muted)',
};

function jamLagi(detik) {
  return Math.max(1, Math.round((detik || 0) / 3600));
}

export default function KunciGeminiCard({ card, sectionTitle, helpText, onBerubah }) {
  const t = useT();
  const [daftar, setDaftar] = useState(null);
  const [nama, setNama] = useState('');
  const [kunci, setKunci] = useState('');
  const [lihat, setLihat] = useState(false);
  const [sibuk, setSibuk] = useState('');        // '' | 'tambah' | id kunci
  const [kabar, setKabar] = useState(null);
  const [ubahNama, setUbahNama] = useState(null);   // {id, nama}

  const muat = () => apiGet('/settings/ai-keys')
    .then((r) => setDaftar(r.kunci || []))
    .catch((e) => setKabar({ ok: false, teks: e.message }));
  useEffect(() => { muat(); }, []);

  const selesai = (r, teks) => {
    setDaftar(r.kunci || []);
    if (teks) setKabar({ ok: true, teks });
    onBerubah?.();
  };

  const tambah = async () => {
    if (!kunci.trim()) return;
    setSibuk('tambah'); setKabar(null);
    try {
      const r = await apiPost('/settings/ai-keys', { api_key: kunci.trim(), nama: nama.trim() },
        { timeout: 120000 });
      setKunci(''); setNama('');
      selesai(r, r.uji?.status === 'bekerja' ? t('kunci.tambah_ok') : t('kunci.tambah_catat'));
    } catch (e) {
      setKabar({ ok: false, teks: e.message });
    } finally {
      setSibuk('');
    }
  };

  const uji = async (id) => {
    setSibuk(id); setKabar(null);
    try {
      selesai(await apiPost(`/settings/ai-keys/${id}/uji`, {}, { timeout: 120000 }));
    } catch (e) {
      setKabar({ ok: false, teks: e.message });
    } finally {
      setSibuk('');
    }
  };

  const hapus = async (k) => {
    if (!window.confirm(t('kunci.yakin_hapus', { nama: k.nama }))) return;
    setSibuk(k.id); setKabar(null);
    try {
      selesai(await apiDelete(`/settings/ai-keys/${k.id}`), t('kunci.terhapus', { nama: k.nama }));
    } catch (e) {
      setKabar({ ok: false, teks: e.message });
    } finally {
      setSibuk('');
    }
  };

  const simpanNama = async () => {
    if (!ubahNama) return;
    try {
      selesai(await apiPut(`/settings/ai-keys/${ubahNama.id}`, { nama: ubahNama.nama }));
    } catch (e) {
      setKabar({ ok: false, teks: e.message });
    }
    setUbahNama(null);
  };

  const labelModel = (m) => {
    switch (m.status) {
      case 'ok': return t('kunci.m_ok', { s: m.detik ?? '?' });
      case 'kuota_harian': return m.tunggu ? t('kunci.m_harian_jam', { n: jamLagi(m.tunggu) }) : t('kunci.m_harian');
      case 'kuota_menit': return t('kunci.m_menit');
      case 'tanpa_jatah': return t('kunci.m_tanpa_jatah');
      case 'ditolak': return t('kunci.m_ditolak');
      case 'tidak_ada': return t('kunci.m_tidak_ada');
      case 'tidak_sah': return t('kunci.m_tidak_sah');
      case 'sibuk': return t('kunci.m_sibuk');
      default: return t('kunci.m_galat');
    }
  };

  const input = {
    padding: '10px 12px', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)',
    background: 'var(--bg-glass)', color: 'var(--text-primary)', fontSize: '0.84rem', fontFamily: 'inherit',
  };

  return (
    <div style={card}>
      <div style={sectionTitle}>
        <KeyRound size={18} style={{ color: 'var(--reh)' }} />
        {t('kunci.judul')}
      </div>
      <p className="bantu" style={helpText}>
        {t('kunci.ket')}{' '}
        <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noreferrer"
           style={{ color: 'var(--reh)' }}>aistudio.google.com</a>.
      </p>
      <p className="bantu" style={{ ...helpText, marginTop: '6px' }}>{tebal(t('kunci.ket_uji'))}</p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '14px' }}>
        {daftar === null && <Loader2 size={16} className="animate-spin" />}
        {daftar?.length === 0 && (
          <p style={{ ...helpText, margin: 0 }}>{t('kunci.kosong')}</p>
        )}
        {daftar?.map((k) => {
          const st = k.uji?.status;
          return (
            <div key={k.id} style={{
              border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)',
              padding: '11px 13px', background: 'var(--bg-glass)',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '9px', flexWrap: 'wrap' }}>
                {ubahNama?.id === k.id ? (
                  <input autoFocus value={ubahNama.nama} maxLength={60}
                         onChange={(e) => setUbahNama({ ...ubahNama, nama: e.target.value })}
                         onBlur={simpanNama}
                         onKeyDown={(e) => { if (e.key === 'Enter') simpanNama(); if (e.key === 'Escape') setUbahNama(null); }}
                         style={{ ...input, padding: '5px 8px', fontWeight: 700 }} />
                ) : (
                  <button type="button" onClick={() => setUbahNama({ id: k.id, nama: k.nama_sendiri ? k.nama : '' })}
                          title={t('kunci.ubah_nama')}
                          style={{ background: 'none', border: 0, padding: 0, cursor: 'pointer', color: 'var(--text-primary)',
                                   font: 'inherit', fontWeight: 800, fontSize: '0.88rem', display: 'inline-flex', gap: '6px', alignItems: 'center' }}>
                    {k.nama} <Pencil size={12} style={{ opacity: 0.5 }} />
                  </button>
                )}
                {k.nama_sendiri && (
                  <code style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>…{k.akhiran}</code>
                )}
                {k.sumber === 'env' && (
                  <span style={{ fontSize: '.66rem', color: 'var(--text-muted)', border: '1px solid var(--border-color)', borderRadius: 99, padding: '1px 7px' }}>backend/.env</span>
                )}
                <span style={{ flex: 1 }} />
                <span style={{ fontSize: '0.76rem', fontWeight: 800, color: WARNA[st] || 'var(--text-muted)' }}>
                  {st ? t(`kunci.s_${st}`) : t('kunci.s_belum')}
                </span>
                <button className="btn-secondary" onClick={() => uji(k.id)} disabled={!!sibuk}
                        style={{ fontSize: '0.76rem', padding: '5px 10px' }}>
                  {sibuk === k.id ? <Loader2 size={13} className="animate-spin" /> : <FlaskConical size={13} />}
                  {sibuk === k.id ? t('kunci.menguji') : t('kunci.uji')}
                </button>
                {k.sumber !== 'env' && (
                  <button onClick={() => hapus(k)} disabled={!!sibuk} aria-label={t('kunci.hapus')}
                          title={t('kunci.hapus')}
                          style={{ background: 'none', border: 0, cursor: 'pointer', color: 'var(--danger)', display: 'flex', padding: 4 }}>
                    <Trash2 size={15} />
                  </button>
                )}
              </div>
              {k.uji && (
                <>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '9px' }}>
                    {(k.uji.model || []).map((m) => (
                      <span key={m.model} className="chip" title={m.pesan || ''}
                            style={{ fontSize: '.68rem', padding: '2px 8px', cursor: 'default',
                                     color: WARNA_MODEL[m.status] || 'var(--accent-red, var(--danger))' }}>
                        <b style={{ color: 'var(--text-primary)', fontWeight: 700 }}>{m.model}</b>&nbsp;· {labelModel(m)}
                      </span>
                    ))}
                  </div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '7px', lineHeight: 1.5 }}>
                    {t('kunci.diuji', {
                      waktu: new Date(k.uji.waktu * 1000).toLocaleString(lokal(), { dateStyle: 'medium', timeStyle: 'short' }),
                      n: k.uji.model_tersedia ?? 0,
                    })}
                    {k.uji.proyek ? ` · ${t('kunci.proyek', { n: k.uji.proyek })}` : ''}
                    {st === 'ditolak' && <div style={{ color: WARNA.ditolak, marginTop: 3 }}>{t('kunci.saran_ditolak')}</div>}
                    {st === 'kuota' && <div style={{ marginTop: 3 }}>{t('kunci.saran_kuota')}</div>}
                  </div>
                </>
              )}
            </div>
          );
        })}
      </div>

      <div style={{ display: 'flex', gap: '8px', marginTop: '14px', flexWrap: 'wrap' }}>
        <input value={nama} onChange={(e) => setNama(e.target.value)} maxLength={60}
               placeholder={t('kunci.nama_placeholder')} style={{ ...input, flex: '1 1 160px' }} />
        <div style={{ position: 'relative', flex: '2 1 260px' }}>
          <input value={kunci} onChange={(e) => setKunci(e.target.value)} spellCheck={false}
                 type={lihat ? 'text' : 'password'} autoComplete="off"
                 onKeyDown={(e) => { if (e.key === 'Enter') tambah(); }}
                 placeholder={t('kunci.kunci_placeholder')} style={{ ...input, width: '100%', paddingRight: 38 }} />
          <button type="button" onClick={() => setLihat((v) => !v)}
                  aria-label={lihat ? t('set.sembunyi_kunci') : t('set.tampil_kunci')}
                  style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)',
                           background: 'none', border: 0, cursor: 'pointer', color: 'var(--text-muted)', display: 'flex' }}>
            {lihat ? <EyeOff size={16} /> : <Eye size={16} />}
          </button>
        </div>
        <button className="btn-primary" onClick={tambah} disabled={!!sibuk || !kunci.trim()}
                style={{ whiteSpace: 'nowrap' }}>
          {sibuk === 'tambah' ? <Loader2 size={15} className="animate-spin" /> : <FlaskConical size={15} />}
          {sibuk === 'tambah' ? t('kunci.menguji') : t('kunci.tambah')}
        </button>
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
