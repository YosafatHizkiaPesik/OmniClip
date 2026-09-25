/**
 * Model tata letak bingkai.
 *
 * Satu bingkai punya DUA persegi, dan memisahkan keduanya adalah seluruh isi
 * fitur ini:
 *
 *   src — bagian mana dari video SUMBER yang diambil, dalam persen lebar dan
 *         tinggi video aslinya;
 *   dst — di mana potongan itu diletakkan pada kanvas HASIL, dalam persen
 *         lebar dan tinggi kanvas keluaran.
 *
 * Karena keduanya terpisah, "reaksi streamer memenuhi layar dengan mediashare
 * kecil di pojok kiri bawah" dan "muka gamer di atas, permainannya di bawah"
 * adalah tata letak yang sama bentuknya — hanya angkanya yang berbeda. Tidak
 * ada mode khusus untuk masing-masing.
 *
 * Semua angka persen, tidak ada piksel. Video sumber 1080p dan 360p menghasilkan
 * susunan yang sama, dan kanvas 9:16 maupun 1:1 memakai berkas tata letak yang
 * sama tanpa dihitung ulang.
 */

// Ukuran terkecil yang masih bisa dipegang dengan jari, dan masih menghasilkan
// crop yang berarti pada sumber 360p (8% dari 640 = 51 piksel).
export const MIN_PCT = 8;

/** Pensil bingkai. Merah dipakai huruf latihan, jadi ia tidak ikut di sini. */
export const FRAME_INKS = ['#0F52B8', '#07683B', '#B2560A', '#6B21A8'];

export function frameInk(i) {
  return FRAME_INKS[i % FRAME_INKS.length];
}

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, Number.isFinite(v) ? v : lo));
}

/**
 * Menahan persegi di dalam bidangnya.
 *
 * Lebar dijepit lebih dulu, baru posisinya — urutan sebaliknya membuat persegi
 * yang diseret ke tepi ikut menyusut, yang terasa seperti kotaknya melawan
 * tangan.
 */
export function clampRect(r) {
  const w = clamp(r.w, MIN_PCT, 100);
  const h = clamp(r.h, MIN_PCT, 100);
  return {
    x: Math.round(clamp(r.x, 0, 100 - w) * 10) / 10,
    y: Math.round(clamp(r.y, 0, 100 - h) * 10) / 10,
    w: Math.round(w * 10) / 10,
    h: Math.round(h * 10) / 10,
  };
}

const FULL = { x: 0, y: 0, w: 100, h: 100 };

let seq = 0;
export function newFrameId() {
  seq += 1;
  return `f${Date.now().toString(36)}${seq}`;
}

export function makeFrame(label, src, dst) {
  return {
    id: newFrameId(),
    label,
    src: clampRect(src),
    dst: clampRect(dst),
    // 'cover' memenuhi kotak tujuan dan memotong kelebihannya; 'contain' memuat
    // seluruhnya dan menyisakan bilah. Cover jadi bawaan karena bilah hitam di
    // tengah susunan hampir selalu bukan yang dimaui.
    fit: 'cover',
    // Bila benar, posisi MENDATAR kotak sumber digerakkan jejak wajah. Lebar,
    // tinggi, dan posisi tegaknya tetap milik pengguna — itulah gunanya:
    // pengguna menentukan seberapa rapat bingkainya, sistem menjaga orangnya
    // tetap di dalamnya.
    follow: false,
  };
}

/**
 * Susunan siap pakai.
 *
 * Angka `src` untuk kamera wajah menebak pojok kiri atas karena di situlah
 * kebanyakan overlay streaming menaruhnya — tebakan yang salah pun tetap lebih
 * cepat digeser daripada dibuat dari nol.
 */
export const LAYOUT_PRESETS = [
  {
    id: 'single',
    label: 'Satu bingkai',
    hint: 'Satu potongan bebas dari video sumber, memenuhi kanvas.',
    build: () => [makeFrame('Utama', FULL, FULL)],
  },
  {
    id: 'reaction-stack',
    label: 'Reaksi di atas, layar di bawah',
    hint: 'Untuk klip main game: muka di atas, permainannya di bawah.',
    build: () => [
      makeFrame('Reaksi', { x: 0, y: 0, w: 30, h: 30 }, { x: 0, y: 0, w: 100, h: 38 }),
      makeFrame('Layar', FULL, { x: 0, y: 38, w: 100, h: 62 }),
    ],
  },
  {
    id: 'pip-corner',
    label: 'Penuh + sisipan pojok',
    hint: 'Reaksi memenuhi layar, mediashare jadi kotak kecil di pojok kiri bawah.',
    build: () => [
      makeFrame('Reaksi', FULL, FULL),
      makeFrame('Mediashare', { x: 0, y: 0, w: 40, h: 40 },
        { x: 4, y: 64, w: 40, h: 24 }),
    ],
  },
  // Reaksi terbagi: wajah beberapa orang ditumpuk di satu kanvas 9:16, untuk
  // momen tawa atau kaget bersama. Sutradara AI mengisi `src` dari posisi
  // wajah yang sebenarnya; kotak sumber di sini hanya titik awal manual.
  {
    id: 'reaction-2',
    label: 'Reaksi 2 orang',
    hint: 'Dua wajah bertumpuk, atas dan bawah, untuk tawa atau kaget bersama.',
    build: () => [
      makeFrame('Orang 1', { x: 10, y: 10, w: 36, h: 64 }, { x: 0, y: 0, w: 100, h: 50 }),
      makeFrame('Orang 2', { x: 54, y: 10, w: 36, h: 64 }, { x: 0, y: 50, w: 100, h: 50 }),
    ],
  },
  {
    id: 'reaction-3',
    label: 'Reaksi 3 orang',
    hint: 'Tiga wajah bertumpuk.',
    build: () => [
      makeFrame('Orang 1', { x: 4, y: 12, w: 28, h: 50 }, { x: 0, y: 0, w: 100, h: 33.333 }),
      makeFrame('Orang 2', { x: 36, y: 12, w: 28, h: 50 }, { x: 0, y: 33.333, w: 100, h: 33.334 }),
      makeFrame('Orang 3', { x: 68, y: 12, w: 28, h: 50 }, { x: 0, y: 66.667, w: 100, h: 33.333 }),
    ],
  },
  {
    id: 'reaction-4',
    label: 'Reaksi 4 orang',
    hint: 'Empat wajah dalam kisi 2×2.',
    build: () => [
      makeFrame('Orang 1', { x: 2, y: 10, w: 22, h: 70 }, { x: 0, y: 0, w: 50, h: 50 }),
      makeFrame('Orang 2', { x: 26, y: 10, w: 22, h: 70 }, { x: 50, y: 0, w: 50, h: 50 }),
      makeFrame('Orang 3', { x: 51, y: 10, w: 22, h: 70 }, { x: 0, y: 50, w: 50, h: 50 }),
      makeFrame('Orang 4', { x: 76, y: 10, w: 22, h: 70 }, { x: 50, y: 50, w: 50, h: 50 }),
    ],
  },
  {
    id: 'split-even',
    label: 'Dua tumpuk sama besar',
    hint: 'Membelah sumber jadi atas dan bawah, keduanya setengah kanvas.',
    build: () => [
      makeFrame('Atas', { x: 0, y: 0, w: 100, h: 50 }, { x: 0, y: 0, w: 100, h: 50 }),
      makeFrame('Bawah', { x: 0, y: 50, w: 100, h: 50 }, { x: 0, y: 50, w: 100, h: 50 }),
    ],
  },
];

export function presetLayout(id) {
  const preset = LAYOUT_PRESETS.find((p) => p.id === id) ?? LAYOUT_PRESETS[0];
  return { background: 'blur', frames: preset.build() };
}

export function defaultLayout() {
  return presetLayout('single');
}

/**
 * Titik tengah wajah pada detik `t`, dalam persen lebar sumber.
 *
 * Rata-rata orang yang BENAR-BENAR terlihat saat itu, bukan orang pertama:
 * pada bidikan dua orang, memakai orang pertama saja akan menaruh kotaknya di
 * pinggir dan memenggal yang lain.
 */
export function pusatWajahPada(reframe, t) {
  const people = reframe?.people;
  const seen = reframe?.people_seen;
  const fps = reframe?.people_fps || 8;
  if (!people?.length) return 50;
  const i = Math.max(0, Math.round(t * fps));
  const x = [];
  people.forEach((track, p) => {
    const terlihat = seen?.[p]?.[Math.min(i, (seen[p]?.length ?? 1) - 1)];
    const v = track[Math.min(i, track.length - 1)];
    if (v != null && (terlihat === undefined || terlihat)) x.push(v);
  });
  if (!x.length) return 50;
  return x.reduce((a, b) => a + b, 0) / x.length;
}

/**
 * Susunan awal yang MENIRU bingkai otomatis yang sedang terlihat.
 *
 * Dipakai saat berpindah ke "Susun sendiri" dari "Ikuti wajah" atau "Ikuti
 * gerakan". Tanpa ini, susunannya mulai dari kotak bawaan yang letaknya tidak
 * ada hubungannya dengan apa yang barusan di layar, dan yang terlihat adalah
 * gambar melompat lalu berkedip hitam sesaat sebelum kotak barunya terpasang.
 *
 * `pusatX` dalam persen lebar sumber, dari jejak wajah pada detik itu. Bila
 * tidak ada jejaknya, kotaknya diletakkan di tengah.
 */
export function layoutDariCrop(sourceAspect, canvasAspect, pusatX = 50) {
  const dasar = presetLayout('single');
  const bingkai = dasar.frames[0];
  // Lebar jendela 9:16 yang dipotong dari sumber 16:9: sekian persen lebarnya.
  const lebar = Math.max(MIN_PCT,
    Math.min(100, (canvasAspect / sourceAspect) * 100));
  const x = Math.max(0, Math.min(100 - lebar, pusatX - lebar / 2));
  return {
    ...dasar,
    frames: [{ ...bingkai, src: { x, y: 0, w: lebar, h: 100 },
               dst: { x: 0, y: 0, w: 100, h: 100 } }],
  };
}

/** Bingkai baru yang tidak menimpa persis bingkai sebelumnya. */
export function addedFrame(existing) {
  const n = existing.length;
  const step = Math.min(8 * n, 40);
  return makeFrame(`Bingkai ${n + 1}`,
    { x: 0, y: 0, w: 50, h: 50 },
    { x: 6 + step / 4, y: 10 + step, w: 44, h: 26 });
}

/**
 * Bentuk yang dikirim ke server.
 *
 * Disaring, bukan diteruskan apa adanya: `id` hanya berarti di browser, dan
 * ffmpeg tidak boleh menerima kunci yang tidak dikenalnya.
 */
export function serializeLayout(layout) {
  if (!layout?.frames?.length) return null;
  return {
    background: layout.background === 'black' ? 'black' : 'blur',
    frames: layout.frames.map((f) => ({
      label: String(f.label ?? '').slice(0, 40),
      src: clampRect(f.src),
      dst: clampRect(f.dst),
      fit: f.fit === 'contain' ? 'contain' : 'cover',
      follow: !!f.follow,
      // Nomor orang yang dibuntuti — diisi sutradara AI. Tanpa ini server
      // menebak dari letak kotak.
      ...(Number.isInteger(f.person) ? { person: f.person } : {}),
    })),
    // Main game: letak wajah per detik klip, dan setelan susunannya.
    ...(layout.reaksi?.length
      ? { reaksi: layout.reaksi.map((r) => ({ t: Math.max(0, Number(r.t) || 0), src: { ...r.src } })) }
      : {}),
    ...(layout.gaming ? { gaming: { ...layout.gaming } } : {}),
  };
}

/**
 * Geometri 'cover' untuk pratinjau, dalam PERSEN kotak tujuan.
 *
 * Persen, bukan piksel, dan itu bukan soal selera. Versi piksel harus mengukur
 * kotak pratinjau lebih dulu, dan ukuran hasil pengukuran itu bisa basi satu
 * frame — ketika kotaknya berubah lebar, videonya tetap diberi ukuran lama.
 * Yang terlihat: video yang tidak lagi menutupi kotaknya, dan sisa kotak
 * tergambar hitam. Pada bingkai sempit, sisanya hampir seluruh kotak, dan
 * bingkainya terbaca sebagai "gelap saja". Saya sempat mengirimkan versi itu.
 *
 * Semua yang dibutuhkan rumus ini sudah diketahui tanpa mengukur apa pun:
 * persegi sumber, persegi tujuan, rasio video sumber, dan rasio kanvas hasil.
 * Karena tidak ada yang diukur, tidak ada yang bisa basi.
 *
 * Rumusnya sama dengan `scale=…:force_original_aspect_ratio=increase,crop=…`
 * di ffmpeg, jadi apa yang terlihat di layar adalah apa yang akan dirender.
 *
 * @param srcRect      persegi sumber, persen video asli
 * @param dstRect      persegi tujuan, persen kanvas hasil
 * @param sourceAspect lebar/tinggi video sumber
 * @param canvasAspect lebar/tinggi kanvas hasil (9/16 dan seterusnya)
 */
export function coverPercent(srcRect, dstRect, sourceAspect, canvasAspect,
                             fit = 'cover') {
  const fw = srcRect.w / 100;
  const fh = srcRect.h / 100;
  if (!(fw > 0) || !(fh > 0) || !(sourceAspect > 0) || !(canvasAspect > 0)) return null;
  if (!(dstRect.w > 0) || !(dstRect.h > 0)) return null;

  // Rasio kotak tujuan diturunkan, bukan diukur: kotak tujuan adalah sekian
  // persen lebar dikali sekian persen tinggi dari kanvas yang rasionya sudah
  // ditentukan pengguna.
  const boxAspect = (dstRect.w / dstRect.h) * canvasAspect;
  const rectAspect = (fw / fh) * sourceAspect;
  const heightBinds = fit === 'cover' ? rectAspect > boxAspect : rectAspect < boxAspect;

  // Lebar dan tinggi potongan sumber, sebagai persen kotak tujuan.
  const rectW = heightBinds ? (rectAspect / boxAspect) * 100 : 100;
  const rectH = heightBinds ? 100 : (boxAspect / rectAspect) * 100;

  return {
    width: rectW / fw,
    height: rectH / fh,
    left: -(srcRect.x / 100) * (rectW / fw) + (100 - rectW) / 2,
    top: -(srcRect.y / 100) * (rectH / fh) + (100 - rectH) / 2,
  };
}

/**
 * Waktu VIDEO SUMBER -> waktu KLIP.
 *
 * Jejak wajah dan subtitle keduanya berwaktu klip: nol adalah awal klip, dan
 * potongan dari menit 10 dan menit 50 menyambung jadi satu garis waktu tanpa
 * lompatan. Elemen `<video>` sebaliknya melaporkan waktu video sumber. Mencari
 * jejak dengan angka yang salah tidak melempar galat apa pun — ia hanya selalu
 * mengembalikan titik terakhir, dan kotaknya terlihat berhenti mengikuti.
 */
export function clipTimeFor(segments, sourceTime) {
  if (!segments?.length) return sourceTime;
  let acc = 0;
  for (const s of segments) {
    const len = Math.max(0, s.end - s.start);
    if (sourceTime < s.end || s === segments[segments.length - 1]) {
      return Math.max(0, acc + Math.min(len, sourceTime - s.start));
    }
    acc += len;
  }
  return acc;
}

/**
 * Orang yang paling dekat dengan satu posisi mendatar.
 *
 * Kembaran `ReframePlan.person_near` di server. Beginilah cara pengguna
 * menunjuk: ia menaruh kotak bingkainya di atas seseorang, dan yang diikuti
 * adalah orang yang rata-rata duduk paling dekat kotak itu.
 */
export function personNear(people, xPct) {
  if (!people?.length) return null;
  let best = null;
  let bestD = Infinity;
  people.forEach((track, i) => {
    const seen = track.filter((v) => v !== null && v !== undefined);
    if (!seen.length) return;
    const mean = seen.reduce((a, b) => a + b, 0) / seen.length;
    const d = Math.abs(mean - xPct);
    if (d < bestD) { best = i; bestD = d; }
  });
  return best;
}

/** Waktu klip → waktu video sumber. Kebalikan dari `clipTimeFor`. */
export function sourceTimeFor(segments, clipTime) {
  if (!segments?.length) return clipTime;
  let acc = 0;
  for (const s of segments) {
    const len = Math.max(0, s.end - s.start);
    if (clipTime < acc + len) return s.start + (clipTime - acc);
    acc += len;
  }
  return segments[segments.length - 1].end;
}

/**
 * Memindahkan tanda arah bingkai mengikuti batas klip yang baru.
 *
 * Tanda hidup dalam waktu KLIP — detik keberapa terhitung dari awal klip. Jadi
 * begitu awal klipnya digeser dua detik, seluruh tanda menunjuk dua detik ke
 * tempat yang salah, dan pekerjaan menandai tadi terbuang tanpa satu pun tanda
 * terlihat hilang. Yang sebenarnya dimaksud pengguna saat menaruh tanda adalah
 * MOMEN DI REKAMAN, bukan hitungan dari awal klip.
 *
 * Karena itu tiap tanda diterjemahkan lewat waktu sumber: dari waktu klip lama
 * ke detik di rekaman, lalu kembali ke waktu klip yang baru. Tanda yang
 * momennya sudah tidak ada di dalam klip dibuang — menahannya di tepi berarti
 * menaruh perintah pada bagian yang sudah tidak dipotong.
 */
export function remapPersonKeys(keys, fromSegments, toSegments) {
  if (!keys?.length || !fromSegments?.length || !toSegments?.length) return keys ?? [];
  const inside = (t) => toSegments.some((s) => t >= s.start - 1e-6 && t <= s.end + 1e-6);
  const out = [];
  for (const k of keys) {
    const at = sourceTimeFor(fromSegments, Number(k.t) || 0);
    // Tanda di detik nol klip lama tetap di detik nol: ia berarti "sejak awal",
    // bukan sebuah momen tertentu di rekaman.
    if ((Number(k.t) || 0) <= 1e-6) { out.push({ ...k, t: 0 }); continue; }
    if (!inside(at)) continue;
    out.push({ ...k, t: Math.max(0, Math.round(clipTimeFor(toSegments, at) * 100) / 100) });
  }
  return out
    .filter((k, i, a) => a.findIndex((o) => Math.abs(o.t - k.t) <= 0.05) === i)
    .sort((a, b) => a.t - b.t);
}

/**
 * Berapa lama posisi seseorang boleh ditahan setelah wajahnya hilang.
 *
 * Deteksi wajah berkedip: satu-dua sampel kosong saat kepala menoleh adalah
 * hal biasa, dan menyembunyikan penandanya tiap kali itu terjadi membuatnya
 * berkedip-kedip. Tapi menahan tanpa batas — yang dilakukan versi sebelumnya —
 * meninggalkan penanda "orang 2" berdiri di atas kursi kosong sepanjang klip
 * setelah orangnya benar-benar keluar dari kamera. Setengah detik memaafkan
 * kedipan tanpa memalsukan kehadiran.
 */
export const PERSON_HOLD = 0.5;

/**
 * Berapa lama sebuah PIN di atas video boleh bertahan setelah orangnya hilang.
 *
 * Jauh lebih pendek dari PERSON_HOLD, dan sengaja. Lajur di linimasa butuh
 * jeda panjang supaya rentangnya tidak berlubang tiap kali kepala menoleh —
 * lajur berlubang tidak bisa dibaca. Tapi pin digambar di ATAS gambarnya, dan
 * pin yang bertahan setengah detik di posisi lamanya adalah nomor yang berdiri
 * di tempat yang salah — persis keluhan "ada 4 dan 5 berjejer padahal yang
 * bicara orang ke-3". Dua sampel cukup untuk menambal kedipan deteksi; lebih
 * dari itu yang tergambar bukan lagi orangnya, melainkan ingatannya.
 */
export const PIN_HOLD = 0.25;

/**
 * Posisi seseorang pada detik tertentu, atau null bila ia memang tidak ada di
 * layar saat itu.
 *
 * Inilah pembacaan yang membedakan "sedang tidak terdeteksi" dari "sudah tidak
 * di sini": jejaknya ditelusuri mundur, tapi hanya sejauh PERSON_HOLD.
 */
export function personAt(reframe, index, t, hold = PIN_HOLD) {
  const track = reframe?.people?.[index];
  if (!track?.length) return null;
  const fps = reframe?.people_fps || 8;
  const seen = reframe?.people_seen?.[index];
  const i = Math.max(0, Math.min(track.length - 1, Math.round(t * fps)));
  const floor = Math.max(0, i - Math.ceil(hold * fps));
  for (let j = i; j >= floor; j -= 1) {
    // Kehadiran yang menentukan, bukan celah pada jejaknya: jejak posisi
    // sengaja menahan nilai terakhir supaya crop tidak melompat, jadi ia tidak
    // pernah kosong setelah orangnya sekali terlihat.
    const here = seen ? seen[j] : (track[j] !== null && track[j] !== undefined);
    if (here) return track[j];
  }
  return null;
}

/**
 * Rentang waktu di mana seseorang benar-benar terlihat.
 *
 * Dipakai lajur bingkai di linimasa: tanpa gambaran ini, menaruh tanda berarti
 * menebak — pengguna tidak punya cara tahu bahwa orang yang ditunjuknya sedang
 * tidak ada di kamera pada detik itu.
 */
/**
 * Siapa yang benar-benar hadir di klip ini, bukan sekadar pernah terdeteksi.
 *
 * Nomor orang milik SELURUH video, jadi daftar yang datang dari server memuat
 * semua orang yang pernah dikenali di video itu — termasuk yang tidak sekali
 * pun lewat pada rentang klip ini. Terukur pada rekaman lapangan: enam nomor
 * ditawarkan padahal empat di antaranya terlihat 1-2% durasi klip, dan tidak
 * pernah lebih dari dua wajah ada di layar bersamaan.
 *
 * Nomornya TIDAK dipakai ulang — daftar bisa melompat dari 1 ke 3, dan lompatan
 * itu keterangan: orang 2 memang tidak ada di sini. Menomori ulang per klip
 * akan membuat tanda arah bingkai yang sudah disimpan menunjuk orang lain.
 */
export function presentPeople(reframe, duration, { minSeconds = 1.0, minShare = 0.04 } = {}) {
  const people = reframe?.people ?? [];
  const total = Math.max(0.001, duration || 0.001);
  return people
    .map((_, i) => i)
    .filter((i) => {
      const lama = personSpans(reframe, i)
        .reduce((a, [s0, s1]) => a + Math.max(0, s1 - s0), 0);
      return lama >= minSeconds && lama / total >= minShare;
    });
}

export function personSpans(reframe, index, hold = PERSON_HOLD) {
  const track = reframe?.people?.[index];
  if (!track?.length) return [];
  const fps = reframe?.people_fps || 8;
  const seen = reframe?.people_seen?.[index];
  const present = track.map((v, i) => (
    seen ? !!seen[i] : (v !== null && v !== undefined)));
  const gap = Math.ceil(hold * fps);
  const spans = [];
  let open = null;
  let missing = 0;
  present.forEach((here, i) => {
    if (here) {
      if (open === null) open = i;
      missing = 0;
    } else if (open !== null) {
      missing += 1;
      if (missing > gap) {
        spans.push([open / fps, (i - missing + 1) / fps]);
        open = null;
      }
    }
  });
  if (open !== null) spans.push([open / fps, present.length / fps]);
  return spans.filter(([a, b]) => b > a);
}

/** Orang yang ditunjuk tanda linimasa pada detik tertentu. */
export function personKeyAt(keys, t) {
  if (!keys?.length) return null;
  let active = null;
  for (const k of keys) {
    if (k.t <= t + 1e-6) active = k;
    else break;
  }
  return active ? active.person : null;
}

/** Menyisipkan tanda baru dan membuang tanda lain pada detik yang sama. */
export function withPersonKey(keys, t, person) {
  const at = Math.max(0, Math.round(t * 100) / 100);
  return [...(keys ?? []).filter((k) => Math.abs(k.t - at) > 0.05), { t: at, person }]
    .sort((a, b) => a.t - b.t);
}

/**
 * Posisi mendatar bingkai pengikut pada detik tertentu, dalam persen.
 *
 * Kembaran persis `ReframePlan.x_track` di server: titik tengah orangnya
 * dikurangi separuh lebar jendela, lalu dijepit di dalam bidang video. Karena
 * keduanya membaca jejak yang sama dan menghitungnya dengan cara yang sama,
 * kotak yang bergerak di layar adalah kotak yang akan dipakai ffmpeg.
 *
 * Celah pada jejak diisi nilai terakhir yang diketahui — sama seperti server —
 * supaya kotaknya menahan posisi saat orangnya sesaat tidak terdeteksi, bukan
 * melompat ke tengah.
 */
export function followX(reframe, frame, t) {
  const people = reframe?.people;
  const fps = reframe?.people_fps || 8;
  if (!people?.length) return null;

  // Orang yang ditentukan (bingkai reaksi dari sutradara) menang atas tebakan
  // dari letak kotak — sama seperti server.
  const idx = Number.isInteger(frame.person) && frame.person < people.length
    ? frame.person : personNear(people, frame.src.x + frame.src.w / 2);
  if (idx === null) return null;

  const track = people[idx];
  const i = Math.max(0, Math.min(track.length - 1, Math.round(t * fps)));
  let v = null;
  for (let j = i; j >= 0; j -= 1) {
    if (track[j] !== null && track[j] !== undefined) { v = track[j]; break; }
  }
  if (v === null) return null;

  const half = frame.src.w / 2;
  return Math.max(0, Math.min(100 - frame.src.w, v - half));
}

/** Rasio kanvas keluaran sebagai angka. */
export const CANVAS_ASPECT = {
  '9:16': 9 / 16, '1:1': 1, '4:5': 4 / 5, '16:9': 16 / 9,
};

// --- Ingatan susunan ---------------------------------------------------------

const STORE_KEY = 'omniclip_framing';

const MODES = new Set(['smart', 'layout', 'blur', 'center', 'original']);

/**
 * Susunan bingkai diingat PER VIDEO, bukan satu untuk semua.
 *
 * Letak kamera wajah pada rekaman game berbeda dari letak mediashare pada
 * rekaman streaming, jadi satu susunan global akan memulihkan angka yang salah
 * lebih sering daripada yang benar. Sebaliknya, membiarkannya kembali ke bawaan
 * tiap kali editor dibuka berarti seluruh penyetelan diulang dari nol.
 *
 * CARA membingkainya ikut disimpan. Menyimpan susunannya saja membuat
 * pemulihannya tidak terlihat: editor terbuka di mode ikut-wajah, panelnya
 * tidak menampilkan daftar bingkai apa pun, dan bagi pengguna itu tidak bisa
 * dibedakan dari susunan yang hilang.
 */
export function loadFraming(videoId) {
  const fallback = { mode: 'smart', layout: defaultLayout() };
  if (!videoId) return fallback;
  try {
    const all = JSON.parse(localStorage.getItem(STORE_KEY) || '{}');
    const saved = all[videoId];
    if (!saved?.layout?.frames?.length) return fallback;
    const l = saved.layout;
    return {
      mode: MODES.has(saved.mode) ? saved.mode : 'smart',
      layout: {
        background: l.background === 'black' ? 'black' : 'blur',
        // id dibuat ulang: yang tersimpan hanya bentuknya, dan id lama bisa
        // bertabrakan dengan bingkai yang dibuat di sesi ini.
        frames: l.frames.map((f) => ({
          ...makeFrame(f.label || 'Bingkai', f.src, f.dst),
          fit: f.fit === 'contain' ? 'contain' : 'cover',
          follow: !!f.follow,
        })),
      },
    };
  } catch {
    return fallback;
  }
}

export function saveFraming(videoId, mode, layout) {
  if (!videoId) return;
  try {
    const all = JSON.parse(localStorage.getItem(STORE_KEY) || '{}');
    all[videoId] = { mode, layout: serializeLayout(layout) };
    // Dibatasi 40 video supaya penyimpanan browser tidak tumbuh tanpa batas.
    const keys = Object.keys(all);
    if (keys.length > 40) delete all[keys[0]];
    localStorage.setItem(STORE_KEY, JSON.stringify(all));
  } catch { /* penyimpanan penuh atau ditolak: bukan alasan menjatuhkan editor */ }
}


/**
 * Mode membingkai yang bisa dipasang per potongan waktu di lajur Bingkai.
 *
 * Label pendeknya berupa KATA, bukan huruf. Versi pertama memakai satu huruf
 * (W/K/G/T/B) meniru lajur Arah bingkai di sebelahnya — dan itu salah menarik
 * kesimpulan: angka di lajur itu bisa berdiri sendiri karena "1" dan "2" memang
 * nomor orang yang terlihat di layar. Huruf tidak menunjuk apa pun. Ditanyakan
 * langsung oleh pemiliknya: "apa maksud dari w, k, g, t, b".
 */
export const MODE_BINGKAI = [
  { id: 'smart', huruf: 'Wajah', nama: 'Ikuti wajah', warna: 'var(--accent-cyan)' },
  { id: 'motion', huruf: 'Gerak', nama: 'Ikuti gerakan', warna: '#2fb6c9' },
  { id: 'box', huruf: 'Kotak', nama: 'Kotak tetap', warna: '#e8a33d' },
  { id: 'gaming', huruf: 'Game', nama: 'Main game', warna: '#8f7bff' },
  { id: 'center', huruf: 'Tengah', nama: 'Potong tengah', warna: '#3dbd8a' },
  { id: 'layout', huruf: 'Susun', nama: 'Susun sendiri', warna: '#e05c8a' },
  { id: 'blur', huruf: 'Kabur', nama: 'Bilah kabur', warna: '#8c8c8c' },
];

export function modeBingkai(id) {
  return MODE_BINGKAI.find((m) => m.id === id) ?? MODE_BINGKAI[0];
}

/**
 * Menaruh atau mengganti satu kunci bingkai di detik `t`.
 *
 * Kunci pertama selalu ditarik ke nol: potongan tanpa pembingkaian akan
 * dirender sebagai latar kabur kosong, dan itu tidak pernah diinginkan siapa
 * pun. Server memaksakan aturan yang sama, tapi memaksakannya di sini juga
 * membuat linimasanya jujur SEBELUM dirender.
 */
export function withFrameKey(keys, t, patch, modeAwal = 'smart') {
  const at = Math.max(0, Math.round(t * 100) / 100);
  const lama = (keys ?? []).find((k) => Math.abs(k.t - at) <= 0.05);
  const sisa = (keys ?? []).filter((k) => Math.abs(k.t - at) > 0.05);
  // Kunci yang disentuh tangan menjadi milik pengguna: label asal dan alasan
  // dari sutradara dilepas, supaya "Susun bingkai dengan AI" berikutnya tidak
  // menimpanya. Sutradara sendiri tidak memakai fungsi ini.
  const hasil = [...sisa, { ...(lama ?? { mode: modeAwal }), asal: undefined,
                            alasan: undefined, ...patch, t: at }]
    .sort((a, b) => a.t - b.t);
  // Rentang sebelum kunci pertama harus punya pemiliknya sendiri.
  //
  // Versi pertama menyeret kunci paling awal ke detik nol, dan itu diam-diam
  // membatalkan pembelahan: pada lajur yang masih kosong, membelah di detik 30
  // membuat satu kunci di 30 yang lalu ditarik ke 0 — hasilnya tetap satu
  // potongan, dan tombol belahnya terlihat tidak bekerja. Yang benar adalah
  // MENAMBAH kunci pembuka, bukan memindahkan kunci yang baru dibuat.
  if (hasil.length && hasil[0].t > 0.05) {
    hasil.unshift({ t: 0, mode: modeAwal });
  }
  return hasil;
}

/** Membuang satu kunci; potongan itu menyatu dengan yang sebelumnya. */
export function withoutFrameKey(keys, index) {
  const baru = (keys ?? []).filter((_, i) => i !== index);
  if (baru.length) baru[0] = { ...baru[0], t: 0 };
  return baru;
}


// --- Main game: susunan dua bidang yang bisa disetel ---------------------------
//
// Cermin `render.susun_layout_gaming` di server. Keduanya harus menghitung hal
// yang sama, karena yang disetel di sini dikirim apa adanya ke render.

export const GAMING_WAJAH_BAWAAN = 40;
const RASIO_KELUARAN = { '9:16': 9 / 16, '1:1': 1, '4:5': 4 / 5, '16:9': 16 / 9 };

export function rasioKeluaran(aspectRatio) {
  return RASIO_KELUARAN[aspectRatio] ?? 9 / 16;
}

/**
 * Kotak sumber berasio PIKSEL `rasioPx`, berpusat di tengah `r`, sebesar
 * mungkin tanpa keluar bingkai. Kotak yang rasionya sama dengan bidangnya
 * tidak dipotong lagi oleh "cover" — yang terlihat di meja bingkai = hasilnya.
 */
export function pasRasio(r, rasioPx, srcAspek, { pertahankan = 'h', dalam = false } = {}) {
  const cx = r.x + r.w / 2;
  const cy = r.y + r.h / 2;
  const k = rasioPx / Math.max(1e-6, srcAspek);
  let h;
  let w;
  if (pertahankan === 'w') { w = r.w; h = w / k; } else { h = r.h; w = h * k; }
  // Di dalam kotaknya saja (facecam): dipangkas, tidak dilebarkan ke layar
  // permainan di sebelahnya.
  if (dalam) { w = Math.min(r.w, r.h * k); h = w / k; }
  if (w > 100) { w = 100; h = w / k; }
  if (h > 100) { h = 100; w = h * k; }
  const x = Math.min(Math.max(0, cx - w / 2), 100 - w);
  const y = Math.min(Math.max(0, cy - h / 2), 100 - h);
  const bulat = (v) => Math.round(v * 100) / 100;
  return { x: bulat(x), y: bulat(y), w: bulat(w), h: bulat(h) };
}

/** Rasio piksel bidang tujuan di kanvas. */
export function rasioBidang(dst, outAspek) {
  return (dst.w * outAspek) / Math.max(1e-6, dst.h);
}

/** Bidang permainan selebar kanvas, setinggi BENTUK kotak sumbernya. */
export function bidangPermainan(src, wajah, srcAspek, outAspek) {
  const rasioPx = (src.w / Math.max(1e-6, src.h)) * srcAspek;
  const sisa = 100 - wajah;
  let h = (100 * outAspek) / rasioPx;
  if (h > sisa) {
    h = sisa;
    const w = (h * rasioPx) / outAspek;
    return { x: (100 - w) / 2, y: wajah, w, h };
  }
  return { x: 0, y: wajah, w: 100, h };
}

// Cermin konstanta render.py: ruang kepala di sekitar petak wajah YuNet.
const KEPALA_ATAS = 0.35;
const KEPALA_BAWAH = 0.22;
const KEPALA_SAMPING = 0.25;
const PERMAINAN_GESER_MAKS = 3.0;

/** Cermin `render._ruang_wajah`: petak wajah [x1,y1,x2,y2] -> kepala utuh. */
function ruangWajah(muka) {
  if (!Array.isArray(muka) || muka.length !== 4) return null;
  const [x1, y1, x2, y2] = muka.map(Number);
  const fw = Math.max(0.1, x2 - x1);
  const fh = Math.max(0.1, y2 - y1);
  const a = Math.max(0, x1 - KEPALA_SAMPING * fw);
  const b = Math.min(100, x2 + KEPALA_SAMPING * fw);
  const c = Math.max(0, y1 - KEPALA_ATAS * fh);
  const d = Math.min(100, y2 + KEPALA_BAWAH * fh);
  return { x: a, y: c, w: b - a, h: d - c };
}

function pilihDalam(lo, hi, plo, phi, ingin) {
  if (lo > hi) { const m = (lo + hi) / 2; lo = m; hi = m; }
  const a = Math.max(lo, plo);
  const b = Math.min(hi, phi);
  if (a <= b) return Math.min(Math.max(ingin, a), b);
  return Math.min(Math.max((plo + phi) / 2, lo), hi);
}

/**
 * Cermin `render.kotak_reaksi`: potongan bidang reaksi yang memuat SELURUH
 * kepala dan sebisanya tetap di dalam panel facecam.
 */
export function kotakReaksi(kotak, muka, rasioPx, srcAspek) {
  const dasar = pasRasio(kotak, rasioPx, srcAspek, { dalam: true });
  const butuh = ruangWajah(muka);
  if (!butuh) return dasar;
  const k = rasioPx / Math.max(1e-6, srcAspek);
  let h = Math.max(dasar.h, butuh.h, butuh.w / k);
  let w = h * k;
  if (w > 100) { w = 100; h = 100 / k; }
  if (h > 100) { h = 100; w = 100 * k; }
  let x = pilihDalam(butuh.x + butuh.w - w, butuh.x, kotak.x, kotak.x + kotak.w - w,
    butuh.x + butuh.w / 2 - w / 2);
  let y = pilihDalam(butuh.y + butuh.h - h, butuh.y, kotak.y, kotak.y + kotak.h - h,
    butuh.y + butuh.h / 2 - h / 2);
  x = Math.min(Math.max(0, x), 100 - w);
  y = Math.min(Math.max(0, y), 100 - h);
  const bulat = (v) => Math.round(v * 100) / 100;
  return { x: bulat(x), y: bulat(y), w: bulat(w), h: bulat(h) };
}

/**
 * Cermin `render._permainan_tanpa_wajah`: potongan permainan tanpa facecam.
 * Bila menghindari seluruh panel mendorongnya lebih dari 3% dari tengah, yang
 * dihindari hanya kepala di dalamnya (`wajahSaja`).
 */
export function permainanTanpaWajah(facecams, rasioPx, srcAspek, wajahSaja = null) {
  if (wajahSaja?.length) {
    const hasil = permainanTanpaWajah(facecams, rasioPx, srcAspek);
    const w = Math.min(100, 100 * (rasioPx / Math.max(1e-6, srcAspek)));
    if (Math.abs(hasil.x - (50 - w / 2)) > PERMAINAN_GESER_MAKS) {
      return permainanTanpaWajah(wajahSaja, rasioPx, srcAspek);
    }
    return hasil;
  }
  const k = rasioPx / Math.max(1e-6, srcAspek);
  const w = Math.min(100, 100 * k);
  if (w >= 100) {
    const h = Math.min(100, 100 / k);
    return { x: 0, y: (100 - h) / 2, w: 100, h };
  }
  const tengah = 50 - w / 2;
  const calon = [tengah];
  for (const f of facecams) calon.push(f.x - w, f.x + f.w);
  const bebas = (x) => facecams.every((f) => x + w <= f.x + 0.5 || x >= f.x + f.w - 0.5);
  const sah = calon.filter((x) => x >= -1e-6 && x <= 100 - w + 1e-6 && bebas(x));
  const x = sah.length
    ? sah.reduce((a, v) => (Math.abs(v - tengah) < Math.abs(a - tengah) ? v : a))
    : tengah;
  return { x: Math.min(Math.max(0, x), 100 - w), y: 0, w, h: 100 };
}

/**
 * Susunan Main game dari PRESET: tinggi bidang wajah dan cara menaruh
 * permainan. Dipanggil hanya saat preset dipilih atau penggeser digeser —
 * sesudah itu kedua bingkai bebas diatur seperti di Susun sendiri, dan tidak
 * ada yang menimpanya.
 *
 *   'isi'  (bawaan) permainan memenuhi seluruh sisa kanvas, dipotong dari
 *          bagian yang tidak memuat facecam supaya wajah tidak tampil dua kali;
 *   'utuh' seluruh layar permainan selebar kanvas, sisanya latar kabur.
 */
export function susunGaming(lama, { wajah, permainan = 'isi', srcAspek, outAspek }) {
  const main = lama.frames[0];
  const muka = lama.frames[1];
  const tinggiWajah = Math.max(15, Math.min(75, wajah));
  const mukaDst = { x: 0, y: 0, w: 100, h: tinggiWajah };
  const rasioMuka = rasioBidang(mukaDst, outAspek);
  // Dibentuk dari `kotak` — panel facecam yang ditemukan, atau kotak terakhir
  // yang diseret pengguna — supaya tiap geseran tidak memangkasnya lagi.
  const reaksi = (lama.reaksi?.length ? lama.reaksi : [{ t: 0, src: muka.src }])
    .map((r) => {
      const kotak = r.kotak ?? r.src;
      return { t: r.t, kotak, ...(r.muka ? { muka: r.muka } : {}),
               src: kotakReaksi(kotak, r.muka, rasioMuka, srcAspek) };
    });
  let mainSrc;
  let mainDst;
  if (permainan === 'utuh') {
    mainSrc = { x: 0, y: 0, w: 100, h: 100 };
    mainDst = bidangPermainan(mainSrc, tinggiWajah, srcAspek, outAspek);
  } else {
    mainDst = { x: 0, y: tinggiWajah, w: 100, h: 100 - tinggiWajah };
    mainSrc = permainanTanpaWajah(reaksi.map((r) => r.kotak),
      rasioBidang(mainDst, outAspek), srcAspek,
      reaksi.map((r) => ruangWajah(r.muka) ?? r.kotak));
  }
  return {
    ...lama,
    gaming: { ...(lama.gaming ?? {}), wajah: tinggiWajah, permainan, sumber: srcAspek },
    reaksi,
    frames: [
      { ...main, src: mainSrc, dst: mainDst, fit: 'cover', follow: false },
      { ...muka, src: reaksi[0].src, dst: mukaDst, fit: 'cover', follow: false },
    ],
  };
}

/** Indeks letak wajah yang berlaku pada detik klip `t`. */
export function reaksiAktif(layout, t) {
  const r = layout?.reaksi ?? [];
  let i = 0;
  for (let j = 0; j < r.length; j += 1) if ((r[j].t ?? 0) <= t + 1e-6) i = j;
  return i;
}

/** Susunan Main game seperti yang tampil pada detik klip `t`. */
export function gamingPadaWaktu(layout, t) {
  if (!layout?.frames?.length || !(layout.reaksi?.length > 1)) return layout;
  const r = layout.reaksi[reaksiAktif(layout, t)];
  return { ...layout,
           frames: layout.frames.map((f, i) => (i === 1 ? { ...f, src: r.src } : f)) };
}

/** Susunan dari server (tanpa id) -> susunan editor. */
export function susunanDariServer(l) {
  if (!l?.frames?.length) return null;
  return {
    background: l.background === 'black' ? 'black' : 'blur',
    gaming: l.gaming ?? null,
    reaksi: (l.reaksi ?? []).map((r) => ({
      t: Number(r.t) || 0, src: { ...r.src }, ...(r.kotak ? { kotak: { ...r.kotak } } : {}),
      ...(Array.isArray(r.muka) ? { muka: [...r.muka] } : {}),
    })),
    frames: l.frames.map((f, i) => ({
      ...makeFrame(f.label || (i === 0 ? 'Permainan' : 'Reaksi'), f.src, f.dst),
      // Tanpa pembulatan clampRect: rasio kotak harus tepat sama dengan
      // bidangnya, dan 0,1% di sini sudah terlihat sebagai potongan tipis.
      src: { ...f.src },
      dst: { ...f.dst },
      fit: f.fit === 'contain' ? 'contain' : 'cover',
    })),
  };
}

/**
 * Susun sendiri: bentuk kotak sumber dan bidang tujuannya saling mengikuti.
 *
 * Dengan "cover", kotak sumber yang bentuknya berbeda dari bidangnya dipotong
 * lagi saat ditampilkan — terlapor: kotak di sekeliling notifikasi donasi yang
 * lebar dan pendek, ditaruh di bidang yang tinggi, keluar dengan kiri-kanan
 * teksnya hilang. Yang dikotaki pengguna harus tampil utuh. Jadi:
 *
 *   - kotak SUMBER diubah ukurannya -> tinggi bidang tujuan menyesuaikan
 *     (lebar dan letak atasnya tetap);
 *   - bidang TUJUAN diubah ukurannya -> kotak sumber menyesuaikan (lebar dan
 *     pusatnya tetap).
 *
 * Memindahkan tanpa mengubah ukuran tidak menyentuh apa pun, dan bingkai
 * "Muat semua" (contain) dibiarkan: bilahnya memang pilihan pengguna.
 */
export function selaraskanBentuk(lama, baru, { srcAspek, outAspek }) {
  if (!lama?.frames?.length || !baru?.frames?.length) return baru;
  const sebelum = new Map(lama.frames.map((f) => [f.id, f]));
  const beda = (a, b) => Math.abs(a.w - b.w) > 0.05 || Math.abs(a.h - b.h) > 0.05;
  const bulat = (v) => Math.round(v * 100) / 100;
  let berubah = false;
  const frames = baru.frames.map((f) => {
    const p = sebelum.get(f.id);
    if (!p || f.fit === 'contain') return f;
    if (beda(p.src, f.src)) {
      const rasioPx = (f.src.w / Math.max(1e-6, f.src.h)) * srcAspek;
      let { x, y, w } = f.dst;
      let h = (w * outAspek) / rasioPx;
      if (h > 100) { h = 100; w = (h * rasioPx) / outAspek; x = (100 - w) / 2; }
      if (y + h > 100) y = 100 - h;
      berubah = true;
      return { ...f, dst: { x: bulat(x), y: bulat(Math.max(0, y)), w: bulat(w), h: bulat(h) } };
    }
    if (beda(p.dst, f.dst)) {
      berubah = true;
      return { ...f, src: pasRasio(f.src, rasioBidang(f.dst, outAspek), srcAspek, { pertahankan: 'w' }) };
    }
    return f;
  });
  return berubah ? { ...baru, frames } : baru;
}
