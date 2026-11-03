// Komponen uji M0.5, ditulis Claude (lewat Claude Code) persis seperti balasan
// yang diharapkan dari AI: satu berkas, mengikuti kontrak JOB-4.md bagian 21.
// Permintaannya: "Teks 'GILA!' memantul masuk, berguncang, lalu pecah jadi
// serpihan yang terbang ke segala arah."
import { AbsoluteFill, interpolate, random, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { z } from 'zod';

export const skema = z.object({
  teks: z.string().max(20),
  warna: z.string().regex(/^#[0-9a-fA-F]{6}$/),
  serpihan: z.number().int().min(4).max(40),
});

export const contohProps = { teks: 'GILA!', warna: '#FFD400', serpihan: 18 };
export const durasiBawaan = 75;
export const kategori = 'reaksi';

type Props = z.infer<typeof skema>;

export default function TeksPecah({ teks, warna, serpihan }: Props) {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const pecahPada = Math.round(durationInFrames * 0.6);
  const masuk = spring({ frame, fps, config: { damping: 8, stiffness: 180 } });
  const guncang = frame < pecahPada ? Math.sin(frame * 2.3) * 6 * masuk : 0;
  const sesudahPecah = Math.max(0, frame - pecahPada);
  const pudar = interpolate(sesudahPecah, [0, durationInFrames - pecahPada], [1, 0], {
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
      {frame < pecahPada ? (
        <div
          style={{
            fontFamily: 'sans-serif',
            fontWeight: 900,
            fontSize: 220,
            color: warna,
            transform: `translateX(${guncang}px) scale(${masuk})`,
            textShadow: '0 10px 0 rgba(0,0,0,0.45)',
            WebkitTextStroke: '6px #000000',
          }}
        >
          {teks}
        </div>
      ) : (
        Array.from({ length: serpihan }, (_, i) => {
          const sudut = random(`sudut-${i}`) * Math.PI * 2;
          const laju = 18 + random(`laju-${i}`) * 26;
          const ukuran = 30 + random(`ukuran-${i}`) * 50;
          return (
            <div
              key={i}
              style={{
                position: 'absolute',
                width: ukuran,
                height: ukuran,
                background: warna,
                border: '5px solid #000000',
                opacity: pudar,
                transform: `translate(${Math.cos(sudut) * laju * sesudahPecah}px, ${Math.sin(sudut) * laju * sesudahPecah + 2 * sesudahPecah * sesudahPecah}px) rotate(${sesudahPecah * (8 + i)}deg)`,
              }}
            />
          );
        })
      )}
    </AbsoluteFill>
  );
}
