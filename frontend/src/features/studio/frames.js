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
    })),
  };
}

/**
 * Geometri 'cover' untuk pratinjau.
 *
 * Mengembalikan ukuran dan geseran elemen video di dalam kotak tujuan sehingga
 * `src` persis mengisi kotak itu — rumus yang sama dengan
 * `scale=…:force_original_aspect_ratio=increase,crop=…` di ffmpeg, supaya apa
 * yang terlihat di layar adalah apa yang akan dirender.
 *
 * @param srcRect  persegi sumber dalam persen
 * @param boxW,boxH  ukuran kotak tujuan dalam piksel layar
 * @param aspect   lebar/tinggi video sumber
 */
export function coverGeometry(srcRect, boxW, boxH, aspect, fit = 'cover') {
  if (!boxW || !boxH || !aspect) return null;
  const fw = srcRect.w / 100;
  const fh = srcRect.h / 100;
  if (fw <= 0 || fh <= 0) return null;

  // Aspek potongan sumber, dinyatakan lewat aspek video utuhnya.
  const rectAspect = (fw / fh) * aspect;
  const boxAspect = boxW / boxH;
  const heightBinds = fit === 'cover' ? rectAspect > boxAspect : rectAspect < boxAspect;

  const rectW = heightBinds ? boxH * rectAspect : boxW;
  const rectH = heightBinds ? boxH : boxW / rectAspect;

  const fullW = rectW / fw;
  const fullH = rectH / fh;

  return {
    width: fullW,
    height: fullH,
    left: -(srcRect.x / 100) * fullW + (boxW - rectW) / 2,
    top: -(srcRect.y / 100) * fullH + (boxH - rectH) / 2,
  };
}


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
