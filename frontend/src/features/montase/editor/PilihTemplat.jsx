/**
 * Pilihan templat video (JOB-5 P3): lima kerangka bawaan, tiga variasi
 * masing-masing. Dipakai di formulir proyek baru dan di tab Asisten.
 */
import React from 'react';
import { useT } from '../../../lib/i18n';
import { TEMPLAT } from '../model/templat.js';

export default function PilihTemplat({ nilai, variasi, onUbah, onVariasi, denganKosong = false }) {
  const t = useT();
  return (
    <div className="montase-templat">
      <div className="montase-templat-kisi" role="radiogroup" aria-label={t('montase.templat.judul')}>
        {denganKosong && (
          <button type="button" role="radio" aria-checked={!nilai} className={`montase-templat-pil ${!nilai ? 'aktif' : ''}`}
                  onClick={() => onUbah(null)}
          >
            <b>{t('montase.templat.kosong')}</b><small>{t('montase.templat.kosong_ket')}</small>
          </button>
        )}
        {TEMPLAT.map((x) => (
          <button key={x.id} type="button" role="radio" aria-checked={nilai === x.id}
                  className={`montase-templat-pil ${nilai === x.id ? 'aktif' : ''}`} onClick={() => onUbah(x.id)}
          >
            <b>{t(`montase.templat.nama_${x.id}`)}</b>
            <small>{t(`montase.templat.ket_${x.id}`)}</small>
          </button>
        ))}
      </div>
      {nilai && (
        <div className="montase-baris-tombol" role="radiogroup" aria-label={t('montase.templat.variasi')}>
          <span className="montase-petunjuk">{t('montase.templat.variasi')}</span>
          {[0, 1, 2].map((v) => (
            <button key={v} type="button" role="radio" aria-checked={variasi === v}
                    className={`btn-secondary ${variasi === v ? 'aktif' : ''}`} onClick={() => onVariasi(v)}
            >
              {v + 1}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
