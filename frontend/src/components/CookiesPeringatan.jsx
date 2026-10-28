import React, { useEffect, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, Cookie, Loader2, X } from 'lucide-react';
import { apiGet, apiPost } from '../lib/api';
import { bahasa, tebal, useT } from '../lib/i18n';

const NAMA = {
  firefox: 'Firefox', chrome: 'Chrome', chromium: 'Chromium', brave: 'Brave',
  edge: 'Edge', opera: 'Opera', vivaldi: 'Vivaldi', safari: 'Safari',
};
// Galat yang berarti "YouTube minta bukti Anda bukan bot". Lihat ytdlp.py.
const GALAT_BOT = new Set(['YTDLP_BOT_CHECK', 'YTDLP_FORBIDDEN']);

/**
 * Peringatan cookies TEPAT saat YouTube mulai menolak, di halaman mana pun.
 *
 * Diminta pemiliknya 28 Oktober 2026: "kadang ada error ... mengapa tidak ada
 * alert atau apapun yang meminta cookies agar bisa digunakan oleh sistem".
 * Kartu di Beranda bertanya sekali di awal; jendela ini muncul setiap kali
 * sebuah pekerjaan gagal karena verifikasi bot sementara cookies masih mati,
 * karena saat itulah jawabannya benar-benar dibutuhkan. Satu kali per sesi.
 */
export default function CookiesPeringatan() {
  const t = useT();
  const [buka, setBuka] = useState(false);
  const [info, setInfo] = useState(null);
  const [sibuk, setSibuk] = useState('');
  const [galat, setGalat] = useState('');
  const [beres, setBeres] = useState(false);
  const sudah = useRef(false);

  useEffect(() => {
    const es = new EventSource(`/api/jobs/events?lang=${bahasa()}`);
    es.onmessage = (evt) => {
      if (sudah.current) return;
      let d;
      try { d = JSON.parse(evt.data); } catch { return; }
      if (d.status !== 'failed' || !GALAT_BOT.has(d.error_code)) return;
      sudah.current = true;
      apiGet('/settings/cookies?periksa=1', { timeout: 180000 })
        .then((r) => {
          // Cookies sudah menyala: pesannya sendiri sudah menjelaskan
          // langkahnya, dan jendela ini tidak punya tawaran apa pun.
          if (r.mode !== 'mati') return;
          setInfo(r);
          setBuka(true);
        })
        .catch(() => { sudah.current = false; });
    };
    return () => es.close();
  }, []);

  if (!buka || !info) return null;
  const daftar = (info.browser_tersedia || []).filter((b) => b.login);

  const pakai = async (nama) => {
    setSibuk(nama); setGalat('');
    try {
      // Langsung DINYALAKAN, bukan siaga: YouTube sudah menolak.
      await apiPost('/settings/cookies', { mode: 'browser', browser: nama });
      setBeres(true);
    } catch (e) {
      setGalat(e?.message || t('ca.gagal'));
    } finally { setSibuk(''); }
  };

  return (
    <div className="modal-overlay" onClick={() => setBuka(false)}>
      <div className="card" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true"
           style={{ maxWidth: 520, width: 'calc(100% - 32px)', margin: '12vh auto 0', position: 'relative' }}>
        <button onClick={() => setBuka(false)} aria-label={t('umum.tutup')}
                style={{ position: 'absolute', top: 10, right: 10, background: 'none', border: 0,
                         color: 'var(--ink-3)', cursor: 'pointer' }}>
          <X size={16} />
        </button>
        <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
          <Cookie size={20} style={{ color: 'var(--accent-cyan)', flexShrink: 0, marginTop: 2 }} />
          <div style={{ minWidth: 0 }}>
            <div style={{ fontWeight: 700, marginBottom: 6 }}>{t('cp.judul')}</div>
            {beres ? (
              <p style={{ fontSize: '.82rem', color: 'var(--entry)', lineHeight: 1.6, margin: 0,
                          display: 'flex', gap: 6, alignItems: 'flex-start' }}>
                <CheckCircle2 size={15} style={{ flexShrink: 0, marginTop: 2 }} /> {t('cp.beres')}
              </p>
            ) : (
              <>
                <p style={{ fontSize: '.8rem', color: 'var(--ink-2)', lineHeight: 1.6, margin: '0 0 12px' }}>
                  {tebal(t('cp.ket'))}
                </p>
                {daftar.length > 0 ? (
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
                    {daftar.map((b) => (
                      <button key={b.nama} className="btn-primary" disabled={!!sibuk}
                              style={{ fontSize: '.8rem' }} onClick={() => pakai(b.nama)}>
                        {sibuk === b.nama ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />}
                        {t('cp.pakai', { browser: NAMA[b.nama] || b.nama })}
                      </button>
                    ))}
                  </div>
                ) : (
                  <p style={{ fontSize: '.78rem', color: 'var(--ink-2)', lineHeight: 1.6, margin: '0 0 8px' }}>
                    <AlertTriangle size={12} style={{ verticalAlign: '-1px', marginRight: 4 }} />
                    {tebal(t('cp.tanpa_browser'))}
                  </p>
                )}
                {galat && <div style={{ fontSize: '.75rem', color: 'var(--danger)', marginBottom: 6 }}>{galat}</div>}
                <p style={{ fontSize: '.72rem', color: 'var(--ink-3)', margin: 0, lineHeight: 1.55 }}>{t('cp.catatan')}</p>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
