import React, { useEffect, useState } from 'react';
import { AudioLines } from 'lucide-react';
import { apiGet, apiPost } from '../lib/api';

const PILIHAN = [
  {
    id: 'mati', label: 'Biarkan apa adanya',
    nota: 'Suara klip persis seperti di video aslinya.',
  },
  {
    id: 'seimbang', label: 'Seimbangkan kekerasannya',
    nota: 'Semua klip keluar pada tingkat yang sama (-16 LUFS), jadi penonton '
        + 'tidak perlu mengubah volume tiap ganti klip. Aman untuk musik dan '
        + 'suara permainan.',
  },
  {
    id: 'bersih', label: 'Seimbangkan dan bersihkan',
    nota: 'Menambah tiga hal yang ditujukan pada suara ORANG: desis dihilangkan, '
        + 'gemuruh di bawah 80 Hz dipotong, dan jarak antara bisikan dan teriakan '
        + 'dirapatkan. Rekaman HP terdengar jauh lebih rapi — tapi musik ikut '
        + 'terpengaruh, jadi jangan dipakai untuk klip musik.',
  },
];

/** Perapian suara saat render. Berlaku untuk semua render berikutnya. */
export default function SuaraCard({ card, sectionTitle, helpText }) {
  const [nilai, setNilai] = useState(null);
  const [kabar, setKabar] = useState(null);

  useEffect(() => {
    apiGet('/settings').then((r) => setNilai(r.render_suara || 'seimbang'))
      .catch(() => setNilai('seimbang'));
  }, []);

  const pilih = async (v) => {
    const sebelumnya = nilai;
    setNilai(v);
    try {
      await apiPost('/settings/suara', { nilai: v });
      setKabar('Tersimpan — berlaku untuk render berikutnya.');
      setTimeout(() => setKabar(null), 2500);
    } catch (e) {
      setNilai(sebelumnya);
      setKabar(e.message);
    }
  };

  return (
    <div style={card}>
      <div style={sectionTitle}>
        <AudioLines size={18} style={{ color: 'var(--reh)' }} />
        Perapian suara
      </div>
      <p style={helpText}>
        Dikerjakan saat render, pada suara klipnya saja — berkas sumbernya tidak
        disentuh.
      </p>
      <div style={{ marginTop: '10px' }}>
        {PILIHAN.map((p) => (
          <label key={p.id} style={{
            display: 'flex', gap: '9px', alignItems: 'flex-start', cursor: 'pointer',
            padding: '8px 0', borderTop: '1px solid var(--border-color)',
          }}>
            <input type="radio" name="suara" checked={nilai === p.id}
                   onChange={() => pilih(p.id)} disabled={nilai === null}
                   style={{ marginTop: '3px', accentColor: 'var(--reh)' }} />
            <span>
              <span style={{ fontSize: '0.79rem', fontWeight: 700 }}>{p.label}</span>
              <span style={{ ...helpText, display: 'block', marginTop: '2px' }}>{p.nota}</span>
            </span>
          </label>
        ))}
      </div>
      {kabar && <p style={{ ...helpText, marginTop: '8px' }}>{kabar}</p>}
    </div>
  );
}
