import { useCallback, useEffect, useRef, useState } from 'react';
import { apiPost } from '../lib/api';

const TERMINAL = new Set(['done', 'failed', 'cancelled']);

/**
 * Menjalankan pekerjaan panjang di backend dan mengikuti progresnya lewat SSE.
 *
 * Semua teks progres datang DARI server. Komponen tidak boleh mengarang tahapan
 * atau persentase sendiri — itulah yang dulu menghasilkan "progress theatre"
 * berdurasi tetap yang tidak ada hubungannya dengan pekerjaan sebenarnya.
 */
export function useJobRunner() {
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const [starting, setStarting] = useState(false);
  const sourceRef = useRef(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      sourceRef.current?.close();
      sourceRef.current = null;
    };
  }, []);

  const follow = useCallback((jobId) => {
    sourceRef.current?.close();
    const es = new EventSource(`/api/jobs/${jobId}/events`);
    sourceRef.current = es;

    es.onmessage = (evt) => {
      if (!mountedRef.current) return;
      let data;
      try {
        data = JSON.parse(evt.data);
      } catch {
        return;
      }
      setJob(data);
      if (TERMINAL.has(data.status)) {
        es.close();
        if (sourceRef.current === es) sourceRef.current = null;
        if (data.status === 'failed') setError(new Error(data.error || 'Pekerjaan gagal.'));
      }
    };

    es.onerror = () => {
      // EventSource mencoba menyambung ulang sendiri. Biarkan, kecuali koneksi
      // sudah benar-benar ditutup.
      if (es.readyState === EventSource.CLOSED && mountedRef.current) {
        setError(new Error('Koneksi ke server terputus.'));
      }
    };
  }, []);

  /** startFn harus mengembalikan {job_id}. */
  const run = useCallback(async (path, body) => {
    setError(null);
    setJob(null);
    setStarting(true);
    try {
      const res = await apiPost(path, body);
      if (!res?.job_id) throw new Error('Server tidak mengembalikan job.');
      follow(res.job_id);
      return res.job_id;
    } catch (err) {
      if (mountedRef.current) setError(err);
      throw err;
    } finally {
      if (mountedRef.current) setStarting(false);
    }
  }, [follow]);

  const cancel = useCallback(async () => {
    if (!job?.job_id) return;
    try {
      await apiPost(`/jobs/${job.job_id}/cancel`);
    } catch {
      /* status akhir tetap datang lewat SSE */
    }
  }, [job?.job_id]);

  const reset = useCallback(() => {
    sourceRef.current?.close();
    sourceRef.current = null;
    setJob(null);
    setError(null);
  }, []);

  const status = job?.status ?? (starting ? 'queued' : null);
  return {
    job,
    error,
    run,
    cancel,
    reset,
    follow,
    status,
    active: starting || (!!status && !TERMINAL.has(status)),
    progress: job?.progress ?? 0,
    message: job?.message ?? (starting ? 'Menyiapkan…' : null),
    result: job?.status === 'done' ? job.result : null,
  };
}
