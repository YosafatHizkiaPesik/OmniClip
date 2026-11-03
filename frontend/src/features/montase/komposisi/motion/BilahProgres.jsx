/**
 * Animasi bawaan: bilah progres (JOB-4 M3.8). Mengisi dari kiri ke kanan
 * sepanjang item ini, jadi item yang dibentang sepanjang video menunjukkan
 * berapa jauh penonton sudah menonton. Ditulis mengikuti kontrak komponen
 * (bagian 21), sama dengan animasi buatan AI.
 */
import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { z } from 'zod';

export const skema = z.object({
  warna: z.string().regex(/^#[0-9a-fA-F]{6}$/),
  latar: z.string().regex(/^#[0-9a-fA-F]{6}$/),
  tebal: z.number().int().min(4).max(80),
  letak: z.enum(['atas', 'bawah']),
});

export const contohProps = { warna: '#FF3355', latar: '#000000', tebal: 14, letak: 'bawah' };
export const durasiBawaan = 300;
export const kategori = 'informasi';

export default function BilahProgres({ warna, latar, tebal, letak }) {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const isi = interpolate(frame, [0, Math.max(1, durationInFrames - 1)], [0, 100], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  return (
    <AbsoluteFill style={{ justifyContent: letak === 'atas' ? 'flex-start' : 'flex-end' }}>
      <div style={{ height: tebal, width: '100%', background: `${latar}88` }}>
        <div style={{ height: '100%', width: `${isi}%`, background: warna, boxShadow: `0 0 ${tebal}px ${warna}` }} />
      </div>
    </AbsoluteFill>
  );
}
