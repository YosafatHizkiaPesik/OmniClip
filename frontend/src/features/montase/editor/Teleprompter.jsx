/**
 * Teleprompter narasi (JOB-5 O2): naskah narasi dibaca dengan suara pemilik
 * sendiri, satu per satu, dan tiap rekaman langsung menggantikan suara AI di
 * tempat yang sama (`gantiBahanItem`, satu langkah batal per rekaman).
 *
 * Kenapa: kebijakan konten yang digunakan ulang YouTube menilai apakah video
 * "jelas ciptaan Anda sendiri". Narasi asisten berupa suara TTS umum; suara
 * pemilik kanal yang membacakan pendapatnya sendiri adalah tanda yang jauh
 * lebih jelas, dan meter orisinalitas (O1) menyarankannya.
 *
 * Naskahnya tetap tersimpan di item (`narasi.teks`, `narasi.direkam: true`):
 * untuk subtitle/caption, dan supaya "Kembali ke suara AI" tetap bisa.
 */
import React, { useEffect, useState } from 'react';
import {
  ChevronLeft, ChevronRight, Loader2, Mic, Square, X,
} from 'lucide-react';
import { useT } from '../../../lib/i18n';
import { simpanRekaman } from '../api.js';
import { detikRekam, useRekamMikrofon } from './rekamMikrofon.js';

export default function Teleprompter({ daftar, onRekaman, onTutup }) {
  const t = useT();
  const mik = useRekamMikrofon();
  const [i, setI] = useState(0);
  const [sibuk, setSibuk] = useState(false);
  const [galat, setGalat] = useState(null);
  const [selesai, setSelesai] = useState(() => new Set());
  const kini = daftar[i];

  useEffect(() => {
    const tombol = (e) => {
      if (e.key === 'Escape' && !mik.merekam) { e.stopPropagation(); onTutup(); }
    };
    window.addEventListener('keydown', tombol, true);
    return () => window.removeEventListener('keydown', tombol, true);
  }, [mik.merekam, onTutup]);

  const rekam = async () => {
    setGalat(null);
    const item = kini;
    try {
      await mik.mulai(async (blob) => {
        setSibuk(true);
        try {
          const bahan = await simpanRekaman(blob, `${t('montase.teleprompter.nama_rekaman')} ${i + 1}`);
          onRekaman(item.id, bahan);
          setSelesai((s) => new Set(s).add(item.id));
          if (i < daftar.length - 1) setI(i + 1);
        } catch (e) {
          setGalat(e.message);
        } finally {
          setSibuk(false);
        }
      });
    } catch {
      setGalat(t('montase.suara.mik_ditolak'));
    }
  };

  if (!kini) return null;
  return (
    <div className="montase-bantuan-latar" role="presentation">
      <div className="montase-bantuan-jendela plate montase-teleprompter" role="dialog" aria-modal="true"
           aria-label={t('montase.teleprompter.judul')}
      >
        <div className="montase-bantuan-kepala">
          <h2>{t('montase.teleprompter.judul')}</h2>
          <button type="button" className="btn-secondary montase-ikon" onClick={onTutup} disabled={mik.merekam}
                  aria-label={t('umum.tutup')} title={t('umum.tutup')}
          >
            <X size={14} />
          </button>
        </div>
        <p className="montase-petunjuk">{t('montase.teleprompter.ket')}</p>
        <p className="montase-teleprompter-nomor">
          {t('montase.teleprompter.nomor', { n: i + 1, total: daftar.length })}
          {selesai.has(kini.id) || kini.direkam ? ` · ${t('montase.teleprompter.sudah_direkam')}` : ''}
        </p>
        <blockquote className={`montase-teleprompter-naskah ${mik.merekam ? 'merekam' : ''}`}>{kini.teks}</blockquote>
        {galat && <p className="montase-galat" role="alert">{galat}</p>}
        <div className="montase-baris-tombol montase-teleprompter-tombol">
          <button type="button" className="btn-secondary" disabled={i === 0 || mik.merekam || sibuk}
                  onClick={() => setI(i - 1)} aria-label={t('montase.teleprompter.sebelumnya')}
          >
            <ChevronLeft size={14} />
          </button>
          {mik.merekam ? (
            <button type="button" className="btn-primary montase-rekam-aktif" onClick={mik.berhenti}>
              <Square size={14} />{t('montase.suara.berhenti')} · {detikRekam(mik.lama)}
            </button>
          ) : (
            <button type="button" className="btn-primary" disabled={sibuk} onClick={rekam}>
              {sibuk ? <Loader2 size={14} className="animate-spin" /> : <Mic size={14} />}
              {t(selesai.has(kini.id) || kini.direkam ? 'montase.teleprompter.rekam_ulang' : 'montase.teleprompter.rekam')}
            </button>
          )}
          <button type="button" className="btn-secondary" disabled={i === daftar.length - 1 || mik.merekam || sibuk}
                  onClick={() => setI(i + 1)} aria-label={t('montase.teleprompter.berikutnya')}
          >
            <ChevronRight size={14} />
          </button>
        </div>
        <p className="montase-petunjuk">{t('montase.teleprompter.progres', { n: selesai.size, total: daftar.length })}</p>
      </div>
    </div>
  );
}
