/**
 * Item video. `<Video>` dari `@remotion/media` dipakai karena itulah yang
 * dianjurkan Remotion untuk kode baru: tepat ke bingkai baik di Player maupun
 * di render (tag `<video>` HTML biasa tidak menjamin itu).
 */
import React from 'react';
import { AbsoluteFill } from 'remotion';
import { Video } from '@remotion/media';
import { gayaUbah } from '../ubah.js';

export default function ItemVideo({ item, lajur, sumber }) {
  const src = sumber?.bahan?.[item.bahan];
  if (!src) return null;
  const bisu = Boolean(lajur?.bisu);
  return (
    <AbsoluteFill style={gayaUbah(item.ubah)}>
      <Video
        src={src}
        trimBefore={item.potong_awal || undefined}
        playbackRate={item.kecepatan ?? 1}
        preservePitch
        muted={bisu}
        volume={bisu ? 0 : (item.volume ?? 1) * (lajur?.volume ?? 1)}
        objectFit={item.isi ?? 'contain'}
        style={{ width: '100%', height: '100%' }}
      />
    </AbsoluteFill>
  );
}
