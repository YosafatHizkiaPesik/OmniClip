/**
 * Item gambar diam. `<Img>` dari Remotion menahan render sampai gambarnya
 * termuat, jadi bingkai pertama tidak pernah kosong.
 */
import React from 'react';
import { Img } from 'remotion';
import { KotakItem } from './ItemVideo.jsx';

export default function ItemGambar({ item, sumber, dokumen }) {
  const src = sumber?.bahan?.[item.bahan];
  if (!src) return null;
  return (
    <KotakItem dokumen={dokumen} item={item}>
      <Img src={src} style={{ width: '100%', height: '100%', objectFit: item.isi ?? 'contain' }} />
    </KotakItem>
  );
}
