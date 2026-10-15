/**
 * Avatar channel untuk kartu video (JOB-3 J3-3).
 *
 * Kartu-kartu di satu layar mendaftarkan channel-nya; permintaan dikumpulkan
 * 60 ms lalu dikirim SEKALI ke /api/channel/avatar (yang dengan kunci YouTube
 * Data API menjawab 50 channel dalam satu panggilan). Hasilnya diingat selama
 * halaman terbuka.
 */
import { useSyncExternalStore } from 'react';
import { apiGet } from './api';

const data = new Map();          // channel_id -> {avatar, nama, handle, pelanggan} | null
const antre = new Set();
const pendengar = new Set();
let timer = null;
let versi = 0;

function beri() { versi += 1; pendengar.forEach((f) => f()); }

function kirim() {
  timer = null;
  const ids = [...antre];
  antre.clear();
  for (let i = 0; i < ids.length; i += 50) {
    const potong = ids.slice(i, i + 50);
    apiGet(`/channel/avatar?ids=${encodeURIComponent(potong.join(','))}`)
      .then((r) => {
        for (const id of potong) data.set(id, r?.channel?.[id] ?? null);
        beri();
      })
      .catch(() => { for (const id of potong) data.set(id, null); beri(); });
  }
}

export function mintaAvatar(id) {
  if (!id || data.has(id) || antre.has(id)) return;
  antre.add(id);
  if (!timer) timer = setTimeout(kirim, 60);
}

export function simpanAvatar(id, info) {
  if (!id || !info) return;
  data.set(id, { ...(data.get(id) || {}), ...info });
  beri();
}

function langganan(f) { pendengar.add(f); return () => pendengar.delete(f); }

/** Info channel (atau undefined selama dimuat, null bila tidak ada). */
export function useChannelInfo(id) {
  useSyncExternalStore(langganan, () => versi, () => versi);
  if (id && !data.has(id)) mintaAvatar(id);
  return id ? data.get(id) : null;
}
