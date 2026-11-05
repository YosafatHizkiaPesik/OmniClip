/**
 * Pilihan templat video: lima kerangka bawaan dengan tiga variasi masing-
 * masing (JOB-5 P3), ditambah templat milik sendiri (P4, nilai "saya:<id>").
 * Dipakai di formulir proyek baru dan di tab Asisten.
 */
import React from 'react';
import { X } from 'lucide-react';
import { useT } from '../../../lib/i18n';
import { TEMPLAT } from '../model/templat.js';
import { AWALAN_SAYA } from '../model/templatSaya.js';

export default function PilihTemplat({
  nilai, variasi, onUbah, onVariasi, denganKosong = false, milik = [], onHapus = null,
}) {
  const t = useT();
  const bawaan = nilai && !nilai.startsWith(AWALAN_SAYA);
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
      {milik.length > 0 && (
        <>
          <span className="montase-petunjuk">{t('montase.templat.saya_judul')}</span>
          <div className="montase-templat-kisi" role="radiogroup" aria-label={t('montase.templat.saya_judul')}>
            {milik.map((x) => {
              const v = AWALAN_SAYA + x.id;
              return (
                <div key={x.id} className="montase-templat-saya">
                  <button type="button" role="radio" aria-checked={nilai === v}
                          className={`montase-templat-pil ${nilai === v ? 'aktif' : ''}`} onClick={() => onUbah(v)}
                  >
                    <b>{x.nama}</b>
                    <small>{t('montase.templat.saya_ket', { n: x.isi?.length ?? 0, d: Math.round(x.detik || 0) })}</small>
                  </button>
                  {onHapus && (
                    <button type="button" className="montase-templat-hapus" onClick={() => onHapus(x.id)}
                            aria-label={t('montase.templat.saya_hapus', { nama: x.nama })}
                            title={t('montase.templat.saya_hapus', { nama: x.nama })}
                    >
                      <X size={12} />
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
      {bawaan && (
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
