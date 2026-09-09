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
    })),
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
 * Posisi mendatar bingkai pengikut pada detik tertentu, dalam persen.
 *
 * Kembaran persis `ReframePlan.x_track` di server: titik tengah wajah dikurangi
 * separuh lebar jendela, lalu dijepit di dalam bidang video. Karena keduanya
 * membaca jejak yang sama dan menghitungnya dengan cara yang sama, kotak yang
 * bergerak di layar adalah kotak yang akan dipakai ffmpeg.
 *
 * @param centers  [[detik, titikTengahPiksel]] dari /api/clip-reframe
 * @param widthPct lebar jendela, persen lebar video
 * @param sourceW  lebar video sumber dalam piksel
 */
export function followX(centers, widthPct, sourceW, t) {
  if (!centers?.length || !sourceW) return null;
  let lo = 0;
  let hi = centers.length - 1;
  if (t <= centers[0][0]) lo = 0;
  else {
    while (lo < hi) {
      const mid = Math.ceil((lo + hi) / 2);
      if (centers[mid][0] <= t) lo = mid;
      else hi = mid - 1;
    }
  }
  const halfPct = widthPct / 2;
  const centerPct = (centers[lo][1] / sourceW) * 100;
  return Math.max(0, Math.min(100 - widthPct, centerPct - halfPct));
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
