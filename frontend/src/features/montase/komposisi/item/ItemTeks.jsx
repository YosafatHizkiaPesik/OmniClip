/**
 * Item teks sederhana: muncul dan hilang dengan lembut.
 *
 * Gaya lengkap (font bawaan, pelat latar, tema dari tema_judul.py) datang di
 * M3.1. Sampai saat itu huruf memakai `sans-serif` peramban, yang bisa sedikit
 * berbeda antara komputer pratinjau dan mesin render; itu sengaja dibiarkan
 * di Tahap 0 karena yang diuji di sini jalurnya, bukan rupanya.
 */
import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { gayaUbah } from '../ubah.js';

export default function ItemTeks({ item }) {
  const frame = useCurrentFrame();
  const d = item.durasi;
  const lembut = Math.min(8, Math.floor(d / 4));
  const opacity = lembut >= 1
    ? interpolate(frame, [0, lembut, d - lembut, d], [0, 1, 1, 0],
      { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
    : 1;
  const g = item.gaya ?? {};
  return (
    <AbsoluteFill
      style={{
        justifyContent: g.letak === 'atas' ? 'flex-start' : g.letak === 'bawah' ? 'flex-end' : 'center',
        alignItems: 'center',
        padding: '160px 60px',
        ...gayaUbah(item.ubah),
      }}
    >
      <div
        style={{
          opacity,
          fontFamily: g.font ?? 'sans-serif',
          fontSize: g.ukuran ?? 96,
          fontWeight: 800,
          color: g.warna ?? '#ffffff',
          textAlign: 'center',
          lineHeight: 1.1,
          textShadow: '0 4px 18px rgba(0,0,0,0.65)',
        }}
      >
        {item.teks}
      </div>
    </AbsoluteFill>
  );
}
