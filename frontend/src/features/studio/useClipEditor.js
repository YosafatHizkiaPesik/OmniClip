import { useCallback, useMemo, useRef, useState } from 'react';
import { apiPost, apiPut } from '../../lib/api';

/**
 * Satu-satunya sumber kebenaran untuk klip yang sedang diedit.
 *
 * Bug lama yang diperbaiki di sini: StudioEditor menyimpan start/end/hook/
 * subtitle sebagai SALINAN useState dari clipList, lalu sebuah efek menyalin
 * ulang dari clipList setiap kali indeks klip ATAU clipList berubah — sementara
 * tidak ada yang pernah menulis balik. Akibatnya setiap suntingan subtitle
 * hilang begitu pengguna berpindah klip, dan menambah klip menghapus suntingan
 * klip yang sedang dibuka.
 *
 * Sekarang tidak ada state cermin: setiap panel membaca dari `clips` dan menulis
 * lewat `updateClip`.
 */

const round3 = (v) => Math.round(v * 1000) / 1000;

/**
 * Menyusun ulang waktu per kata setelah teks sebuah baris disunting.
 *
 * Bila jumlah katanya tidak berubah — kasus yang paling sering, karena koreksi
 * biasanya menukar satu kata salah dengar — waktu aslinya dipertahankan supaya
 * sorotan karaoke tetap jatuh tepat pada ucapannya. Bila jumlahnya berubah,
 * rentang baris dibagi menurut panjang tiap kata: itu tebakan, tapi tebakan
 * yang bergerak searah dengan ucapan, dan jauh lebih baik daripada baris yang
 * suntingannya tidak muncul sama sekali.
 */
function retimeWords(line, text) {
  const tokens = String(text).trim().split(/\s+/).filter(Boolean);
  if (!tokens.length) return [];

  const old = line.words ?? [];
  if (old.length === tokens.length) {
    return tokens.map((w, i) => ({ ...old[i], w }));
  }

  const start = Number(line.start) || 0;
  const end = Math.max(Number(line.end) || start, start + 0.25);
  const weights = tokens.map((t) => t.length + 1);
  const total = weights.reduce((a, b) => a + b, 0);

  let cursor = start;
  return tokens.map((w, i) => {
    const dur = (end - start) * (weights[i] / total);
    const word = { w, s: round3(cursor), e: round3(cursor + dur) };
    cursor += dur;
    return word;
  });
}

export function useClipEditor() {
  const [clips, setClips] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [checked, setChecked] = useState(() => new Set());
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const videoIdRef = useRef(null);

  const load = useCallback((videoId, incoming) => {
    videoIdRef.current = videoId;
    const prepared = (incoming || []).map((c, i) => ({
      ...c,
      clip_id: c.clip_id || `clip_${i}`,
      segments: c.segments?.length
        ? c.segments.map((s) => ({ ...s }))
        : [{ start: c.start_seconds, end: c.end_seconds }],
    }));
    setClips(prepared);
    setSelectedId(prepared[0]?.clip_id ?? null);
    setChecked(new Set(prepared.map((c) => c.clip_id)));
    setDirty(false);
  }, []);

  const selected = useMemo(
    () => clips.find((c) => c.clip_id === selectedId) ?? null,
    [clips, selectedId],
  );

  const updateClip = useCallback((id, patch) => {
    setClips((prev) => prev.map((c) => (c.clip_id === id ? { ...c, ...patch } : c)));
    setDirty(true);
  }, []);

  /**
   * Meminta backend menghitung ulang subtitle untuk susunan segmen baru.
   * Perhitungan hanya ada di satu tempat, sehingga preview dan hasil render
   * memakai subtitle yang persis sama.
   */
  const recomputeSubtitles = useCallback(async (id, segments) => {
    const videoId = videoIdRef.current;
    if (!videoId) return;
    setBusy(true);
    try {
      const res = await apiPost('/clip-preview', { video_id: videoId, segments });
      updateClip(id, {
        segments: res.segments,
        subtitles: res.subtitles,
        duration: res.duration,
        start_seconds: res.segments[0].start,
        end_seconds: res.segments[res.segments.length - 1].end,
      });
    } catch {
      // Kalau transkrip tidak ada, batas tetap berubah tanpa subtitle baru.
      updateClip(id, {
        segments,
        duration: segments.reduce((a, s) => a + (s.end - s.start), 0),
        start_seconds: segments[0].start,
        end_seconds: segments[segments.length - 1].end,
      });
    } finally {
      setBusy(false);
    }
  }, [updateClip]);

  /** Menggeser batas satu segmen; nilai negatif memundurkan, positif memajukan. */
  const nudgeSegment = useCallback((id, segIndex, edge, delta, maxDuration) => {
    const clip = clips.find((c) => c.clip_id === id);
    if (!clip) return;
    const segments = clip.segments.map((s) => ({ ...s }));
    const seg = segments[segIndex];
    if (!seg) return;

    if (edge === 'start') {
      seg.start = Math.max(0, Math.min(seg.end - 1.5, seg.start + delta));
    } else {
      seg.end = Math.min(maxDuration || seg.end + delta, Math.max(seg.start + 1.5, seg.end + delta));
    }
    recomputeSubtitles(id, segments);
  }, [clips, recomputeSubtitles]);

  const setSegmentBounds = useCallback((id, segIndex, start, end) => {
    const clip = clips.find((c) => c.clip_id === id);
    if (!clip) return;
    const segments = clip.segments.map((s) => ({ ...s }));
    if (!segments[segIndex]) return;
    segments[segIndex] = { start: Math.max(0, start), end: Math.max(start + 1.5, end) };
    recomputeSubtitles(id, segments);
  }, [clips, recomputeSubtitles]);

  /** Menambahkan potongan dari bagian lain video ke klip yang sama. */
  const addSegment = useCallback((id, start, end) => {
    const clip = clips.find((c) => c.clip_id === id);
    if (!clip) return;
    recomputeSubtitles(id, [...clip.segments.map((s) => ({ ...s })), { start, end }]);
  }, [clips, recomputeSubtitles]);

  const removeSegment = useCallback((id, segIndex) => {
    const clip = clips.find((c) => c.clip_id === id);
    if (!clip || clip.segments.length <= 1) return;
    recomputeSubtitles(id, clip.segments.filter((_, i) => i !== segIndex));
  }, [clips, recomputeSubtitles]);

  const updateSubtitle = useCallback((id, lineIndex, patch) => {
    const clip = clips.find((c) => c.clip_id === id);
    if (!clip) return;
    const subtitles = clip.subtitles.map((l, i) => {
      if (i !== lineIndex) return l;
      const next = { ...l, ...patch };
      // Baris yang teksnya diubah HARUS ikut memperbarui daftar katanya.
      // Sorotan karaoke — di pratinjau maupun di file ASS — dibangun dari
      // `words`, bukan dari `text`; selama daftar kata tidak ikut berubah,
      // setiap koreksi salah dengar hanya terlihat di kotak isian dan hilang
      // tanpa jejak begitu videonya diputar atau dirender.
      if (patch.text !== undefined && patch.text !== l.text) {
        next.words = retimeWords(l, patch.text);
      }
      return next;
    });
    updateClip(id, { subtitles });
  }, [clips, updateClip]);

  /**
   * Menebak pergantian pembicara dari panjang jeda antar baris.
   *
   * Ini BUKAN pengenalan suara: sistem tidak mendengar siapa yang bicara, ia
   * hanya berasumsi jeda panjang menandai giliran berganti. Diarisasi sungguhan
   * butuh model embedding suara yang tidak muat di anggaran memori mesin ini.
   * Hasilnya sengaja bisa disunting satu per satu karena memang akan meleset —
   * misalnya saat satu orang berhenti untuk berpikir.
   */
  const autoSpeakers = useCallback((id, gapSeconds = 1.2) => {
    const clip = clips.find((c) => c.clip_id === id);
    if (!clip?.subtitles?.length) return;
    let current = 0;
    const subtitles = clip.subtitles.map((line, i) => {
      if (i > 0) {
        const gap = line.start - clip.subtitles[i - 1].end;
        if (gap >= gapSeconds) current = current === 0 ? 1 : 0;
      }
      return { ...line, speaker: current };
    });
    updateClip(id, { subtitles });
  }, [clips, updateClip]);

  const removeSubtitle = useCallback((id, lineIndex) => {
    const clip = clips.find((c) => c.clip_id === id);
    if (!clip) return;
    updateClip(id, { subtitles: clip.subtitles.filter((_, i) => i !== lineIndex) });
  }, [clips, updateClip]);

  const toggleChecked = useCallback((id) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const setAllChecked = useCallback((value) => {
    setChecked(value ? new Set(clips.map((c) => c.clip_id)) : new Set());
  }, [clips]);

  /**
   * Membuat klip baru dari rentang yang dipilih pengguna sendiri.
   *
   * Mesin otomatis pasti melewatkan momen: ia menilai dari pola bicara dan
   * kosakata, bukan dari apa yang lucu atau mengena. Pengguna menonton
   * videonya dan melihatnya. Tanpa jalan ini, satu-satunya cara mengambil
   * momen itu adalah menggeser batas klip lain sampai menutupinya — yang
   * berarti mengorbankan klip tersebut.
   */
  const createClip = useCallback(async (start, end) => {
    const videoId = videoIdRef.current;
    const segments = [{ start: Math.max(0, start), end: Math.max(start + 1.5, end) }];
    const id = `manual_${Date.now().toString(36)}`;
    setBusy(true);
    try {
      let payload = {
        segments,
        subtitles: [],
        duration: segments[0].end - segments[0].start,
      };
      if (videoId) {
        try {
          const res = await apiPost('/clip-preview', { video_id: videoId, segments });
          payload = { segments: res.segments, subtitles: res.subtitles, duration: res.duration };
        } catch {
          // Tanpa transkrip klipnya tetap dibuat, hanya tanpa subtitle.
        }
      }
      const hook = (payload.subtitles[0]?.text || '').trim().toUpperCase();
      const clip = {
        clip_id: id,
        index: 0,                       // dinomori ulang di bawah
        ...payload,
        start_seconds: payload.segments[0].start,
        end_seconds: payload.segments[payload.segments.length - 1].end,
        // Skor tidak dikarang untuk klip buatan tangan: pengguna yang memilih
        // momennya, bukan mesin yang menilainya.
        score: null,
        source: 'manual',
        reasons: ['Dipilih sendiri'],
        hook_text: hook.slice(0, 60),
      };
      setClips((prev) => {
        const next = [...prev, clip].sort(
          (a, b) => a.segments[0].start - b.segments[0].start,
        );
        return next.map((c, i) => ({ ...c, index: i + 1 }));
      });
      setChecked((prev) => new Set([...prev, id]));
      setSelectedId(id);
      setDirty(true);
      return id;
    } finally {
      setBusy(false);
    }
  }, []);

  /** Menyimpan susunan klip ke server supaya bertahan setelah halaman ditutup. */
  const saveClips = useCallback(async () => {
    const videoId = videoIdRef.current;
    if (!videoId) return false;
    const payload = clips.map(({ clip_id: _ignored, ...rest }) => rest);
    await apiPut(`/projects/${videoId}/clips`, { clips: payload });
    setDirty(false);
    return true;
  }, [clips]);

  const removeClip = useCallback((id) => {
    setClips((prev) => {
      const next = prev.filter((c) => c.clip_id !== id);
      if (selectedId === id) setSelectedId(next[0]?.clip_id ?? null);
      return next;
    });
    setChecked((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }, [selectedId]);

  return {
    clips, selected, selectedId, checked, dirty, busy,
    load, setSelectedId, updateClip, createClip, saveClips,
    nudgeSegment, setSegmentBounds, addSegment, removeSegment, recomputeSubtitles,
    updateSubtitle, removeSubtitle, autoSpeakers,
    toggleChecked, setAllChecked, removeClip,
  };
}
