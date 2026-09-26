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
  const [sejak, setSejak] = useState(null);
  const [, paksaGambar] = useState(0);
  const esRef = useRef(null);

  // Mencari pekerjaannya, lalu mengikutinya lewat SSE. Dicari berkala selama
  // belum ketemu: pekerjaan ini diantrekan sesudah auto-klip, jadi ia bisa
  // baru muncul beberapa saat setelah Studio dibuka.
  useEffect(() => {
    if (!videoId) return undefined;
    let batal = false;
    let timer = null;

    const ikuti = (id) => {
      esRef.current?.close();
      const es = new EventSource(`/api/jobs/${id}/events`);
      esRef.current = es;
      es.onmessage = (evt) => {
        if (batal) return;
        let d;
        try { d = JSON.parse(evt.data); } catch { return; }
        setJob(d);
        if (SELESAI.has(d.status)) { es.close(); esRef.current = null; }
      };
      es.onerror = () => {
        if (es.readyState === EventSource.CLOSED) { esRef.current = null; }
      };
    };

    const cari = async () => {
      if (batal) return;
      try {
        const r = await apiGet('/jobs?limit=40');
        const daftar = r?.jobs ?? (Array.isArray(r) ? r : []);
        const milik = daftar.find((j) => j.type === 'bingkai_awal'
          && j.video_id === videoId
          && !SELESAI.has(j.status));
        if (milik && !batal) {
          setJob(milik);
          setSejak(Date.now());
          ikuti(milik.job_id ?? milik.id);
          return;
        }
      } catch { /* daftar pekerjaan yang gagal dibaca bukan alasan menampilkan galat */ }
      if (!batal) timer = setTimeout(cari, 6000);
    };
    cari();

    return () => {
      batal = true;
      if (timer) clearTimeout(timer);
      esRef.current?.close();
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
  const persen = Math.round((job.progress ?? 0) * 100);
  const berjalan = sejak ? (Date.now() - sejak) / 1000 : 0;

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
            {persen}%{berjalan > 3 ? ` · berjalan ${lamanya(berjalan)}` : ''}
          </span>
        )}
      </div>
      {jalan && (
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
