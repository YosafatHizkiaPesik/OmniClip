/**
 * Memuat font bawaan untuk item teks (JOB-4 M3.1), di pratinjau dan render.
 *
 * Font dimuat dengan FontFace dari alamat bertoken (`sumber.font`), lalu
 * render ditahan dengan `delayRender` sampai fontnya siap. Tanpa itu bingkai
 * pertama digambar dengan font cadangan peramban dan hurufnya "meloncat" di
 * tengah video hasil ekspor.
 *
 * FontFace didaftarkan TANPA ketebalan (bawaannya 400). Setiap berkas font
 * bawaan hanya punya satu ketebalan, jadi teks harus memintanya dengan
 * ketebalan 400 juga; meminta 800 membuat peramban menebalkan sendiri
 * (huruf palsu tebal) dan hasilnya berbeda antara mesin.
 */
import { useEffect, useState } from 'react';
import { continueRender, delayRender } from 'remotion';

const janji = new Map();
const siap = new Set();

export function muatFont(keluarga, url) {
  if (!janji.has(keluarga)) {
    const face = new FontFace(keluarga, `url(${JSON.stringify(url)})`);
    janji.set(keluarga, face.load()
      .then((f) => {
        document.fonts.add(f);
        siap.add(keluarga);
        return true;
      })
      .catch(() => {
        janji.delete(keluarga);
        return false;
      }));
  }
  return janji.get(keluarga);
}

export function fontSiap(keluarga) {
  return siap.has(keluarga);
}

/** Menahan render sampai `keluarga` termuat. Tanpa alamat: tidak menahan. */
export function useFont(keluarga, url) {
  const [tahan] = useState(() => (keluarga && url && !siap.has(keluarga)
    ? delayRender(`Font ${keluarga}`, { timeoutInMilliseconds: 30000 })
    : null));
  const [, setVersi] = useState(0);
  useEffect(() => {
    if (!keluarga || !url) return undefined;
    let hidup = true;
    let dilepas = false;
    const lepas = () => {
      if (tahan !== null && !dilepas) { dilepas = true; continueRender(tahan); }
    };
    muatFont(keluarga, url).then(() => {
      if (hidup) setVersi((v) => v + 1);
      lepas();
    });
    return () => { hidup = false; lepas(); };
  }, [tahan, keluarga, url]);
}
