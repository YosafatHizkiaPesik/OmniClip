import React from 'react';
import { Plus, Trash2 } from 'lucide-react';

export const MODE_KUNCI = [
  ['smart', 'Ikuti wajah'],
  ['box', 'Kotak tetap'],
  ['gaming', 'Main game'],
  ['center', 'Potong tengah'],
  ['blur', 'Bilah kabur'],
];

const jam = (d) => `${Math.floor(d / 60)}:${String(Math.floor(d % 60)).padStart(2, '0')}`;

/**
 * Linimasa pembingkaian: satu klip, beberapa cara membingkai.
 *
 * Yang dijawab di sini adalah keterbatasan yang tidak bisa diakali dengan
 * pengaturan apa pun sebelumnya. "Ikuti wajah" menurut definisinya memberi SATU
 * wajah — jadi di podcast bertiga, saat satu orang melempar lelucon dan yang
 * berharga justru reaksi dua orang lainnya, tidak ada cara mendapatkannya. Sama
 * di gameplay horor: adegan menegangkan butuh wajah dan permainan berdampingan,
 * tapi begitu jumpscare datang yang ingin dilihat orang cuma wajahnya, penuh
 * satu layar.
 *
 * Tiap kunci berlaku dari waktunya sampai kunci berikutnya. Kunci pertama
 * selalu dimulai dari detik nol — dipaksa di server, karena potongan tanpa
 * pembingkaian hanya akan tampil sebagai latar kabur kosong.
 */
export default function FrameKeysPanel({ keys, onKeys, waktuSekarang = 0, durasi = 0 }) {
  const daftar = keys ?? [];

  const tambah = () => {
    const t = daftar.length === 0 ? 0 : Math.max(0, Math.min(waktuSekarang, durasi - 0.5));
    if (daftar.some((k) => Math.abs((k.t ?? 0) - t) < 0.25)) return;
    const berikut = [...daftar, { t, mode: 'smart' }].sort((a, b) => (a.t ?? 0) - (b.t ?? 0));
    if (berikut.length) berikut[0] = { ...berikut[0], t: 0 };
    onKeys(berikut);
  };

  const ubah = (i, patch) => {
    const berikut = daftar.map((k, j) => (j === i ? { ...k, ...patch } : k));
    onKeys(berikut);
  };

  const hapus = (i) => {
    const berikut = daftar.filter((_, j) => j !== i);
    if (berikut.length) berikut[0] = { ...berikut[0], t: 0 };
    onKeys(berikut);
  };

  return (
    <div style={{ marginTop: '14px', paddingTop: '12px',
                  borderTop: '1px solid var(--rule-2, var(--border-color))' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
        <strong style={{ fontSize: '0.8rem' }}>Linimasa bingkai</strong>
        <button className="chip" onClick={tambah} style={{ fontSize: '0.73rem' }}>
          <Plus size={12} /> Tambah di {jam(waktuSekarang)}
        </button>
      </div>

      {daftar.length < 2 ? (
        <p style={{ fontSize: '0.74rem', color: 'var(--text-secondary)',
                    lineHeight: 1.55, margin: '8px 0 0' }}>
          Kosong berarti seluruh klip memakai satu mode di atas. Tambahkan dua kunci
          atau lebih untuk berganti cara membingkai di tengah klip, misalnya mengikuti
          wajah saat narasumber bicara, lalu kotak tetap yang memuat semua orang saat
          reaksinya yang penting.
        </p>
      ) : null}

      {daftar.map((k, i) => {
        const sampai = i + 1 < daftar.length ? daftar[i + 1].t : durasi;
        return (
          <div key={i} style={{
            marginTop: '8px', padding: '8px 10px',
            border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm, 8px)',
            background: 'var(--plate-3, rgba(255,255,255,0.03))',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '7px', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.73rem', color: 'var(--text-muted)',
                             fontVariantNumeric: 'tabular-nums' }}>
                {jam(k.t ?? 0)}-{jam(sampai)}
              </span>
              <select value={k.mode || 'smart'}
                      onChange={(e) => ubah(i, { mode: e.target.value })}
                      style={{
                        fontSize: '0.75rem', padding: '3px 6px', fontFamily: 'inherit',
                        background: 'var(--bg-card)', color: 'var(--text-primary)',
                        border: '1px solid var(--border-color)',
                        borderRadius: 'var(--radius-sm, 6px)',
                      }}>
                {MODE_KUNCI.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              {i > 0 && (
                <input type="number" step="0.5" min="0" max={durasi}
                       value={Number(k.t ?? 0).toFixed(1)}
                       onChange={(e) => ubah(i, { t: Math.max(0, Number(e.target.value) || 0) })}
                       style={{
                         width: '68px', fontSize: '0.75rem', padding: '3px 6px',
                         background: 'var(--bg-card)', color: 'var(--text-primary)',
                         border: '1px solid var(--border-color)',
                         borderRadius: 'var(--radius-sm, 6px)', fontFamily: 'inherit',
                       }} />
              )}
              <div style={{ flex: 1 }} />
              {i > 0 && (
                <button className="chip" onClick={() => hapus(i)}
                        style={{ fontSize: '0.72rem' }} title="Hapus kunci">
                  <Trash2 size={12} />
                </button>
              )}
            </div>

            {k.mode === 'box' && (
              <div style={{ display: 'flex', gap: '6px', marginTop: '7px', flexWrap: 'wrap',
                            alignItems: 'center' }}>
                <span style={{ fontSize: '0.71rem', color: 'var(--text-muted)' }}>
                  Kotak (%)
                </span>
                {['x', 'y', 'w', 'h'].map((sumbu) => (
                  <label key={sumbu} style={{ display: 'flex', alignItems: 'center', gap: '3px',
                                              fontSize: '0.71rem', color: 'var(--text-muted)' }}>
                    {sumbu}
                    <input type="number" min="0" max="100" step="1"
                           value={Math.round(k.rect?.[sumbu] ?? (sumbu === 'w' || sumbu === 'h' ? 60 : 20))}
                           onChange={(e) => ubah(i, {
                             rect: {
                               x: 20, y: 20, w: 60, h: 60, ...(k.rect || {}),
                               [sumbu]: Math.max(sumbu === 'w' || sumbu === 'h' ? 1 : 0,
                                                 Math.min(100, Number(e.target.value) || 0)),
                             },
                           })}
                           style={{
                             width: '52px', fontSize: '0.72rem', padding: '3px 5px',
                             background: 'var(--bg-card)', color: 'var(--text-primary)',
                             border: '1px solid var(--border-color)',
                             borderRadius: 'var(--radius-sm, 6px)', fontFamily: 'inherit',
                           }} />
                  </label>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
