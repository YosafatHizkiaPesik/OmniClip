/**
 * Rekam reaksi kamera (JOB-5 O5).
 *
 * Panel mengambang: tampilan kamera langsung, lalu "Rekam" memutar pratinjau
 * dari garis putar SAMBIL merekam kamera dan mikrofon, jadi reaksinya sinkron
 * dengan yang sedang ditonton. "Berhenti" menjeda pratinjau, mengirim rekaman
 * (server mengubahnya ke MP4, bahan `rekam`), dan editor menaruhnya sebagai
 * gambar-dalam-gambar di bingkai tempat rekaman dimulai.
 *
 * Reaksi wajah dan suara pemilik kanal yang mengomentari aslinya adalah
 * bentuk yang disebut kebijakan konten yang digunakan ulang YouTube sebagai
 * transformatif; reaksi yang hampir tanpa kata justru disebut ditolak, jadi
 * panel ini mengingatkan untuk berbicara.
 */
import React, { useEffect, useRef, useState } from 'react';
import { Loader2, Square, Video, X } from 'lucide-react';
import { useT } from '../../../lib/i18n';
import { simpanRekamanVideo } from '../api.js';
import { detikRekam } from './rekamMikrofon.js';

export default function RekamReaksi({ garis, pratinjau, onSelesai, onTutup }) {
  const t = useT();
  const layar = useRef(null);
  const aliran = useRef(null);
  const perekam = useRef(null);
  const mulaiDi = useRef(0);
  const [siap, setSiap] = useState(false);
  const [merekam, setMerekam] = useState(null);
  const [lama, setLama] = useState(0);
  const [sibuk, setSibuk] = useState(false);
  const [galat, setGalat] = useState(null);

  useEffect(() => {
    let hidup = true;
    navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, audio: true })
      .then((s) => {
        if (!hidup) { s.getTracks().forEach((x) => x.stop()); return; }
        aliran.current = s;
        if (layar.current) layar.current.srcObject = s;
        setSiap(true);
      })
      .catch(() => setGalat(t('montase.reaksi.kamera_ditolak')));
    return () => {
      hidup = false;
      aliran.current?.getTracks().forEach((x) => x.stop());
    };
  }, [t]);

  useEffect(() => {
    if (!merekam) return undefined;
    const id = setInterval(() => setLama(Date.now() - merekam), 250);
    return () => clearInterval(id);
  }, [merekam]);

  const rekam = () => {
    setGalat(null);
    const rec = new MediaRecorder(aliran.current);
    const potongan = [];
    rec.ondataavailable = (e) => { if (e.data.size) potongan.push(e.data); };
    rec.onstop = async () => {
      setMerekam(null);
      setSibuk(true);
      try {
        const nama = `${t('montase.reaksi.nama')} ${new Date().toLocaleTimeString().slice(0, 5)}`;
        const bahan = await simpanRekamanVideo(new Blob(potongan, { type: rec.mimeType }), nama);
        onSelesai(bahan, mulaiDi.current);
      } catch (e) {
        setGalat(e.message);
      } finally {
        setSibuk(false);
      }
    };
    perekam.current = rec;
    mulaiDi.current = garis.get();
    rec.start(500);
    setLama(0);
    setMerekam(Date.now());
    pratinjau.current?.putar();
  };
  const berhenti = () => {
    pratinjau.current?.jeda();
    if (perekam.current?.state === 'recording') perekam.current.stop();
  };

  return (
    <div className="montase-reaksi plate" role="dialog" aria-label={t('montase.reaksi.judul')}>
      <div className="montase-bantuan-kepala">
        <h2>{t('montase.reaksi.judul')}</h2>
        <button type="button" className="btn-secondary montase-ikon" onClick={onTutup} disabled={Boolean(merekam) || sibuk}
                aria-label={t('umum.tutup')} title={t('umum.tutup')}
        >
          <X size={14} />
        </button>
      </div>
      <video ref={layar} className="montase-reaksi-layar" autoPlay muted playsInline />
      <p className="montase-petunjuk">{t('montase.reaksi.ket')}</p>
      {galat && <p className="montase-galat" role="alert">{galat}</p>}
      {merekam ? (
        <button type="button" className="btn-primary montase-rekam-aktif" onClick={berhenti}>
          <Square size={13} />{t('montase.suara.berhenti')} · {detikRekam(lama)}
        </button>
      ) : (
        <button type="button" className="btn-primary" onClick={rekam} disabled={!siap || sibuk}>
          {sibuk ? <Loader2 size={13} className="animate-spin" /> : <Video size={13} />}
          {t(sibuk ? 'montase.reaksi.menyimpan' : 'montase.reaksi.rekam')}
        </button>
      )}
    </div>
  );
}
