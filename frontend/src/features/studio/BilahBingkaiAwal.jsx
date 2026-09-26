import React, { useEffect, useRef, useState } from 'react';
import { Loader2, CheckCircle2 } from 'lucide-react';
import { apiGet } from '../../lib/api';

/**
 * Bilah kemajuan penyiapan bingkai untuk SEMUA klip sebuah video.
 *
 * Pekerjaan ini berjalan di latar belakang sesudah auto-klip selesai, dan
 * sampai sekarang tidak ada satu pun tempat di layar yang menunjukkannya.
 * Terlapor dua kali oleh pemiliknya, kalimat yang sama dua kali: "tampilan yang
 * memproses semua klip tidak ada", "sudah menunggu beberapa menit, satu klip
 * pun bingkainya belum tersusun". Keduanya bukan tentang lamanya, melainkan
 * tentang tidak tahu apakah ada yang sedang berjalan.
 *
 * Karena itu bilah ini menyebut ANGKA: klip ke berapa dari berapa, judulnya,
 * persentase, dan sudah berjalan berapa lama. Semua teksnya datang dari server;
 * tidak ada tahapan yang dikarang di sini.
 */
const SELESAI = new Set(['done', 'failed', 'cancelled']);

/** "2 menit 5 detik", untuk lama yang sudah berjalan. */
function lamanya(detik) {
  const d = Math.max(0, Math.round(detik));
  if (d < 60) return `${d} detik`;
  const m = Math.floor(d / 60);
  return `${m} menit ${d % 60} detik`;
}

export default function BilahBingkaiAwal({ videoId }) {
  const [job, setJob] = useState(null);
  const [, paksaGambar] = useState(0);
  const esRef = useRef(null);

  // Satu tanyaan ringan saat dibuka, lalu ikut aliran kabar semua pekerjaan.
  //
  // Versi pertama menjajaki `/api/jobs?limit=40` tiap enam detik selama belum
  // menemukan apa-apa. Terukur pada penyimpanan pemiliknya: jawaban itu 2,4 MB
  // dan makan 0,48 detik, karena tiap baris membawa seluruh daftar klip
  // beserta subtitle-nya. Menariknya berulang kali hanya untuk tahu "apakah
  // ada yang berjalan" adalah beban yang jauh lebih besar daripada
  // pertanyaannya. Aliran SSE-nya sudah ada dan mengabarkan pekerjaan yang
  // baru diantrekan juga, jadi tidak ada yang perlu dijajaki.
  useEffect(() => {
    if (!videoId) return undefined;
    let batal = false;

    // Kabar bisa datang TIDAK BERURUTAN. Terlihat saat mengujinya: untuk satu
    // pekerjaan yang sama, "running 95%" tiba lebih dulu daripada "queued 0%".
    // Dipakai apa adanya, bilahnya melompat mundur ke nol dan terbaca seperti
    // mengulang dari awal. Jadi: satu pekerjaan diikuti sampai selesai, dan di
    // dalamnya kemajuan tidak pernah turun.
    const pakai = (d) => {
      setJob((lama) => {
        if (!lama) return d;
        const sama = (lama.job_id ?? lama.id) === (d.job_id ?? d.id);
        if (!sama) {
          // Pekerjaan lain hanya diambil alih kalau yang lama sudah selesai.
          if (!SELESAI.has(lama.status)) return lama;
          return d;
        }
        if (SELESAI.has(d.status)) return d;
        if ((d.progress ?? 0) < (lama.progress ?? 0)) {
          // Kabar yang tertinggal: pesannya pun sudah usang, jadi keduanya
          // dibuang bersama.
          return lama;
        }
        return d;
      });
    };

    apiGet(`/jobs/aktif?video_id=${encodeURIComponent(videoId)}&type=bingkai_awal`)
      .then((r) => {
        const ada = (r?.jobs || [])[0];
        if (ada && !batal) pakai({ ...ada, job_id: ada.id });
      })
      .catch(() => { /* gagal dibaca bukan alasan menampilkan galat */ });

    const es = new EventSource('/api/jobs/events');
    esRef.current = es;
    es.onmessage = (evt) => {
      if (batal) return;
      let d;
      try { d = JSON.parse(evt.data); } catch { return; }
      if (d.type !== 'bingkai_awal' || d.video_id !== videoId) return;
      pakai(d);
    };
    es.onerror = () => {
      // EventSource menyambung ulang sendiri; hanya penutupan yang final.
      if (es.readyState === EventSource.CLOSED) esRef.current = null;
    };

    return () => {
      batal = true;
      es.close();
      esRef.current = null;
    };
  }, [videoId]);

  // Angka "sudah berjalan" hanya hidup kalau digambar ulang.
  useEffect(() => {
    if (!job || SELESAI.has(job.status)) return undefined;
    const t = setInterval(() => paksaGambar((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, [job?.status]);       // eslint-disable-line react-hooks/exhaustive-deps

  if (!job) return null;
  if (job.status === 'failed' || job.status === 'cancelled') return null;

  const jalan = !SELESAI.has(job.status);
  const antre = job.status === 'queued';
  const persen = Math.round((job.progress ?? 0) * 100);
  // Lama dihitung dari waktu pekerjaannya SENDIRI, bukan dari saat bilah ini
  // pertama melihatnya. Versi pertama memakai `Date.now()` saat komponen
  // pertama kali menerima kabar, jadi menutup lalu membuka Studio membuat
  // angkanya mulai dari nol lagi untuk pekerjaan yang sudah lama berjalan —
  // dilaporkan pemiliknya: "detik menghitungnya mulai dari 0 tapi tetap
  // seperti itu terus".
  const mulai = antre ? job.created_at : (job.started_at || job.created_at);
  const berjalan = mulai ? Math.max(0, Date.now() / 1000 - mulai) : 0;

  return (
    <div style={{
      border: '1px solid var(--border-color)', borderRadius: 'var(--r-sm)',
      padding: '9px 11px', marginBottom: '10px', background: 'var(--plate-3)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '9px', fontSize: '.8rem' }}>
        {jalan
          ? <Loader2 size={13} className="animate-spin" style={{ color: 'var(--reh)', flex: 'none' }} />
          : <CheckCircle2 size={13} style={{ color: 'var(--entry)', flex: 'none' }} />}
        <span style={{ color: 'var(--ink-2)', flex: 1, minWidth: 0, overflow: 'hidden',
                       textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {job.message || 'Menyiapkan bingkai semua klip…'}
        </span>
        {jalan && (
          <span style={{ color: 'var(--ink-2)', fontVariantNumeric: 'tabular-nums',
                         flex: 'none' }}>
            {antre ? 'antre' : `${persen}%`}
            {berjalan > 3 ? ` · ${antre ? 'menunggu' : 'berjalan'} ${lamanya(berjalan)}` : ''}
          </span>
        )}
      </div>
      {jalan && !antre && (
        <div style={{ height: '5px', marginTop: '6px', borderRadius: '99px',
                      background: 'var(--bg-glass)', overflow: 'hidden',
                      border: '1px solid var(--border-color)' }}>
          <div style={{ width: `${Math.max(2, persen)}%`, height: '100%',
                        background: 'var(--reh)', transition: 'width .5s' }} />
        </div>
      )}
      {jalan && (
        <p style={{ fontSize: '.71rem', color: 'var(--ink-3)', lineHeight: 1.5,
                    margin: '6px 0 0' }}>
          Berjalan di latar belakang dan mengalah pada apa pun yang Anda tunggu.
          Klip yang belum sampai gilirannya tetap bisa dibuka; ia akan menghitung
          bingkainya sendiri saat itu juga.
        </p>
      )}
    </div>
  );
}
