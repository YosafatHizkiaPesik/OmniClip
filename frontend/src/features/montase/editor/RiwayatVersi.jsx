/**
 * Riwayat versi proyek (JOB-4 M6.4), di panel Proyek.
 *
 * Server memotret dokumen paling sering dua menit sekali saat disimpan,
 * sebelum ekspor, dan sebelum sebuah versi dipulihkan; 10 terbaru disimpan.
 * Memulihkan memotret keadaan sekarang dulu, jadi pemulihan pun bisa
 * dibatalkan dengan memulihkan potret "sebelum dipulihkan".
 */
import React, { useEffect, useState } from 'react';
import { History, Loader2, RotateCcw } from 'lucide-react';
import { useT } from '../../../lib/i18n';
import { formatTime } from '../../../utils/timeFormat';
import { daftarVersi } from '../api.js';

export default function RiwayatVersi({ proyekId, revisi, onPulihkan }) {
  const t = useT();
  const [buka, setBuka] = useState(false);
  const [versi, setVersi] = useState(null);
  const [sibuk, setSibuk] = useState(null);
  const [galat, setGalat] = useState(null);

  useEffect(() => {
    if (!buka) return;
    daftarVersi(proyekId).then(setVersi).catch((e) => setGalat(e.message));
  }, [buka, proyekId, revisi]);

  const pulihkan = async (v) => {
    setSibuk(v.id);
    setGalat(null);
    try {
      await onPulihkan(v.id);
    } catch (e) {
      setGalat(e.message);
    } finally {
      setSibuk(null);
    }
  };

  return (
    <details className="montase-pintasan montase-riwayat-versi" onToggle={(e) => setBuka(e.currentTarget.open)}>
      <summary><History size={13} /> {t('montase.versi.judul')}</summary>
      {galat && <p className="montase-galat" role="alert">{galat}</p>}
      {buka && versi === null && <Loader2 size={14} className="animate-spin" />}
      {versi?.length === 0 && <p className="montase-petunjuk">{t('montase.versi.kosong')}</p>}
      <ul>
        {versi?.map((v) => (
          <li key={v.id}>
            <span>
              <b>{new Date(v.created_at * 1000).toLocaleString()}</b>
              <small>
                {t(`montase.versi.alasan_${v.alasan}`)}
                {' · '}{formatTime(v.durasi_detik || 0)}
                {' · '}{t('montase.versi.item', { n: v.jumlah_item ?? 0 })}
              </small>
            </span>
            <button type="button" className="btn-secondary" disabled={sibuk !== null}
                    onClick={() => pulihkan(v)} aria-label={t('montase.versi.pulihkan')}
            >
              {sibuk === v.id ? <Loader2 size={13} className="animate-spin" /> : <RotateCcw size={13} />}
              {t('montase.versi.pulihkan')}
            </button>
          </li>
        ))}
      </ul>
    </details>
  );
}
