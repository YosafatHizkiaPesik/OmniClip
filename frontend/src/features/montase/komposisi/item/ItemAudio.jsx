/** Item audio: narasi, musik, efek suara. Tidak menggambar apa pun. */
import React from 'react';
import { Audio } from '@remotion/media';

export default function ItemAudio({ item, lajur, sumber }) {
  const src = sumber?.bahan?.[item.bahan];
  if (!src || lajur?.bisu) return null;
  return (
    <Audio
      src={src}
      trimBefore={item.potong_awal || undefined}
      playbackRate={item.kecepatan ?? 1}
      preservePitch
      volume={(item.volume ?? 1) * (lajur?.volume ?? 1)}
    />
  );
}
