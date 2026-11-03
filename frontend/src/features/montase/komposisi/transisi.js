/**
 * Transisi antar item di lajur yang sama (JOB-4 M3.5).
 *
 * `item.transisi = {jenis, durasi}` adalah transisi MASUK ke item itu dari
 * item sebelumnya di lajur yang sama, bila keduanya bersambung (ujung yang
 * satu = awal yang lain). Tanpa item sebelumnya, transisinya dari latar
 * (misalnya larut dari hitam).
 *
 * Kenapa bukan `<TransitionSeries>` dari @remotion/transitions: seri itu
 * menumpukkan dua potongan sehingga video jadi lebih pendek sepanjang
 * transisinya, padahal di Montase letak item mutlak (bingkai) dan item di
 * lajur lain, teks, dan penanda sudah diletakkan di waktu itu. Di sini
 * linimasa tidak bergeser: jendela transisi berpusat di sambungan, item
 * keluar menahan bingkai terakhirnya selama separuh kedua, item masuk menahan
 * bingkai pertamanya selama separuh pertama (dengan `<Freeze>`), lalu gaya
 * di bawah ini menggabungkan keduanya. Suara tetap terpotong di sambungan.
 */
export const JENIS_TRANSISI = ['potong', 'larut', 'geser', 'usap', 'perbesar', 'kilat', 'glitch'];

/**
 * Rencana per item: berapa bingkai ditambahkan sebelum (`pra`) dan sesudah
 * (`pasca`) item, dan transisi masuk/keluarnya beserta jendelanya (bingkai
 * relatif ke awal Sequence item yang sudah diperpanjang).
 */
export function rencanaTransisi(itemUrut) {
  const rencana = new Map();
  for (const it of itemUrut) rencana.set(it.id, { pra: 0, pasca: 0, masuk: null, keluar: null });
  for (let i = 0; i < itemUrut.length; i += 1) {
    const b = itemUrut[i];
    const tr = b.transisi;
    if (!tr || tr.jenis === 'potong' || !JENIS_TRANSISI.includes(tr.jenis) || !(tr.durasi > 0)) continue;
    const a = i > 0 ? itemUrut[i - 1] : null;
    const bersambung = a && a.mulai + a.durasi === b.mulai;
    const d = Math.max(1, Math.min(Math.round(tr.durasi), b.durasi, bersambung ? a.durasi : b.durasi));
    const rb = rencana.get(b.id);
    if (bersambung) {
      const pra = Math.floor(d / 2);
      rb.pra = pra;
      rb.masuk = { jenis: tr.jenis, mulai: 0, d };
      const ra = rencana.get(a.id);
      ra.pasca = d - pra;
      ra.keluar = { jenis: tr.jenis, mulai: ra.pra + a.durasi - pra, d };
    } else {
      rb.masuk = { jenis: tr.jenis, mulai: 0, d };
    }
  }
  return rencana;
}

function jepit01(x) {
  return Math.max(0, Math.min(1, x));
}

/** Getaran glitch yang tetap sama di pratinjau dan render (tanpa acak). */
function getar(f) {
  return Math.sin(f * 12.9898) * 43758.5453 % 1;
}

/**
 * Gaya lapis transisi pada bingkai `f` (relatif ke Sequence item yang sudah
 * diperpanjang). Mengembalikan {gaya, kilat} dengan `kilat` = opasitas lapisan
 * putih (hanya untuk transisi kilat, digambar oleh item yang masuk).
 */
export function gayaTransisi(rencana, f) {
  const gaya = {};
  let kilat = 0;
  const tf = [];
  const filter = [];
  let opasitas = 1;
  const pakai = (tr, peran) => {
    if (!tr) return;
    const p = jepit01((f - tr.mulai) / tr.d);
    if (f < tr.mulai || f >= tr.mulai + tr.d) {
      if (peran === 'masuk' && f < tr.mulai) opasitas = 0;
      return;
    }
    const puncak = 1 - Math.abs(2 * p - 1);
    if (tr.jenis === 'larut') {
      if (peran === 'masuk') opasitas *= p;
    } else if (tr.jenis === 'geser') {
      tf.push(`translateX(${peran === 'masuk' ? (1 - p) * 100 : -p * 100}%)`);
    } else if (tr.jenis === 'usap') {
      if (peran === 'masuk') gaya.clipPath = `inset(0 ${(1 - p) * 100}% 0 0)`;
    } else if (tr.jenis === 'perbesar') {
      if (peran === 'masuk') {
        tf.push(`scale(${1.25 - 0.25 * p})`);
        opasitas *= p;
      } else {
        tf.push(`scale(${1 + 0.6 * p})`);
        opasitas *= 1 - p;
      }
    } else if (tr.jenis === 'kilat') {
      if (peran === 'masuk') {
        if (p < 0.5) opasitas = 0;
        kilat = puncak;
      }
    } else if (tr.jenis === 'glitch') {
      tf.push(`translateX(${getar(f) * 60 * puncak}px)`);
      filter.push(`hue-rotate(${Math.round(160 * puncak)}deg)`, `saturate(${1 + 2 * puncak})`);
      if (peran === 'masuk' && p < 0.5) opasitas = 0;
    }
  };
  pakai(rencana?.keluar, 'keluar');
  pakai(rencana?.masuk, 'masuk');
  if (tf.length) gaya.transform = tf.join(' ');
  if (filter.length) gaya.filter = filter.join(' ');
  if (opasitas !== 1) gaya.opacity = opasitas;
  return { gaya, kilat };
}
