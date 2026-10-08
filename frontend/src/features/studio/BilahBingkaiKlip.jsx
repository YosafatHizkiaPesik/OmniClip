import React, { useEffect, useRef, useState } from 'react';
import { apiGet } from '../../lib/api';

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
  // Kemajuan SUNGGUHAN dari pemindainya: langkah keberapa dari berapa.
  // Perkiraan di bawah hanya dipakai selama jawaban itu belum ada.
  const [nyata, setNyata] = useState(null);
  const mulaiRef = useRef(0);

  useEffect(() => {
    if (!aktif) { setBerjalan(0); setNyata(null); return undefined; }
    mulaiRef.current = Date.now();
    setBerjalan(0);
    const jam = setInterval(() => {
      setBerjalan((Date.now() - mulaiRef.current) / 1000);
    }, 200);
    let batal = false;
    const tanya = () => {
      apiGet('/clip-bingkai/kemajuan')
        .then((k) => { if (!batal) setNyata(k?.segar ? k : null); })
        .catch(() => { if (!batal) setNyata(null); });
    };
    tanya();
    const jamTanya = setInterval(tanya, 1000);
    return () => { batal = true; clearInterval(jam); clearInterval(jamTanya); };
  }, [aktif]);

  if (!aktif) return null;

  // Dengan kemajuan sungguhan, sisa waktunya DIHITUNG dari laju yang sedang
  // terjadi, bukan dari rumus: (lama berjalan / bagian yang sudah selesai)
  // dikali bagian yang tersisa. Itu angka yang benar-benar berubah mengikuti
  // kenyataan — melambat saat mesin sibuk, mempercepat saat lega.
  let persen;
  let kanan;
  if (nyata && nyata.total > 0 && nyata.selesai > 0) {
    const bagian = Math.max(0, Math.min(1, nyata.selesai / nyata.total));
    persen = Math.min(99, bagian * 100);
    const sisaDetik = berjalan * (1 - bagian) / Math.max(0.02, bagian);
    kanan = `${Math.round(nyata.selesai)}/${Math.round(nyata.total)} · `
          + `${lamanya(sisaDetik)} lagi`;
  } else {
    const kira = TETAP + PER_DETIK * Math.max(0, panjangKlip);
    const lewat = berjalan > kira;
    persen = lewat ? 95 : Math.min(95, (berjalan / Math.max(1, kira)) * 95);
    kanan = lewat ? `berjalan ${lamanya(berjalan)}` : 'menyiapkan…';
  }

  const tahap = nyata?.tahap
    ? (nyata.tahap === 'kamera wajah' ? 'Mencari kamera wajah pemain…'
                                      : 'Melacak wajah di klip ini…')
    : (label || 'Menghitung bingkai klip ini…');

  return (
    <div className="bingkai-kira" role="status" aria-live="polite">
      <div className="bingkai-kira-teks">
        <span>{tahap}</span>
        <span className="tc">{kanan}</span>
      </div>
      <div className="bingkai-kira-alur">
        <div className="bingkai-kira-isi" style={{ width: `${persen}%` }} />
      </div>
    </div>
  );
}
