import { clampRect, MIN_PCT } from './frames';

/**
 * Menyeret dan mengubah ukuran satu persegi persen di atas sebuah kotak.
 *
 * Dipakai di dua tempat yang memakai satuan berbeda — persegi SUMBER di atas
 * video asli, dan persegi TUJUAN di atas kanvas hasil — dan keduanya harus
 * terasa persis sama di tangan. Menuliskannya dua kali adalah cara termudah
 * membuat yang satu terasa lain dari yang lain.
 *
 * Pendengarnya dipasang di `window`, bukan di elemennya: jari atau kursor yang
 * keluar dari kotak saat menyeret tidak boleh menjatuhkan seretannya.
 *
 * @param handle  null untuk memindahkan; 'nw' | 'ne' | 'sw' | 'se' untuk sudut
 *                yang dipegang — sisi seberangnya jadi jangkar.
 */
export function beginRectDrag(e, { boxW, boxH, rect, handle, onChange, onEnd,
                                  lockX = false }) {
  if (!boxW || !boxH) return;
  e.preventDefault();
  e.stopPropagation();
  e.currentTarget.setPointerCapture?.(e.pointerId);

  const origin = { ...rect };
  const startX = e.clientX;
  const startY = e.clientY;

  const move = (ev) => {
    const dx = ((ev.clientX - startX) / boxW) * 100;
    const dy = ((ev.clientY - startY) / boxH) * 100;

    if (!handle) {
      // Bingkai yang mengikuti orang tidak punya posisi mendatar sendiri —
      // jejak wajahnya yang menentukan. Membiarkannya digeser ke samping akan
      // membuat kotaknya melompat balik begitu videonya jalan lagi.
      onChange(clampRect({
        ...origin,
        x: lockX ? origin.x : origin.x + dx,
        y: origin.y + dy,
      }));
      return;
    }

    let { x, y, w, h } = origin;
    if (handle.includes('e')) w = Math.max(MIN_PCT, Math.min(100 - x, origin.w + dx));
    if (handle.includes('s')) h = Math.max(MIN_PCT, Math.min(100 - y, origin.h + dy));
    if (handle.includes('w')) {
      const nx = Math.max(0, Math.min(origin.x + origin.w - MIN_PCT, origin.x + dx));
      w = origin.x + origin.w - nx;
      x = nx;
    }
    if (handle.includes('n')) {
      const ny = Math.max(0, Math.min(origin.y + origin.h - MIN_PCT, origin.y + dy));
      h = origin.y + origin.h - ny;
      y = ny;
    }
    onChange(clampRect({ x, y, w, h }));
  };

  const up = () => {
    window.removeEventListener('pointermove', move);
    window.removeEventListener('pointerup', up);
    onEnd?.();
  };
  window.addEventListener('pointermove', move);
  window.addEventListener('pointerup', up);
}
