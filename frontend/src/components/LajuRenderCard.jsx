import React, { useEffect, useState } from 'react';
import { Gauge } from 'lucide-react';
import { apiGet, apiPost } from '../lib/api';

const PILIHAN = [
  {
    id: 'sumber', label: 'Ikut video aslinya',
    nota: 'Rekaman 60 fps keluar 60 fps. Untuk klip permainan ini perbedaan '
        + 'mutu yang paling kelihatan di layar, jauh lebih terasa daripada '
        + 'bitrate. Harganya: render memakan waktu lebih lama, karena setiap '
        + 'potong, skala, dan kabur dikerjakan dua kali lebih sering.',
  },
  {
    id: '30', label: 'Selalu 30 fps',
    nota: 'Render paling cepat, dan untuk klip bicara hampir tidak ada bedanya '
        + 'di mata. Untuk permainan cepat, gerakannya akan terlihat lebih '
        + 'patah-patah daripada rekaman aslinya.',
  },
];

/**
 * Laju bingkai hasil render.
 *
 * Sampai 5 Oktober 2026 selalu 30, dipatok di tiga tempat terpisah. Alasannya
 * masuk akal — sumber 60 fps membawa dua kali bingkai yang dibutuhkan melewati
 * setiap filter, lalu separuhnya dibuang begitu sampai ke pengode — tapi yang
 * hilang tidak ikut dihitung.
 *
 * Dilaporkan pemiliknya sesudah mengunggah beberapa video: "kualitasnya jelek
 * meskipun sudah ada tulisan SD dan HD". Terukur pada klip jadinya: 1080x1920
 * dan 13,7 Mbps — resolusi dan bitrate justru baik — tapi 30 fps dari sumber
 * 60 fps.
 */
export default function LajuRenderCard({ card, sectionTitle, helpText }) {
  const [nilai, setNilai] = useState(null);
  const [kabar, setKabar] = useState(null);

  useEffect(() => {
    apiGet('/settings').then((r) => setNilai(r.render_fps || 'sumber'))
      .catch(() => setNilai('sumber'));
  }, []);

  const pilih = async (v) => {
    const sebelumnya = nilai;
    setNilai(v);
    try {
      await apiPost('/settings/render-fps', { nilai: v });
      setKabar('Tersimpan. Berlaku untuk render berikutnya.');
      setTimeout(() => setKabar(null), 2500);
    } catch (e) {
      setNilai(sebelumnya);
      setKabar(e.message);
    }
  };

  return (
    <div style={card}>
      <div style={sectionTitle}>
        <Gauge size={18} style={{ color: 'var(--reh)' }} />
        Laju bingkai render
      </div>
      <p className="bantu" style={helpText}>
        Berapa bingkai per detik yang keluar dari render. Tidak menyentuh
        resolusi maupun bitrate, yang selalu 1080x1920 pada mutu penuh.
      </p>
      <div style={{ marginTop: '10px' }}>
        {PILIHAN.map((p) => (
          <label key={p.id} style={{
            display: 'flex', gap: '9px', alignItems: 'flex-start', cursor: 'pointer',
            padding: '8px 0', borderTop: '1px solid var(--border-color)',
          }}>
            <input type="radio" name="laju-render" checked={nilai === p.id}
                   onChange={() => pilih(p.id)} disabled={nilai === null}
                   style={{ marginTop: '3px', accentColor: 'var(--reh)' }} />
            <span>
              <span style={{ fontSize: '0.79rem', fontWeight: 700 }}>{p.label}</span>
              <span style={{ ...helpText, display: 'block', marginTop: '2px' }}>{p.nota}</span>
            </span>
          </label>
        ))}
      </div>
      {kabar && (
        <div style={{ ...helpText, marginTop: '8px', color: 'var(--entry)' }}>{kabar}</div>
      )}
    </div>
  );
}
