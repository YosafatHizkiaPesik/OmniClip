/** Angka yang menghitung naik dari nol (statistik), dengan pemisah ribuan. */
import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { z } from 'zod';
import { zColor } from '@remotion/zod-types';

export const skema = z.object({
  angka: z.number().int().min(1).max(1000000000),
  label: z.string().max(40),
  warna: zColor(),
  pemisah: z.enum(['.', ',', ' ']),
});

export const contohProps = { angka: 1000000, label: 'penonton', warna: '#FFFFFF', pemisah: '.' };
export const durasiBawaan = 90;
export const kategori = 'statistik';

function bentuk(n, pemisah) {
  return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, pemisah);
}

export default function AngkaNaik({ angka, label, warna, pemisah }) {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const ujung = Math.max(10, durationInFrames - 20);
  const nilai = Math.round(interpolate(frame, [0, ujung], [0, angka], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic),
  }));
  const selesai = frame >= ujung;
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', fontFamily: 'sans-serif' }}>
      <div style={{
        fontWeight: 900, fontSize: 160, color: warna, fontVariantNumeric: 'tabular-nums',
        transform: `scale(${selesai ? 1.08 : 1})`, textShadow: '0 8px 30px rgba(0,0,0,0.6)',
      }}
      >
        {bentuk(nilai, pemisah)}
      </div>
      <div style={{ fontWeight: 700, fontSize: 64, color: warna, opacity: 0.9 }}>{label}</div>
    </AbsoluteFill>
  );
}
