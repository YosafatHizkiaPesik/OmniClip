import React, { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';
import { apiGet, apiPost } from '../lib/api';

import { useT } from '../lib/i18n';
/**
 * Sakelar pembuang bunyi ragu dari subtitle.
 *
 * Dilaporkan pemiliknya 5 Oktober 2026: "saya sering menemukan kata ee h dan
 * lain lain yang mana saya rasa tidak perlu dimasukkan ke dalam subtitle".
 *
 * Bentuknya sengaja sama persis dengan `SakelarSensor` di sebelahnya: keduanya
 * menjawab pertanyaan yang sama — kata apa yang boleh tertulis di layar — dan
 * dua sakelar bersebelahan yang berbeda rupanya membuat orang mengira keduanya
 * bekerja dengan cara yang berbeda pula.
 */
export default function SakelarGumam({ helpText }) {
  const t = useT();
  const [aktif, setAktif] = useState(null);
  const [sibuk, setSibuk] = useState(false);

  useEffect(() => {
    let batal = false;
    apiGet('/settings')
      .then((r) => { if (!batal) setAktif(r?.buang_gumam !== false); })
      .catch(() => { if (!batal) setAktif(true); });
    return () => { batal = true; };
  }, []);

  const ubah = async (nilai) => {
    const sebelum = aktif;
    setAktif(nilai);
    setSibuk(true);
    try {
      await apiPost('/settings/buang-gumam', { aktif: nilai });
    } catch {
      setAktif(sebelum);          // gagal disimpan: jangan berbohong di layar
    } finally {
      setSibuk(false);
    }
  };

  const menyala = aktif === true;
  return (
    <div style={{
      border: '1px solid var(--rule-2)', borderRadius: 'var(--r-sm)',
      padding: '11px 13px', background: 'var(--plate-3)', marginTop: '10px',
    }}>
      <label style={{ display: 'flex', alignItems: 'center', gap: '9px', cursor: 'pointer' }}>
        <input type="checkbox" checked={menyala} disabled={aktif === null || sibuk}
               onChange={(e) => ubah(e.target.checked)}
               style={{ width: '15px', height: '15px', flex: 'none' }} />
        <b style={{ fontSize: '0.82rem', flex: 1 }}>{t('gumam.judul')}</b>
        {sibuk && <Loader2 size={12} className="animate-spin" style={{ color: 'var(--ink-3)' }} />}
        <span style={{
          fontSize: '0.64rem', fontWeight: 800, padding: '2px 8px', borderRadius: '99px',
          flex: 'none',
          background: menyala ? 'var(--reh)' : 'var(--bg-glass)',
          color: menyala ? '#fff' : 'var(--text-muted)',
        }}>
          {aktif === null ? '…' : menyala ? t('umum.nyala') : t('umum.mati')}
        </span>
      </label>
      <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', margin: '6px 0 0',
                  lineHeight: 1.55 }}>
        {menyala
          ? t('gumam.nyala')
          : t('gumam.mati')}
      </p>
      <p className="bantu" style={{ ...helpText, fontSize: '0.7rem',
                                    color: 'var(--text-muted)', margin: '6px 0 0' }}>
        {t('gumam.ket')}
      </p>
    </div>
  );
}
