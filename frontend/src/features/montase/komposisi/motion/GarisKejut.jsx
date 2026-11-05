/** Garis kejut gaya manga: garis tajam dari tepi menuju tengah, untuk kaget. */
import React from 'react';
import { AbsoluteFill, interpolate, random, useCurrentFrame, useVideoConfig } from 'remotion';
import { z } from 'zod';
import { zColor } from '@remotion/zod-types';

export const skema = z.object({
  warna: zColor(),
  jumlah: z.number().int().min(12).max(120),
  lubang: z.number().min(0.1).max(0.8),
});

export const contohProps = { warna: '#FFFFFF', jumlah: 64, lubang: 0.32 };
export const durasiBawaan = 30;
export const kategori = 'reaksi';

export default function GarisKejut({ warna, jumlah, lubang }) {
  const frame = useCurrentFrame();
  const { width, height, durationInFrames } = useVideoConfig();
  const cx = width / 2;
  const cy = height / 2;
  const r = Math.hypot(cx, cy);
  const opasitas = interpolate(frame, [0, 3, durationInFrames - 6, durationInFrames], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const denyut = 1 + 0.06 * Math.sin(frame * 1.7);
  return (
    <AbsoluteFill style={{ opacity: opasitas }}>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        {Array.from({ length: jumlah }, (_, i) => {
          const a = (i / jumlah) * Math.PI * 2 + random(`a-${i}`) * 0.08;
          const lebar = 0.012 + random(`l-${i}-${Math.floor(frame / 2)}`) * 0.02;
          const dalam = r * lubang * denyut * (0.85 + random(`d-${i}-${Math.floor(frame / 2)}`) * 0.3);
          const p = (sudut, jarak) => `${cx + Math.cos(sudut) * jarak},${cy + Math.sin(sudut) * jarak}`;
          return <polygon key={i} fill={warna} points={`${p(a - lebar, r * 1.1)} ${p(a + lebar, r * 1.1)} ${p(a, dalam)}`} />;
        })}
      </svg>
    </AbsoluteFill>
  );
}
