import { describe, expect, it } from 'vitest';
import { pesan, pesanSah, TANDA } from './jembatan.js';

describe('jembatan pratinjau', () => {
  it('pesan selalu bertanda dan berjenis', () => {
    expect(pesan('ke', { bingkai: 12 })).toEqual({ bingkai: 12, tanda: TANDA, jenis: 'ke' });
  });
  it('isi tidak bisa menimpa tanda atau jenis', () => {
    expect(pesan('putar', { tanda: 'lain', jenis: 'muat' })).toMatchObject({ tanda: TANDA, jenis: 'putar' });
  });
  it('pesan dari pihak lain diabaikan', () => {
    expect(pesanSah(pesan('siap'))).toBe(true);
    for (const lain of [null, 'siap', {}, { jenis: 'siap' }, { tanda: TANDA }, { tanda: 'x', jenis: 'siap' }]) {
      expect(pesanSah(lain)).toBe(false);
    }
  });
});
