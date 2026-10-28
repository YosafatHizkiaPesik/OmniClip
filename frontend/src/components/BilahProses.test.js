import { describe, expect, it } from 'vitest';
import { detailPesan, keadaanProses } from './BilahProses';

describe('BilahProses', () => {
  it('membuang ulangan judul langkah dan persennya dari pesan server', () => {
    expect(detailPesan('Mengunduh video… 47% · 18,2 MB/dtk')).toBe('18,2 MB/dtk');
    expect(detailPesan('Menyalin ucapan… 3:12 dari 12:40')).toBe('3:12 dari 12:40');
    expect(detailPesan('Menunggu jawaban AI lokal (Qwen3 4B)…')).toBe('Menunggu jawaban AI lokal (Qwen3 4B)');
    expect(detailPesan('Klip dipilih mesin lokal')).toBe('Klip dipilih mesin lokal');
    expect(detailPesan('')).toBe('');
  });

  it('memetakan tahap server ke langkah', () => {
    expect(keadaanProses({ status: 'running', stage: 'transcribe', progress: 0.62 }).aktif).toBe(1);
    expect(keadaanProses({ status: 'running', stage: 'gemini', progress: 0.95 }).menunggu).toBe(true);
    expect(keadaanProses({ status: 'queued', progress: 0 }).antre).toBe(true);
  });
});
