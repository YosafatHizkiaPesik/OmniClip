/** Label nama (lower third): nama dan peran penutur, masuk dari kiri. */
import React from 'react';
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { z } from 'zod';
import { zColor } from '@remotion/zod-types';

export const skema = z.object({
  nama: z.string().max(40),
  peran: z.string().max(60),
  warna: zColor(),
  bawah: z.number().int().min(0).max(60),
});

export const contohProps = { nama: 'Dr. Tirta', peran: 'Dokter', warna: '#E11D2E', bawah: 26 };
export const durasiBawaan = 120;
export const kategori = 'label';

export default function LabelNama({ nama, peran, warna, bawah }) {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const masuk = spring({ frame, fps, config: { damping: 14 } });
  const keluar = interpolate(frame, [durationInFrames - 10, durationInFrames], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const geser = (1 - masuk + keluar) * -110;
  return (
    <AbsoluteFill style={{ justifyContent: 'flex-end', paddingBottom: `${bawah}%`, paddingLeft: 60 }}>
      <div style={{ transform: `translateX(${geser}%)`, display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
        <div style={{
          background: warna, color: '#fff', fontFamily: 'sans-serif', fontWeight: 900, fontSize: 64,
          padding: '14px 28px', borderRadius: 10,
        }}
        >
          {nama}
        </div>
        <div style={{
          background: 'rgba(10,10,14,0.88)', color: '#fff', fontFamily: 'sans-serif', fontWeight: 600,
          fontSize: 40, padding: '10px 24px', borderRadius: 8, marginTop: 8,
          opacity: interpolate(frame, [8, 18], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }),
        }}
        >
          {peran}
        </div>
      </div>
    </AbsoluteFill>
  );
}
