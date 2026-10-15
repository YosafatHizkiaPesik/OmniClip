import React, { useEffect, useRef, useState } from 'react';
import { Video, Square, Loader2, Trash2 } from 'lucide-react';
import { apiPost } from '../../lib/api';
import { formatTime } from '../../utils/timeFormat';

/**
 * Reaksi kamera pemilik kanal (15 Oktober 2026).
 *
 * Rekam wajah dan suara sendiri SAMBIL klipnya diputar, lalu rekaman itu
 * menempel di pojok sebagai gambar-dalam-gambar, dan suara klip mengecil
 * selama Anda bicara. Format reaksi seperti ini adalah transformasi yang
 * paling jelas di mata kebijakan konten YouTube: yang ditonton orang adalah
 * Anda menanggapi klipnya, bukan potongan ulang.
 *
 * Disimpan sebagai sisipan video biasa (asal "reaksi"), jadi bisa digeser,
 * diubah ukurannya, atau dihapus di tab Sisipan.
 */
export default function ReaksiKamera({ clip, waktuSekarang = 0, durasiKlip = 0, onLayers,
  onSeek, onPutar }) {
  const [tahap, setTahap] = useState('diam');           // diam | siap | rekam | simpan
  const [detik, setDetik] = useState(0);
  const [galat, setGalat] = useState('');
  const kamera = useRef(null);
  const stream = useRef(null);
  const perekam = useRef(null);
  const mulaiDi = useRef(0);
  const jam = useRef(null);

  const lepasKamera = () => {
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    clearInterval(jam.current);
  };
  useEffect(() => lepasKamera, []);
  useEffect(() => { if (kamera.current && stream.current) kamera.current.srcObject = stream.current; }, [tahap]);

  if (!clip) return null;
  const reaksi = (clip.media_layers ?? []).filter((l) => l.asal === 'reaksi');

  const nyalakan = async () => {
    setGalat('');
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setGalat('Peramban ini tidak bisa merekam kamera. Pakai Chrome, Edge, atau Firefox terbaru.');
      return;
    }
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
        audio: { echoCancellation: true, noiseSuppression: true },
      });
      setTahap('siap');
    } catch (e) {
      setGalat(e?.name === 'NotAllowedError'
        ? 'Izin kamera/mikrofon ditolak. Izinkan untuk halaman ini di peramban.'
        : 'Kamera tidak bisa dibuka.');
    }
  };

  const rekam = () => {
    const potongan = [];
    const tipe = ['video/webm;codecs=vp9,opus', 'video/webm;codecs=vp8,opus', 'video/webm']
      .find((t) => MediaRecorder.isTypeSupported?.(t)) || '';
    const mr = new MediaRecorder(stream.current, tipe ? { mimeType: tipe } : undefined);
    mr.ondataavailable = (e) => { if (e.data.size) potongan.push(e.data); };
    mr.onstop = async () => {
      onPutar?.(false);
      clearInterval(jam.current);
      setTahap('simpan');
      try {
        const fd = new FormData();
        fd.append('berkas', new Blob(potongan, { type: mr.mimeType || 'video/webm' }), 'reaksi.webm');
        const a = await apiPost('/komentar/reaksi', fd, { timeout: 600000 });
        const t = mulaiDi.current;
        onLayers([...(clip.media_layers ?? []), {
          id: `rk${Date.now().toString(36)}`, aset: a.id, nama: 'Reaksi saya', jenis: 'video',
          t: Math.round(t * 100) / 100,
          dur: Math.round(Math.min(Number(a.durasi) || 0, Math.max(0.5, durasiKlip - t)) * 100) / 100,
          posisi: 'sudut', isi: 'penuh', opasitas: 1, fade_masuk: 0.2, fade_keluar: 0.2,
          volume: 1, redam_utama: true, asal: 'reaksi',
        }]);
        lepasKamera();
        setTahap('diam');
      } catch (e) {
        setGalat(e.message || 'Rekaman gagal disimpan.');
        setTahap('siap');
      }
    };
    perekam.current = mr;
    mulaiDi.current = waktuSekarang;
    onSeek?.(waktuSekarang);
    mr.start(1000);
    onPutar?.(true);
    setDetik(0);
    setTahap('rekam');
    jam.current = setInterval(() => setDetik((n) => n + 1), 1000);
  };

  const berhenti = () => perekam.current?.state === 'recording' && perekam.current.stop();

  return (
    <div style={{ borderTop: '1px solid var(--line)', paddingTop: '10px',
                  display: 'flex', flexDirection: 'column', gap: '8px' }}>
      <b style={{ fontSize: '.8rem', display: 'flex', gap: 6, alignItems: 'center' }}>
        <Video size={14} /> Reaksi kamera
      </b>
      <span style={{ fontSize: '.74rem', color: 'var(--ink-3)', lineHeight: 1.5 }}>
        Rekam wajah dan suara Anda sambil klipnya diputar. Rekamannya menempel di pojok dan suara
        klip mengecil saat Anda bicara. Pakai headset supaya suara klip tidak ikut terekam.
      </span>
      {tahap !== 'diam' && (
        <video ref={kamera} autoPlay muted playsInline
               style={{ width: '100%', borderRadius: 10, background: '#000', transform: 'scaleX(-1)' }} />
      )}
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
        {tahap === 'diam' && (
          <button className="btn-secondary" onClick={nyalakan}><Video size={13} /> Nyalakan kamera</button>
        )}
        {tahap === 'siap' && (
          <>
            <button className="btn-secondary" onClick={rekam}
                    style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }}>
              ● Rekam dari {formatTime(waktuSekarang)}
            </button>
            <button className="btn-secondary" onClick={() => { lepasKamera(); setTahap('diam'); }}>Batal</button>
          </>
        )}
        {tahap === 'rekam' && (
          <button className="btn-secondary" onClick={berhenti}
                  style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }}>
            <Square size={13} /> Berhenti ({detik} dtk)
          </button>
        )}
        {tahap === 'simpan' && (
          <span style={{ fontSize: '.76rem' }}><Loader2 size={13} className="animate-spin" /> Menyimpan rekaman…</span>
        )}
      </div>
      {galat && <div style={{ fontSize: '.74rem', color: 'var(--danger)' }}>{galat}</div>}
      {reaksi.map((l) => (
        <div key={l.id} style={{ display: 'flex', gap: 8, alignItems: 'center', fontSize: '.76rem' }}>
          <span>Reaksi {formatTime(l.t)} · {Number(l.dur).toFixed(1)} dtk</span>
          <button className="btn-secondary" style={{ padding: '2px 6px' }} title="Hapus reaksi ini"
                  onClick={() => onLayers((clip.media_layers ?? []).filter((x) => x.id !== l.id))}>
            <Trash2 size={12} />
          </button>
        </div>
      ))}
    </div>
  );
}
