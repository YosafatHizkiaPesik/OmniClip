/**
 * Panel Properti editor Montase (JOB-4 M1.7).
 *
 * Item dipilih: waktu (dalam detik di layar, bingkai di dokumen), dan kolom
 * sesuai jenisnya. Untuk animasi, kolomnya dibuat dari contohProps modulnya:
 * teks -> kotak teks, angka -> isian angka, warna "#rrggbb" -> pemilih warna.
 * Panel yang dibangun dari skema zod lengkap (penggeser, pilihan, titik di
 * pratinjau) datang di M4.5.
 *
 * Tidak ada item dipilih: pengaturan proyek.
 */
import React from 'react';
import { Trash2 } from 'lucide-react';
import { useT } from '../../../lib/i18n';
import { formatTime } from '../../../utils/timeFormat';
import { BAWAAN } from '../komposisi/index.js';

const WARNA = /^#[0-9a-fA-F]{6}$/;

function Angka({ label, nilai, onUbah, langkah = 0.1, min = 0, max, akhiran }) {
  return (
    <label className="montase-kolom">
      <span>{label}</span>
      <span className="montase-isian-akhiran">
        <input type="number" step={langkah} min={min} max={max}
               value={Number.isFinite(nilai) ? Number(nilai.toFixed(3)) : ''}
               onChange={(e) => { if (e.target.value !== '') onUbah(Number(e.target.value)); }} />
        {akhiran && <small>{akhiran}</small>}
      </span>
    </label>
  );
}

function KolomProps({ props, onUbah }) {
  return Object.entries(props).map(([kunci, nilai]) => {
    if (typeof nilai === 'number') {
      return <Angka key={kunci} label={kunci} nilai={nilai} langkah={1}
                    onUbah={(v) => onUbah({ ...props, [kunci]: v })} />;
    }
    if (typeof nilai === 'string' && WARNA.test(nilai)) {
      return (
        <label key={kunci} className="montase-kolom">
          <span>{kunci}</span>
          <input type="color" value={nilai} onChange={(e) => onUbah({ ...props, [kunci]: e.target.value })} />
        </label>
      );
    }
    if (typeof nilai === 'string') {
      return (
        <label key={kunci} className="montase-kolom">
          <span>{kunci}</span>
          <input value={nilai} onChange={(e) => onUbah({ ...props, [kunci]: e.target.value })} />
        </label>
      );
    }
    return null;
  });
}

export default function PanelProperti({ dokumen, terpilih, onUbahItem, onHapus, onUbahProyek }) {
  const t = useT();
  const fps = dokumen.kanvas.fps;
  const keDetik = (b) => b / fps;
  const keBingkai = (d) => Math.round(d * fps);

  if (!terpilih) {
    const k = dokumen.kanvas;
    return (
      <aside className="montase-panel montase-panel-properti" aria-label={t('montase.properti.judul')}>
        <div className="montase-panel-kepala"><h2>{t('montase.properti.proyek')}</h2></div>
        <div className="montase-panel-isi">
          <label className="montase-kolom">
            <span>{t('montase.home.nama')}</span>
            <input value={dokumen.nama} maxLength={120}
                   onChange={(e) => onUbahProyek({ nama: e.target.value || dokumen.nama })} />
          </label>
          <dl className="montase-ringkas">
            <dt>{t('montase.home.ukuran')}</dt><dd>{k.lebar}×{k.tinggi}</dd>
            <dt>{t('montase.home.fps')}</dt><dd>{k.fps} fps</dd>
            <dt>{t('montase.properti.durasi_proyek')}</dt><dd>{formatTime(dokumen.durasi / fps)}</dd>
          </dl>
          <label className="montase-kolom">
            <span>{t('montase.properti.latar')}</span>
            <input type="color" value={k.latar}
                   onChange={(e) => onUbahProyek({ kanvas: { latar: e.target.value } })} />
          </label>
          <p className="montase-petunjuk">{t('montase.properti.petunjuk')}</p>
        </div>
      </aside>
    );
  }

  const { item } = terpilih;
  const ubah = (perubahan) => onUbahItem(item.id, perubahan);
  const gaya = item.gaya ?? {};
  return (
    <aside className="montase-panel montase-panel-properti" aria-label={t('montase.properti.judul')}>
      <div className="montase-panel-kepala">
        <h2>{t(`montase.jenis.${item.jenis}`)}</h2>
        <button type="button" className="btn-secondary montase-ikon" onClick={onHapus}
                title={t('montase.linimasa.hapus')} aria-label={t('montase.linimasa.hapus')}
        >
          <Trash2 size={13} />
        </button>
      </div>
      <div className="montase-panel-isi">
        {item.asal === 'ai' && <p className="montase-label-ai">{t('montase.properti.ai', { alasan: item.alasan ?? '' })}</p>}
        <Angka label={t('montase.properti.mulai')} nilai={keDetik(item.mulai)} akhiran={t('montase.satuan.detik')}
               onUbah={(v) => ubah({ mulai: keBingkai(v) })} />
        <Angka label={t('montase.properti.durasi')} nilai={keDetik(item.durasi)} akhiran={t('montase.satuan.detik')} min={0.05}
               onUbah={(v) => ubah({ durasi: keBingkai(v) })} />

        {(item.jenis === 'video' || item.jenis === 'audio') && (
          <>
            <Angka label={t('montase.properti.potong_awal')} nilai={keDetik(item.potong_awal || 0)}
                   akhiran={t('montase.satuan.detik')} onUbah={(v) => ubah({ potong_awal: keBingkai(v) })} />
            <Angka label={t('montase.properti.volume')} nilai={(item.volume ?? 1) * 100} langkah={5}
                   max={200} akhiran="%" onUbah={(v) => ubah({ volume: v / 100 })} />
            <Angka label={t('montase.properti.kecepatan')} nilai={item.kecepatan ?? 1} langkah={0.25}
                   min={0.25} max={4} akhiran="x" onUbah={(v) => ubah({ kecepatan: v })} />
          </>
        )}
        {(item.jenis === 'video' || item.jenis === 'gambar') && (
          <label className="montase-kolom">
            <span>{t('montase.properti.isi')}</span>
            <select value={item.isi ?? 'contain'} onChange={(e) => ubah({ isi: e.target.value })}>
              <option value="contain">{t('montase.properti.isi_muat')}</option>
              <option value="cover">{t('montase.properti.isi_penuh')}</option>
            </select>
          </label>
        )}
        {item.jenis === 'teks' && (
          <>
            <label className="montase-kolom">
              <span>{t('montase.properti.teks')}</span>
              <textarea rows={3} maxLength={500} value={item.teks ?? ''}
                        onChange={(e) => ubah({ teks: e.target.value })} />
            </label>
            <Angka label={t('montase.properti.ukuran_huruf')} nilai={gaya.ukuran ?? 96} langkah={4} min={12}
                   onUbah={(v) => ubah({ gaya: { ...gaya, ukuran: v } })} />
            <label className="montase-kolom">
              <span>{t('montase.properti.warna')}</span>
              <input type="color" value={gaya.warna ?? '#ffffff'}
                     onChange={(e) => ubah({ gaya: { ...gaya, warna: e.target.value } })} />
            </label>
            <label className="montase-kolom">
              <span>{t('montase.properti.letak')}</span>
              <select value={gaya.letak ?? 'tengah'} onChange={(e) => ubah({ gaya: { ...gaya, letak: e.target.value } })}>
                <option value="atas">{t('montase.properti.letak_atas')}</option>
                <option value="tengah">{t('montase.properti.letak_tengah')}</option>
                <option value="bawah">{t('montase.properti.letak_bawah')}</option>
              </select>
            </label>
          </>
        )}
        {item.jenis === 'motion' && (
          <>
            <p className="montase-petunjuk">{BAWAAN[item.komponen] ? t('montase.properti.bawaan') : item.komponen}</p>
            <KolomProps props={item.props ?? {}} onUbah={(props) => ubah({ props })} />
          </>
        )}
      </div>
    </aside>
  );
}
