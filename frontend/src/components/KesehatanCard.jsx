import React, { useEffect, useState } from 'react';
import { Activity, AlertTriangle, CheckCircle2, Loader2, RefreshCw } from 'lucide-react';
import { apiGet } from '../lib/api';

/**
 * Kesehatan sistem: satu layar untuk "apakah semuanya baik-baik saja".
 *
 * Sebelum ini semuanya hanya terlihat di log — encoder mana yang dipakai,
 * apakah server PO Token menyala, cookies masih hidup atau tidak. Artinya
 * satu-satunya cara tahu ada yang rusak adalah menemukan hasil yang salah,
 * dan itu selalu terjadi di tengah pekerjaan.
 *
 * Tiap baris menyebut akibatnya bila mati, bukan hanya keadaannya: "POT: mati"
 * tidak berarti apa-apa bagi yang tidak menulis kodenya.
 */
export default function KesehatanCard({ card, sectionTitle, helpText }) {
  const [data, setData] = useState(null);
  const [sibuk, setSibuk] = useState(false);

  const muat = () => {
    setSibuk(true);
    apiGet('/settings/kesehatan')
      .then(setData)
      .catch((e) => setData({ galat: e.message, baris: [] }))
      .finally(() => setSibuk(false));
  };
  useEffect(() => { muat(); }, []);

  const buruk = (data?.baris || []).filter((b) => !b.baik).length;

  return (
    <div style={card}>
      <div style={{ ...sectionTitle, justifyContent: 'space-between' }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
          <Activity size={18} style={{ color: 'var(--reh)' }} />
          Kesehatan sistem
          {data?.versi && (
            <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--text-muted)' }}>
              versi {data.versi}
            </span>
          )}
        </span>
        <button onClick={muat} disabled={sibuk} aria-label="Periksa lagi"
                style={{ background: 'none', border: 'none', cursor: 'pointer',
                         color: 'var(--text-secondary)', display: 'flex', padding: '3px' }}>
          {sibuk ? <Loader2 size={15} className="animate-spin" /> : <RefreshCw size={15} />}
        </button>
      </div>
      <p style={helpText}>
        {data?.galat
          ? `${data.galat} Tekan ikon segarkan di kanan untuk memeriksa lagi.`
          : data
          ? (buruk === 0
            ? 'Semua bagian yang diperiksa dalam keadaan baik.'
            : `${buruk} hal belum siap. Yang belum siap tidak membuat OmniClip berhenti, `
              + 'dan tiap baris menyebut apa akibatnya.')
          : 'Memeriksa…'}
      </p>

      <div style={{ marginTop: '10px' }}>
        {(data?.baris || []).map((b) => (
          <div key={b.nama} style={{
            display: 'flex', gap: '9px', alignItems: 'flex-start',
            padding: '8px 0', borderTop: '1px solid var(--border-color)',
          }}>
            {b.baik
              ? <CheckCircle2 size={15} style={{ color: 'var(--entry)', flexShrink: 0, marginTop: '2px' }} />
              : <AlertTriangle size={15} style={{ color: 'var(--accent-red)', flexShrink: 0, marginTop: '2px' }} />}
            <div style={{ minWidth: 0 }}>
              <div style={{ fontSize: '0.78rem', fontWeight: 700 }}>
                {b.nama}
                <span style={{ fontWeight: 500, color: 'var(--text-secondary)' }}> · {b.nilai}</span>
              </div>
              {!b.baik && <div style={{ ...helpText, marginTop: '2px' }}>{b.akibat}</div>}
            </div>
          </div>
        ))}
      </div>

      {data?.galat && (
        <div style={{ ...helpText, marginTop: '10px', color: 'var(--accent-red)' }}>{data.galat}</div>
      )}
    </div>
  );
}
