/**
 * Pegangan transformasi di atas pratinjau (JOB-4 M2.5).
 *
 * Digambar di LUAR iframe kotak pasir: iframe tidak dipercaya (bisa berisi
 * komponen buatan AI), jadi ia tidak pernah mengukur atau melaporkan letak
 * item. Letak bingkai dihitung dari dokumen dengan fungsi yang sama yang
 * dipakai komposisi (komposisi/kotak.js, model/geometri.js), lalu dikalikan
 * skala layar pratinjau.
 *
 *   - seret badan item: geser (menempel ke garis tengah kanvas);
 *   - pegangan sudut: perbesar/perkecil seragam;
 *   - pegangan bulat di atas: putar (menempel ke kelipatan 90 derajat);
 *   - mode potong (tombol gunting atau klik dua kali): seret tepi untuk
 *     memotong; kotak penuh digambar putus-putus.
 *
 * Satu seretan = satu langkah batal (`gabung` unik, jendela tak terbatas).
 * Pegangan hanya muncul saat garis putar berada di dalam item, sama dengan
 * CapCut: di luar itu itemnya memang tidak terlihat.
 */
import React, { useEffect, useRef, useState } from 'react';
import { Crop, RotateCcw } from 'lucide-react';
import { useT } from '../../../lib/i18n';
import { cariItem, ubahItem } from '../model/dokumen.js';
import {
  bingkaiItem, geser, potongDariSisi, putarDari, skalaDariSudut, sudutBingkai,
} from '../model/geometri.js';
import { ubahTransform } from '../model/suntingan.js';
import { useGaris } from './garisPutar.js';

const AMBANG_TENGAH = 8;
let nomor = 0;

function gayaKotak({ cx, cy, w, h }, putar, k) {
  return {
    left: (cx - w / 2) * k,
    top: (cy - h / 2) * k,
    width: w * k,
    height: h * k,
    transform: putar ? `rotate(${putar}deg)` : undefined,
  };
}

export default function PeganganUbah({ dokumen, terpilih, garis, onUbah }) {
  const t = useT();
  const wadah = useRef(null);
  const [lebar, setLebar] = useState(0);
  const [potong, setPotong] = useState(false);
  const [bantu, setBantu] = useState({ tegak: false, datar: false });
  const f = useGaris(garis);
  const kini = useRef(null);
  kini.current = { dokumen, onUbah };

  useEffect(() => {
    const el = wadah.current;
    if (!el) return undefined;
    const amati = new ResizeObserver(([e]) => setLebar(e.contentRect.width));
    amati.observe(el);
    return () => amati.disconnect();
  }, []);

  const item = terpilih?.item;
  const lajur = terpilih?.lajur;
  const tampil = item && item.jenis !== 'audio' && !lajur.sembunyi
    && f >= item.mulai && f < item.mulai + item.durasi && lebar > 0;
  if (!tampil) return <div ref={wadah} className="montase-pegangan-wadah" aria-hidden />;

  const W = dokumen.kanvas.lebar;
  const k = lebar / W;
  const b = bingkaiItem(dokumen, item);
  const bisaPotong = item.jenis !== 'teks';
  const modePotong = potong && bisaPotong;
  const kunci = Boolean(lajur.kunci);

  const mulai = (jenis) => (e) => {
    if (e.button !== 0 || kunci) return;
    e.preventDefault();
    e.stopPropagation();
    // Tangkap penunjuk: tanpa ini, begitu penunjuk keluar dari kotak dan
    // berada di atas iframe, gerakan dan lepasnya dikirim ke dokumen iframe
    // dan seretan berhenti di tengah jalan.
    try { e.currentTarget.setPointerCapture?.(e.pointerId); } catch { /* tidak apa */ }
    const dasar = kini.current.dokumen;
    const it = cariItem(dasar, item.id)?.item;
    if (!it) return;
    const rect = wadah.current.getBoundingClientRect();
    const skalaLayar = rect.width / W;
    const keKanvas = (ev) => ({ x: (ev.clientX - rect.left) / skalaLayar, y: (ev.clientY - rect.top) / skalaLayar });
    const awal = keKanvas(e);
    const u0 = it.ubah ?? {};
    const bb = bingkaiItem(dasar, it);
    const pusat = { x: bb.penuh.cx, y: bb.penuh.cy };
    const opsi = { gabung: `pegangan:${(nomor += 1)}`, jendela: Infinity };
    let posisi = null;
    let raf = 0;
    const proses = () => {
      raf = 0;
      if (!posisi) return;
      const dx = posisi.x - awal.x;
      const dy = posisi.y - awal.y;
      let sebagian;
      if (jenis === 'geser') {
        const g = geser(dasar, it, u0, dx, dy, AMBANG_TENGAH / skalaLayar);
        sebagian = { x: g.x, y: g.y };
        setBantu(g.garis);
      } else if (jenis === 'skala') {
        sebagian = { skala: skalaDariSudut(u0.skala ?? 1, pusat, awal, posisi) };
      } else if (jenis === 'putar') {
        sebagian = { putar: putarDari(u0.putar ?? 0, pusat, awal, posisi) };
      } else {
        sebagian = {
          potong: potongDariSisi(jenis, u0.potong, dx, dy, {
            skala: u0.skala ?? 1, putar: u0.putar ?? 0, w: bb.kotak.w, h: bb.kotak.h,
          }),
        };
      }
      kini.current.onUbah(() => ubahTransform(dasar, it.id, sebagian), opsi);
    };
    const gerak = (ev) => {
      posisi = keKanvas(ev);
      if (!raf) raf = requestAnimationFrame(proses);
    };
    const lepas = (ev) => {
      window.removeEventListener('pointermove', gerak);
      window.removeEventListener('pointerup', lepas);
      window.removeEventListener('pointercancel', lepas);
      if (raf) cancelAnimationFrame(raf);
      if (ev.clientX !== e.clientX || ev.clientY !== e.clientY) {
        posisi = keKanvas(ev);
        proses();
      }
      setBantu({ tegak: false, datar: false });
    };
    window.addEventListener('pointermove', gerak);
    window.addEventListener('pointerup', lepas);
    window.addEventListener('pointercancel', lepas);
  };

  const r = b.tampak;
  const sudut = sudutBingkai(r, b.putar);
  const bawah = Math.min(dokumen.kanvas.tinggi * k - 34, Math.max(...sudut.map((s) => s.y)) * k + 8);
  const tengahX = Math.min(lebar - 40, Math.max(40, r.cx * k));

  return (
    <div ref={wadah} className="montase-pegangan-wadah">
      {bantu.tegak && <div className="montase-bantu-tegak" aria-hidden />}
      {bantu.datar && <div className="montase-bantu-datar" aria-hidden />}
      {modePotong && (
        <div className="montase-pegangan-penuh" style={gayaKotak(b.penuh, b.putar, k)} aria-hidden />
      )}
      <div
        className={`montase-pegangan ${kunci ? 'terkunci' : ''} ${modePotong ? 'mode-potong' : ''}`}
        style={gayaKotak(r, b.putar, k)}
        onPointerDown={mulai('geser')}
        onDoubleClick={() => bisaPotong && setPotong((v) => !v)}
        role="presentation"
        data-pegangan="badan"
      >
        {!kunci && !modePotong && (
          <>
            {['ka', 'kb', 'kib', 'kia'].map((s) => (
              <span key={s} className={`montase-pegangan-sudut ${s}`} onPointerDown={mulai('skala')} data-pegangan="skala" />
            ))}
            <span className="montase-pegangan-putar" onPointerDown={mulai('putar')} data-pegangan="putar" />
          </>
        )}
        {!kunci && modePotong && ['kiri', 'kanan', 'atas', 'bawah'].map((s) => (
          <span key={s} className={`montase-pegangan-sisi ${s}`} onPointerDown={mulai(s)} data-pegangan={`potong-${s}`} />
        ))}
      </div>
      {!kunci && (
        <div className="montase-pegangan-alat" style={{ left: tengahX, top: Math.max(0, bawah) }}>
          {bisaPotong && (
            <button type="button" className={`montase-ikon ${modePotong ? 'aktif' : ''}`} aria-pressed={modePotong}
                    onClick={() => setPotong((v) => !v)}
                    title={t('montase.pegangan.potong')} aria-label={t('montase.pegangan.potong')}
            >
              <Crop size={12} />
            </button>
          )}
          <button type="button" className="montase-ikon"
                  onClick={() => onUbah((d) => ubahItem(d, item.id, { ubah: {} }))}
                  title={t('montase.pegangan.atur_ulang')} aria-label={t('montase.pegangan.atur_ulang')}
          >
            <RotateCcw size={12} />
          </button>
        </div>
      )}
    </div>
  );
}
