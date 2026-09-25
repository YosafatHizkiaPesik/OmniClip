import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Loader2, Palette } from 'lucide-react';
import { apiGet, apiPost } from '../lib/api';

/**
 * Warna subtitle berbeda per penutur: satu sakelar untuk seluruh aplikasi.
 *
 * Kartunya ada supaya keputusannya bisa dibantah dengan angka, bukan dengan
 * selera. Pemisahan penutur sudah diukur pada podcast tiga orang: penambatan
 * wajah benar menemukan tiga orang, tapi model suara yang dilatih dari bukti
 * itu hanya benar 62% pada potongan yang tidak dilatihkan, dan menambah bukti
 * dari 8 ke 15 klip menurunkannya ke 60%. Selama angkanya di situ, satu warna
 * untuk semua orang adalah hasil yang lebih baik, dan sakelar ini yang
 * membalikkannya kembali begitu pemisahannya bisa dipercaya.
 */
export default function WarnaPenuturCard({ card, sectionTitle, helpText }) {
  const [aktif, setAktif] = useState(null);
  const [sibuk, setSibuk] = useState(false);
  const [kabar, setKabar] = useState(null);

  useEffect(() => {
    apiGet('/settings')
      .then((r) => setAktif(r?.warna_penutur === true))
      .catch(() => setAktif(false));
  }, []);

  const ubah = async (nilai) => {
    const sebelum = aktif;
    setAktif(nilai);
    setSibuk(true);
    setKabar(null);
    try {
      await apiPost('/settings/warna-penutur', { aktif: nilai });
      setKabar({
        ok: true,
        teks: nilai
          ? 'Warna per penutur menyala. Periksa hasilnya di Studio sebelum merender banyak klip.'
          : 'Semua baris memakai satu warna.',
      });
    } catch (e) {
      setAktif(sebelum);
      setKabar({ ok: false, teks: e.message });
    } finally {
      setSibuk(false);
    }
  };

  return (
    <div style={card}>
      <div style={sectionTitle}>
        <Palette size={18} style={{ color: 'var(--reh)' }} />
        Warna subtitle per penutur
      </div>
      <p style={helpText}>
        Memberi tiap orang di video warna subtitle sendiri. <strong>Mati</strong>{' '}
        sejak 24 September 2026, dan bukan karena belum sempat dikerjakan:
        pemisahan penuturnya sudah diukur dan belum cukup tepat. Pada podcast
        tiga orang, wajah yang sedang bicara benar menemukan tiga orang, tapi
        model suara yang dilatih dari bukti itu hanya benar 62% pada potongan
        yang tidak dilatihkan, dan menambah buktinya justru menurunkan angka itu
        ke 60%. Artinya sekitar empat dari sepuluh kalimat akan berwarna salah,
        yaitu warna yang berganti di tengah kalimat orang yang sama. Satu warna
        yang tidak pernah salah lebih baik daripada itu.
      </p>
      <p style={helpText}>
        Menyalakannya tetap boleh, misalnya untuk wawancara dua orang dengan
        suara yang jelas berbeda, atau bila Anda bersedia membetulkan sendiri
        label penuturnya di tab Subtitle. Deteksi penutur tetap berjalan meski
        sakelar ini mati, karena hasilnya dipakai untuk mengikuti wajah yang
        sedang bicara; yang dimatikan hanya pewarnaannya.
      </p>

      <label style={{
        display: 'flex', alignItems: 'flex-start', gap: '10px', marginTop: '14px',
        cursor: aktif === null || sibuk ? 'default' : 'pointer',
      }}>
        <input type="checkbox" checked={aktif === true} disabled={aktif === null || sibuk}
               onChange={(e) => ubah(e.target.checked)}
               style={{ marginTop: '3px', width: '16px', height: '16px', accentColor: 'var(--reh)' }} />
        <span style={helpText}>
          <strong style={{ color: 'var(--text-primary)' }}>
            Bedakan warna subtitle tiap penutur.
          </strong>{' '}
          Saat mati, setiap baris memakai warna teks yang dipilih di Studio, apa
          pun tebakan penuturnya.
        </span>
        {sibuk && <Loader2 size={15} className="animate-spin" style={{ marginTop: '3px' }} />}
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
