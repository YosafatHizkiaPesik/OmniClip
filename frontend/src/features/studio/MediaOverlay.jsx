import React, { useEffect, useRef } from 'react';
import { beginRectDrag } from './rectDrag';

/**
 * Sisipan di atas pratinjau: cuplikan dan gambar di petaknya, musik dan efek
 * suara ikut terdengar.
 *
 * Petaknya dihitung dengan pecahan yang SAMA dengan `POSISI_SISIPAN` dan
 * `petak_sisipan` di render.py. Pratinjau yang menaruh cuplikan di tempat lain
 * daripada hasil rendernya memaksa pengguna merender hanya untuk tahu letaknya.
 */
const POSISI = {
  penuh: [0, 0, 1, 1],
  atas: [0, 0, 1, 0.5],
  bawah: [0, 0.5, 1, 0.5],
  tengah: [0, 0.25, 1, 0.5],
  sudut: [0.5, 0.06, 0.46, null],   // tinggi = lebar * 9/16, dalam piksel
};

const url = (id) => `/api/aset/${encodeURIComponent(id)}/berkas`;

/**
 * Petak sebuah sisipan dalam PERSEN kanvas.
 *
 * Cermin dari `petak_sisipan` di backend: rect bebas menang, preset lama
 * dipakai bila belum ada rect. Preset `sudut` tingginya dihitung dari lebar
 * kanvas, jadi ia butuh rasio kotaknya.
 */
export function petakSisipan(l, boxW, boxH) {
  if (l?.rect && Number.isFinite(l.rect.w)) {
    const w = Math.max(2, Math.min(100, l.rect.w));
    const h = Math.max(2, Math.min(100, l.rect.h));
    return {
      x: Math.max(0, Math.min(100 - w, l.rect.x ?? 0)),
      y: Math.max(0, Math.min(100 - h, l.rect.y ?? 0)),
      w,
      h,
    };
  }
  const [fx, fy, fw, fh] = POSISI[l?.posisi] ?? POSISI.penuh;
  // Tinggi `null` berarti "ikut rasio 16:9 dari lebarnya", dan itu piksel,
  // bukan persen. Diubah jadi persen tinggi kanvas di sini.
  const tinggi = fh == null ? ((fw * boxW * 9) / 16 / boxH) : fh;
  return { x: fx * 100, y: fy * 100, w: fw * 100, h: Math.min(100, tinggi * 100) };
}

/** Ketembusan sisipan pada suatu detik, termasuk lembut masuk dan keluarnya. */
function opasitasPada(l, clipTime) {
  const dasar = Number.isFinite(l?.opasitas) ? Math.max(0, Math.min(1, l.opasitas)) : 1;
  const t = clipTime - (l.t ?? 0);
  const dur = l.dur ?? 0;
  const masuk = Math.max(0, Math.min(dur / 2, l.fade_masuk ?? 0));
  const keluar = Math.max(0, Math.min(dur / 2, l.fade_keluar ?? 0));
  let f = 1;
  if (masuk > 0 && t < masuk) f = Math.max(0, t / masuk);
  if (keluar > 0 && t > dur - keluar) f = Math.min(f, Math.max(0, (dur - t) / keluar));
  return dasar * f;
}

const SUDUT = [['nw', 0, 0], ['ne', 1, 0], ['sw', 0, 1], ['se', 1, 1]];

function Lapis({ l, jenis, clipTime, playing, boxW, boxH, terpilih, onRect, onPilih }) {
  const ref = useRef(null);
  const aktif = clipTime >= l.t && clipTime < l.t + (l.dur ?? 0);
  const posisiDalam = clipTime - l.t + (l.mulai_sumber ?? 0);

  // Waktu dan status putar diikat ke pratinjau utama. Selisih kecil dibiarkan:
  // menyetel currentTime tiap bingkai membuat media tersendat terus.
  useEffect(() => {
    const el = ref.current;
    if (!el || jenis === 'gambar') return;
    if (!aktif) { if (!el.paused) el.pause(); return; }
    // Berkas yang diulang berputar sendiri; tanpa ini pratinjau membeku di
    // bingkai terakhir sementara hasil rendernya berputar.
    el.loop = !!l.ulang;
    const dalam = l.ulang && el.duration ? posisiDalam % el.duration : posisiDalam;
    if (Math.abs(el.currentTime - dalam) > 0.3) el.currentTime = Math.max(0, dalam);
    el.volume = Math.max(0, Math.min(1, l.volume ?? 1));
    el.muted = (l.volume ?? 1) <= 0;
    if (playing && el.paused) el.play().catch(() => { /* ditolak peramban */ });
    if (!playing && !el.paused) el.pause();
  }, [aktif, playing, posisiDalam, jenis, l.volume, l.ulang]);

  if (jenis === 'audio') {
    return <audio ref={ref} src={url(l.aset)} preload="auto" hidden />;
  }

  const petak = petakSisipan(l, boxW, boxH);
  const px = (petak.x / 100) * boxW;
  const py = (petak.y / 100) * boxH;
  const pw = (petak.w / 100) * boxW;
  const ph = (petak.h / 100) * boxH;
  // Bawaannya sama dengan render: video memenuhi petaknya, gambar dimuat utuh.
  const isi = l.isi ?? (jenis === 'gambar' ? 'muat' : 'penuh');
  const gaya = {
    position: 'absolute', left: `${px}px`, top: `${py}px`,
    width: `${pw}px`, height: `${ph}px`, pointerEvents: 'none', zIndex: 1,
    objectFit: isi === 'muat' ? 'contain' : 'cover',
    opacity: opasitasPada(l, clipTime),
    visibility: aktif ? 'visible' : 'hidden',
  };
  const media = jenis === 'gambar'
    ? <img src={url(l.aset)} alt="" style={gaya} />
    : <video ref={ref} src={url(l.aset)} preload="auto" playsInline style={gaya} />;

  if (!onRect) return media;

  // Kotak pegangan. Muncul untuk sisipan yang sedang dipilih di panel atau di
  // linimasa, dan tetap muncul walau sisipannya belum waktunya tampil: menyetel
  // letak cuplikan detik ke-40 tidak boleh menuntut pemutarnya digeser dulu ke
  // detik ke-40.
  return (
    <>
      {media}
      <div
        onPointerDown={(e) => {
          onPilih?.(l.id);
          if (!terpilih) return;
          beginRectDrag(e, { boxW, boxH, rect: petak, handle: null, onChange: onRect });
        }}
        title={terpilih
          ? 'Seret untuk memindahkan, tarik sudutnya untuk mengubah ukuran'
          : 'Klik untuk memilih sisipan ini'}
        style={{
          position: 'absolute', left: `${px}px`, top: `${py}px`,
          width: `${pw}px`, height: `${ph}px`, zIndex: 3,
          cursor: terpilih ? 'move' : 'pointer',
          border: terpilih ? '2px solid var(--accent-cyan)' : '1px dashed rgba(255,255,255,0.35)',
          borderRadius: '2px',
          background: 'transparent',
          opacity: aktif ? 1 : 0.5,
        }}
      >
        {terpilih && SUDUT.map(([h, fx, fy]) => (
          <span key={h}
                onPointerDown={(e) => beginRectDrag(e, {
                  boxW, boxH, rect: petak, handle: h, onChange: onRect,
                })}
                style={{
                  position: 'absolute', width: '14px', height: '14px',
                  left: fx ? 'calc(100% - 7px)' : '-7px',
                  top: fy ? 'calc(100% - 7px)' : '-7px',
                  borderRadius: '50%', background: 'var(--accent-cyan)',
                  border: '2px solid #0B1220',
                  cursor: `${fy ? 's' : 'n'}${fx ? 'e' : 'w'}-resize`,
                }} />
        ))}
      </div>
    </>
  );
}

export default function MediaOverlay({
  layers, jenisById, clipTime, playing, boxW, boxH,
  // Sisipan yang sedang dipilih, dan cara menyimpan petak barunya. Keduanya
  // kosong berarti pratinjau saja, tanpa pegangan: itu keadaan di luar tab
  // Sisipan, dan kotak putus-putus di atas video akan mengganggu di sana.
  terpilih = null, onRect = null, onPilih = null,
}) {
  if (!layers?.length || !boxW || !boxH) return null;
  return (
    <>
      {layers.map((l) => {
        // Jenisnya disimpan di sisipan itu sendiri saat ditambahkan.
        const jenis = l.jenis ?? jenisById?.[l.aset];
        if (!jenis) return null;
        return <Lapis key={l.id ?? `${l.aset}@${l.t}`} l={l} jenis={jenis}
                      clipTime={clipTime} playing={playing} boxW={boxW} boxH={boxH}
                      terpilih={terpilih === l.id}
                      onPilih={onPilih}
                      onRect={onRect ? (r) => onRect(l.id, r) : null} />;
      })}
    </>
  );
}
