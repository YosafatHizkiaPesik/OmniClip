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

  const idx = personNear(people, frame.src.x + frame.src.w / 2);
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
