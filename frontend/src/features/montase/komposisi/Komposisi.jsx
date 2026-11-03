/**
 * Komposisi Montase: menggambar SATU dokumen proyek, bingkai demi bingkai.
 *
 * Berkas ini dijalankan di dua tempat: Remotion Player di peramban (pratinjau)
 * dan Chrome headless di Mesin Montase (render). Itulah prinsip P-2 di
 * JOB-4.md: tidak ada jalur kode kedua yang bisa membuat pratinjau berbeda
 * dari hasil akhirnya.
 *
 * Aturan untuk SELURUH folder `komposisi/`: hanya boleh mengimpor `react`,
 * `remotion`, `@remotion/media`, dan `zod`, ditambah berkas lain di folder ini.
 * `montase-mesin/src/bundel.mjs` membundelnya dengan alias ke node_modules
 * milik mesin, dan paket lain tidak ada di sana. Tes
 * `backend/tests/test_montase_batas.py` menjaga aturan ini.
 *
 * Props:
 *   dokumen  dokumen proyek (JOB-4.md bagian 16). Semua waktu dalam bingkai.
 *   sumber   alamat yang dipakai untuk memuat bahan dan komponen:
 *            { bahan: {id: url}, komponen: {"id@versi": url} }. Terpisah dari
 *            dokumen karena alamatnya berbeda antara pratinjau (salinan sunting,
 *            token peramban) dan render (berkas asli, token mesin), sementara
 *            dokumennya sama persis.
 */
import React from 'react';
import { AbsoluteFill, Freeze, Sequence, useCurrentFrame } from 'remotion';
import ItemAudio from './item/ItemAudio.jsx';
import ItemGambar from './item/ItemGambar.jsx';
import ItemMotion from './item/ItemMotion.jsx';
import ItemTeks from './item/ItemTeks.jsx';
import ItemVideo from './item/ItemVideo.jsx';
import { gayaTransisi, rencanaTransisi } from './transisi.js';

export const ID_KOMPOSISI = 'Montase';

const PENGGAMBAR = {
  video: ItemVideo,
  gambar: ItemGambar,
  teks: ItemTeks,
  motion: ItemMotion,
  audio: ItemAudio,
};

/** Ukuran kanvas dan durasi dari dokumen, dengan bawaan Shorts 30 fps. */
export function ukuranDokumen(dokumen) {
  const k = dokumen?.kanvas ?? {};
  return {
    lebar: k.lebar ?? 1080,
    tinggi: k.tinggi ?? 1920,
    fps: k.fps ?? 30,
    durasi: Math.max(1, Math.round(dokumen?.durasi ?? 1)),
  };
}

/** Gaya transisi di sekeliling item, plus lapisan putih untuk transisi kilat. */
function LapisTransisi({ rencana, children }) {
  const frame = useCurrentFrame();
  const { gaya, kilat } = gayaTransisi(rencana, frame);
  return (
    <AbsoluteFill>
      <AbsoluteFill style={gaya}>{children}</AbsoluteFill>
      {kilat > 0 && <AbsoluteFill style={{ backgroundColor: '#ffffff', opacity: kilat }} />}
    </AbsoluteFill>
  );
}

function Lajur({ lajur, sumber, fps, dokumen }) {
  // Lajur audio tidak digambar tapi tetap dipasang: suaranya berasal dari
  // komponennya. Lajur gambar yang disembunyikan tidak dipasang sama sekali,
  // jadi suaranya ikut hilang (sama dengan CapCut).
  if (lajur.sembunyi && lajur.jenis !== 'audio') return null;
  // Urut waktu: item yang masuk lewat transisi tergambar di atas yang keluar.
  const urut = (lajur.item ?? [])
    .filter((item) => PENGGAMBAR[item.jenis] && item.durasi > 0)
    .slice()
    .sort((a, b) => (a.mulai ?? 0) - (b.mulai ?? 0));
  const rencana = lajur.jenis === 'audio' ? new Map() : rencanaTransisi(urut);
  return (
    <AbsoluteFill>
      {urut.map((item) => {
        const Gambar = PENGGAMBAR[item.jenis];
        const r = rencana.get(item.id);
        // Video dipasang satu detik lebih awal supaya dekodernya sudah
        // siap saat gilirannya tiba. Tanpa ini pratinjau tersendat di
        // setiap sambungan potongan.
        const premount = item.jenis === 'video' || item.jenis === 'audio' ? fps : 0;
        const isi = <Gambar item={item} lajur={lajur} sumber={sumber} dokumen={dokumen} />;
        if (!r || (!r.masuk && !r.keluar)) {
          return (
            <Sequence key={item.id} name={item.id} from={item.mulai ?? 0} durationInFrames={item.durasi}
                      premountFor={premount}
            >
              {isi}
            </Sequence>
          );
        }
        // Diperpanjang `pra` bingkai sebelum dan `pasca` sesudah untuk jendela
        // transisi; di perpanjangan itu item menahan bingkai pertama/terakhirnya.
        return (
          <Sequence key={item.id} name={item.id} from={(item.mulai ?? 0) - r.pra}
                    durationInFrames={item.durasi + r.pra + r.pasca} premountFor={premount}
          >
            <LapisTransisi rencana={r}>
              <Freeze frame={r.pra} active={(f) => f < r.pra}>
                <Freeze frame={r.pra + item.durasi - 1} active={(f) => f >= r.pra + item.durasi}>
                  <Sequence from={r.pra} durationInFrames={item.durasi}>{isi}</Sequence>
                </Freeze>
              </Freeze>
            </LapisTransisi>
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
}

export function Komposisi({ dokumen, sumber }) {
  const { fps } = ukuranDokumen(dokumen);
  const latar = dokumen?.kanvas?.latar ?? '#000000';
  return (
    <AbsoluteFill style={{ backgroundColor: latar }}>
      {(dokumen?.lajur ?? []).map((lajur) => (
        <Lajur key={lajur.id} lajur={lajur} sumber={sumber ?? {}} fps={fps} dokumen={dokumen} />
      ))}
    </AbsoluteFill>
  );
}
