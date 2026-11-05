/**
 * Item animasi: komponen dari pustaka bawaan, atau komponen buatan AI yang
 * sudah dikompilasi Mesin Montase dan dimuat lewat `muatKomponen.js`.
 *
 * Props item divalidasi dengan skema komponennya. Props yang tidak sah TIDAK
 * diam-diam diganti contoh: kotak merah berisi galatnya digambar, karena
 * animasi yang tiba-tiba berbeda dari yang disetel lebih sulit ditemukan
 * daripada yang jelas-jelas rusak (prinsip P-3).
 */
import React from 'react';
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { BAWAAN } from '../motion/index.js';
import { useKomponen } from '../muatKomponen.js';
import { useFontBanyak } from '../font.js';
import { ubahPada } from '../keyframe.js';
import { gayaUbah } from '../ubah.js';

function KotakGalat({ pesan }) {
  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      <div style={{
        background: 'rgba(200,0,0,0.85)', color: '#fff', fontFamily: 'monospace',
        fontSize: 32, padding: 24, maxWidth: '80%', whiteSpace: 'pre-wrap',
      }}
      >
        {pesan}
      </div>
    </AbsoluteFill>
  );
}

/** Animasi menempati seluruh kanvas; transformasinya berpusat di tengah kanvas. */
function Lapisan({ item, children }) {
  const frame = useCurrentFrame();
  const ubah = ubahPada(item, frame);
  if (!ubah) return children;
  return <AbsoluteFill style={gayaUbah(ubah)}>{children}</AbsoluteFill>;
}

export default function ItemMotion({ item, sumber }) {
  const bawaan = BAWAAN[item.komponen];
  const kunci = `${item.komponen}@${item.versi ?? 1}`;
  const url = bawaan ? null : sumber?.komponen?.[kunci] ?? null;
  const dimuat = useKomponen(url);
  // Animasi AI boleh memakai font bawaan mana pun (kontrak bagian 21).
  useFontBanyak(bawaan ? null : sumber?.font);
  const modul = bawaan ?? dimuat;
  if (!modul) {
    return url ? null : <KotakGalat pesan={`Komponen tidak dikenal: ${kunci}`} />;
  }
  const Komponen = modul.default;
  if (typeof Komponen !== 'function') {
    return <KotakGalat pesan={`${kunci} tidak mengekspor komponen bawaan`} />;
  }
  const props = { ...modul.contohProps, ...item.props };
  if (modul.skema?.safeParse) {
    const hasil = modul.skema.safeParse(props);
    if (!hasil.success) {
      const pesan = hasil.error.issues.map((i) => `${i.path.join('.')}: ${i.message}`).join('\n');
      // Pemeriksaan mesin (periksa.mjs) butuh kegagalan yang terbaca, bukan
      // kotak merah yang tetap "bergerak" di bingkai contoh.
      if (item.periksa) throw new Error(`Props tidak sesuai skema:\n${pesan}`);
      return <KotakGalat pesan={`${kunci}\n${pesan}`} />;
    }
    return <Lapisan item={item}><Komponen {...hasil.data} /></Lapisan>;
  }
  return <Lapisan item={item}><Komponen {...props} /></Lapisan>;
}
