import React from 'react';
import { Loader2, CheckCircle2, AlertTriangle, XCircle, X } from 'lucide-react';

const STAGE_LABEL = {
  metadata: 'Membaca info video',
  download: 'Mengunduh',
  captions: 'Mengambil transkrip',
  transcribe: 'Menyalin ucapan',
  heuristic: 'Mencari momen menarik',
  gemini: 'Menyusun ulang dengan AI',
  prepare: 'Menyiapkan',
  encode: 'Merender',
  persist: 'Menyimpan',
  done: 'Selesai',
};

/**
 * Menampilkan progres job apa adanya dari server.
 * Tidak ada tahapan atau persentase yang dikarang di sisi klien.
 */
export default function JobProgress({ job, error, onCancel, compact = false }) {
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
    : done ? '#10b981' : 'var(--accent-cyan)';

  const Icon = failed ? AlertTriangle : cancelled ? XCircle : done ? CheckCircle2 : Loader2;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', width: '100%' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '9px', fontSize: '0.82rem', color }}>
        <Icon size={15} className={running ? 'animate-spin' : undefined} style={{ flexShrink: 0 }} />
        <span style={{ flex: 1, minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {message
            || (failed ? (job.error || 'Pekerjaan gagal.')
              : cancelled ? 'Dibatalkan.'
                : STAGE_LABEL[stage] || (status === 'queued' ? 'Menunggu antrean…' : 'Memproses…'))}
        </span>
        {running && <span style={{ color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>{pct}%</span>}
        {running && onCancel && (
          <button
            onClick={onCancel}
            aria-label="Batalkan"
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', padding: 0 }}
          >
            <X size={15} />
          </button>
        )}
      </div>

      {!compact && (
        <div style={{ height: '5px', borderRadius: '99px', background: 'var(--border-color)', overflow: 'hidden' }}>
          <div style={{
            height: '100%',
            width: `${done ? 100 : pct}%`,
            background: color,
            borderRadius: '99px',
            transition: 'width 0.3s ease',
          }} />
        </div>
      )}

      {running && eta > 1 && !compact && (
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          Perkiraan sisa {eta < 60 ? `${Math.ceil(eta)} detik` : `${Math.ceil(eta / 60)} menit`}
        </div>
      )}
    </div>
  );
}
