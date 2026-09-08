import React, { useEffect, useRef } from 'react';

/**
 * Gelombang suara video sumber.
 *
 * Kanvas berukuran VIEWPORT, bukan seluruh panjang timeline. Pada zoom 20x
 * sebuah podcast 75 menit akan berarti kanvas puluhan ribu piksel — melewati
 * batas ukuran kanvas browser (~32767 px) dan memakan puluhan MB. Jadi kanvas
 * tetap selebar layar dan digambar ulang mengikuti jendela tampilan.
 *
 * Ini juga alasan waveform memakai <canvas> sementara klip memakai DOM: bar-nya
 * ribuan, sedangkan klip hanya belasan dan butuh hit-testing serta fokus papan
 * ketik.
 */
export default function WaveformCanvas({ peaks, duration, viewStart, viewEnd, height = 54 }) {
  const ref = useRef(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    const width = canvas.clientWidth;
    if (!width) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(width * dpr);
    canvas.height = Math.round(height * dpr);
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, height);

    if (!peaks?.length || !duration) return;

    const span = Math.max(0.001, viewEnd - viewStart);
    const mid = height / 2;
    const styles = getComputedStyle(document.documentElement);
    ctx.fillStyle = (styles.getPropertyValue('--accent-cyan') || '#00f2fe').trim();
    ctx.globalAlpha = 0.55;

    // Satu bar per piksel: lebih rapat dari itu tidak menambah informasi apa pun
    // yang bisa dilihat mata.
    for (let px = 0; px < width; px += 1) {
      const t = viewStart + (px / width) * span;
      const idx = Math.floor((t / duration) * peaks.length);
      if (idx < 0 || idx >= peaks.length) continue;
      const amp = (peaks[idx] / 255) * mid;
      ctx.fillRect(px, mid - amp, 1, Math.max(1, amp * 2));
    }
    ctx.globalAlpha = 1;
  }, [peaks, duration, viewStart, viewEnd, height]);

  return <canvas ref={ref} style={{ width: '100%', height: `${height}px`, display: 'block' }} />;
}
