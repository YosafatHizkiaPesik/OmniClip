import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ZoomIn, ZoomOut } from 'lucide-react';
import { formatTime, formatTimeFine } from '../../utils/timeFormat';
import { contrastRatio } from '../../lib/contrast';

/**
 * Sistem balok: seluruh durasi rekaman dibaca sekaligus.
 *
 * Satu balok per narasumber, satu balok dinamika di bawahnya, dan tiap klip
 * duduk sebagai frasa bertanda huruf latihan pada balok penuturnya.
 *
 * Inilah gagasan yang dimiliki layar ini: sekali pandang, bentuk seluruh
 * percakapan satu jam itu terbaca — siapa memegang giliran di menit ke berapa,
 * di mana klipnya jatuh, di mana dinamikanya memuncak. Timeline gelombang
 * tunggal yang biasa dipakai kategori ini tidak bisa menjawab pertanyaan
 * pertama sama sekali.
 *
 * Partitur MEMBUNGKUS: satu halaman memuat beberapa sistem bertumpuk, bukan
 * satu garis yang dimampatkan sampai tak terbaca. Di layar sempit sistemnya
 * dipecah per belasan menit — itu yang dilakukan partitur cetak, dan itu pula
 * yang menyelamatkan huruf latihan dari saling bertumpuk.
 *
 * Garis main dan pita stabilo digerakkan lewat ref di dalam satu loop rAF,
 * tidak pernah lewat React state: `timeupdate` menyala ~4 Hz dan me-render
 * ulang pohon komponen tiap denyut adalah persis yang membuat editor berat.
 */

const HUR = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
export const rehearsalLetter = (i) =>
  (i < 26 ? HUR[i] : HUR[Math.floor(i / 26) - 1] + HUR[i % 26]);

/** Berapa sistem yang muat, dari lebar yang benar-benar tersedia. */
function systemCountFor(width, duration) {
  if (!duration) return 1;
  if (width >= 1100) return 1;
  if (width >= 720) return Math.min(3, Math.ceil(duration / 2400));
  return Math.max(1, Math.min(8, Math.ceil(duration / 900)));   // ~15 menit
}

const TICK_STEPS = [0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800];
const ZOOMS = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512];

/** Lebar kolom nama, sama dengan --stave-name di stylesheet. */
const NAME_W = (width) => (width <= 760 ? 62 : 118);

/**
 * Rentang yang sedang ditandai pengguna, digambar di atas balok.
 *
 * Tanpa ini, dua tombol penanda di transport hanya mengubah sebaris angka —
 * tidak ada cara melihat bagian mana dari rekaman yang sedang dipilih, yang
 * membuat keduanya terasa seperti tombol tanpa tujuan.
 */
function markRect(mark, from, span) {
  if (!mark || (mark.in === null && mark.out === null)) return null;
  const a = mark.in ?? mark.out;
  const b = mark.out ?? mark.in;
  const s = Math.max(Math.min(a, b), from);
  const e = Math.min(Math.max(a, b), from + span);
  if (e < from || s > from + span) return null;
  const open = mark.in === null || mark.out === null;
  const w = Math.max(open ? 0.15 : 0.3, ((e - s) / span) * 100);
  return (
    <div className={`stave-mark${open ? ' stave-mark--open' : ''}`}
         style={{ left: `${((s - from) / span) * 100}%`, width: `${w}%` }} />
  );
}

export default function StaveSystem({
  duration = 0,
  peaks = [],
  clips = [],
  selectedId = null,
  speakerCount = 2,
  speakerColors = [],
  videoRef,
  onSeek,
  onSelectClip,
  // Menggeser batas klip langsung dari partitur.
  onTrimClip = null,
  busy = false,
  // Rentang yang sedang ditandai pengguna untuk klip buatan tangan.
  mark = null,
}) {
  const wrapRef = useRef(null);
  const scrollRefs = useRef([]);
  const playRefs = useRef([]);
  const clockRefs = useRef([]);
  const overRefs = useRef([]);
  const bandRefs = useRef([]);
  const [width, setWidth] = useState(1200);
  // Sama seperti linimasa klip: satu jam rekaman terbaca sekaligus pada 1×,
  // dan diperbesar sampai pecahan detik saat sebuah batas perlu ditaruh persis.
  const [zoom, setZoom] = useState(1);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width));
    ro.observe(el);
    setWidth(el.getBoundingClientRect().width);
    return () => ro.disconnect();
  }, []);

  const voices = Math.max(1, Math.min(8, speakerCount || 1));
  // Diperbesar berarti satu sistem yang panjang, bukan beberapa sistem yang
  // masing-masing ikut memanjang: membungkus DAN memperbesar sekaligus membuat
  // satu detik muncul di dua tempat berjauhan di layar.
  const nSystems = zoom > 1 ? 1 : systemCountFor(width, duration);
  const span = duration > 0 ? duration / nSystems : 1;

  /** Penutur mana yang paling banyak bicara di sebuah klip. */
  const voiceOf = useCallback((clip) => {
    const lines = clip.subtitles ?? [];
    if (!lines.length) return 0;
    const tally = {};
    for (const l of lines) {
      const s = l.speaker || 0;
      tally[s] = (tally[s] || 0) + 1;
    }
    return Number(Object.entries(tally).sort((a, b) => b[1] - a[1])[0][0]);
  }, []);

  const lettered = useMemo(
    () => clips.map((clip, i) => ({
      clip,
      letter: rehearsalLetter(i),
      voice: Math.min(voiceOf(clip), voices - 1),
      start: clip.segments[0].start,
      end: clip.segments[clip.segments.length - 1].end,
    })),
    [clips, voices, voiceOf],
  );

  const selected = clips.find((c) => c.clip_id === selectedId) ?? null;

  // Pita stabilo meluncur ke frasa terpilih — satu momen gerak yang diarang.
  // Digerakkan lewat transform, bukan left/width: menganimasikan geometri
  // memaksa tata letak dihitung ulang tiap bingkai.
  useEffect(() => {
    bandRefs.current.forEach((band, i) => {
      if (!band) return;
      if (!selected || !duration) { band.style.opacity = '0'; return; }
      const from = i * span;
      const s = Math.max(selected.segments[0].start, from);
      const e = Math.min(selected.segments[selected.segments.length - 1].end, from + span);
      if (e <= s) { band.style.opacity = '0'; return; }
      band.style.opacity = '1';
      band.style.transform =
        `translateX(${((s - from) / span) * 100}%) scaleX(${Math.max(0.004, (e - s) / span)})`;
    });
  }, [selected, span, duration, nSystems]);

  // Garis main hidup di sistem yang sedang dilewati; yang lain disembunyikan.
  //
  // Jamnya ikut digerakkan di sini, bukan lewat React state: itulah yang
  // menjawab "saya di menit ke berapa" tanpa harus mencari jam lain di halaman,
  // dan menaruh angka yang berubah 60 kali per detik di state akan me-render
  // ulang seluruh partitur tiap denyut.
  useEffect(() => {
    let raf;
    let last = -1;
    const tick = () => {
      const v = videoRef?.current;
      if (v && duration > 0) {
        const active = Math.min(nSystems - 1, Math.floor(v.currentTime / span));
        const pos = ((v.currentTime - active * span) / span) * 100;
        playRefs.current.forEach((line, i) => {
          if (!line) return;
          if (i !== active) { line.style.opacity = '0'; return; }
          line.style.opacity = '1';
          // `left`, bukan `translateX`: persentase pada translate dihitung dari
          // lebar ELEMEN ITU SENDIRI, dan garis ini lebarnya 2px — jadi
          // `translateX(50%)` menggesernya satu piksel, bukan ke tengah sistem.
          // Itulah sebabnya garisnya seolah tidak pernah beranjak dari tepi
          // kiri betapapun jauh videonya sudah berjalan.
          line.style.left = `${pos}%`;
        });
        // Menjaga garisnya tetap terlihat saat diperbesar. Pada 64× satu layar
        // hanya memuat sekitar setengah menit; tanpa ini, gambarnya berjalan
        // keluar pandangan hampir seketika.
        const sc = scrollRefs.current[active];
        if (sc && sc.scrollWidth > sc.clientWidth + 4 && !v.paused) {
          const px = (v.currentTime / (duration || 1)) * sc.scrollWidth;
          const pad = sc.clientWidth * 0.25;
          if (px < sc.scrollLeft + pad || px > sc.scrollLeft + sc.clientWidth - pad) {
            sc.scrollLeft = Math.max(0, px - sc.clientWidth / 2);
          }
        }
        clockRefs.current.forEach((el, i) => {
          if (!el) return;
          if (i !== active) { el.style.opacity = '0'; return; }
          el.style.opacity = '1';
          // Dijepit di dalam sistemnya supaya angkanya tidak terpotong di tepi.
          el.style.left = `${Math.max(3, Math.min(97, pos))}%`;
          if (Math.abs(v.currentTime - last) > 0.2) {
            last = v.currentTime;
            el.textContent = formatTime(v.currentTime);
          }
        });
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [videoRef, duration, span, nSystems]);

  /**
   * Balok dinamika: simpangan dari rata-rata, digambar dari garis tengah.
   *
   * Bukan gelombang amplitudo — itu justru timeline gelombang tunggal yang
   * ditolak layar ini, hanya dipindah ke baris bawah. Yang dibaca konduktor
   * dari partitur adalah dinamika: di mana suaranya naik di atas kebiasaan,
   * di mana ia turun. Itu z-skor, dan itulah yang dipakai mesin pemilih klip.
   */
  const dynamics = useMemo(() => {
    if (!peaks?.length) return [];
    const mean = peaks.reduce((a, b) => a + b, 0) / peaks.length;
    const sd = Math.sqrt(peaks.reduce((a, b) => a + (b - mean) ** 2, 0) / peaks.length) || 1;
    const N = 320;
    const out = [];
    const chunk = peaks.length / N;
    for (let i = 0; i < N; i += 1) {
      let sum = 0;
      let n = 0;
      for (let j = Math.floor(i * chunk); j < Math.floor((i + 1) * chunk); j += 1) {
        sum += peaks[j]; n += 1;
      }
      out.push(Math.max(-1, Math.min(1, ((sum / (n || 1)) - mean) / (sd * 2))));
    }
    return out;
  }, [peaks]);

  /**
   * Menggeser waktu dengan menyeret, bukan hanya mengklik sekali.
   *
   * Mencari satu momen berarti maju-mundur beberapa detik berkali-kali. Dengan
   * klik tunggal setiap percobaan adalah bidikan baru; dengan seret, gambarnya
   * mengalir di bawah jari sampai ketemu.
   */
  const scrub = (sysIndex) => (e) => {
    if (!duration) return;
    // Diukur dari lapisan yang MENGGAMBAR waktunya, bukan dari papannya.
    // Papan ikut memuat kolom nama selebar 118px dan sisa 14px di kanan; diukur
    // dari sana, klik pada label "20:00" mendarat dua menit dari tempatnya.
    const rect = (overRefs.current[sysIndex] ?? e.currentTarget).getBoundingClientRect();
    const to = (clientX) => onSeek?.(Math.max(0, Math.min(duration,
      sysIndex * span + ((clientX - rect.left) / rect.width) * span)));
    to(e.clientX);
    const onMove = (ev) => to(ev.clientX);
    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  };

  /**
   * Menyeret ujung sebuah frasa untuk memanjangkan atau memendekkan klipnya.
   *
   * Sebelum ini batas klip hanya bisa diubah lewat angka di panel Batas atau
   * lewat linimasa klip di bawah — keduanya menuntut pengguna berpindah tempat
   * dan berhenti melihat rekaman utuhnya. Padahal di sinilah ia sedang melihat
   * klipnya duduk di antara klip lain, dan di sinilah keputusan "kurang lima
   * detik di depan" sebenarnya diambil.
   */
  const dragEdge = (clip, edge) => (e) => {
    if (!onTrimClip || busy || !duration) return;
    e.preventDefault();
    e.stopPropagation();
    const board = e.currentTarget.closest('.stave-overlay')
      ?? e.currentTarget.closest('.stave');
    const rect = board.getBoundingClientRect();
    const segs = clip.segments;
    const last = segs.length - 1;
    const awal = segs[0].start;
    const akhir = segs[last].end;
    const at = (clientX) => Math.max(0, Math.min(duration,
      ((clientX - rect.left) / rect.width) * span + (Math.floor(
        (edge === 'start' ? awal : akhir) / span) * span)));

    let terakhir = edge === 'start' ? awal : akhir;
    const onMove = (ev) => { terakhir = at(ev.clientX); };
    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      if (edge === 'start' && Math.abs(terakhir - awal) > 0.15) {
        onTrimClip(clip.clip_id, 0, Math.min(terakhir, segs[0].end - 1.5), segs[0].end);
      } else if (edge === 'end' && Math.abs(terakhir - akhir) > 0.15) {
        onTrimClip(clip.clip_id, last, segs[last].start,
                   Math.max(terakhir, segs[last].start + 1.5));
      }
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  };

  /**
   * Pensil untuk sebuah suara.
   *
   * Warna subtitle dipakai lebih dulu supaya penutur yang sama terbaca sama di
   * partitur dan di video. Tapi warna itu dipilih untuk teks di ATAS gambar —
   * orang pertama bawaannya putih — dan putih di atas pelat kertas tidak
   * terlihat sama sekali. Warna yang terlalu terang untuk kertas diganti pensil
   * partitur sendiri; identitasnya tetap terbaca, hanya bahannya yang berganti.
   */
  const pencil = useCallback((v) => {
    // Merah TIDAK ada di tangga ini: OWN-WORLD menyimpannya untuk menandai
    // klip, dan memberikannya ke sebuah suara membuat frasa dan huruf
    // latihannya berwarna sama di balok yang sama. Sisanya grafit, bukan
    // pensil kelima yang tidak disebut dunia ini.
    const own = ['var(--entry)', 'var(--cue)', 'var(--ink-2)', 'var(--ink-3)'][v % 4];
    const c = speakerColors[v];
    if (typeof c !== 'string' || !/^#[0-9a-f]{6}$/i.test(c)) return own;
    // Diukur sebagai kontras terhadap pelat, bukan luminansi sendirian:
    // pastel lolos penjagaan luminansi lalu hilang di atas kertas.
    const ratio = contrastRatio(c, '#E3E9F1');
    return ratio !== null && ratio >= 3 ? c : own;
  }, [speakerColors]);

  // Lebar tergambar per sistem, dalam piksel. Kolom nama tidak ikut memanjang —
  // ia tetap menempel di kiri sementara baloknya yang berjalan di bawahnya.
  const boardW = Math.max(320, width - 4) * zoom;
  const drawW = Math.max(0, boardW - NAME_W(width) - 14);
  const step = TICK_STEPS.find((x) => (x / span) * drawW >= 68) ?? 1800;
  const dec = step >= 1 ? 0 : 1;

  const zoomStep = (dir) => {
    const i = ZOOMS.indexOf(zoom);
    const j = Math.max(0, Math.min(ZOOMS.length - 1, (i < 0 ? 0 : i) + dir));
    if (ZOOMS[j] === zoom) return;
    setZoom(ZOOMS[j]);
    // Dijangkarkan pada garis main, sama seperti linimasa klip: memperbesar
    // yang melompat ke awal rekaman adalah kebalikan dari yang diminta.
    const t = videoRef?.current?.currentTime ?? 0;
    requestAnimationFrame(() => {
      scrollRefs.current.forEach((sc) => {
        if (!sc) return;
        const w = Math.max(320, width - 4) * ZOOMS[j];
        sc.scrollLeft = Math.max(0, (t / (duration || 1)) * w - sc.clientWidth / 2);
      });
    });
  };

  return (
    <div ref={wrapRef} className="plate stave-plate">
      <div className="stave-head">
        <span className="mark" style={{ color: 'var(--ink)' }}>Seluruh rekaman</span>
        <span style={{ fontSize: '.72rem', color: 'var(--ink-3)' }}>
          {zoom > 1 ? 'geser mendatar untuk menjelajah' : 'satu huruf latihan per klip · warnanya menandai penuturnya'}
        </span>
        <span style={{ marginLeft: 'auto', display: 'flex', gap: '5px' }}>
          <button className="btn-secondary tl-zoom" title="Perkecil"
                  disabled={zoom <= ZOOMS[0]} onClick={() => zoomStep(-1)}>
            <ZoomOut size={13} />
          </button>
          <span className="tc" style={{
            fontSize: '.7rem', color: 'var(--ink-3)', alignSelf: 'center',
            minWidth: '30px', textAlign: 'center',
          }}>{zoom}×</span>
          <button className="btn-secondary tl-zoom" title="Perbesar"
                  disabled={zoom >= ZOOMS[ZOOMS.length - 1]} onClick={() => zoomStep(1)}>
            <ZoomIn size={13} />
          </button>
        </span>
      </div>

      {Array.from({ length: nSystems }, (_, sys) => {
        const from = sys * span;
        const ticks = [];
        for (let i = Math.ceil(from / step); i * step < from + span; i += 1) {
          ticks.push(Math.round(i * step * 1000) / 1000);
        }

        return (
          <div key={sys} className="stave-system">
            <div className="stave-scroll" ref={(el) => { scrollRefs.current[sys] = el; }}>
            <div className="stave-inner" style={{ width: `${boardW}px` }}>
            <div className="stave-ticks tc">
              {ticks.map((t) => (
                <span key={t} style={{ left: `${((t - from) / span) * 100}%` }}>
                  {formatTimeFine(t, dec)}
                </span>
              ))}
            </div>

            <div className="stave-board" onPointerDown={scrub(sys)}>
              {/* SATU balok, bukan satu per narasumber.
                  Balok per orang dulu ada supaya tiap klip duduk di baris
                  penuturnya. Diukur terhadap pemakaiannya, baris-baris itu
                  tidak menjawab satu pun pertanyaan yang sebenarnya diajukan di
                  layar ini: ia memakai penomoran SUARA sementara lajur bingkai
                  memakai penomoran WAJAH, jadi "Orang 3" di sini dan "Wajah 3"
                  di bawah bisa dua orang berbeda — dan tidak ada cara
                  mengetahuinya dari layar. Penuturnya tetap terbaca dari warna
                  frasanya; yang hilang cuma empat baris kosong.
                  Siapa-berbicara-kapan sekarang tinggal di linimasa klip,
                  tempat ia bisa disandingkan dengan subtitle dan bingkainya. */}
              {[0].map((v) => (
                <div key={v} className="stave-row">
                  <div className="stave-name" title="Semua klip pada rekaman ini">
                    <span className="voice-name">Klip</span>
                  </div>
                  <div className="stave">
                    <div className="stave-lines" />
                    {lettered
                      .filter((x) => x.end > from && x.start < from + span)
                      .map(({ clip, letter, start, end, voice }) => {
                        const s = Math.max(start, from);
                        const e = Math.min(end, from + span);
                        const left = ((s - from) / span) * 100;
                        const w = Math.max(0.6, ((e - s) / span) * 100);
                        const nearEdge = left + w > 94;
                        return (
                          <div key={clip.clip_id} className="stave-phrase"
                               onClick={(ev) => { ev.stopPropagation(); onSelectClip?.(clip.clip_id); }}
                               title={`${letter} · ${formatTime(start)} · ${Math.round(end - start)} dtk`}
                               style={{
                                 left: `${left}%`, width: `${w}%`,
                                 background: `color-mix(in srgb, ${pencil(voice)} 24%, transparent)`,
                                 borderLeftColor: pencil(voice),
                               }}>
                            <span className={`reh${clip.source === 'manual' ? ' reh--manual' : ''}`}
                                  style={{
                                    position: 'absolute', top: '-11px',
                                    ...(nearEdge ? { right: 0 } : { left: 0 }),
                                    transformOrigin: nearEdge ? 'right bottom' : 'left bottom',
                                    transform: clip.clip_id === selectedId ? 'scale(1.14)' : 'none',
                                    transition: 'transform .18s cubic-bezier(.16,1,.3,1)',
                                  }}>{letter}</span>
                            {/* Pegangan di kedua ujung frasa. Hanya digambar
                                pada frasa yang benar-benar mulai dan berakhir
                                di sistem ini: menyeret ujung yang terpotong
                                batas halaman akan memindahkan batas ke tempat
                                yang tidak terlihat pengguna. */}
                            {onTrimClip && start >= from && (
                              <span className="phrase-grip phrase-grip--l"
                                    title="Seret untuk memajukan atau memundurkan awal klip"
                                    onPointerDown={dragEdge(clip, 'start')} />
                            )}
                            {onTrimClip && end <= from + span && (
                              <span className="phrase-grip phrase-grip--r"
                                    title="Seret untuk memanjangkan atau memendekkan akhir klip"
                                    onPointerDown={dragEdge(clip, 'end')} />
                            )}
                          </div>
                        );
                      })}
                  </div>
                </div>
              ))}

              <div className="stave-row stave-row--dyn">
                <div className="stave-name"><span>Dinamika</span></div>
                <div className="dyn">
                  <span className="dyn-rule" />
                  {dynamics.length
                    ? dynamics.map((z, i) => (
                      <span key={i} className="dyn-mark" style={{
                        left: `${(i / dynamics.length) * 100}%`,
                        height: `${Math.abs(z) * 46}%`,
                        top: z >= 0 ? `${50 - Math.abs(z) * 46}%` : '50%',
                        background: z >= 0 ? 'var(--ink-2)' : 'var(--ink-3)',
                      }} />
                    ))
                    : <span className="dyn-empty">Gelombang suara belum dihitung.</span>}
                </div>
              </div>

              <div className="stave-overlay"
                   ref={(el) => { overRefs.current[sys] = el; }}>
                <div ref={(el) => { bandRefs.current[sys] = el; }}
                     className="stave-band" style={{ opacity: 0 }} />
                {markRect(mark, from, span)}
                <div ref={(el) => { playRefs.current[sys] = el; }}
                     className="playline" style={{ opacity: 0 }} />
                <span ref={(el) => { clockRefs.current[sys] = el; }}
                      className="playline-clock tc" style={{ opacity: 0 }}>0:00</span>
              </div>
            </div>
            </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
