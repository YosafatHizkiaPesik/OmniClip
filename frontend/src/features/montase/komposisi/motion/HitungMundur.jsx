/**
 * Animasi bawaan: hitung mundur peringkat ("#5 … #1") untuk konten Top N.
 *
 * Ditulis mengikuti kontrak komponen (JOB-4.md bagian 21) persis seperti yang
 * diminta dari AI: `skema`, `contohProps`, `durasiBawaan`, `kategori`, dan
 * komponen sebagai ekspor bawaan, dengan gerak yang hanya berasal dari
 * `useCurrentFrame()`. Gunanya dua: siap dipakai, dan menjadi contoh bagi AI.
 */
import React from 'react';
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { z } from 'zod';

export const skema = z.object({
  angka: z.number().int().min(1).max(99),
  judul: z.string().max(60),
  warna: z.string().regex(/^#[0-9a-fA-F]{6}$/),
});

export const contohProps = { angka: 5, judul: 'Momen paling kacau', warna: '#FF3355' };
export const durasiBawaan = 60;
export const kategori = 'peringkat';

export default function HitungMundur({ angka, judul, warna }) {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const masuk = spring({ frame, fps, config: { damping: 11, stiffness: 140 } });
  const keluar = interpolate(frame, [durationInFrames - 10, durationInFrames], [1, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const judulMasuk = interpolate(frame, [8, 20], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', opacity: keluar }}>
      <div
        style={{
          fontFamily: 'sans-serif', fontWeight: 900, fontSize: 360, lineHeight: 1,
          color: warna, transform: `scale(${0.4 + 0.6 * masuk}) rotate(${(1 - masuk) * -12}deg)`,
          textShadow: `0 0 40px ${warna}, 0 12px 0 rgba(0,0,0,0.5)`,
        }}
      >
        #{angka}
      </div>
      <div
        style={{
          marginTop: 40, fontFamily: 'sans-serif', fontWeight: 800, fontSize: 72,
          color: '#ffffff', opacity: judulMasuk, transform: `translateY(${(1 - judulMasuk) * 40}px)`,
          textAlign: 'center', padding: '0 80px', textShadow: '0 4px 18px rgba(0,0,0,0.7)',
        }}
      >
        {judul}
      </div>
    </AbsoluteFill>
  );
}
