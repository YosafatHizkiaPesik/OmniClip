/**
 * Transformasi item (posisi, ukuran, putar, transparansi) menjadi gaya CSS.
 *
 * `x` dan `y` dalam piksel kanvas dari titik tengah, `skala` 1 = ukuran asli,
 * `putar` dalam derajat. Satuan kanvas, bukan persen, supaya angka yang sama
 * menghasilkan letak yang sama di pratinjau yang diperkecil dan di render
 * ukuran penuh: Player menskalakan seluruh kanvas, bukan isinya satu per satu.
 */
export function gayaUbah(ubah) {
  if (!ubah) return undefined;
  const { x = 0, y = 0, skala = 1, putar = 0, opasitas = 1 } = ubah;
  const transform = [];
  if (x || y) transform.push(`translate(${x}px, ${y}px)`);
  if (skala !== 1) transform.push(`scale(${skala})`);
  if (putar) transform.push(`rotate(${putar}deg)`);
  return {
    transform: transform.length ? transform.join(' ') : undefined,
    opacity: opasitas === 1 ? undefined : opasitas,
  };
}
