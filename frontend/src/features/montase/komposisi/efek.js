/**
 * Efek bawaan item video/gambar (JOB-4 M3.8), dihitung per bingkai.
 *
 * `item.efek = { kenburns, guncang, punch }`:
 *   kenburns  'masuk' | 'keluar' | 'kiri' | 'kanan': perbesar/geser pelan
 *             sepanjang item, untuk gambar diam yang terasa hidup;
 *   guncang   0..100: getaran kamera (deterministik, sama di pratinjau dan
 *             render: dari sinus bingkai, bukan Math.random);
 *   punch     [{t, d, kuat}]: zoom sekejap di bingkai relatif `t` selama `d`,
 *             naik 3 bingkai, tahan, turun 3 bingkai. Sama dengan punch-in
 *             Studio Klip.
 * Efek dipasang di DALAM kotak item dengan `overflow: hidden`, jadi gambar
 * membesar di dalam bingkainya sendiri dan tidak menutupi item lain.
 */
export const ARAH_KENBURNS = ['masuk', 'keluar', 'kiri', 'kanan'];
export const KUAT_PUNCH = 0.15;
const LANDAI = 3;

function amplop(f, t, d) {
  if (f < t || f >= t + d) return 0;
  const naik = Math.min(1, (f - t + 1) / LANDAI);
  const turun = Math.min(1, (t + d - f) / LANDAI);
  return Math.min(naik, turun);
}

/** CSS transform efek pada bingkai relatif `f`, atau undefined bila tanpa efek. */
export function transformEfek(efek, f, durasi) {
  if (!efek) return undefined;
  const tf = [];
  let skala = 1;
  const p = durasi > 1 ? Math.max(0, Math.min(1, f / (durasi - 1))) : 0;
  if (efek.kenburns === 'masuk') skala *= 1 + 0.15 * p;
  else if (efek.kenburns === 'keluar') skala *= 1.15 - 0.15 * p;
  else if (efek.kenburns === 'kiri' || efek.kenburns === 'kanan') {
    skala *= 1.12;
    const arah = efek.kenburns === 'kiri' ? -1 : 1;
    tf.push(`translateX(${arah * (p * 8 - 4)}%)`);
  }
  for (const pc of Array.isArray(efek.punch) ? efek.punch : []) {
    skala *= 1 + (pc.kuat ?? KUAT_PUNCH) * amplop(f, pc.t, pc.d);
  }
  const g = Number(efek.guncang) || 0;
  if (g > 0) {
    const a = (g / 100) * 2.5;
    const x = (Math.sin(f * 1.7) + 0.5 * Math.sin(f * 4.3)) * a;
    const y = (Math.cos(f * 2.1) + 0.5 * Math.sin(f * 3.7)) * a;
    tf.push(`translate(${x.toFixed(3)}%, ${y.toFixed(3)}%)`, `rotate(${(Math.sin(f * 1.3) * a * 0.4).toFixed(3)}deg)`);
    skala *= 1 + a / 40;
  }
  if (skala !== 1) tf.push(`scale(${skala.toFixed(4)})`);
  return tf.length ? tf.join(' ') : undefined;
}
