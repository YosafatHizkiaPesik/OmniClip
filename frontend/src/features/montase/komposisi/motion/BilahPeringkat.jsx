/** Bilah peringkat: segmen di atas layar, segmen yang aktif menyala. */
import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { z } from 'zod';
import { zColor } from '@remotion/zod-types';

export const skema = z.object({
  jumlah: z.number().int().min(2).max(10),
  aktif: z.number().int().min(1).max(10),
  warna: zColor(),
  atas: z.number().int().min(0).max(40),
});

export const contohProps = { jumlah: 5, aktif: 3, warna: '#FFD400', atas: 7 };
export const durasiBawaan = 150;
export const kategori = 'peringkat';

export default function BilahPeringkat({ jumlah, aktif, warna, atas }) {
  const frame = useCurrentFrame();
  const nyala = interpolate(frame, [0, 10], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const denyut = 0.75 + 0.25 * Math.sin(frame / 5);
  return (
    <AbsoluteFill style={{ paddingTop: `${atas}%`, paddingLeft: 60, paddingRight: 60 }}>
      <div style={{ display: 'flex', gap: 14 }}>
        {Array.from({ length: jumlah }, (_, i) => {
          const no = jumlah - i;
          const ini = no === aktif;
          const lewat = no > aktif;
          return (
            <div key={i} style={{
              flex: 1, height: 70, borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: 'sans-serif', fontWeight: 900, fontSize: 40,
              background: ini ? warna : lewat ? 'rgba(255,255,255,0.55)' : 'rgba(0,0,0,0.55)',
              color: ini ? '#111' : '#fff', opacity: ini ? 1 : 0.85,
              boxShadow: ini ? `0 0 ${36 * denyut * nyala}px ${warna}` : 'none',
              transform: `scale(${ini ? 1 + 0.08 * nyala : 1})`,
            }}
            >
              #{no}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
}
