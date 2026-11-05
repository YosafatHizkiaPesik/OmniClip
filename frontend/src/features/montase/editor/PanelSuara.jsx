/**
 * Narasi dan rekaman suara (JOB-4 M3.3).
 *
 * PanelSuara (tab "Suara" di panel Bahan):
 *   - Narasi: ketik teks, pilih suara dari katalog tts.py, buat. Hasilnya bahan
 *     audio yang ditaruh di garis putar, di lajur audio yang kosong.
 *   - Rekam: mikrofon lewat MediaRecorder; hasilnya diubah server ke M4A dan
 *     ditaruh di garis putar dengan cara yang sama.
 *
 * KolomNarasi (panel Properti, item narasi): teks dan suara item itu. Teks
 * yang diubah tidak langsung mengirim permintaan per ketukan; tombol "Buat
 * ulang suara" menyala dan menggantinya sekali.
 */
import React, { useEffect, useState } from 'react';
import { Loader2, Mic, RefreshCw, Square, Wand2 } from 'lucide-react';
import { useT, angka } from '../../../lib/i18n';
import { buatNarasi, daftarSuara, simpanRekaman } from '../api.js';
import { detikRekam, useRekamMikrofon } from './rekamMikrofon.js';

let simpananSuara = null;
function useSuara() {
  const [suara, setSuara] = useState(simpananSuara ?? []);
  useEffect(() => {
    if (simpananSuara) return undefined;
    let hidup = true;
    daftarSuara().then((s) => { simpananSuara = s; if (hidup) setSuara(s); }).catch(() => {});
    return () => { hidup = false; };
  }, []);
  return suara;
}

function PilihSuara({ suara, nilai, onUbah }) {
  const t = useT();
  return (
    <label className="montase-kolom">
      <span>{t('montase.suara.pilih')}</span>
      <select value={nilai} onChange={(e) => onUbah(e.target.value)}>
        {suara.map((s) => (
          <option key={s.id} value={s.id} disabled={!s.siap}>
            {s.label} · {s.bahasa.toUpperCase()}{s.siap ? '' : ` (${t('montase.suara.belum_siap')})`}
          </option>
        ))}
      </select>
    </label>
  );
}

function suaraAwal(suara) {
  return suara.find((s) => s.siap && s.bahasa === 'id')?.id ?? suara.find((s) => s.siap)?.id ?? '';
}

export default function PanelSuara({ onTambahSuara }) {
  const t = useT();
  const suara = useSuara();
  const [teks, setTeks] = useState('');
  const [pilihan, setPilihan] = useState('');
  const [kecepatan, setKecepatan] = useState(1);
  const [sibuk, setSibuk] = useState(false);
  const [galat, setGalat] = useState(null);
  const mik = useRekamMikrofon();
  const suaraDipakai = pilihan || suaraAwal(suara);

  const narasi = async () => {
    setGalat(null);
    setSibuk(true);
    try {
      const bahan = await buatNarasi(teks, suaraDipakai, kecepatan);
      onTambahSuara(bahan, { teks: teks.trim(), suara: suaraDipakai, kecepatan });
      setTeks('');
    } catch (e) {
      setGalat(e.message);
    } finally {
      setSibuk(false);
    }
  };

  const mulaiRekam = async () => {
    setGalat(null);
    try {
      await mik.mulai(async (blob) => {
        setSibuk(true);
        try {
          const nama = `${t('montase.suara.rekaman')} ${new Date().toLocaleTimeString().slice(0, 5)}`;
          const bahan = await simpanRekaman(blob, nama);
          onTambahSuara(bahan, null);
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

  return (
    <div className="montase-suara">
      {galat && <p className="montase-galat" role="alert">{galat}</p>}
      <section className="montase-bagian">
        <h3>{t('montase.suara.narasi')}</h3>
        <textarea rows={4} maxLength={2000} value={teks} placeholder={t('montase.suara.narasi_contoh')}
                  aria-label={t('montase.suara.narasi')} onChange={(e) => setTeks(e.target.value)} />
        <PilihSuara suara={suara} nilai={suaraDipakai} onUbah={setPilihan} />
        <label className="montase-kolom">
          <span>{t('montase.suara.tempo')}</span>
          <span className="montase-geser-angka">
            <input type="range" min={0.6} max={1.6} step={0.05} value={kecepatan}
                   onChange={(e) => setKecepatan(Number(e.target.value))} />
            <small>{angka(kecepatan)}x</small>
          </span>
        </label>
        <button type="button" className="btn-primary" disabled={sibuk || !teks.trim() || !suaraDipakai}
                onClick={narasi}
        >
          {sibuk ? <Loader2 size={13} className="animate-spin" /> : <Wand2 size={13} />}
          {t('montase.suara.buat_narasi')}
        </button>
      </section>
      <section className="montase-bagian">
        <h3>{t('montase.suara.rekam')}</h3>
        <p className="montase-petunjuk">{t('montase.suara.rekam_ket')}</p>
        {mik.merekam ? (
          <button type="button" className="btn-primary montase-rekam-aktif" onClick={mik.berhenti}>
            <Square size={13} />{t('montase.suara.berhenti')} · {detikRekam(mik.lama)}
          </button>
        ) : (
          <button type="button" className="btn-secondary" disabled={sibuk} onClick={mulaiRekam}>
            <Mic size={13} />{t('montase.suara.mulai_rekam')}
          </button>
        )}
      </section>
    </div>
  );
}

export function KolomNarasi({ item, onBuatUlang, onRekam }) {
  const t = useT();
  const suara = useSuara();
  const asli = item.narasi;
  const [draf, setDraf] = useState({ teks: asli.teks, suara: asli.suara, kecepatan: asli.kecepatan ?? 1 });
  const [sibuk, setSibuk] = useState(false);
  const [galat, setGalat] = useState(null);
  const berubah = draf.teks.trim() !== asli.teks || draf.suara !== asli.suara
    || draf.kecepatan !== (asli.kecepatan ?? 1);
  const buatUlang = async () => {
    setSibuk(true);
    setGalat(null);
    try {
      await onBuatUlang({ teks: draf.teks.trim(), suara: draf.suara, kecepatan: draf.kecepatan });
    } catch (e) {
      setGalat(e.message);
    } finally {
      setSibuk(false);
    }
  };
  return (
    <section className="montase-bagian">
      <h3>{t('montase.suara.narasi')}</h3>
      {galat && <p className="montase-galat" role="alert">{galat}</p>}
      <textarea rows={4} maxLength={2000} value={draf.teks} aria-label={t('montase.suara.narasi')}
                onChange={(e) => setDraf((d) => ({ ...d, teks: e.target.value }))} />
      <PilihSuara suara={suara} nilai={draf.suara} onUbah={(v) => setDraf((d) => ({ ...d, suara: v }))} />
      <label className="montase-kolom">
        <span>{t('montase.suara.tempo')}</span>
        <span className="montase-geser-angka">
          <input type="range" min={0.6} max={1.6} step={0.05} value={draf.kecepatan}
                 onChange={(e) => setDraf((d) => ({ ...d, kecepatan: Number(e.target.value) }))} />
          <small>{angka(draf.kecepatan)}x</small>
        </span>
      </label>
      {asli.direkam && <p className="montase-petunjuk">{t('montase.teleprompter.sudah_direkam')}</p>}
      <div className="montase-baris-tombol">
        {onRekam && (
          <button type="button" className="btn-primary" disabled={sibuk} onClick={onRekam}>
            <Mic size={13} />{t(asli.direkam ? 'montase.teleprompter.rekam_ulang' : 'montase.teleprompter.rekam_satu')}
          </button>
        )}
        <button type="button" className="btn-secondary"
                disabled={(!berubah && !asli.direkam) || sibuk || !draf.teks.trim()} onClick={buatUlang}
        >
          {sibuk ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
          {t(asli.direkam ? 'montase.teleprompter.kembali_ai' : 'montase.suara.buat_ulang')}
        </button>
      </div>
    </section>
  );
}
