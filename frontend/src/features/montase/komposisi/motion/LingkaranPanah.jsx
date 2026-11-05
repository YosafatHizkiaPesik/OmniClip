/** Lingkaran yang menggambar dirinya mengelilingi satu titik, lalu panah menunjuk. */
import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { z } from 'zod';
import { zColor } from '@remotion/zod-types';

export const skema = z.object({
  posisi: z.object({ x: z.number().min(0).max(100), y: z.number().min(0).max(100) }).describe('posisi'),
  jari: z.number().int().min(40).max(500),
  warna: zColor(),
  tebal: z.number().int().min(4).max(30),
});

export const contohProps = { posisi: { x: 50, y: 45 }, jari: 160, warna: '#FF2D2D', tebal: 12 };
export const durasiBawaan = 75;
export const kategori = 'penunjuk';

export default function LingkaranPanah({ posisi, jari, warna, tebal }) {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const cx = (posisi.x / 100) * width;
  const cy = (posisi.y / 100) * height;
  const keliling = 2 * Math.PI * jari;
  const gambar = interpolate(frame, [0, 22], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const panah = interpolate(frame, [20, 34], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const goyang = Math.sin(frame / 4) * 10 * panah;
  const ax = cx + jari * 0.9 + 160 - goyang;
  const ay = cy + jari * 0.9 + 160 - goyang;
  return (
    <AbsoluteFill>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        <circle cx={cx} cy={cy} r={jari} fill="none" stroke={warna} strokeWidth={tebal} strokeLinecap="round"
                strokeDasharray={keliling} strokeDashoffset={keliling * (1 - gambar)}
                transform={`rotate(-90 ${cx} ${cy})`} />
        <g opacity={panah} transform={`translate(${ax} ${ay}) rotate(-135)`}>
          <line x1={0} y1={0} x2={150 * panah} y2={0} stroke={warna} strokeWidth={tebal} strokeLinecap="round" />
          <polygon fill={warna} points={`${150 * panah + 30},0 ${150 * panah - 6},-26 ${150 * panah - 6},26`} />
        </g>
      </svg>
    </AbsoluteFill>
  );
}
