/** Kartu ajakan berlangganan; kursor datang dan menekan tombolnya. */
import React from 'react';
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { z } from 'zod';
import { zColor } from '@remotion/zod-types';

export const skema = z.object({
  kanal: z.string().max(40),
  tombol: z.string().max(20),
  sudah: z.string().max(20),
  warna: zColor(),
});

export const contohProps = { kanal: 'OmniClip', tombol: 'SUBSCRIBE', sudah: 'SUBSCRIBED', warna: '#E11D2E' };
export const durasiBawaan = 90;
export const kategori = 'ajakan';

export default function AjakanLangganan({ kanal, tombol, sudah, warna }) {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const masuk = spring({ frame, fps, config: { damping: 12 } });
  const keluar = interpolate(frame, [durationInFrames - 10, durationInFrames], [1, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const kursorX = interpolate(frame, [12, 38], [520, 150], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const kursorY = interpolate(frame, [12, 38], [260, 40], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const tekan = frame >= 40 && frame < 46 ? 0.92 : 1;
  const ditekan = frame >= 43;
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'flex-end', paddingBottom: '24%', opacity: keluar }}>
      <div style={{
        position: 'relative', display: 'flex', alignItems: 'center', gap: 24, padding: '22px 26px', borderRadius: 22,
        background: 'rgba(255,255,255,0.96)', boxShadow: '0 18px 60px rgba(0,0,0,0.45)',
        transform: `translateY(${(1 - masuk) * 300}px)`, fontFamily: 'sans-serif',
      }}
      >
        <div style={{ width: 84, height: 84, borderRadius: '50%', background: warna, color: '#fff', display: 'flex',
          alignItems: 'center', justifyContent: 'center', fontWeight: 900, fontSize: 44 }}
        >
          {kanal.slice(0, 1)}
        </div>
        <div style={{ fontWeight: 800, fontSize: 44, color: '#111' }}>{kanal}</div>
        <div style={{
          marginLeft: 12, padding: '18px 30px', borderRadius: 999, fontWeight: 900, fontSize: 36,
          background: ditekan ? '#D9D9D9' : warna, color: ditekan ? '#333' : '#fff', transform: `scale(${tekan})`,
        }}
        >
          {ditekan ? sudah : tombol}
        </div>
        <svg width="70" height="70" viewBox="0 0 24 24" style={{ position: 'absolute', left: kursorX + 300, top: kursorY, opacity: frame > 10 ? 1 : 0 }}>
          <path d="M4 2 L4 20 L9 15 L12 22 L15 21 L12 14 L19 14 Z" fill="#fff" stroke="#000" strokeWidth="1.4" />
        </svg>
      </div>
    </AbsoluteFill>
  );
}
