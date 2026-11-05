/**
 * Judul kinetik: kata muncul satu per satu, memantul masuk (spring). Untuk
 * pembuka dan kalimat kunci.
 */
import React from 'react';
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { z } from 'zod';
import { zColor } from '@remotion/zod-types';

export const skema = z.object({
  teks: z.string().max(80),
  warna: zColor(),
  sorot: zColor(),
  ukuran: z.number().int().min(40).max(220),
  jeda: z.number().int().min(2).max(20),
});

export const contohProps = { teks: 'Ini momen paling gila', warna: '#FFFFFF', sorot: '#FFD400', ukuran: 120, jeda: 6 };
export const durasiBawaan = 90;
export const kategori = 'judul';

export default function JudulKinetik({ teks, warna, sorot, ukuran, jeda }) {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const kata = teks.split(/\s+/).filter(Boolean);
  const keluar = interpolate(frame, [durationInFrames - 8, durationInFrames], [1, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center', padding: 80, opacity: keluar }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: `0 ${ukuran * 0.28}px` }}>
        {kata.map((k, i) => {
          const s = spring({ frame: frame - i * jeda, fps, config: { damping: 10, stiffness: 160 } });
          const terakhir = i === kata.length - 1;
          return (
            <span key={i} style={{
              display: 'inline-block', fontFamily: 'sans-serif', fontWeight: 900, fontSize: ukuran,
              lineHeight: 1.1, color: terakhir ? sorot : warna, opacity: Math.min(1, s * 1.5),
              transform: `translateY(${(1 - s) * 60}px) scale(${0.6 + 0.4 * s})`,
              textShadow: '0 6px 24px rgba(0,0,0,0.55)',
            }}
            >
              {k}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
}
