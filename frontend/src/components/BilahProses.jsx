import React, { useEffect, useState } from 'react';
import { AudioLines, Check, Download, Hourglass, ListChecks, ScanSearch, Sparkles } from 'lucide-react';
import { useT } from '../lib/i18n';

/**
 * Kemajuan pekerjaan klip: satu langkah yang jelas, bukan lima hal kecil.
 *
 * Versi sebelumnya menumpuk judul "Sedang diproses", lima bilah tipis dengan
 * lima label mungil, baris "Tahap 1/5 · Unduh · Mengunduh video… 47%", baris
 * waktu, dan untuk tahap AI satu paragraf penjelasan. Nama tahapnya muncul
 * tiga kali. Dilaporkan pemiliknya 28 Oktober 2026: "tampilan loading
 * tersebut kurang menarik karena ada beberapa tampilan proses loading menjadi
 * satu mulai dari unduh proses dll".
 *
 * Sekarang: stepper lima titik (selesai, sedang, belum), SATU baris nama
 * langkah beserta persennya, satu baris detail dari server, satu baris waktu.
 * Gambar mini kartunya mendapat `LapisProses`: cincin persen besar.
 *
 * Rentang tahap SAMA dengan STAGES di backend/app/services/pipeline.py.
 */
// `label` dan `judul` adalah kunci kamus. Tahap AI tidak bernama "Gemini":
// sejak 17 Oktober 2026 pemilihnya bisa koneksi AI mana pun.
export const TAHAP = [
  { label: 'proses.unduh', judul: 'proses.j_unduh', Ikon: Download, stages: ['resolve', 'download'], lo: 0.0, hi: 0.45 },
  { label: 'proses.transkrip', judul: 'proses.j_transkrip', Ikon: AudioLines, stages: ['captions', 'transcribe'], lo: 0.45, hi: 0.8 },
  { label: 'proses.analisis', judul: 'proses.j_analisis', Ikon: ScanSearch, stages: ['analyze'], lo: 0.8, hi: 0.92 },
  { label: 'proses.ai', judul: 'proses.j_ai', Ikon: Sparkles, stages: ['gemini'], lo: 0.92, hi: 0.98 },
  { label: 'proses.simpan', judul: 'proses.j_simpan', Ikon: ListChecks, stages: ['persist', 'done'], lo: 0.98, hi: 1.0 },
];

// Tahap yang isinya menunggu pihak lain: kemajuannya tidak terukur.
const MENUNGGU = new Set(['gemini']);

function jam(detik) {
  const d = Math.max(0, Math.round(detik));
  const m = Math.floor(d / 60);
  return `${m}:${String(d % 60).padStart(2, '0')}`;
}

/** Keadaan yang sama untuk stepper dan lapisan gambar mini. */
export function keadaanProses(job) {
  const progress = Math.max(0, Math.min(1, job?.progress ?? 0));
  let aktif = TAHAP.findIndex((th) => th.stages.includes(job?.stage));
  if (aktif < 0) aktif = TAHAP.findIndex((th) => progress < th.hi);
  if (aktif < 0) aktif = TAHAP.length - 1;
  const tahap = TAHAP[aktif];
  const bagian = Math.max(0, Math.min(1, (progress - tahap.lo) / (tahap.hi - tahap.lo)));
  const jalan = job && (job.status === 'running' || job.status === 'queued');
  return {
    progress, aktif, tahap, bagian, jalan,
    antre: job?.status === 'queued',
    menunggu: !!jalan && MENUNGGU.has(job?.stage),
  };
}

function useDetik(jalan) {
  const [kini, setKini] = useState(() => Date.now() / 1000);
  useEffect(() => {
    if (!jalan) return undefined;
    const jeda = setInterval(() => setKini(Date.now() / 1000), 1000);
    return () => clearInterval(jeda);
  }, [jalan]);
  return kini;
}

/**
 * Pesan server tanpa ulangan: "Mengunduh video… 47% · 18,2 MB/dtk" sudah
 * diwakili judul langkah dan persennya, jadi yang tersisa "18,2 MB/dtk".
 */
export function detailPesan(pesan) {
  if (!pesan) return '';
  const s = String(pesan).trim();
  const m = s.match(/^(.*?)(?:…|\.\.\.)\s*(.*)$/);
  if (!m) return s;
  // Sesudah "…" ada angka yang sudah tampil sebagai persen langkah.
  const sesudah = m[2].replace(/^\d+(?:[.,]\d+)?%\s*(?:·\s*)?/, '').trim();
  return sesudah || m[1].trim();
}

export default function BilahProses({ job, ringkas = false }) {
  const t = useT();
  const k = keadaanProses(job);
  const kini = useDetik(k.jalan);
  if (!job) return null;
  const { aktif, tahap, menunggu, antre } = k;
  const lama = job.started_at ? kini - job.started_at : null;
  // SATU angka: kemajuan total, sama dengan cincin di gambar mini. Dulu di
  // sini persen langkahnya sendiri, jadi kartu yang sama menulis "5%" di
  // gambar dan "11%" di bawahnya. Dilaporkan pemiliknya 28 Oktober 2026.
  // Langkahnya sudah terbaca dari stepper dan baris detail.
  const persen = Math.round(k.progress * 100);
  const detail = antre ? '' : detailPesan(job.message);
  const IkonAktif = antre ? Hourglass : tahap.Ikon;

  return (
    <div className="proses" aria-live="polite">
      <ol className="proses-langkah" aria-label={t('proses.tahap', { n: aktif + 1, total: TAHAP.length, nama: t(tahap.label) })}>
        {TAHAP.map((th, i) => {
          const keadaan = antre ? 'belum' : i < aktif ? 'lewat' : i === aktif ? 'aktif' : 'belum';
          return (
            <li key={th.label} className={`proses-titik is-${keadaan}`} title={t(th.label)}>
              <span className="proses-bulat">
                {keadaan === 'lewat' ? <Check size={11} strokeWidth={3} /> : <th.Ikon size={11} strokeWidth={2.4} />}
              </span>
              {i < TAHAP.length - 1 && (
                <span className="proses-garis">
                  <span style={{ width: `${keadaan === 'lewat' ? 100 : 0}%` }} />
                </span>
              )}
            </li>
          );
        })}
      </ol>

      <div className="proses-kepala">
        <IkonAktif size={14} className="proses-ikon" />
        <span className="proses-judul">{antre ? t('proses.menunggu') : t(tahap.judul)}</span>
        {!antre && (
          <span className="proses-persen" title={menunggu ? t('proses.gemini_ket') : t('proses.total')}>
            {menunggu ? t('proses.menanti') : `${persen}%`}
          </span>
        )}
      </div>

      {!antre && (
        <div className={`proses-bilah${menunggu ? ' is-menunggu' : ''}`}>
          <span className={menunggu ? 'bilah-menunggu' : undefined}
                style={{ width: menunggu ? '100%' : `${Math.max(2, persen)}%` }} />
        </div>
      )}

      {!ringkas && detail && <div className="proses-detail" title={job.message}>{detail}</div>}

      {!ringkas && k.jalan && lama != null && (
        <div className="proses-waktu">
          {t('proses.berjalan', { n: jam(lama) })}
          {!menunggu && job.eta_seconds > 1 && t('proses.sisa', { n: jam(job.eta_seconds) })}
          {menunggu && <span title={t('proses.gemini_ket')}>{t('proses.gemini_singkat')}</span>}
        </div>
      )}
    </div>
  );
}

/**
 * Lapisan di atas gambar mini kartu yang sedang diproses: cincin persen
 * keseluruhan dan nama langkahnya, terbaca dari jauh di antara kartu lain.
 */
export function LapisProses({ job }) {
  const t = useT();
  const k = keadaanProses(job);
  if (!job || !k.jalan) return null;
  const R = 22;
  const keliling = 2 * Math.PI * R;
  const persen = Math.round(k.progress * 100);
  return (
    <div className="proses-lapis" aria-hidden="true">
      <div className={`proses-cincin${k.menunggu || k.antre ? ' is-putar' : ''}`}>
        <svg viewBox="0 0 56 56" width="56" height="56">
          <circle cx="28" cy="28" r={R} className="proses-cincin-alas" />
          <circle cx="28" cy="28" r={R} className="proses-cincin-isi"
                  strokeDasharray={keliling}
                  strokeDashoffset={k.antre ? keliling * 0.75 : keliling * (1 - Math.max(0.02, k.progress))} />
        </svg>
        <span>{k.antre ? <Hourglass size={16} /> : `${persen}%`}</span>
      </div>
      <div className="proses-lapis-teks">
        {k.antre ? t('proses.menunggu') : t(k.tahap.judul)}
      </div>
    </div>
  );
}
