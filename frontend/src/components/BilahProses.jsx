import React, { useEffect, useState } from 'react';

/**
 * Bilah kemajuan pekerjaan klip, dibagi per TAHAP.
 *
 * Dulu kartu menulis dua angka sekaligus: persen keseluruhan, dan persen tahap
 * yang ada di dalam pesannya ("Mengunduh… 80%", lalu "Menyalin ucapan… 10%").
 * Yang terbaca oleh pengguna adalah angka yang turun. Di sini tiap tahap punya
 * bagiannya sendiri dan mengisinya sendiri: yang sudah lewat (atau dilewati
 * karena video dan transkripnya sudah ada) penuh, dan menunggu jawaban Gemini — yang memang tidak bisa diukur — ditampilkan
 * sebagai menunggu dengan hitungan detik, bukan persen karangan.
 *
 * Rentangnya SAMA dengan STAGES di backend/app/services/pipeline.py.
 */
const TAHAP = [
  { label: 'Unduh', stages: ['resolve', 'download'], lo: 0.0, hi: 0.45 },
  { label: 'Transkrip', stages: ['captions', 'transcribe'], lo: 0.45, hi: 0.8 },
  { label: 'Analisis', stages: ['analyze'], lo: 0.8, hi: 0.92 },
  { label: 'Gemini', stages: ['gemini'], lo: 0.92, hi: 0.98 },
  { label: 'Simpan', stages: ['persist', 'done'], lo: 0.98, hi: 1.0 },
];

// Tahap yang isinya menunggu pihak lain: kemajuannya tidak terukur.
const MENUNGGU = new Set(['gemini']);

function jam(detik) {
  const d = Math.max(0, Math.round(detik));
  const m = Math.floor(d / 60);
  return `${m}:${String(d % 60).padStart(2, '0')}`;
}

export default function BilahProses({ job, ringkas = false }) {
  const [kini, setKini] = useState(() => Date.now() / 1000);
  const jalan = job && (job.status === 'running' || job.status === 'queued');
  useEffect(() => {
    if (!jalan) return undefined;
    const t = setInterval(() => setKini(Date.now() / 1000), 1000);
    return () => clearInterval(t);
  }, [jalan]);

  if (!job) return null;
  const progress = Math.max(0, Math.min(1, job.progress ?? 0));
  let aktif = TAHAP.findIndex((t) => t.stages.includes(job.stage));
  if (aktif < 0) aktif = TAHAP.findIndex((t) => progress < t.hi);
  if (aktif < 0) aktif = TAHAP.length - 1;
  const tahap = TAHAP[aktif];
  const bagian = Math.max(0, Math.min(1, (progress - tahap.lo) / (tahap.hi - tahap.lo)));
  const menunggu = jalan && MENUNGGU.has(job.stage);
  const lama = job.started_at ? kini - job.started_at : null;
  const antre = job.status === 'queued';

  return (
    <div style={{ display: 'grid', gap: '6px' }}>
      <div style={{ display: 'grid', gridTemplateColumns: `repeat(${TAHAP.length}, 1fr)`, gap: '3px' }}>
        {TAHAP.map((t, i) => {
          // Tahap sebelum yang aktif sudah lewat (atau dilewati).
          const lewat = i < aktif;
          const isi = lewat ? 1 : i === aktif ? (menunggu ? 1 : bagian) : 0;
          return (
            <div key={t.label} title={t.label}
                 style={{ height: ringkas ? '5px' : '7px', borderRadius: '99px',
                          background: 'var(--bg-glass)', overflow: 'hidden',
                          border: '1px solid var(--border-color)' }}>
              <div className={i === aktif && menunggu ? 'bilah-menunggu' : undefined}
                   style={{
                     width: `${isi * 100}%`, height: '100%',
                     background: i === aktif && menunggu ? undefined : 'var(--reh, var(--accent-cyan))',
                     transition: 'width .4s cubic-bezier(.16,1,.3,1)',
                   }} />
            </div>
          );
        })}
      </div>
      {!ringkas && (
        <div style={{ display: 'grid', gridTemplateColumns: `repeat(${TAHAP.length}, 1fr)`, gap: '3px' }}>
          {TAHAP.map((t, i) => (
            <span key={t.label} style={{
              fontSize: '0.62rem', textAlign: 'center', fontWeight: i === aktif ? 800 : 500,
              color: i === aktif ? 'var(--text-primary)' : 'var(--text-muted)',
            }}>{t.label}</span>
          ))}
        </div>
      )}
      <div style={{ fontSize: '0.71rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
        <b style={{ color: 'var(--text-primary)' }}>
          {antre ? 'Menunggu giliran' : `Tahap ${aktif + 1}/${TAHAP.length} · ${tahap.label}`}
        </b>
        {!antre && !menunggu && !/\d%/.test(job.message || '') && ` ${Math.round(bagian * 100)}%`}
        {job.message ? ` · ${job.message}` : ''}
      </div>
      {jalan && lama != null && (
        <div style={{ fontSize: '0.66rem', color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>
          berjalan {jam(lama)}
          {!menunggu && job.eta_seconds > 1 && ` · perkiraan sisa ${jam(job.eta_seconds)}`}
          {menunggu && ' · menunggu jawaban Gemini (biasanya 1-3 menit; bila tidak ada jawaban, mesin lokal yang dipakai)'}
        </div>
      )}
    </div>
  );
}
