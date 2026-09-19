import React, { useEffect, useRef } from 'react';

/**
 * Sisipan di atas pratinjau: cuplikan dan gambar di petaknya, musik dan efek
 * suara ikut terdengar.
 *
 * Petaknya dihitung dengan pecahan yang SAMA dengan `POSISI_SISIPAN` di
 * render.py. Pratinjau yang menaruh cuplikan di tempat lain daripada hasil
 * rendernya memaksa pengguna merender hanya untuk tahu letaknya.
 */
const POSISI = {
  penuh: [0, 0, 1, 1],
  atas: [0, 0, 1, 0.5],
  bawah: [0, 0.5, 1, 0.5],
  tengah: [0, 0.25, 1, 0.5],
  sudut: [0.5, 0.06, 0.46, null],   // tinggi = lebar * 9/16, dalam piksel
};

const url = (id) => `/api/aset/${encodeURIComponent(id)}/berkas`;

function Lapis({ l, jenis, clipTime, playing, boxW, boxH }) {
  const ref = useRef(null);
  const aktif = clipTime >= l.t && clipTime < l.t + (l.dur ?? 0);
  const posisiDalam = clipTime - l.t + (l.mulai_sumber ?? 0);

  // Waktu dan status putar diikat ke pratinjau utama. Selisih kecil dibiarkan:
  // menyetel currentTime tiap bingkai membuat media tersendat terus.
  useEffect(() => {
    const el = ref.current;
    if (!el || jenis === 'gambar') return;
    if (!aktif) { if (!el.paused) el.pause(); return; }
    if (Math.abs(el.currentTime - posisiDalam) > 0.3) el.currentTime = Math.max(0, posisiDalam);
    el.volume = Math.max(0, Math.min(1, l.volume ?? 1));
    el.muted = (l.volume ?? 1) <= 0;
    if (playing && el.paused) el.play().catch(() => { /* ditolak peramban */ });
    if (!playing && !el.paused) el.pause();
  }, [aktif, playing, posisiDalam, jenis, l.volume]);

  if (jenis === 'audio') {
    return <audio ref={ref} src={url(l.aset)} preload="auto" hidden />;
  }
  const [fx, fy, fw, fh] = POSISI[l.posisi] ?? POSISI.penuh;
  const w = fw * boxW;
  const h = fh == null ? w * 9 / 16 : fh * boxH;
  const gaya = {
    position: 'absolute', left: `${fx * boxW}px`, top: `${fy * boxH}px`,
    width: `${w}px`, height: `${h}px`, pointerEvents: 'none', zIndex: 1,
    // Video memenuhi petaknya (dipotong), gambar dimuat utuh — sama dengan render.
    objectFit: jenis === 'gambar' ? 'contain' : 'cover',
    visibility: aktif ? 'visible' : 'hidden',
  };
  if (jenis === 'gambar') return <img src={url(l.aset)} alt="" style={gaya} />;
  return <video ref={ref} src={url(l.aset)} preload="auto" playsInline style={gaya} />;
}

export default function MediaOverlay({ layers, jenisById, clipTime, playing, boxW, boxH }) {
  if (!layers?.length || !boxW || !boxH) return null;
  return (
    <>
      {layers.map((l) => {
        // Jenisnya disimpan di sisipan itu sendiri saat ditambahkan.
        const jenis = l.jenis ?? jenisById?.[l.aset];
        if (!jenis) return null;
        return <Lapis key={l.id ?? `${l.aset}@${l.t}`} l={l} jenis={jenis}
                      clipTime={clipTime} playing={playing} boxW={boxW} boxH={boxH} />;
      })}
    </>
  );
}
