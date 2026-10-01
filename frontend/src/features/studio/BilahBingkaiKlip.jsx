import React, { useEffect, useRef, useState } from 'react';

/**
 * Bilah kemajuan untuk perhitungan bingkai SATU klip yang sedang dibuka.
 *
 * Diminta pemiliknya 30 September 2026: "bisakah kamu menambahkan progress bar
 * kecil untuk membuat bingkai karena saya tidak tahu hingga kapan bingkai akan
 * selesai". Sebelum ini yang ada hanya kalimat "mencari kamera wajah pemain…"
 * yang menetap tanpa tanda apa pun, dan pada klip 80 detik itu setengah menit
 * tanpa cara membedakannya dari macet.
 *
 * Bilahnya berdasar PERKIRAAN, dan menyebut dirinya perkiraan.
 *
 * Pemindaian dikerjakan satu panggilan yang menjawab saat selesai; ia tidak
 * mengabarkan kemajuannya di tengah jalan. Menyambungkan kabar per jendela
 * sampai ke layar berarti mengubah jalur itu jadi pekerjaan berantre dengan
 * alirannya sendiri, dan itu perubahan yang jauh lebih besar daripada yang
 * ditanyakan. Jadi yang dipakai adalah lama yang benar-benar terukur di mesin
 * pemiliknya:
 *
 *   klip 10 dtk -> 11,6 dtk     klip 45 dtk -> 20,2 dtk
 *   klip 20 dtk -> 10,5 dtk     klip 80 dtk -> 34,1 dtk
 *
 * yang jatuh di sekitar `6 + 0,36 x panjang klip`.
 *
 * Dua aturan menjaganya tetap jujur. Ia tidak pernah mencapai 100% sendiri —
 * berhenti di 95% dan menunggu hasil yang sebenarnya — dan begitu lewat dari
 * perkiraan ia mengatakannya, bukan diam-diam menahan bilahnya.
 */

const TETAP = 6.0;         // detik, biaya membuka dan menyiapkan berkasnya
const PER_DETIK = 0.36;    // detik pemindaian per detik klip

function lamanya(d) {
  const s = Math.max(0, Math.round(d));
  return s < 60 ? `${s} dtk` : `${Math.floor(s / 60)} mnt ${s % 60} dtk`;
}

export default function BilahBingkaiKlip({ aktif, panjangKlip = 0, label }) {
  const [berjalan, setBerjalan] = useState(0);
  const mulaiRef = useRef(0);

  useEffect(() => {
    if (!aktif) { setBerjalan(0); return undefined; }
    mulaiRef.current = Date.now();
    setBerjalan(0);
    const jam = setInterval(() => {
      setBerjalan((Date.now() - mulaiRef.current) / 1000);
    }, 200);
    return () => clearInterval(jam);
  }, [aktif]);

  if (!aktif) return null;

  const kira = TETAP + PER_DETIK * Math.max(0, panjangKlip);
  const lewat = berjalan > kira;
  const persen = lewat ? 95 : Math.min(95, (berjalan / Math.max(1, kira)) * 95);
  const sisa = Math.max(0, kira - berjalan);

  return (
    <div className="bingkai-kira" role="status" aria-live="polite">
      <div className="bingkai-kira-teks">
        <span>{label || 'Menghitung bingkai klip ini…'}</span>
        <span className="tc">
          {lewat
            ? `lebih lama dari biasanya · ${lamanya(berjalan)}`
            : `kira-kira ${lamanya(sisa)} lagi`}
        </span>
      </div>
      <div className="bingkai-kira-alur">
        <div className="bingkai-kira-isi" style={{ width: `${persen}%` }} />
      </div>
    </div>
  );
}
