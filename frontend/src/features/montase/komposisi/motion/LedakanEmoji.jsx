/**
 * Ledakan emoji di sekitar satu titik (saat tawa). Arah dan kecepatan tiap
 * emoji dari `random(seed)` Remotion: sama di pratinjau dan render.
 */
import React from 'react';
import { AbsoluteFill, interpolate, random, useCurrentFrame } from 'remotion';
import { z } from 'zod';

export const skema = z.object({
  emoji: z.string().max(8),
  jumlah: z.number().int().min(4).max(40),
  posisi: z.object({ x: z.number().min(0).max(100), y: z.number().min(0).max(100) }).describe('posisi'),
  ukuran: z.number().int().min(40).max(200),
});

export const contohProps = { emoji: '😂', jumlah: 16, posisi: { x: 50, y: 55 }, ukuran: 110 };
export const durasiBawaan = 45;
export const kategori = 'reaksi';

export default function LedakanEmoji({ emoji, jumlah, posisi, ukuran }) {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill>
      {Array.from({ length: jumlah }, (_, i) => {
        const sudut = random(`sudut-${i}`) * Math.PI * 2;
        const laju = 14 + random(`laju-${i}`) * 22;
        const t = frame;
        const x = Math.cos(sudut) * laju * t;
        const y = Math.sin(sudut) * laju * t + 0.9 * t * t;
        const putar = (random(`putar-${i}`) - 0.5) * 40 * t;
        const opasitas = interpolate(t, [0, 3, 30, 45], [0, 1, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
        return (
          <div key={i} style={{
            position: 'absolute', left: `${posisi.x}%`, top: `${posisi.y}%`, fontSize: ukuran * (0.7 + random(`b-${i}`) * 0.6),
            transform: `translate(-50%, -50%) translate(${x}px, ${y}px) rotate(${putar}deg)`, opacity: opasitas,
          }}
          >
            {emoji}
          </div>
        );
      })}
    </AbsoluteFill>
  );
}
