/** Transisi kilat: cahaya putih dengan guncangan, dipasang di atas sambungan. */
import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from 'remotion';
import { z } from 'zod';
import { zColor } from '@remotion/zod-types';

export const skema = z.object({
  warna: zColor(),
  guncang: z.number().int().min(0).max(80),
});

export const contohProps = { warna: '#FFFFFF', guncang: 30 };
export const durasiBawaan = 14;
export const kategori = 'transisi';

export default function TransisiKilat({ warna, guncang }) {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const tengah = durationInFrames / 2;
  const cahaya = interpolate(frame, [0, tengah, durationInFrames], [0, 1, 0], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const x = Math.sin(frame * 2.3) * guncang * cahaya;
  const y = Math.cos(frame * 3.1) * guncang * cahaya;
  return (
    <AbsoluteFill style={{ transform: `translate(${x}px, ${y}px)` }}>
      <AbsoluteFill style={{ background: warna, opacity: cahaya }} />
    </AbsoluteFill>
  );
}
