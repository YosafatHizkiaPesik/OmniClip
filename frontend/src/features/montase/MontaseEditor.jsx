/**
 * Editor satu proyek Montase (/montase/:proyekId, JOB-4 M1.7-M1.9).
 *
 * Empat area yang ukurannya bisa diatur: Bahan (kiri), Pratinjau (tengah),
 * Properti (kanan), Linimasa (bawah). Semua perubahan lewat fungsi murni di
 * model/dokumen.js, lalu disimpan otomatis 1,5 detik sesudah perubahan
 * terakhir.
 *
 * Penyimpanan BERURUTAN: simpan berikutnya menunggu yang sebelumnya selesai
 * dan memakai revisi yang baru dikembalikan. Tanpa itu, dua perubahan cepat
 * berangkat dengan revisi yang sama dan yang kedua ditolak 409 oleh server
 * kita sendiri. 409 yang sungguhan (tab atau perangkat lain) menghentikan
 * simpan otomatis dan meminta muat ulang, bukan menimpa diam-diam.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowLeft, Check, CloudOff, Download, Loader2, MonitorSmartphone, RefreshCw,
} from 'lucide-react';
import { useT } from '../../lib/i18n';
import { useJobRunner } from '../../hooks/useJob';
import JobProgress from '../../components/JobProgress';
import { BAWAAN } from './komposisi/index.js';
import {
  ambilProyek, ambilToken, simpanProyek, sumberPratinjau,
} from './api.js';
import {
  cariItem, hapusItem, pindahUrutan, tambahBahan, tambahMotion, tambahTeks, ubahItem,
  ubahProyek,
} from './model/dokumen.js';
import PratinjauKotakPasir from './pratinjau/PratinjauKotakPasir.jsx';
import PanelBahan from './editor/PanelBahan.jsx';
import PanelProperti from './editor/PanelProperti.jsx';
import Linimasa from './editor/Linimasa.jsx';

const JEDA_SIMPAN = 1500;
const KUNCI_TATA = 'omniclip.montase.tata';
const TATA_BAWAAN = { kiri: 280, kanan: 300, bawah: 270 };

function bacaTata() {
  try {
    return { ...TATA_BAWAAN, ...JSON.parse(localStorage.getItem(KUNCI_TATA) || '{}') };
  } catch {
    return TATA_BAWAAN;
  }
}

function useLayarSempit() {
  const [sempit, setSempit] = useState(() => window.matchMedia('(max-width: 899px)').matches);
  useEffect(() => {
    const mq = window.matchMedia('(max-width: 899px)');
    const ubah = (e) => setSempit(e.matches);
    mq.addEventListener('change', ubah);
    return () => mq.removeEventListener('change', ubah);
  }, []);
  return sempit;
}

/** Pembatas yang bisa diseret untuk mengubah lebar/tinggi satu area. */
function Pembatas({ arah, onGeser }) {
  const mulai = (e) => {
    e.preventDefault();
    const awal = arah === 'tegak' ? e.clientX : e.clientY;
    const gerak = (ev) => onGeser((arah === 'tegak' ? ev.clientX : ev.clientY) - awal, false);
    const lepas = (ev) => {
      onGeser((arah === 'tegak' ? ev.clientX : ev.clientY) - awal, true);
      window.removeEventListener('pointermove', gerak);
      window.removeEventListener('pointerup', lepas);
    };
    window.addEventListener('pointermove', gerak);
    window.addEventListener('pointerup', lepas);
  };
  return (
    <div className={`montase-pembatas montase-pembatas-${arah}`} onPointerDown={mulai}
         role="separator" aria-orientation={arah === 'tegak' ? 'vertical' : 'horizontal'} />
  );
}

function StatusSimpan({ status, onMuatUlang }) {
  const t = useT();
  if (status === 'menyimpan' || status === 'belum') {
    return <span className="montase-simpan"><Loader2 size={12} className="animate-spin" />{t('montase.editor.menyimpan')}</span>;
  }
  if (status === 'bentrok') {
    return (
      <span className="montase-simpan montase-simpan-galat">
        <CloudOff size={12} />{t('montase.editor.bentrok')}
        <button type="button" className="btn-secondary" onClick={onMuatUlang}>
          <RefreshCw size={12} />{t('umum.muat_ulang')}
        </button>
      </span>
    );
  }
  if (status === 'gagal') {
    return <span className="montase-simpan montase-simpan-galat"><CloudOff size={12} />{t('montase.editor.gagal_simpan')}</span>;
  }
  return <span className="montase-simpan"><Check size={12} />{t('montase.editor.tersimpan')}</span>;
}

export default function MontaseEditor() {
  const t = useT();
  const { proyekId } = useParams();
  const navigate = useNavigate();
  const sempit = useLayarSempit();
  const [dokumen, setDokumen] = useState(null);
  const [galat, setGalat] = useState(null);
  const [galatPratinjau, setGalatPratinjau] = useState(null);
  const [token, setToken] = useState(null);
  const [dipilih, setDipilih] = useState(null);
  const [bingkai, setBingkai] = useState(0);
  const [status, setStatus] = useState('tersimpan');
  const [tata, setTata] = useState(bacaTata);
  const [bahanSiap, setBahanSiap] = useState(() => new Set());
  const catatBahan = useCallback((daftar) => {
    setBahanSiap(new Set(daftar.filter((b) => b.siap).map((b) => b.id)));
  }, []);
  const tataSeret = useRef(tata);
  const pratinjau = useRef(null);
  const ekspor = useJobRunner();

  const revisi = useRef(null);
  const kotor = useRef(false);
  const dokRef = useRef(null);
  const antrean = useRef(Promise.resolve());
  dokRef.current = dokumen;

  const muat = useCallback(() => {
    setGalat(null);
    ambilProyek(proyekId)
      .then((p) => {
        revisi.current = p.revisi;
        kotor.current = false;
        setDokumen(p.dokumen);
        setStatus('tersimpan');
      })
      .catch((e) => setGalat(e.message));
    ambilToken().then(setToken).catch(() => {});
  }, [proyekId]);
  useEffect(() => { muat(); }, [muat]);

  const simpanSekarang = useCallback(() => {
    antrean.current = antrean.current.then(async () => {
      if (!kotor.current || !dokRef.current) return;
      const d = dokRef.current;
      kotor.current = false;
      setStatus('menyimpan');
      try {
        const r = await simpanProyek(proyekId, d, revisi.current);
        revisi.current = r.revisi;
        setStatus(kotor.current ? 'belum' : 'tersimpan');
      } catch (e) {
        kotor.current = true;
        setStatus(e.status === 409 ? 'bentrok' : 'gagal');
        setGalat(e.message);
      }
    });
    return antrean.current;
  }, [proyekId]);

  useEffect(() => {
    if (!kotor.current || status === 'bentrok') return undefined;
    setStatus('belum');
    const id = setTimeout(simpanSekarang, JEDA_SIMPAN);
    return () => clearTimeout(id);
    // `status` sengaja tidak ikut: perubahannya bukan alasan menyimpan.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dokumen, simpanSekarang]);

  useEffect(() => {
    const tahan = (e) => { if (kotor.current) { e.preventDefault(); e.returnValue = ''; } };
    window.addEventListener('beforeunload', tahan);
    return () => window.removeEventListener('beforeunload', tahan);
  }, []);

  const ubah = useCallback((fn) => {
    setDokumen((d) => {
      const baru = fn(d);
      if (baru !== d) kotor.current = true;
      return baru;
    });
  }, []);

  const sumber = useMemo(
    () => (dokumen ? sumberPratinjau(dokumen, token) : null),
    // Hanya daftar bahan yang menentukan alamat; perubahan item tidak.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [dokumen && Object.keys(dokumen.bahan).join(','), token],
  );

  const tambahKeLinimasa = (b) => {
    let baru = null;
    ubah((d) => {
      const hasil = tambahBahan(d, b);
      baru = hasil.itemId;
      return hasil.dokumen;
    });
    setTimeout(() => baru && setDipilih(baru), 0);
  };
  const tambahTeksDiGaris = () => {
    let baru = null;
    ubah((d) => {
      const hasil = tambahTeks(d, { mulai: bingkai, teks: t('montase.editor.teks_baru') });
      baru = hasil.itemId;
      return hasil.dokumen;
    });
    setTimeout(() => baru && setDipilih(baru), 0);
  };
  const tambahAnimasiDiGaris = () => {
    let baru = null;
    ubah((d) => {
      const hasil = tambahMotion(d, {
        komponen: 'ko_hitung_mundur', modul: BAWAAN.ko_hitung_mundur, mulai: bingkai,
      });
      baru = hasil.itemId;
      return hasil.dokumen;
    });
    setTimeout(() => baru && setDipilih(baru), 0);
  };
  const hapusTerpilih = () => {
    if (!dipilih) return;
    ubah((d) => hapusItem(d, dipilih));
    setDipilih(null);
  };

  const mulaiEkspor = async () => {
    await simpanSekarang();
    if (kotor.current) return;
    ekspor.run(`/montase/proyek/${encodeURIComponent(proyekId)}/ekspor`).catch(() => {});
  };

  const geser = (kunci, tanda, batas) => (delta, selesai) => {
    const nilai = Math.min(batas[1], Math.max(batas[0], tataSeret.current[kunci] + tanda * delta));
    const baru = { ...tata, [kunci]: nilai };
    setTata(baru);
    if (selesai) {
      tataSeret.current = baru;
      try { localStorage.setItem(KUNCI_TATA, JSON.stringify(baru)); } catch { /* tidak apa */ }
    }
  };

  if (sempit) {
    return (
      <div className="page montase-sempit">
        <MonitorSmartphone size={32} aria-hidden />
        <h1>{t('montase.editor.sempit_judul')}</h1>
        <p>{t('montase.editor.sempit_ket')}</p>
        <Link className="btn-secondary" to="/montase"><ArrowLeft size={14} />{t('montase.editor.kembali')}</Link>
      </div>
    );
  }
  if (!dokumen) {
    return (
      <div className="page montase-memuat">
        {galat ? <p className="montase-galat" role="alert">{galat}</p> : <Loader2 size={20} className="animate-spin" />}
      </div>
    );
  }

  const terpilih = dipilih ? cariItem(dokumen, dipilih) : null;
  const hasil = ekspor.result;
  return (
    <div className="montase-editor"
         style={{ gridTemplateRows: `auto minmax(0, 1fr) 6px ${tata.bawah}px` }}
    >
      <header className="montase-editor-kepala">
        <button type="button" className="btn-secondary montase-ikon" onClick={() => navigate('/montase')}
                aria-label={t('montase.editor.kembali')} title={t('montase.editor.kembali')}
        >
          <ArrowLeft size={14} />
        </button>
        <h1 title={dokumen.nama}>{dokumen.nama}</h1>
        <StatusSimpan status={status} onMuatUlang={muat} />
        <span className="montase-linimasa-spasi" />
        {(ekspor.job || ekspor.error) && (
          <div className="montase-ekspor-kabar">
            <JobProgress job={ekspor.job} error={ekspor.error} onCancel={ekspor.cancel} compact />
          </div>
        )}
        {hasil && (
          <Link className="btn-secondary" to="/clips">{t('montase.editor.lihat_klip', { berkas: hasil.berkas })}</Link>
        )}
        <button type="button" className="btn-primary" onClick={mulaiEkspor}
                disabled={ekspor.active || status === 'bentrok'}
        >
          {ekspor.active ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
          {t('montase.editor.ekspor')}
        </button>
      </header>

      <div className="montase-editor-tengah"
           style={{ gridTemplateColumns: `${tata.kiri}px 6px minmax(0, 1fr) 6px ${tata.kanan}px` }}
      >
        <PanelBahan token={token} onTambahKeLinimasa={tambahKeLinimasa} onBahan={catatBahan} />
        <Pembatas arah="tegak" onGeser={geser('kiri', 1, [220, 520])} />
        <section className="montase-panel montase-panel-pratinjau" aria-label={t('montase.pratinjau.judul')}>
          {galat && status !== 'bentrok' && <p className="montase-galat" role="alert">{galat}</p>}
          {galatPratinjau && <p className="montase-galat" role="alert">{galatPratinjau}</p>}
          <PratinjauKotakPasir ref={pratinjau} dokumen={dokumen} sumber={sumber} lengkap
                               onBingkai={setBingkai} onGalat={setGalatPratinjau} />
        </section>
        <Pembatas arah="tegak" onGeser={geser('kanan', -1, [240, 520])} />
        <PanelProperti
          dokumen={dokumen}
          terpilih={terpilih}
          onUbahItem={(id, perubahan) => ubah((d) => ubahItem(d, id, perubahan))}
          onHapus={hapusTerpilih}
          onUbahProyek={(perubahan) => ubah((d) => ubahProyek(d, perubahan))}
        />
      </div>

      <Pembatas arah="datar" onGeser={geser('bawah', -1, [150, 480])} />
      <Linimasa
        dokumen={dokumen}
        bingkai={bingkai}
        token={token}
        dipilih={dipilih}
        onPilih={setDipilih}
        onKe={(b) => { setBingkai(b); pratinjau.current?.ke(b); }}
        onTambahTeks={tambahTeksDiGaris}
        onTambahMotion={tambahAnimasiDiGaris}
        onHapus={hapusTerpilih}
        onPindah={(arah) => dipilih && ubah((d) => pindahUrutan(d, dipilih, arah))}
        bahanSiap={bahanSiap}
      />
    </div>
  );
}
