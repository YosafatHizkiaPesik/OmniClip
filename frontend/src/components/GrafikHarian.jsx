import React, { useMemo, useRef, useState } from 'react';

/**
 * Tayangan yang DITAMBAH tiap hari, bukan totalnya.
 *
 * Total kumulatif selalu naik, jadi grafiknya selalu terlihat bagus walau
 * tidak ada satu pun orang yang menonton sejak minggu lalu. Yang menjawab
 * "video saya jalan atau tidak" adalah tambahannya.
 *
 * Satu deret, jadi tidak ada legenda: judulnya sendiri yang menyebut apa yang
 * digambar. Angka tidak ditulis di tiap titik; yang ditulis hanya titik
 * tertinggi dan yang sedang disentuh.
 *
 * Datanya dicatat OmniClip sendiri sekali sehari, karena YouTube Data API
 * hanya memberi angka saat ini dan tidak punya riwayat sama sekali. Jadi
 * grafik ini tidak bisa memberi masa lalu, dan itu dikatakan apa adanya alih-
 * alih digambar sebagai garis datar yang seolah berarti "tidak ada penonton".
 */

const H = 180;          // tinggi bidang gambar
const ATAS = 16;
const BAWAH = 26;
const KIRI = 44;
const KANAN = 12;

const tanggalPendek = (iso) => {
  const d = new Date(`${iso}T00:00:00`);
  return Number.isNaN(d.getTime()) ? iso
    : d.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' });
};

export default function GrafikHarian({ harian, helpText }) {
  const wrapRef = useRef(null);
  const [lebar, setLebar] = useState(680);
  const [sorot, setSorot] = useState(null);

  React.useEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const obs = new ResizeObserver(([e]) => {
      const w = e.contentRect.width;
      if (w > 0) setLebar(w);
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // Hari pertama tidak punya pembanding, jadi tambahannya tidak diketahui.
  const titik = useMemo(
    () => (harian || []).filter((d) => typeof d.tambahan === 'number'),
    [harian],
  );

  const geo = useMemo(() => {
    if (titik.length < 2) return null;
    const maks = Math.max(1, ...titik.map((d) => d.tambahan));
    const w = Math.max(320, lebar);
    const px = (i) => KIRI + (i * (w - KIRI - KANAN)) / Math.max(1, titik.length - 1);
    const py = (v) => ATAS + (1 - v / maks) * (H - ATAS - BAWAH);
    return { maks, w, px, py };
  }, [titik, lebar]);

  if ((harian || []).length === 0) {
    return (
      <p style={helpText}>
        Grafiknya belum punya data. OmniClip mencatat tayangan sekali sehari,
        jadi garisnya mulai terbentuk setelah halaman ini dibuka pada dua hari
        yang berbeda.
      </p>
    );
  }
  if (!geo) {
    const satu = harian[harian.length - 1];
    return (
      <p style={helpText}>
        Baru satu hari tercatat ({tanggalPendek(satu.tanggal)}, total{' '}
        <b>{satu.total}</b> tayangan). Besok garisnya mulai terbentuk. Riwayat
        sebelum hari ini tidak ada: YouTube Data API hanya memberi angka saat
        ini, tanpa masa lalu.
      </p>
    );
  }

  const { maks, w, px, py } = geo;
  const garis = titik.map((d, i) => `${i ? 'L' : 'M'}${px(i).toFixed(1)},${py(d.tambahan).toFixed(1)}`).join(' ');
  const isi = `${garis} L${px(titik.length - 1).toFixed(1)},${py(0).toFixed(1)} L${px(0).toFixed(1)},${py(0).toFixed(1)} Z`;
  const puncak = titik.reduce((a, b, i) => (b.tambahan > titik[a].tambahan ? i : a), 0);

  const sentuh = (e) => {
    const kotak = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - kotak.left;
    let dekat = 0;
    for (let i = 1; i < titik.length; i += 1) {
      if (Math.abs(px(i) - x) < Math.abs(px(dekat) - x)) dekat = i;
    }
    setSorot(dekat);
  };

  const aktif = sorot === null ? null : titik[sorot];

  return (
    <div ref={wrapRef} style={{ width: '100%' }}>
      <svg width="100%" height={H} viewBox={`0 0 ${w} ${H}`} role="img"
           aria-label={`Tambahan tayangan per hari, ${titik.length} hari, tertinggi ${titik[puncak].tambahan}`}
           onMouseMove={sentuh} onMouseLeave={() => setSorot(null)}
           style={{ display: 'block', touchAction: 'none' }}>
        {/* Garis bantu recessive: tiga saja, dan tidak menuntut perhatian. */}
        {[0, 0.5, 1].map((f) => (
          <g key={f}>
            <line x1={KIRI} x2={w - KANAN} y1={py(maks * f)} y2={py(maks * f)}
                  stroke="var(--rule-2)" strokeWidth="1" />
            <text x={KIRI - 8} y={py(maks * f) + 4} textAnchor="end"
                  fill="var(--text-muted)" fontSize="10"
                  style={{ fontVariantNumeric: 'tabular-nums' }}>
              {Math.round(maks * f)}
            </text>
          </g>
        ))}

        <path d={isi} fill="var(--reh)" opacity="0.12" />
        <path d={garis} fill="none" stroke="var(--reh)" strokeWidth="2"
              strokeLinejoin="round" strokeLinecap="round" />

        {titik.map((d, i) => (
          <circle key={d.tanggal} cx={px(i)} cy={py(d.tambahan)}
                  r={sorot === i ? 5 : 3.5}
                  fill="var(--reh)" stroke="var(--plate)" strokeWidth="2" />
        ))}

        {/* Hanya puncaknya yang diberi angka tetap. Angka di tiap titik membuat
            grafik jadi tabel yang digambar. */}
        {sorot === null && (
          <text x={px(puncak)} y={py(titik[puncak].tambahan) - 10} textAnchor="middle"
                fill="var(--text-primary)" fontSize="11" fontWeight="800"
                style={{ fontVariantNumeric: 'tabular-nums' }}>
            +{titik[puncak].tambahan}
          </text>
        )}

        {aktif && (
          <>
            <line x1={px(sorot)} x2={px(sorot)} y1={ATAS} y2={py(0)}
                  stroke="var(--text-muted)" strokeWidth="1" strokeDasharray="3 3" />
            <text x={Math.min(Math.max(px(sorot), KIRI + 40), w - KANAN - 40)}
                  y={ATAS - 3} textAnchor="middle"
                  fill="var(--text-primary)" fontSize="11" fontWeight="800">
              {tanggalPendek(aktif.tanggal)}: +{aktif.tambahan}
            </text>
          </>
        )}

        <text x={KIRI} y={H - 8} fill="var(--text-muted)" fontSize="10">
          {tanggalPendek(titik[0].tanggal)}
        </text>
        <text x={w - KANAN} y={H - 8} textAnchor="end"
              fill="var(--text-muted)" fontSize="10">
          {tanggalPendek(titik[titik.length - 1].tanggal)}
        </text>
      </svg>
      <p style={{ ...helpText, marginTop: 6 }}>
        Tambahan tayangan tiap hari di seluruh kanal, dicatat OmniClip sendiri.
        Hari yang aplikasinya tidak dibuka tidak tercatat, dan hari seperti itu
        dilewati, bukan dianggap nol.
      </p>
    </div>
  );
}
