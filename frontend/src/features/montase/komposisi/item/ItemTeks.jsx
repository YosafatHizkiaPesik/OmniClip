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
import { TEPI_TEKS, TINGGI_BARIS } from '../kotak.js';
import { gayaUbah } from '../ubah.js';

export default function ItemTeks({ item }) {
  const frame = useCurrentFrame();
  const d = item.durasi;
  const lembut = Math.min(8, Math.floor(d / 4));
  const muncul = lembut >= 1
    ? interpolate(frame, [0, lembut, d - lembut, d], [0, 1, 1, 0],
      { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
    : 1;
  const g = item.gaya ?? {};
  // Transformasi dipasang di kotak teksnya sendiri (titik pusatnya = pusat
  // teks), bukan di seluruh kanvas, supaya memperbesar teks di atas tidak
  // ikut menggesernya ke tengah. Lihat kotak.js untuk perkiraan kotaknya.
  const { opacity: opasitas, ...ubah } = gayaUbah(item.ubah) ?? {};
  return (
    <AbsoluteFill
      style={{
        justifyContent: g.letak === 'atas' ? 'flex-start' : g.letak === 'bawah' ? 'flex-end' : 'center',
        alignItems: 'center',
        padding: `${TEPI_TEKS.tegak}px ${TEPI_TEKS.datar}px`,
      }}
    >
      <div
        style={{
          ...ubah,
          opacity: muncul * (opasitas ?? 1),
          fontFamily: g.font ?? 'sans-serif',
          fontSize: g.ukuran ?? 96,
          fontWeight: 800,
          color: g.warna ?? '#ffffff',
          textAlign: 'center',
          lineHeight: TINGGI_BARIS,
          whiteSpace: 'pre-wrap',
          textShadow: '0 4px 18px rgba(0,0,0,0.65)',
        }}
      >
        {item.teks}
      </div>
    </AbsoluteFill>
  );
}
