/**
 * Rekam mikrofon lewat MediaRecorder, dipakai tab Suara (M3.3) dan
 * teleprompter narasi (JOB-5 O2). Hasilnya Blob WebM/Opus; server mengubahnya
 * ke M4A dan mencatatnya sebagai bahan `rekam`.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

export function useRekamMikrofon() {
  const [merekam, setMerekam] = useState(null);     // {mulai} saat merekam
  const [lama, setLama] = useState(0);
  const perekam = useRef(null);

  useEffect(() => {
    if (!merekam) return undefined;
    const id = setInterval(() => setLama(Date.now() - merekam.mulai), 250);
    return () => clearInterval(id);
  }, [merekam]);
  useEffect(() => () => perekam.current?.stream?.getTracks().forEach((x) => x.stop()), []);

  /** Mulai merekam; `onSelesai(blob)` dipanggil sesudah `berhenti()`. Melempar bila mikrofon ditolak. */
  const mulai = useCallback(async (onSelesai) => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const rec = new MediaRecorder(stream);
    const potongan = [];
    rec.ondataavailable = (e) => { if (e.data.size) potongan.push(e.data); };
    rec.onstop = () => {
      stream.getTracks().forEach((x) => x.stop());
      setMerekam(null);
      onSelesai(new Blob(potongan, { type: rec.mimeType }));
    };
    perekam.current = rec;
    rec.start(250);
    setLama(0);
    setMerekam({ mulai: Date.now() });
  }, []);

  const berhenti = useCallback(() => {
    if (perekam.current?.state === 'recording') perekam.current.stop();
  }, []);

  return { merekam: Boolean(merekam), lama, mulai, berhenti };
}

export function detikRekam(ms) {
  const d = Math.floor(ms / 1000);
  return `${Math.floor(d / 60)}:${String(d % 60).padStart(2, '0')}`;
}
