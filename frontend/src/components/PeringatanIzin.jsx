import React, { useEffect, useState } from 'react';
import { AlertTriangle, Check, Loader2 } from 'lucide-react';
import { apiGet, apiPost } from '../lib/api';

/**
 * Peringatan izin kanal sumber, sebelum sebuah klip diunggah (JOB-2 F0-3).
 *
 * TIDAK memblokir apa pun. Pemilik menjawab 9 Oktober 2026 bahwa belum ada
 * izin dari kreator mana pun yang ia klip; yang dibutuhkannya adalah tahu
 * risikonya pada saat menekan tombol unggah, bukan dihentikan.
 *
 * Satu tombol mencatat izin untuk kanal itu, dan peringatannya berhenti untuk
 * semua klip dari kanal yang sama. Tidak ada yang dicatat tanpa ditekan.
 */
export default function PeringatanIzin({ clipName }) {
  const [data, setData] = useState(null);
  const [sibuk, setSibuk] = useState(false);
  const [galat, setGalat] = useState('');

  useEffect(() => {
    let batal = false;
    apiGet(`/uploads/izin?clip_name=${encodeURIComponent(clipName)}`)
      .then((r) => { if (!batal) setData(r); })
      .catch(() => { /* peringatan yang gagal dimuat tidak menahan unggahan */ });
    return () => { batal = true; };
  }, [clipName]);

  if (!data || !data.peringatan) return null;

  const catat = async () => {
    setSibuk(true); setGalat('');
    try {
      setData(await apiPost('/uploads/izin', { clip_name: clipName, diizinkan: true }));
    } catch (e) {
      setGalat(e.message || 'Gagal mencatat izin.');
    } finally { setSibuk(false); }
  };

  const kanal = data.sumber?.kanal;
  return (
    <div style={{ display: 'flex', gap: 9, alignItems: 'flex-start', padding: '10px 12px',
                  margin: '0 0 12px', borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--reh)', background: 'var(--plate-2)' }}>
      <AlertTriangle size={16} style={{ flex: 'none', marginTop: 2, color: 'var(--reh)' }} />
      <div style={{ fontSize: '0.76rem', lineHeight: 1.6, color: 'var(--text-secondary)' }}>
        {data.peringatan}
        <div style={{ marginTop: 7 }}>
          <button className="btn-secondary" disabled={sibuk} onClick={catat}
                  style={{ fontSize: '0.72rem', padding: '4px 9px' }}>
            {sibuk ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
            Saya sudah punya izin dari {kanal || 'kanal ini'}
          </button>
          {galat && <span style={{ marginLeft: 8, color: 'var(--danger)' }}>{galat}</span>}
        </div>
      </div>
    </div>
  );
}
