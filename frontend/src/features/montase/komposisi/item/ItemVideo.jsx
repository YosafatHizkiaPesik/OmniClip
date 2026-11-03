/**
 * Item video. `<Video>` dari `@remotion/media` dipakai karena itulah yang
 * dianjurkan Remotion untuk kode baru: tepat ke bingkai baik di Player maupun
 * di render (tag `<video>` HTML biasa tidak menjamin itu).
 *
 * Video digambar di kotak dasarnya (kotak.js), lalu transformasi dan potongan
 * diterapkan pada kotak itu. Item `beku` (bekukan bingkai, M2.6) menahan
 * bingkai pertamanya dengan `<Freeze>`; `@remotion/media` mengenali Freeze dan
 * membisukan suaranya sendiri, tapi `muted` tetap dipasang supaya jelas.
 */
import React from 'react';
import { AbsoluteFill, Freeze, useCurrentFrame } from 'remotion';
import { Video } from '@remotion/media';
import { kotakDasar } from '../kotak.js';
import { ubahPada } from '../keyframe.js';
import { gayaUbah, volumeItem } from '../ubah.js';

export function KotakItem({ dokumen, item, children }) {
  const frame = useCurrentFrame();
  const k = kotakDasar(dokumen, item);
  return (
    <AbsoluteFill>
      <div style={{
        position: 'absolute', left: k.x, top: k.y, width: k.w, height: k.h,
        ...gayaUbah(ubahPada(item, frame)),
      }}
      >
        {children}
      </div>
    </AbsoluteFill>
  );
}

export default function ItemVideo({ item, lajur, sumber, dokumen }) {
  const src = sumber?.bahan?.[item.bahan];
  if (!src) return null;
  const bisu = Boolean(lajur?.bisu) || Boolean(item.beku);
  const video = (
    <Video
      src={src}
      trimBefore={item.potong_awal || undefined}
      playbackRate={item.beku ? 1 : (item.kecepatan ?? 1)}
      preservePitch
      muted={bisu}
      volume={bisu ? 0 : volumeItem(item, lajur)}
      objectFit={item.isi ?? 'contain'}
      style={{ width: '100%', height: '100%' }}
    />
  );
  return (
    <KotakItem dokumen={dokumen} item={item}>
      {item.beku ? <Freeze frame={0}>{video}</Freeze> : video}
    </KotakItem>
  );
}
