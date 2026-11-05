/**
 * Bantuan singkat Montase (JOB-4 M6.7): satu halaman cara pakai, dipakai di
 * beranda Montase (bisa dibuka-tutup) dan sebagai jendela dari tombol "?" di
 * editor. Isinya alur kerja, bukan daftar fitur: urutan yang benar-benar
 * dijalani orang saat membuat satu video.
 */
import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import { useT } from '../../lib/i18n';

const LANGKAH = ['bahan', 'linimasa', 'teks', 'animasi', 'asisten', 'ekspor', 'aman'];

export function IsiBantuan() {
  const t = useT();
  return (
    <ol className="montase-bantuan-langkah">
      {LANGKAH.map((k) => (
        <li key={k}>
          <b>{t(`montase.bantuan.${k}_judul`)}</b>
          <p>{t(`montase.bantuan.${k}_ket`)}</p>
        </li>
      ))}
    </ol>
  );
}

export function JendelaBantuan({ onTutup }) {
  const t = useT();
  useEffect(() => {
    // Fase capture: pintasan keyboard editor juga memakai Escape (dan
    // menghentikan peristiwanya), jadi jendela ini harus mendengar lebih dulu.
    const tutup = (e) => {
      if (e.key !== 'Escape') return;
      e.stopPropagation();
      onTutup();
    };
    window.addEventListener('keydown', tutup, true);
    return () => window.removeEventListener('keydown', tutup, true);
  }, [onTutup]);
  return (
    <div className="montase-bantuan-latar" role="presentation" onClick={onTutup}>
      <div className="montase-bantuan-jendela plate" role="dialog" aria-modal="true"
           aria-label={t('montase.bantuan.judul')} onClick={(e) => e.stopPropagation()}
      >
        <div className="montase-bantuan-kepala">
          <h2>{t('montase.bantuan.judul')}</h2>
          <button type="button" className="btn-secondary montase-ikon" onClick={onTutup}
                  aria-label={t('umum.tutup')} title={t('umum.tutup')}
          >
            <X size={14} />
          </button>
        </div>
        <IsiBantuan />
      </div>
    </div>
  );
}
