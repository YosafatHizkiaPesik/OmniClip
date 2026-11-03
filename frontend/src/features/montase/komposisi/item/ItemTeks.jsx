/**
 * Item teks bergaya (JOB-4 M3.1).
 *
 * Semua rupa dibaca dari `item.gaya` apa adanya: font bawaan, ukuran, warna,
 * huruf kapital, perataan, latar (tanpa, pelat, sorot per baris, pita selebar
 * layar, label dengan cip), garis tepi, bayangan, cahaya, dan gerak masuk.
 * Tema siap pakai (kartu putih, pita hitam, stabilo, ...) berasal dari
 * `services/tema_judul.py` lewat /api/montase/gaya-teks dan DITULIS ke
 * `gaya` saat dipilih, jadi komposisi tidak menyimpan salinan tema dan proyek
 * lama tidak berubah bila tema diperbarui.
 *
 * Gerak meniru tag ASS di `tema_judul.GERAK` (lama dalam milidetik, sama
 * dengan kartu judul Studio Klip) supaya tema yang sama terasa sama di kedua
 * tempat.
 *
 * Transformasi item (`ubah`) dipasang di kotak teksnya sendiri, titik
 * pusatnya pusat teks, bukan di seluruh kanvas; lihat kotak.js untuk
 * perkiraan kotaknya.
 */
import React from 'react';
import {
  AbsoluteFill, Easing, interpolate, useCurrentFrame, useVideoConfig,
} from 'remotion';
import { useFont } from '../font.js';
import { TEPI_TEKS, tinggiBaris } from '../kotak.js';
import { ubahPada } from '../keyframe.js';
import { gayaUbah } from '../ubah.js';

const JEPIT = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' };
const KELUAR = Easing.out(Easing.cubic);

/** Lama memudar masuk/keluar (ms), sama dengan \fad di tema_judul.GERAK. */
const PUDAR = {
  muncul: [220, 260], pop: [160, 260], hentak: [100, 260], naik: [240, 280],
  turun: [200, 280], geser: [160, 280], lempar: [140, 260], getar: [200, 300],
  kedip: [0, 260], pelan: [700, 500],
};

/** Opasitas dan transformasi gerak pada `ms` sejak mulai, `sisa` ms sebelum akhir. */
export function gerakTeks(jenis, ms, sisa, ukuran) {
  const [masuk, keluar] = PUDAR[jenis] ?? PUDAR.muncul;
  let opasitas = 1;
  if (masuk > 0) opasitas = Math.min(opasitas, interpolate(ms, [0, masuk], [0, 1], JEPIT));
  if (keluar > 0) opasitas = Math.min(opasitas, interpolate(sisa, [0, keluar], [0, 1], JEPIT));
  const t = [];
  if (jenis === 'pop') {
    t.push(`scale(${interpolate(ms, [0, 160, 280], [0.88, 1.04, 1], JEPIT)})`);
  } else if (jenis === 'hentak') {
    t.push(`scale(${interpolate(ms, [0, 130, 250], [0.7, 1.1, 1], JEPIT)})`);
  } else if (jenis === 'naik' || jenis === 'turun') {
    const dari = (jenis === 'naik' ? 0.9 : -0.9) * ukuran;
    t.push(`translateY(${interpolate(ms, [0, 280], [dari, 0], { ...JEPIT, easing: KELUAR })}px)`);
  } else if (jenis === 'geser') {
    t.push(`translateX(${interpolate(ms, [0, 280], [-2.4 * ukuran, 0], { ...JEPIT, easing: KELUAR })}px)`);
  } else if (jenis === 'lempar') {
    t.push(`rotate(${interpolate(ms, [0, 280], [9, 0], JEPIT)}deg)`);
    t.push(`scale(${interpolate(ms, [0, 280], [0.84, 1], JEPIT)})`);
  } else if (jenis === 'getar') {
    t.push(`rotate(${interpolate(ms, [0, 160, 320, 480, 640], [1.4, -1.4, 1.4, -1.2, 0], JEPIT)}deg)`);
  } else if (jenis === 'kedip') {
    opasitas = Math.min(opasitas, interpolate(ms, [0, 60, 120, 200, 260, 340], [0, 1, 0.44, 1, 0.62, 1], JEPIT));
  }
  return { opasitas, transform: t.join(' ') };
}

/** #RRGGBB + alfa -> rgba(). */
export function rgba(hex, alfa = 1) {
  const m = /^#?([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex ?? '');
  if (!m) return hex ?? 'transparent';
  const [r, g, b] = m.slice(1).map((x) => parseInt(x, 16));
  return `rgba(${r}, ${g}, ${b}, ${alfa})`;
}

/** Bayangan, cahaya, dan (untuk item lama tanpa gaya) bayangan lembut bawaan. */
function bayanganTeks(g) {
  const lapis = [];
  if (g.bayang > 0) lapis.push(`${g.bayang}px ${g.bayang}px 0 rgba(0, 0, 0, 0.6)`);
  if (g.kabur > 0) {
    const w = g.warna_garis ?? '#ffffff';
    lapis.push(`0 0 ${g.kabur * 2}px ${w}`, `0 0 ${g.kabur * 5}px ${w}`);
  }
  if (!lapis.length && g.bayang === undefined) lapis.push('0 4px 18px rgba(0, 0, 0, 0.65)');
  return lapis.length ? lapis.join(', ') : undefined;
}

const RATA = { kiri: 'flex-start', tengah: 'center', kanan: 'flex-end' };
const RATA_TEKS = { kiri: 'left', tengah: 'center', kanan: 'right' };

export default function ItemTeks({ item, sumber }) {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const g = item.gaya ?? {};
  const font = g.font && sumber?.font?.[g.font] ? g.font : null;
  useFont(font, font ? sumber.font[font] : null);

  const ukuran = g.ukuran ?? 96;
  const latar = g.latar ?? 'tanpa';
  const rata = g.perataan ?? 'tengah';
  const pad = `${(g.pad_y ?? 0.22) * ukuran}px ${(g.pad_x ?? 0.42) * ukuran}px`;
  const radius = (g.radius ?? 0.22) * ukuran;
  const warnaLatar = rgba(g.warna_latar ?? '#000000', g.alfa_latar ?? 1);
  const gerak = gerakTeks(g.gerak ?? 'muncul', (frame / fps) * 1000, ((item.durasi - frame) / fps) * 1000, ukuran);
  const { opacity: opasitasUbah, transform: transformUbah, clipPath } = gayaUbah(ubahPada(item, frame)) ?? {};

  const huruf = {
    fontFamily: font ? `"${font}", sans-serif` : 'sans-serif',
    // Font bawaan hanya punya satu ketebalan, didaftarkan sebagai 400
    // (lihat font.js); meminta lebih tebal membuat peramban memalsukannya.
    fontWeight: font ? 400 : 800,
    fontSize: ukuran,
    color: g.warna ?? '#ffffff',
    textTransform: g.kapital ? 'uppercase' : undefined,
    textAlign: RATA_TEKS[rata] ?? 'center',
    lineHeight: tinggiBaris(latar),
    whiteSpace: 'pre-wrap',
    overflowWrap: 'anywhere',
    textShadow: bayanganTeks(g),
  };
  if (g.garis > 0) {
    // Garis tengah: separuhnya tertutup isi huruf karena paint-order, jadi
    // yang terlihat di luar huruf setebal `garis`, sama dengan \bord ASS.
    huruf.WebkitTextStroke = `${g.garis * 2}px ${g.warna_garis ?? '#000000'}`;
    huruf.paintOrder = 'stroke fill';
  }

  const blok = {
    position: 'relative',
    maxWidth: '100%',
    transform: [transformUbah, gerak.transform].filter(Boolean).join(' ') || undefined,
    opacity: gerak.opasitas * (opasitasUbah ?? 1),
    clipPath,
  };
  if (latar === 'pelat' || latar === 'label') {
    Object.assign(blok, { background: warnaLatar, padding: pad, borderRadius: radius });
  } else if (latar === 'pita') {
    Object.assign(blok, {
      alignSelf: 'stretch', maxWidth: 'none', background: warnaLatar,
      margin: `0 -${TEPI_TEKS.datar}px`, padding: `${(g.pad_y ?? 0.3) * ukuran}px ${TEPI_TEKS.datar}px`,
    });
  }

  let isi = item.teks;
  // Subtitle otomatis (M3.2): kata yang sedang diucapkan disorot. Hanya bila
  // jumlah kata teks masih sama dengan jumlah kata berwaktu; teks yang sudah
  // disunting jauh tetap tampil, tanpa sorotan yang salah tempat.
  const kataTeks = String(item.teks ?? '').split(/\s+/).filter(Boolean);
  if (g.warna_sorot && Array.isArray(item.kata) && item.kata.length === kataTeks.length && kataTeks.length) {
    isi = kataTeks.map((w, i) => {
      const k = item.kata[i];
      const aktif = frame >= k.t && frame < k.t + k.d;
      return (
        <React.Fragment key={i}>
          {i > 0 ? ' ' : null}
          <span style={aktif ? { color: g.warna_sorot } : undefined}>{w}</span>
        </React.Fragment>
      );
    });
  }
  if (latar === 'sorot') {
    isi = (
      <span style={{
        background: warnaLatar, padding: pad, borderRadius: radius,
        boxDecorationBreak: 'clone', WebkitBoxDecorationBreak: 'clone',
      }}
      >
        {isi}
      </span>
    );
  }

  return (
    <AbsoluteFill
      style={{
        justifyContent: g.letak === 'atas' ? 'flex-start' : g.letak === 'bawah' ? 'flex-end' : 'center',
        alignItems: RATA[rata] ?? 'center',
        padding: `${TEPI_TEKS.tegak}px ${TEPI_TEKS.datar}px`,
      }}
    >
      <div style={blok}>
        {latar === 'label' && g.cip && (
          <div style={{
            position: 'absolute', left: (g.pad_x ?? 0.42) * ukuran, top: -0.36 * ukuran,
            background: g.warna_cip ?? '#E11D2E', color: g.teks_cip ?? '#FFFFFF',
            fontFamily: huruf.fontFamily, fontWeight: huruf.fontWeight, fontSize: 0.42 * ukuran,
            lineHeight: 1, padding: `${0.12 * ukuran}px ${0.24 * ukuran}px`, borderRadius: 0.1 * ukuran,
            textTransform: 'uppercase',
          }}
          >
            {g.cip}
          </div>
        )}
        <div style={huruf}>{isi}</div>
      </div>
    </AbsoluteFill>
  );
}
