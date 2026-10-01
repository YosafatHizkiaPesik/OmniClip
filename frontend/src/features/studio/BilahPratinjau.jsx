import React, { useEffect, useRef, useState } from 'react';
import { Loader2, CheckCircle2 } from 'lucide-react';

/**
 * Kabar saat salinan pratinjau sedang disiapkan, dan saat ia siap diputar.
 *
 * Diminta pemiliknya 1 Oktober 2026: "saat video sedang diproses tunjukan
 * progres atau apapun itu barulah setelah siap beritahu user bahwa video siap
 * diputar".
 *
 * Server sudah melaporkan keduanya sejak lama — `pratinjau_disiapkan` dan
 * `pratinjau_kemajuan` di `GET /api/projects/{id}` — dan Editor sudah
 * memantaunya tiap delapan detik. Yang tidak ada hanyalah tempat untuk
 * menampilkannya, jadi pengguna menunggu tanpa tahu bahwa ada yang sedang
 * dikerjakan, lalu videonya tiba-tiba berganti sendiri di tengah menonton.
 *
 * Kabar "siap" ditahan beberapa detik lalu hilang: pemberitahuan yang menetap
 * di layar sesudah peristiwanya lewat berubah jadi perabot.
 */

const TAHAN_SIAP = 6000;

export default function BilahPratinjau({ disiapkan = false, kemajuan = null }) {
  const [siap, setSiap] = useState(false);
  const sebelum = useRef(disiapkan);

  useEffect(() => {
    // Yang menandai selesai adalah PERALIHAN dari sedang-disiapkan ke tidak,
    // bukan keadaan "tidak disiapkan" — yang juga berlaku untuk video yang
    // memang tidak pernah butuh salinan.
    if (sebelum.current && !disiapkan) {
      setSiap(true);
      const t = setTimeout(() => setSiap(false), TAHAN_SIAP);
      sebelum.current = disiapkan;
      return () => clearTimeout(t);
    }
    sebelum.current = disiapkan;
    return undefined;
  }, [disiapkan]);

  if (!disiapkan && !siap) return null;

  const persen = Number.isFinite(kemajuan) ? Math.round(kemajuan * 100) : null;
  return (
    <div style={{
      border: '1px solid var(--border-color)', borderRadius: 'var(--r-sm)',
      padding: '9px 11px', marginBottom: '10px', background: 'var(--plate-3)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '9px', fontSize: '.8rem' }}>
        {disiapkan
          ? <Loader2 size={13} className="animate-spin" style={{ color: 'var(--reh)', flex: 'none' }} />
          : <CheckCircle2 size={13} style={{ color: 'var(--entry)', flex: 'none' }} />}
        <span style={{ color: 'var(--ink-2)', flex: 1, minWidth: 0 }}>
          {disiapkan
            ? 'Menyiapkan salinan video untuk pratinjau…'
            : 'Salinan pratinjau siap. Videonya sekarang berjalan lancar.'}
        </span>
        {disiapkan && persen !== null && (
          <span style={{ color: 'var(--ink-2)', fontVariantNumeric: 'tabular-nums',
                         flex: 'none' }}>{persen}%</span>
        )}
      </div>
      {disiapkan && (
        <>
          <div style={{ height: '5px', marginTop: '6px', borderRadius: '99px',
                        background: 'var(--bg-glass)', overflow: 'hidden',
                        border: '1px solid var(--border-color)' }}>
            <div style={{ width: `${Math.max(2, persen ?? 2)}%`, height: '100%',
                          background: 'var(--reh)', transition: 'width .5s' }} />
          </div>
          <p style={{ fontSize: '.71rem', color: 'var(--ink-3)', lineHeight: 1.5,
                      margin: '6px 0 0' }}>
            Sementara ini yang diputar berkas aslinya, dan itu bisa tersendat di
            klip beresolusi tinggi. Begitu salinannya selesai, pemutarnya
            berpindah sendiri tanpa kehilangan posisi Anda.
          </p>
        </>
      )}
    </div>
  );
}
