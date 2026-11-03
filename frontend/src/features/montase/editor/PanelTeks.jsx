/**
 * Kolom item teks di panel Properti (JOB-4 M3.1).
 *
 * Tema siap pakai diambil dari /api/montase/gaya-teks (sumbernya
 * services/tema_judul.py, sama dengan kartu judul Studio Klip). Memilih tema
 * MENULIS seluruh nilainya ke `item.gaya`; sesudah itu setiap kolom bisa
 * diubah sendiri. Letak dan perataan tidak ikut diganti tema, karena itu
 * keputusan tata letak, bukan gaya.
 */
import React, { useEffect, useState } from 'react';
import { AlignCenter, AlignLeft, AlignRight } from 'lucide-react';
import { useT } from '../../../lib/i18n';
import { fontStack, loadFonts } from '../../../lib/fonts';
import { ambilGayaTeks } from '../api.js';

const LATAR = ['tanpa', 'pelat', 'sorot', 'pita', 'label'];
const GERAK = ['muncul', 'pop', 'hentak', 'naik', 'turun', 'geser', 'lempar', 'getar', 'kedip', 'pelan'];
const RATA = [['kiri', AlignLeft], ['tengah', AlignCenter], ['kanan', AlignRight]];

function rgba(hex, a) {
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex ?? '');
  if (!m) return hex;
  return `rgba(${parseInt(m[1], 16)}, ${parseInt(m[2], 16)}, ${parseInt(m[3], 16)}, ${a})`;
}

/** Contoh kecil tema: huruf, warna, dan pelatnya, bukan hanya nama. */
function ContohTema({ gaya }) {
  const berpelat = gaya.latar !== 'tanpa';
  return (
    <span
      className="montase-tema-contoh"
      style={{
        fontFamily: fontStack(gaya.font),
        color: gaya.warna,
        background: berpelat ? rgba(gaya.warna_latar, gaya.alfa_latar) : 'transparent',
        WebkitTextStroke: gaya.garis > 0 ? `${Math.min(2, gaya.garis / 3)}px ${gaya.warna_garis}` : undefined,
        textShadow: gaya.kabur > 0 ? `0 0 6px ${gaya.warna_garis}` : undefined,
        textTransform: gaya.kapital ? 'uppercase' : undefined,
      }}
    >
      Aa
    </span>
  );
}

function Angka({ label, nilai, onUbah, min = 0, max = 40, langkah = 1, akhiran }) {
  return (
    <label className="montase-kolom">
      <span>{label}</span>
      <span className="montase-isian-akhiran">
        <input type="number" min={min} max={max} step={langkah} value={Number(nilai.toFixed(2))}
               onChange={(e) => { if (e.target.value !== '') onUbah(Number(e.target.value)); }} />
        {akhiran && <small>{akhiran}</small>}
      </span>
    </label>
  );
}

export default function PanelTeks({ item, onUbah }) {
  const t = useT();
  const [daftar, setDaftar] = useState({ gaya: [], font: [] });
  useEffect(() => {
    let hidup = true;
    loadFonts().catch(() => {});
    ambilGayaTeks().then((d) => { if (hidup) setDaftar(d); }).catch(() => {});
    return () => { hidup = false; };
  }, []);

  const gaya = item.gaya ?? {};
  const ubahGaya = (p) => onUbah({ gaya: { ...gaya, ...p } });
  const pakaiTema = (tema) => onUbah({
    gaya: { ...tema.gaya, letak: gaya.letak ?? 'tengah', perataan: gaya.perataan ?? 'tengah' },
  });
  const latar = gaya.latar ?? 'tanpa';

  return (
    <>
      <label className="montase-kolom">
        <span>{t('montase.properti.teks')}</span>
        <textarea rows={3} maxLength={500} value={item.teks ?? ''}
                  onChange={(e) => onUbah({ teks: e.target.value })} />
      </label>

      <section className="montase-bagian">
        <h3>{t('montase.teks.tema')}</h3>
        <div className="montase-tema-kisi">
          {daftar.gaya.map((tm) => (
            <button key={tm.id} type="button"
                    className={`montase-tema ${gaya.tema === tm.id ? 'aktif' : ''}`}
                    aria-pressed={gaya.tema === tm.id} onClick={() => pakaiTema(tm)}
                    title={t(`montase.tema.${tm.id}`)}
            >
              <ContohTema gaya={tm.gaya} />
              <small>{t(`montase.tema.${tm.id}`)}</small>
            </button>
          ))}
        </div>
      </section>

      <section className="montase-bagian">
        <h3>{t('montase.teks.huruf')}</h3>
        <label className="montase-kolom">
          <span>{t('montase.teks.font')}</span>
          <select value={gaya.font ?? ''} onChange={(e) => ubahGaya({ font: e.target.value || undefined })}
                  style={{ fontFamily: gaya.font ? fontStack(gaya.font) : undefined }}
          >
            <option value="">{t('montase.teks.font_sistem')}</option>
            {daftar.font.map((f) => (
              <option key={f.keluarga} value={f.keluarga} style={{ fontFamily: fontStack(f.keluarga) }}>{f.keluarga}</option>
            ))}
          </select>
        </label>
        <div className="montase-kolom-dua">
          <Angka label={t('montase.properti.ukuran_huruf')} nilai={gaya.ukuran ?? 96} min={12} max={600} langkah={4}
                 akhiran="px" onUbah={(v) => ubahGaya({ ukuran: v })} />
          <label className="montase-kolom">
            <span>{t('montase.properti.warna')}</span>
            <input type="color" value={gaya.warna ?? '#ffffff'} onChange={(e) => ubahGaya({ warna: e.target.value })} />
          </label>
        </div>
        <div className="montase-baris-tombol">
          {RATA.map(([r, Ikon]) => (
            <button key={r} type="button"
                    className={`btn-secondary montase-ikon ${(gaya.perataan ?? 'tengah') === r ? 'aktif' : ''}`}
                    aria-pressed={(gaya.perataan ?? 'tengah') === r} onClick={() => ubahGaya({ perataan: r })}
                    title={t(`montase.teks.rata_${r}`)} aria-label={t(`montase.teks.rata_${r}`)}
            >
              <Ikon size={13} />
            </button>
          ))}
          <label className="montase-centang">
            <input type="checkbox" checked={Boolean(gaya.kapital)} onChange={(e) => ubahGaya({ kapital: e.target.checked })} />
            {t('montase.teks.kapital')}
          </label>
        </div>
        <label className="montase-kolom">
          <span>{t('montase.properti.letak')}</span>
          <select value={gaya.letak ?? 'tengah'} onChange={(e) => ubahGaya({ letak: e.target.value })}>
            <option value="atas">{t('montase.properti.letak_atas')}</option>
            <option value="tengah">{t('montase.properti.letak_tengah')}</option>
            <option value="bawah">{t('montase.properti.letak_bawah')}</option>
          </select>
        </label>
      </section>

      <section className="montase-bagian">
        <h3>{t('montase.teks.latar')}</h3>
        <select value={latar} onChange={(e) => ubahGaya({ latar: e.target.value })}
                aria-label={t('montase.teks.latar')}
        >
          {LATAR.map((l) => <option key={l} value={l}>{t(`montase.teks.latar_${l}`)}</option>)}
        </select>
        {latar !== 'tanpa' && (
          <div className="montase-kolom-dua">
            <label className="montase-kolom">
              <span>{t('montase.teks.warna_latar')}</span>
              <input type="color" value={gaya.warna_latar ?? '#000000'}
                     onChange={(e) => ubahGaya({ warna_latar: e.target.value })} />
            </label>
            <Angka label={t('montase.teks.pekat')} nilai={(gaya.alfa_latar ?? 1) * 100} max={100} langkah={5}
                   akhiran="%" onUbah={(v) => ubahGaya({ alfa_latar: Math.min(1, Math.max(0, v / 100)) })} />
          </div>
        )}
        {latar === 'label' && (
          <label className="montase-kolom">
            <span>{t('montase.teks.cip')}</span>
            <input value={gaya.cip ?? ''} maxLength={20} onChange={(e) => ubahGaya({ cip: e.target.value })} />
          </label>
        )}
      </section>

      <section className="montase-bagian">
        <h3>{t('montase.teks.efek')}</h3>
        <div className="montase-kolom-dua">
          <Angka label={t('montase.teks.garis')} nilai={gaya.garis ?? 0} akhiran="px"
                 onUbah={(v) => ubahGaya({ garis: v })} />
          <label className="montase-kolom">
            <span>{t('montase.teks.warna_garis')}</span>
            <input type="color" value={gaya.warna_garis ?? '#000000'}
                   onChange={(e) => ubahGaya({ warna_garis: e.target.value })} />
          </label>
          <Angka label={t('montase.teks.bayang')} nilai={gaya.bayang ?? 0} akhiran="px"
                 onUbah={(v) => ubahGaya({ bayang: v })} />
          <Angka label={t('montase.teks.cahaya')} nilai={gaya.kabur ?? 0} akhiran="px"
                 onUbah={(v) => ubahGaya({ kabur: v })} />
        </div>
        {Array.isArray(item.kata) && item.kata.length > 0 && (
          <label className="montase-kolom">
            <span>{t('montase.teks.warna_sorot')}</span>
            <input type="color" value={gaya.warna_sorot ?? '#FFE500'}
                   onChange={(e) => ubahGaya({ warna_sorot: e.target.value })} />
          </label>
        )}
        <label className="montase-kolom">
          <span>{t('montase.teks.gerak')}</span>
          <select value={gaya.gerak ?? 'muncul'} onChange={(e) => ubahGaya({ gerak: e.target.value })}>
            {GERAK.map((g) => <option key={g} value={g}>{t(`montase.teks.gerak_${g}`)}</option>)}
          </select>
        </label>
      </section>
    </>
  );
}
