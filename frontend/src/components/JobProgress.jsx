import React from 'react';
import { Loader2, CheckCircle2, AlertTriangle, XCircle, X } from 'lucide-react';
import { useT } from '../lib/i18n';

const TAHAP = ['metadata', 'download', 'captions', 'transcribe', 'heuristic', 'gemini',
  'prepare', 'encode', 'persist', 'done'];

/**
 * Menampilkan progres job apa adanya dari server.
 * Tidak ada tahapan atau persentase yang dikarang di sisi klien.
 */
export default function JobProgress({ job, error, onCancel, compact = false }) {
  const t = useT();
  if (error && !job) {
    return (
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center', color: 'var(--accent-red)', fontSize: '0.82rem' }}>
        <AlertTriangle size={15} /> {error.message}
      </div>
    );
  }
  if (!job) return null;

  const { status, progress = 0, message, stage, eta_seconds: eta } = job;
  const pct = Math.round(progress * 100);
  const failed = status === 'failed';
  const cancelled = status === 'cancelled';
  const done = status === 'done';
  const running = status === 'running' || status === 'queued';

  const color = failed ? 'var(--accent-red)' : cancelled ? 'var(--text-muted)'
    : done ? 'var(--entry)' : 'var(--accent-cyan)';

  const Icon = failed ? AlertTriangle : cancelled ? XCircle : done ? CheckCircle2 : Loader2;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '9px', fontSize: '0.82rem', color }}>
        <Icon size={15} className={running ? 'animate-spin' : undefined} style={{ flexShrink: 0 }} />
        <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {message
            || (failed ? (job.error || t('tugas.gagal'))
              : cancelled ? t('tugas.dibatalkan')
                : (TAHAP.includes(stage) && t(`tahap.${stage}`))
                  || (status === 'queued' ? t('tugas.menunggu') : t('tugas.memproses')))}
        </span>
        {running && <span style={{ color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>{pct}%</span>}
        {running && onCancel && (
          <button
            onClick={onCancel}
            aria-label={t('umum.batal')}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', padding: 0 }}
          >
            <X size={15} />
          </button>
        )}
      </div>

      {!compact && (
        // Bilah yang sama dengan kartu Partitur (components/BilahProses.jsx).
        <div className="proses-bilah">
          <span style={{
            width: `${Math.max(2, done ? 100 : pct)}%`,
            ...(running ? {} : { background: color }),
          }} />
        </div>
      )}

      {running && eta > 1 && !compact && (
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          {eta < 60 ? t('tugas.sisa_detik', { n: Math.ceil(eta) }) : t('tugas.sisa_menit', { n: Math.ceil(eta / 60) })}
        </div>
      )}
    </div>
  );
}
