/**
 * Panel Bahan editor Montase (JOB-4 M1.6).
 *
 * Dua bagian:
 *   - "Bahan saya": pustaka bahan profil ini. Tombol + menaruhnya di ujung
 *     lajurnya (video/gambar ke lajur gambar, suara ke lajur suara); diseret,
 *     bahan jatuh di lajur dan bingkai tempat ia dilepas.
 *   - "Ambil dari": Unduhan, Klip jadi, Aset, atau impor berkas dari komputer.
 *     Memilih satu mencatatnya sebagai bahan (berkasnya tidak disalin) dan
 *     langsung menaruhnya di linimasa.
 *
 * Bahan yang baru dicatat disiapkan di latar (sampul, strip, gelombang,
 * salinan sunting); selama itu daftar diperbarui tiap beberapa detik.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Film, Image as Gambar, Loader2, Music, Plus, Upload,
} from 'lucide-react';
import { useT } from '../../../lib/i18n';
import { formatTime } from '../../../utils/timeFormat';
import {
  alamatBahan, daftarBahan, imporBahan, rujukBahan, sumberBahan,
} from '../api.js';
import { JENIS_SERET_BAHAN } from './garisPutar.js';
import PanelSuara from './PanelSuara.jsx';
import PanelAnimasi from './PanelAnimasi.jsx';
import PanelAsisten from './PanelAsisten.jsx';

const ASAL = [
  { id: 'unduhan', kunci: 'montase.bahan.unduhan' },
  { id: 'klip_jadi', kunci: 'montase.bahan.klip_jadi' },
  { id: 'aset', kunci: 'montase.bahan.aset' },
];
const IKON = { video: Film, audio: Music, gambar: Gambar };

function BarisBahan({ b, token, onTambah, sibuk, bisaDiseret = false }) {
  const t = useT();
  const Ikon = IKON[b.jenis] ?? Film;
  // Bahan di pustaka bisa diseret ke lajur dan bingkai tertentu di linimasa;
  // tombol + tetap menaruhnya di ujung lajur.
  const seret = bisaDiseret ? {
    draggable: true,
    onDragStart: (e) => {
      e.dataTransfer.setData(JENIS_SERET_BAHAN, JSON.stringify(b));
      e.dataTransfer.effectAllowed = 'copy';
    },
  } : {};
  return (
    <li className={`montase-bahan-baris ${bisaDiseret ? 'bisa-diseret' : ''}`} {...seret}>
      <span className="montase-bahan-sampul">
        {b.jenis !== 'audio' && token && b.siap !== false && b.id
          ? <img src={alamatBahan(token, b.id, { turunan: 'sampul' })} alt="" loading="lazy" />
          : <Ikon size={16} aria-hidden />}
      </span>
      <span className="montase-bahan-teks">
        <b title={b.nama}>{b.nama}</b>
        <small>
          {t(`montase.jenis.${b.jenis}`)}
          {b.durasi ? ` · ${formatTime(b.durasi)}` : ''}
          {b.siap === false && ` · ${t('montase.bahan.menyiapkan')}`}
        </small>
      </span>
      <button type="button" className="btn-secondary montase-ikon" onClick={onTambah}
              disabled={sibuk} title={t('montase.bahan.tambah')}
              aria-label={t('montase.bahan.tambah_ke', { nama: b.nama })}
      >
        {sibuk ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
      </button>
    </li>
  );
}

export default function PanelBahan({ token, onTambahKeLinimasa, onTambahSuara, onBahan, animasi, asisten }) {
  const t = useT();
  const [bahan, setBahan] = useState([]);
  const [asal, setAsal] = useState(null);
  const [sumber, setSumber] = useState(null);
  const [sibuk, setSibuk] = useState(null);
  const [unggah, setUnggah] = useState(null);
  const [galat, setGalat] = useState(null);
  const masukan = useRef(null);
  // Tab yang bukan daftar berkas: isinya panel sendiri.
  const tabPanel = asal === 'suara' || asal === 'animasi' || asal === 'asisten';

  const muat = useCallback(() => daftarBahan()
    .then((daftar) => { setBahan(daftar); onBahan?.(daftar); })
    .catch((e) => setGalat(e.message)), [onBahan]);
  useEffect(() => { muat(); }, [muat]);

  // Bahan yang masih disiapkan: perbarui sampai semuanya siap.
  useEffect(() => {
    if (!bahan.some((b) => !b.siap)) return undefined;
    const id = setInterval(muat, 4000);
    return () => clearInterval(id);
  }, [bahan, muat]);

  useEffect(() => {
    if (!asal || tabPanel) return;
    setSumber(null);
    sumberBahan(asal).then(setSumber).catch((e) => { setGalat(e.message); setSumber([]); });
  }, [asal, tabPanel]);

  const tambahDariSumber = async (s) => {
    const kunci = `${s.asal}:${s.rujukan}`;
    setSibuk(kunci);
    setGalat(null);
    try {
      const b = await rujukBahan(s.asal, s.rujukan);
      await muat();
      onTambahKeLinimasa(b);
    } catch (e) {
      setGalat(e.message);
    } finally {
      setSibuk(null);
    }
  };

  const impor = async (e) => {
    const berkas = e.target.files?.[0];
    e.target.value = '';
    if (!berkas) return;
    setGalat(null);
    setUnggah(0);
    try {
      const b = await imporBahan(berkas, setUnggah);
      await muat();
      onTambahKeLinimasa(b);
    } catch (err) {
      setGalat(err.message);
    } finally {
      setUnggah(null);
    }
  };

  return (
    <aside className="montase-panel montase-panel-bahan" aria-label={t('montase.bahan.judul')}>
      <div className="montase-panel-kepala">
        <h2>{t('montase.bahan.judul')}</h2>
        <button type="button" className="btn-secondary" onClick={() => masukan.current?.click()}
                disabled={unggah !== null}
        >
          {unggah !== null ? <Loader2 size={13} className="animate-spin" /> : <Upload size={13} />}
          {unggah !== null ? `${Math.round(unggah * 100)}%` : t('montase.bahan.impor')}
        </button>
        <input ref={masukan} type="file" hidden onChange={impor}
               accept="video/*,audio/*,image/*" />
      </div>
      {galat && <p className="montase-galat" role="alert">{galat}</p>}

      <div className="montase-tab" role="tablist">
        <button type="button" role="tab" aria-selected={asal === null}
                className={asal === null ? 'aktif' : ''} onClick={() => setAsal(null)}
        >
          {t('montase.bahan.saya')}
        </button>
        {ASAL.map((a) => (
          <button key={a.id} type="button" role="tab" aria-selected={asal === a.id}
                  className={asal === a.id ? 'aktif' : ''} onClick={() => setAsal(a.id)}
          >
            {t(a.kunci)}
          </button>
        ))}
        <button type="button" role="tab" aria-selected={asal === 'suara'}
                className={asal === 'suara' ? 'aktif' : ''} onClick={() => setAsal('suara')}
        >
          {t('montase.suara.tab')}
        </button>
        <button type="button" role="tab" aria-selected={asal === 'animasi'}
                className={asal === 'animasi' ? 'aktif' : ''} onClick={() => setAsal('animasi')}
        >
          {t('montase.ai.tab')}
        </button>
        {asisten && (
          <button type="button" role="tab" aria-selected={asal === 'asisten'}
                  className={asal === 'asisten' ? 'aktif' : ''} onClick={() => setAsal('asisten')}
          >
            {t('montase.asisten.tab')}
          </button>
        )}
      </div>
      {asal === 'asisten' && <PanelAsisten bahan={bahan} {...asisten} />}
      {asal === 'animasi' && <PanelAnimasi token={token} {...animasi} />}

      {asal === 'suara' && (
        <PanelSuara onTambahSuara={async (b, narasi) => { await muat(); onTambahSuara(b, narasi); }} />
      )}

      <ul className="montase-bahan-daftar" hidden={tabPanel}>
        {asal === null && bahan.length === 0 && (
          <li className="montase-kosong-kecil">{t('montase.bahan.kosong')}</li>
        )}
        {asal === null && bahan.map((b) => (
          <BarisBahan key={b.id} b={b} token={token} onTambah={() => onTambahKeLinimasa(b)} bisaDiseret />
        ))}
        {asal !== null && sumber === null && <li><Loader2 size={16} className="animate-spin" /></li>}
        {asal !== null && sumber?.length === 0 && (
          <li className="montase-kosong-kecil">{t('montase.bahan.sumber_kosong')}</li>
        )}
        {asal !== null && sumber?.map((s) => (
          <BarisBahan key={`${s.asal}:${s.rujukan}`} b={s} token={null}
                      sibuk={sibuk === `${s.asal}:${s.rujukan}`}
                      onTambah={() => tambahDariSumber(s)} />
        ))}
      </ul>
    </aside>
  );
}
