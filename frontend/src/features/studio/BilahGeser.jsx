import React, { useCallback, useEffect, useRef, useState } from 'react';

/**
 * Bilah geser mendatar yang digambar sendiri, untuk linimasa yang diperbesar.
 *
 * Bilah gulung bawaan di mesin pemiliknya BERSIFAT OVERLAY: ia tidak menempati
 * ruang, tebalnya tidak bisa diatur CSS, dan ia menghilang saat tidak disentuh.
 * Pada zoom 8x lebar linimasa 18.600 piksel di dalam jendela 1.238 piksel, jadi
 * pegangannya tinggal sekitar tujuh puluh piksel yang muncul-hilang. Terlapor
 * 30 September 2026: "saya harus menggeser geser scroll bar yang kecil itu",
 * lalu sekali lagi untuk linimasa Seluruh rekaman yang tidak punya bilah sama
 * sekali.
 *
 * Jadi bilahnya digambar sendiri: tingginya tetap, selalu terlihat selama isi
 * linimasa memang lebih lebar daripada jendelanya, dan pegangannya tidak pernah
 * lebih pendek dari `MIN_PX`. Pegangannya diseret, dan alurnya bisa diklik
 * untuk melompat ke sana.
 *
 * `bagi` adalah elemen yang digulung (`ref.current`), diberikan pemanggil.
 * `penanda` menyuruhnya membaca ulang ukuran saat sesuatu di luar berubah,
 * misalnya tingkat zoom.
 */

// Pegangan yang lebih pendek dari ini tidak bisa ditangkap dengan nyaman.
const MIN_PX = 56;

export default function BilahGeser({ bagi, penanda }) {
  const [ukur, setUkur] = useState({ kiri: 0, tampak: 1, penuh: 1 });
  const alurRef = useRef(null);

  const baca = useCallback(() => {
    const el = typeof bagi === 'function' ? bagi() : bagi?.current;
    if (!el) return;
    setUkur({ kiri: el.scrollLeft, tampak: el.clientWidth, penuh: el.scrollWidth });
  }, [bagi]);

  useEffect(() => {
    const el = typeof bagi === 'function' ? bagi() : bagi?.current;
    if (!el) return undefined;
    baca();
    el.addEventListener('scroll', baca, { passive: true });
    const ro = new ResizeObserver(baca);
    ro.observe(el);
    return () => { el.removeEventListener('scroll', baca); ro.disconnect(); };
  }, [baca, bagi, penanda]);

  const perlu = ukur.penuh > ukur.tampak + 1;
  const lebarPegangan = perlu
    ? Math.max(MIN_PX, (ukur.tampak / ukur.penuh) * ukur.tampak) : 0;
  const kiriPegangan = perlu
    ? (ukur.kiri / Math.max(1, ukur.penuh - ukur.tampak))
      * Math.max(0, ukur.tampak - lebarPegangan) : 0;

  const seret = useCallback((e) => {
    const alur = alurRef.current;
    const sc = typeof bagi === 'function' ? bagi() : bagi?.current;
    if (!alur || !sc) return;
    e.preventDefault();
    const kotak = alur.getBoundingClientRect();
    const jangkauan = Math.max(1, kotak.width - lebarPegangan);
    // Menyeret pegangan mempertahankan titik yang dipegang, supaya tidak
    // melompat saat ditekan. Mengklik alurnya menaruh TENGAH pegangan di situ.
    const pegang = e.target?.dataset?.pegangan === '1';
    const jarak = pegang ? e.clientX - (kotak.left + kiriPegangan) : lebarPegangan / 2;
    const ke = (x) => {
      const p = Math.min(1, Math.max(0, (x - kotak.left - jarak) / jangkauan));
      sc.scrollLeft = p * (sc.scrollWidth - sc.clientWidth);
    };
    ke(e.clientX);
    const gerak = (ev) => ke(ev.clientX);
    const lepas = () => {
      window.removeEventListener('pointermove', gerak);
      window.removeEventListener('pointerup', lepas);
    };
    window.addEventListener('pointermove', gerak);
    window.addEventListener('pointerup', lepas);
  }, [bagi, lebarPegangan, kiriPegangan]);

  if (!perlu) return null;
  return (
    <div
      className="tl-geser"
      ref={alurRef}
      onPointerDown={seret}
      title="Seret untuk menggeser linimasa. Roda tetikus dan seret tombol tengah juga bisa."
    >
      <div className="tl-geser-pegangan" data-pegangan="1"
           style={{ left: `${kiriPegangan}px`, width: `${lebarPegangan}px` }} />
    </div>
  );
}
