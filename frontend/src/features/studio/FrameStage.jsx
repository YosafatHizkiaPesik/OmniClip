import React, {
  useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState,
} from 'react';
import { clipTimeFor, followX, frameInk, personAt, personKeyAt } from './frames';
import { beginRectDrag } from './rectDrag';

/**
 * Meja bingkai: video sumber seutuhnya, dengan kotak yang menandai apa yang
 * diambil darinya.
 *
 * Sebelum ini, satu-satunya cara mengetahui bagian mana dari video yang masuk
 * ke klip 9:16 adalah dengan merendernya lalu menontonnya. Di sini videonya
 * tampil pada rasio aslinya — utuh, tidak dipotong — dan pemotongannya digambar
 * di atasnya sebagai kotak. Di mode ikut-wajah kotak itu bergerak sendiri
 * mengikuti rencana crop yang sama persis yang dikirim ke ffmpeg; di mode susun
 * sendiri, kotaknya yang diseret pengguna.
 *
 * Elemen videonya sengaja dibisukan dan hanya membuntuti pemutar utama. Dua
 * elemen video yang sama-sama bersuara akan terdengar sebagai gema, dan waktu
 * yang berlaku hanya boleh satu — yang dipegang transport di bawahnya.
 */
export default function FrameStage({
  src,
  videoRef,
  frameMode = 'smart',
  reframe = null,
  aspectRatio = '9:16',
  layout = null,
  onLayoutChange = null,
  // Segmen klip terpilih. Dibutuhkan untuk menerjemahkan waktu video sumber
  // yang dilaporkan elemen <video> ke waktu klip yang dipakai jejak wajah.
  segments = null,
  selectedFrameId = null,
  onSelectFrame = null,
  // Mode ikut-wajah: cara pengguna menunjuk siapa yang harus diikuti.
  onLockPerson = null,
  // Tanda linimasa: siapa yang dituju bingkai, per rentang waktu.
  personKeys = null,
  // Kotak sumber untuk mode "box", dalam persen. Datang dari potongan lajur
  // Bingkai tempat garis main sedang berada.
  boxRect = null,
  // Dipanggil saat kotak itu diseret atau diubah ukurannya. Tanpa ini kotaknya
  // hanya bisa dilihat, dan ukurannya harus ditebak lewat empat kolom angka.
  onBoxRectChange = null,
}) {
  const mirrorRef = useRef(null);
  const boxRef = useRef(null);
  const cropRef = useRef(null);
  // Kotak bingkai pengikut digerakkan lewat ref, bukan state: pada 60 fps,
  // me-render ulang panel setiap frame membuat seluruh editor terasa berat.
  const followRefs = useRef({});
  const [aspect, setAspect] = useState(16 / 9);
  const [box, setBox] = useState({ w: 0, h: 0 });
  const wellRef = useRef(null);
  const [well, setWell] = useState({ w: 0, h: 0 });
  // Posisi tiap orang pada sampel yang sedang tampil, untuk menaruh penandanya.
  const personRefs = useRef({});
  const [drag, setDrag] = useState(null);

  const editable = frameMode === 'layout' && !!layout && !!onLayoutChange;

  // Rasio dibaca dari berkasnya, bukan ditebak 16:9. Sumber 4:3 dan rekaman
  // vertikal keduanya ada, dan menebak akan menaruh kotak crop di tempat yang
  // salah pada keduanya.
  const onMeta = useCallback((e) => {
    const { videoWidth: w, videoHeight: h } = e.currentTarget;
    if (w > 0 && h > 0) setAspect(w / h);
  }, []);

  // Ukuran sumur, diamati sekali per perubahan — bukan dibaca tiap bingkai.
  useLayoutEffect(() => {
    const el = wellRef.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(([entry]) => {
      setWell({ w: entry.contentRect.width, h: entry.contentRect.height });
    });
    ro.observe(el);
    const r = el.getBoundingClientRect();
    setWell({ w: r.width, h: r.height });
    return () => ro.disconnect();
  }, []);

  /** Kotak terbesar berasio `aspect` yang masih muat di dalam sumurnya. */
  const boxFit = useMemo(() => {
    if (!well.w || !well.h) return { w: 0, h: 0 };
    const w = Math.min(well.w, well.h * aspect);
    return { w: Math.round(w), h: Math.round(w / aspect) };
  }, [well.w, well.h, aspect]);

  useLayoutEffect(() => {
    const el = boxRef.current;
    if (!el) return undefined;
    const ro = new ResizeObserver(([entry]) => {
      setBox({ w: entry.contentRect.width, h: entry.contentRect.height });
    });
    ro.observe(el);
    const r = el.getBoundingClientRect();
    setBox({ w: r.width, h: r.height });
    return () => ro.disconnect();
  }, [aspect]);

  /** Posisi crop pada detik tertentu — pembacaan yang sama dengan `sendcmd`. */
  const cropXAt = useMemo(() => {
    const kf = reframe?.keyframes;
    if (!kf?.length || (frameMode !== 'smart' && frameMode !== 'motion')) return null;
    return (t) => {
      if (t <= kf[0][0]) return kf[0][1];
      let lo = 0;
      let hi = kf.length - 1;
      while (lo < hi) {
        const mid = Math.ceil((lo + hi) / 2);
        if (kf[mid][0] <= t) lo = mid;
        else hi = mid - 1;
      }
      return kf[lo][1];
    };
  }, [reframe, frameMode]);

  // Membuntuti pemutar utama: waktu disamakan hanya saat sudah menyimpang lebih
  // dari 0,2 detik. Menyetel `currentTime` tiap frame akan membuat dekoder
  // mencari terus-menerus dan gambarnya tersendat.
  useEffect(() => {
    let raf;
    const tick = () => {
      const main = videoRef?.current;
      const m = mirrorRef.current;
      if (main && m) {
        if (Math.abs(m.currentTime - main.currentTime) > 0.2) {
          m.currentTime = main.currentTime;
        }
        if (main.paused && !m.paused) m.pause();
        else if (!main.paused && m.paused) m.play().catch(() => { /* diabaikan */ });

        // Kotak ikut-wajah digerakkan lewat ref, bukan state: pada 60 fps,
        // me-render ulang pohon komponen tiap frame akan membuat seluruh
        // editor terasa berat.
        const t = clipTimeFor(segments, main.currentTime);
        const c = cropRef.current;
        if (c && cropXAt && reframe?.source_w) {
          const x = cropXAt(t);
          c.style.left = `${(x / reframe.source_w) * 100}%`;
        }

        // Penanda orang di mode ikut-wajah: ikut bergerak bersama orangnya,
        // supaya yang ditunjuk pengguna adalah orang yang benar-benar dilihatnya
        // di detik itu, bukan posisi rata-ratanya sepanjang klip.
        //
        // Dan ia MENGHILANG saat orangnya tidak ada di kamera. Versi sebelumnya
        // menelusuri jejaknya mundur tanpa batas, jadi begitu seseorang pernah
        // terlihat sekali, penandanya berdiri selamanya di posisi terakhirnya —
        // yang di rekaman dua kamera berarti "orang 2" mengambang di atas kursi
        // kosong sepanjang sisa klip.
        const aimed = personKeyAt(personKeys, t);
        // Siapa yang terlihat TEPAT sekarang, dan di mana. Dihitung sekali
        // per bingkai, bukan per penanda.
        const fps = reframe?.people_fps || 8;
        const si = Math.max(0, Math.round(t * fps));
        const segar = (reframe?.people ?? []).map((_, i) => {
          const lane = reframe?.people_seen?.[i];
          return lane ? !!lane[Math.min(si, lane.length - 1)] : true;
        });
        const segarPos = (reframe?.people ?? [])
          .map((tr, i) => (segar[i] ? tr[Math.min(si, tr.length - 1)] : null))
          .filter((x) => x !== null && x !== undefined);

        for (const [key, el] of Object.entries(personRefs.current)) {
          if (!el) continue;
          const idx = Number(key);
          const v = personAt(reframe, idx, t);
          // Penanda yang posisinya sudah basi disembunyikan bila ia jatuh
          // menimpa penanda orang lain yang sedang benar-benar terlihat.
          //
          // `personAt` sengaja menahan posisi terakhir selama seperempat detik
          // supaya penandanya tidak berkedip tiap kali deteksi meleset satu
          // bingkai. Harganya: orang yang baru saja keluar dari kamera masih
          // digambar di tempat lamanya — dan kalau orang lain sekarang berdiri
          // di situ, yang terlihat adalah dua nomor bertumpuk di satu wajah.
          // Itu terbaca sebagai "nomornya tertumpuk", padahal penomorannya
          // sendiri tidak pernah memberi satu nomor ke dua orang sekaligus.
          const tertimpa = v !== null && !segar[idx]
            && segarPos.some((x) => Math.abs(x - v) < 4);
          el.style.visibility = (v === null || tertimpa) ? 'hidden' : 'visible';
          if (v !== null) el.style.left = `${v}%`;
          // Yang sedang dituju bingkai ditandai di sini juga, karena inilah
          // gambar yang dilihat pengguna saat bertanya "kenapa yang diam?".
          el.classList.toggle('is-aimed', aimed === idx);
        }

        // Kotak bingkai pengikut di dalam susunan sendiri.
        if (reframe?.people?.length) {
          for (const f of layout?.frames ?? []) {
            const el = followRefs.current[f.id];
            if (!f.follow || !el) continue;
            const x = followX(reframe, f, t);
            if (x !== null) el.style.left = `${x}%`;
          }
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoRef, reframe, frameMode, layout, segments, personKeys]);


  /** Menyeret kotak sumber. Aturan gerak dan jangkarnya dibagi dengan
      kanvas hasil, supaya keduanya terasa sama di tangan. */
  const startDrag = useCallback((frameId, handle) => (e) => {
    if (!editable) return;
    onSelectFrame?.(frameId);
    const frame = layout.frames.find((f) => f.id === frameId);
    if (!frame) return;
    setDrag({ frameId, handle });
    beginRectDrag(e, {
      boxW: box.w, boxH: box.h, rect: frame.src, handle,
      lockX: !!frame.follow,
      onChange: (src) => onLayoutChange({
        ...layout,
        frames: layout.frames.map((f) => (f.id === frameId ? { ...f, src } : f)),
      }),
      onEnd: () => setDrag(null),
    });
  }, [editable, box.w, box.h, layout, onLayoutChange, onSelectFrame]);

  /**
   * Menyeret kotak mode "Kotak tetap".
   *
   * Memakai mesin seret yang sama dengan bingkai susun-sendiri — `beginRectDrag`
   * — supaya keduanya terasa persis sama di tangan. Dua benda yang berkelakuan
   * sama tidak boleh menuntut cara memegang yang berbeda.
   */
  const bisaSeretKotak = frameMode === 'box' && !!boxRect && !!onBoxRectChange;
  const seretKotak = useCallback((handle) => (e) => {
    if (!bisaSeretKotak) return;
    setDrag({ frameId: '__box', handle });
    beginRectDrag(e, {
      boxW: box.w, boxH: box.h, rect: boxRect, handle,
      onChange: (src) => onBoxRectChange(src),
      onEnd: () => setDrag(null),
    });
  }, [bisaSeretKotak, box.w, box.h, boxRect, onBoxRectChange]);

  // Kotak yang digambar untuk mode selain susun-sendiri: apa yang benar-benar
  // diambil ffmpeg, bukan gambaran umum.
  const staticCrop = useMemo(() => {
    const target = { '9:16': 9 / 16, '1:1': 1, '4:5': 4 / 5, '16:9': 16 / 9 }[aspectRatio] ?? 9 / 16;
    if (frameMode === 'center') {
      const w = Math.min(100, (target / aspect) * 100);
      return { x: (100 - w) / 2, y: 0, w, h: 100, label: 'Potong tengah' };
    }
    // Kotak tetap: gambar kotak yang BENAR-BENAR akan dipotong ffmpeg. Tanpa
    // ini, memilih "Kotak tetap" di linimasa tidak mengubah apa pun di layar —
    // pratinjaunya tetap memperlihatkan bingkai yang mengikuti wajah, dan
    // pilihannya terasa seperti tombol yang tidak tersambung ke mana-mana.
    if (frameMode === 'box' && boxRect) {
      return {
        x: Number(boxRect.x) || 0, y: Number(boxRect.y) || 0,
        w: Number(boxRect.w) || 100, h: Number(boxRect.h) || 100,
        label: 'Kotak tetap',
      };
    }
    if (frameMode === 'gaming' && (layout?.frames ?? []).length) {
      return null;     // kedua bidangnya sudah digambar sendiri di bawah
    }
    if (frameMode === 'gaming') {
      // Susunannya dua bidang, jadi tidak ada satu kotak yang bisa mewakilinya.
      // Yang jujur adalah mengatakan apa yang akan terjadi, bukan menggambar
      // kotak yang tidak benar.
      return { x: 0, y: 0, w: 100, h: 100, label: 'Main game: wajah di atas, permainan di bawah' };
    }
    if (frameMode === 'blur') {
      return { x: 0, y: 0, w: 100, h: 100, label: 'Bilah kabur: seluruh bingkai dipakai' };
    }
    if (frameMode === 'motion' && reframe?.available && reframe.source_w) {
      // Jejak gerakan dari server — rencana yang sama persis dengan render,
      // jadi kotak ini bergeser tepat seperti hasilnya nanti.
      return {
        x: 0, y: 0, w: (reframe.crop_w / reframe.source_w) * 100, h: 100,
        label: 'Ikuti gerakan', moving: true,
      };
    }
    if (frameMode === 'motion') {
      // Belum ada jejak (masih dihitung, atau videonya nyaris tanpa gerakan):
      // tunjukkan lebar jendelanya di tengah, dan katakan begitu.
      const w = Math.min(100, (target / aspect) * 100);
      return { x: (100 - w) / 2, y: 0, w, h: 100,
               label: 'Ikuti gerakan — jendela ini bergeser mengikuti tokoh' };
    }
    if (frameMode === 'smart' && reframe?.available && reframe.source_w) {
      return {
        x: 0, y: 0, w: (reframe.crop_w / reframe.source_w) * 100, h: 100,
        label: 'Ikut wajah', moving: true,
      };
    }
    return null;
  }, [frameMode, aspectRatio, aspect, reframe, boxRect, layout]);

  return (
    /* Pelatnya MEMELUK videonya.
       
       Sebelum ini pelat memenuhi kolomnya dan videonya duduk di tengah dengan
       pelat kosong di kiri-kanan — terukur, sumur 745 piksel untuk video
       selebar 439. Yang terlihat bukan "video di dalam kotaknya" melainkan
       kotak besar yang sebagian besar kosong. Videonya sendiri sudah sebesar
       yang tingginya izinkan; yang bisa dihilangkan adalah kotaknya.
       
       Batasnya diturunkan dari TINGGI sumur saja, bukan dari ukuran kotak yang
       sudah dihitung. Percobaan pertama memakai lebar kotak — dan itu
       mengumpankan lebar hasil kembali ke pengukur lebarnya sendiri, sehingga
       tiap putaran menyusutkannya sedikit: terukur, video 488 piksel menciut
       jadi 416. Tinggi sumur tidak bergantung pada lebar pelat, jadi ia satu-
       satunya masukan yang tidak melingkar.
       
       Dan yang ditulis adalah LEBAR, bukan batas lebar. Dengan `max-width`
       saja, pelat yang dipusatkan mengambil lebar sesuai isinya — dan isinya
       adalah kotak yang lebarnya diukur dari pelat itu juga. Terukur, lingkaran
       itu mengendap di 285 piksel padahal batasnya 773. Lebar yang ditetapkan
       memutusnya: sumur langsung punya lebar pasti, dan kotaknya tinggal
       mengisi.
       
       Angkanya diserahkan lewat variabel CSS, bukan dipasang langsung, karena
       ia hanya sah di tata letak BERLABUH. Di layar sempit studio kembali jadi
       tumpukan yang digulir, tinggi sumurnya ditentukan isinya sendiri, dan
       rumus yang sama berubah jadi lingkaran yang menciut: terukur, pelat 106
       piksel berisi video 82x46. Media query tinggal mengabaikan variabelnya
       di sana. */
    <div className="frame-stage"
         style={well.h > 0
           ? { '--plate-w': `${Math.round(well.h * aspect) + 12}px` }
           : undefined}>
      <div ref={wellRef} className="frame-stage-well">
        {/* Judul pelat sebagai LENCANA di atas gambar, bukan baris tersendiri.
            
            Sebagai baris ia memakan 38 piksel tinggi, dan di studio berlabuh
            tinggi adalah satu-satunya hal yang mengikat besar gambarnya —
            terukur, 38 piksel itu sama dengan 67 piksel lebar video yang tidak
            pernah terpakai, sementara di sebelahnya ada ratusan piksel kosong.
            Keterangannya tetap ada, hanya berhenti menuntut barisnya sendiri. */}
        <div className="frame-stage-tag">
          <b>Video sumber</b>
          <span>
            {frameMode === 'gaming'
              ? 'wajah pemain di atas, permainan utuh di bawah — dicari otomatis'
              : frameMode === 'layout'
              ? `${layout?.frames?.length ?? 0} bingkai — seret kotaknya`
              : frameMode === 'original' ? 'dipakai utuh, tanpa dipotong'
                : frameMode === 'blur' ? 'muat seluruhnya, sisi diisi versi kabur'
                  : staticCrop ? 'kotak menandai bagian yang diambil'
                    : 'menyiapkan kotak…'}
          </span>
        </div>
        {/* Ukuran kotak DIHITUNG dari sumurnya, bukan diserahkan ke CSS.
            
            Versi sebelumnya menyatakan batas tinggi sebagai batas lebar
            (`58vh * rasio`) dan membiarkan `width: 100%` menentukan sisanya.
            Itu bekerja selama halamannya bisa digulir — kotak yang menjulur
            tinggal digulir. Di studio berlabuh tidak ada gulir yang
            menyelamatkannya, dan `58vh` tidak tahu apa-apa tentang tinggi yang
            BENAR-BENAR tersisa setelah bilah dan dok mengambil bagiannya.
            Terukur pada layar 1366x690: sumurnya 717x270, isinya 717x414 —
            144 piksel terpotong diam-diam oleh `overflow: hidden`, dan yang
            hilang adalah bagian bawah wajah orangnya.
            
            CSS murni tidak bisa menjawab ini: elemen ber-`aspect-ratio` yang
            kedua sisinya `auto` tidak punya ukuran intrinsik, sedangkan
            menetapkan salah satunya membuat sisi yang lain menang dan kotaknya
            gepeng. Jadi sumurnya diukur, dan ukurannya dihitung — sekali per
            perubahan ukuran, bukan tiap bingkai. */}
        <div ref={boxRef} className="frame-stage-box"
             style={boxFit.w > 0
               ? { width: `${boxFit.w}px`, height: `${boxFit.h}px` }
               : { aspectRatio: aspect, width: '100%' }}>
          {src ? (
            <video ref={mirrorRef} src={src} muted playsInline preload="auto"
                   onLoadedMetadata={onMeta}
                   style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }} />
          ) : (
            <div className="frame-stage-empty">Video sumber belum tersedia.</div>
          )}

          {/* Penanda orang, hanya di mode ikut-wajah.

              Pencocokan otomatis bisa keliru — mulut yang tertutup mikrofon
              hampir tidak bergerak di gambar, dan sistem lalu mengunci orang
              yang sedang menyimak. Saat itu terjadi, yang dibutuhkan bukan
              tebakan yang lebih pintar melainkan cara membetulkannya. */}
          {frameMode === 'smart' && onLockPerson && (reframe?.people?.length ?? 0) > 1
            && reframe.people.map((_, i) => (
              <button key={i} type="button"
                      ref={(el) => { personRefs.current[i] = el; }}
                      onClick={() => onLockPerson(i)}
                      title={`Tekan: bingkai mengikuti wajah ${i + 1} mulai detik ini. `
                        + 'Tekan lagi di detik lain: potongannya ditutup dan '
                        + 'bingkai kembali memilih sendiri.'}
                      className="person-pin">
                {i + 1}
              </button>
            ))}

          {/* Main game: kedua bidangnya digambar, tapi tidak bisa diseret —
              letaknya memang dicari sistem, bukan disusun pengguna. */}
          {frameMode === 'gaming' && (layout?.frames ?? []).map((f, i) => (
            <div key={`g${i}`} className="frame-rect is-locked"
                 style={{
                   left: `${f.src.x}%`, top: `${f.src.y}%`,
                   width: `${f.src.w}%`, height: `${f.src.h}%`,
                   borderColor: frameInk(i),
                 }}>
              <span className="frame-rect-tag" style={{ background: frameInk(i) }}>
                {i === 0 ? 'Permainan' : 'Reaksi'}
              </span>
            </div>
          ))}

          {/* Kotak tetap: bisa diseret dan diubah ukurannya, sama seperti
              bingkai susun-sendiri. */}
          {bisaSeretKotak && (
            <div className="frame-rect is-on"
                 onPointerDown={seretKotak(null)}
                 style={{
                   left: `${boxRect.x}%`, top: `${boxRect.y}%`,
                   width: `${boxRect.w}%`, height: `${boxRect.h}%`,
                   borderColor: 'var(--hl)', cursor: drag ? 'grabbing' : 'grab',
                   zIndex: 3,
                 }}>
              <span className="frame-rect-tag" style={{ background: 'var(--hl)', color: '#1A1400' }}>
                Kotak tetap · seret untuk memindahkan
              </span>
              {['nw', 'ne', 'sw', 'se'].map((h) => (
                <span key={h} className={`frame-grip grip-${h}`}
                      style={{ borderColor: 'var(--hl)' }}
                      onPointerDown={seretKotak(h)} />
              ))}
            </div>
          )}

          {/* Mode tetap lainnya: satu kotak, tidak bisa diseret. */}
          {!editable && !bisaSeretKotak && staticCrop && (
            <div ref={staticCrop.moving ? cropRef : null} className="frame-rect is-locked"
                 style={{
                   left: `${staticCrop.x}%`, top: `${staticCrop.y}%`,
                   width: `${staticCrop.w}%`, height: `${staticCrop.h}%`,
                   borderColor: 'var(--hl)',
                 }}>
              <span className="frame-rect-tag" style={{ background: 'var(--hl)', color: '#1A1400' }}>
                {staticCrop.label}
              </span>
            </div>
          )}

          {/* Susun sendiri: satu kotak per bingkai, semuanya bisa diseret. */}
          {editable && layout.frames.map((f, i) => {
            const on = f.id === selectedFrameId;
            const ink = frameInk(i);
            return (
              <div key={f.id}
                   ref={(el) => { followRefs.current[f.id] = el; }}
                   className={`frame-rect${on ? ' is-on' : ''}${f.follow ? ' is-following' : ''}`}
                   onPointerDown={startDrag(f.id, null)}
                   style={{
                     left: `${f.src.x}%`, top: `${f.src.y}%`,
                     width: `${f.src.w}%`, height: `${f.src.h}%`,
                     borderColor: ink, cursor: drag ? 'grabbing' : 'grab',
                     // Bingkai yang lebih KECIL berada di atas.
                     //
                     // Dengan urutan daftar, bingkai yang menutupi seluruh
                     // gambar tergambar di atas bingkai kecil di dalamnya, dan
                     // bingkai kecil itu jadi tidak bisa disentuh sama sekali —
                     // setiap klik mengenai yang besar. Yang dipilih orang
                     // hampir selalu yang lebih kecil, karena yang besar bisa
                     // diraih di mana saja di luar yang kecil.
                     zIndex: on ? 40 : 10 + Math.round(
                       100 - (f.src.w * f.src.h) / 100),
                   }}>
                <span className="frame-rect-tag" style={{ background: ink }}>
                  {i + 1}. {f.label}{f.follow ? ' · mengikuti' : ''}
                </span>
                {['nw', 'ne', 'sw', 'se'].map((h) => (
                  <span key={h} className={`frame-grip grip-${h}`}
                        style={{ borderColor: ink }}
                        onPointerDown={startDrag(f.id, h)} />
                ))}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
