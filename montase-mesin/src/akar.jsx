/**
 * Titik masuk bundel render. Satu-satunya komposisi adalah `Montase`, yang
 * menggambar dokumen proyek apa pun dari props. Ukuran, fps, dan durasinya
 * dihitung dari dokumen itu (`calculateMetadata`), jadi satu bundel melayani
 * semua proyek.
 *
 * Kode komposisinya TIDAK ada di sini: ia tinggal di
 * frontend/src/features/montase/komposisi/ dan dipakai bersama Player.
 */
import React from 'react';
import { Composition, registerRoot } from 'remotion';
import {
  ID_KOMPOSISI,
  Komposisi,
  ukuranDokumen,
} from '../../frontend/src/features/montase/komposisi/index.js';

function Akar() {
  return (
    <Composition
      id={ID_KOMPOSISI}
      component={Komposisi}
      width={1080}
      height={1920}
      fps={30}
      durationInFrames={1}
      defaultProps={{ dokumen: null, sumber: {} }}
      calculateMetadata={({ props }) => {
        const u = ukuranDokumen(props.dokumen);
        return { width: u.lebar, height: u.tinggi, fps: u.fps, durationInFrames: u.durasi };
      }}
    />
  );
}

registerRoot(Akar);
