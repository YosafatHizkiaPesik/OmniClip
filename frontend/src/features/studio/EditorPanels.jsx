import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Plus, Trash2, Loader2, Star, ChevronRight, Users, Palette, Sparkles, AlertTriangle, Scissors, Move } from 'lucide-react';
import { apiGet, apiPost } from '../../lib/api';
import { formatTime, parseTimeString } from '../../utils/timeFormat';
import { contrastRatio, inkSafe } from '../../lib/contrast';
import { cachedFonts, fontStack, loadFonts } from '../../lib/fonts';
import { JARAK_KATA, JARAK_KATA_MAKS, JARAK_KATA_MIN, bayanganTeks, gayaKata, hexAlpha, jarakKata } from './ClipPreview';
import {
  COLOR_GROUPS, COLOR_PAIRS, normalizeHex, useFavoriteColors, useRecentColors,
} from '../../lib/colors';
import { useT } from '../../lib/i18n';

/**
 * Sakelar induk warna per penutur, dibaca sekali per sesi.
 *
 * Dibaca di sini dan bukan dititipkan lewat prop karena dua panel yang jauh
 * terpisah membutuhkannya, dan keduanya hanya MEMBACA: yang mengubahnya adalah
 * Pengaturan. Satu panggilan yang dibagi lebih jujur daripada satu prop yang
 * harus dilewatkan melalui empat komponen yang tidak peduli.
 */
let warnaPenuturJanji = null;
const pendengarWarnaPenutur = new Set();

export function muatWarnaPenutur() {
  if (!warnaPenuturJanji) {
    warnaPenuturJanji = apiGet('/settings')
      .then((r) => r?.warna_penutur === true)
      .catch(() => false);
  }
  return warnaPenuturJanji;
}

/**
 * Menyalakan atau mematikan sakelar induk dari mana saja di Studio.
 *
 * Nilainya disiarkan ke semua yang sedang menampilkannya, bukan menunggu
 * halaman dimuat ulang: sakelar di tab Subtitle dan kotak centang di tab Gaya
 * menjelaskan hal yang sama, dan dua tempat yang tidak sepakat lebih
 * membingungkan daripada satu tempat yang sulit dicari.
 */
export async function setelWarnaPenutur(aktif) {
  await apiPost('/settings/warna-penutur', { aktif });
  warnaPenuturJanji = Promise.resolve(aktif);
  for (const beri of pendengarWarnaPenutur) beri(aktif);
}

function useWarnaPenutur() {
  const [boleh, setBoleh] = useState(false);
  useEffect(() => {
    let hidup = true;
    const beri = (v) => { if (hidup) setBoleh(v); };
    muatWarnaPenutur().then(beri);
    pendengarWarnaPenutur.add(beri);
    return () => { hidup = false; pendengarWarnaPenutur.delete(beri); };
  }, []);
  return boleh;
}

const label = {
  fontSize: '0.72rem',
  fontWeight: 700,
  color: 'var(--text-secondary)',
  textTransform: 'uppercase',
  letterSpacing: '0.04em',
};

const field = {
  width: '100%',
  padding: '9px 11px',
  borderRadius: 'var(--radius-sm)',
  border: '1px solid var(--border-color)',
  background: 'var(--bg-glass)',
  color: 'var(--text-primary)',
  fontSize: '0.84rem',
  fontFamily: 'inherit',
};

/**
 * Input waktu MM:SS yang bisa benar-benar diketik.
 *
 * Versi lama sepenuhnya terkendali dan memformat ulang setiap ketukan, sehingga
 * mengetik "2:30" mustahil: menekan "2" langsung berubah jadi "00:02" dan ":"
 * kemudian ditolak. Sekarang nilai draft dibiarkan apa adanya sampai blur/Enter.
 */
function TimeInput({ value, onCommit, disabled }) {
  const [draft, setDraft] = useState(formatTime(value));
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    if (!editing) setDraft(formatTime(value));
  }, [value, editing]);

  const commit = () => {
    setEditing(false);
    const parsed = parseTimeString(draft);
    if (Number.isFinite(parsed) && parsed >= 0) onCommit(parsed);
    else setDraft(formatTime(value));
  };

  return (
    <input
      value={draft}
      disabled={disabled}
      onFocus={() => setEditing(true)}
      onChange={(e) => setDraft(e.target.value)}
      onBlur={commit}
      onKeyDown={(e) => {
        if (e.key === 'Enter') e.currentTarget.blur();
        if (e.key === 'Escape') { setDraft(formatTime(value)); setEditing(false); e.currentTarget.blur(); }
      }}
      style={{ ...field, textAlign: 'center', fontVariantNumeric: 'tabular-nums' }}
    />
  );
}

/** Panel batas klip dan penggabungan potongan. */
// Diindeks langsung: [0] milik orang pertama. Putih di posisi pertama supaya
// video satu narasumber tampil persis seperti sebelum fitur ini ada.
const DEFAULT_SPEAKER_COLORS = ['#FFFFFF', '#7CFFB2', '#FFB3C7', '#B39DFF',
                               '#FFD166', '#5BC8FF', '#FF9F1C', '#B8FF3A'];

export function TrimPanel({ clip, videoDuration, busy, onNudge, onSetBounds, onAddSegment, onRemoveSegment }) {
  const t = useT();
  if (!clip) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', lineHeight: 1.6, margin: 0 }}>
        {t('batas.ket')}
      </p>

      {clip.segments.map((seg, idx) => (
        <div key={idx} style={{
          border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)',
          padding: '12px', background: 'var(--bg-glass)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <span style={label}>
              {clip.segments.length > 1 ? t('batas.potongan_n', { n: idx + 1 }) : t('batas.rentang')}
            </span>
            {clip.segments.length > 1 && (
              <button onClick={() => onRemoveSegment(clip.clip_id, idx)} disabled={busy}
                      aria-label={t('batas.hapus_potongan')}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--accent-red)', display: 'flex' }}>
                <Trash2 size={15} />
              </button>
            )}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
            {['start', 'end'].map((edge) => (
              <div key={edge}>
                <div style={{ ...label, marginBottom: '5px' }}>{edge === 'start' ? t('batas.mulai') : t('batas.selesai')}</div>
                <TimeInput
                  value={seg[edge]}
                  disabled={busy}
                  onCommit={(v) => onSetBounds(clip.clip_id, idx,
                    edge === 'start' ? v : seg.start,
                    edge === 'start' ? seg.end : v)}
                />
                <div style={{ display: 'flex', gap: '5px', marginTop: '6px' }}>
                  {[-5, -1, +1, +5].map((d) => (
                    <button key={d} disabled={busy}
                            onClick={() => onNudge(clip.clip_id, idx, edge, d, videoDuration)}
                            style={{
                              flex: 1, padding: '5px 0', fontSize: '0.72rem', fontWeight: 700,
                              borderRadius: '6px', cursor: busy ? 'default' : 'pointer',
                              border: '1px solid var(--border-color)',
                              background: 'transparent', color: 'var(--text-secondary)',
                            }}>
                      {d > 0 ? `+${d}` : d}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      <button
        className="btn-secondary"
        disabled={busy}
        onClick={() => {
          const last = clip.segments[clip.segments.length - 1];
          const start = Math.min((videoDuration || last.end + 60) - 20, last.end + 30);
          onAddSegment(clip.clip_id, Math.max(0, start), Math.max(0, start) + 15);
        }}
        style={{ fontSize: '0.8rem' }}
      >
        {busy ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
        {t('batas.gabung')}
      </button>
      <p style={{ fontSize: '0.74rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>
        {t('batas.gabung_ket')}
      </p>
    </div>
  );
}

/** Panel penyuntingan subtitle per baris. */
export function SubtitlePanel({ clip, onUpdate, onRemove, onSplit = null,
                               style, onStyle = null, onAutoSpeakers,
                               speakerCount = 2, speakerConfident = null,
                               onRedetect = null, redetecting = false,
                               // Baris yang sedang disorot di linimasa. Dua
                               // tampilan atas isi yang sama harus menunjuk
                               // baris yang sama, kalau tidak keduanya justru
                               // saling membingungkan.
                               selectedLine = null, onSelectLine = null,
                               onSeekLine = null }) {
  const t = useT();
  // Kait dipanggil SEBELUM percabangan keluar apa pun — komponen ini punya dua
  // jalan keluar lebih awal, dan kait di bawahnya akan berubah-ubah jumlahnya
  // antar render.
  const listRef = useRef(null);
  // Peta indeks -> elemen baris, BUKAN satu ref bersyarat.
  //
  // Versi sebelumnya memakai `ref={terpilih ? rowRef : null}`, dan ref bersyarat
  // seperti itu menunjuk baris yang salah pada saat yang salah: saat pilihannya
  // berpindah, React melepas ref dari baris lama dan memasangnya ke baris baru
  // dalam commit yang sama, dan di antara keduanya `rowRef.current` bisa masih
  // memegang baris LAMA. Efek penggulir lalu menggulir ke sana. Terekam
  // sungguhan: mengklik baris pertama, lalu daftarnya melompat ke baris detik
  // ke-18 setengah detik kemudian.
  const rowsRef = useRef(new Map());

  /**
   * Menggulir baris terpilih ke dalam pandangan — di dalam DAFTARNYA saja.
   *
   * Versi sebelumnya memanggil `scrollIntoView` dari sebuah ref callback, dan
   * itu dua kesalahan sekaligus. Ref callback dijalankan ulang pada SETIAP
   * render, bukan hanya saat pilihannya berpindah; dan `scrollIntoView`
   * menggulir seluruh rantai leluhur yang bisa digulir — termasuk halamannya.
   * Gabungan keduanya: selama video diputar, baris terpilih ikut berjalan, tiap
   * denyut menarik seluruh halaman turun ke panel subtitle, dan pengguna tidak
   * bisa menggulir kembali ke atas sampai videonya dijeda.
   *
   * Sekarang yang digulir hanya kotak daftarnya, lewat scrollTop, dan hanya
   * ketika baris terpilih benar-benar berganti.
   *
   * DAN hanya bila tidak ada yang sedang menyunting. Tanpa syarat terakhir itu,
   * membetulkan satu kata di baris pertama praktis tidak mungkin: garis mainnya
   * terus berjalan, baris terpilih ikut pindah ke bawah, dan daftarnya menyeret
   * baris yang sedang diketik keluar dari layar. Dilaporkan persis begitu:
   * "saat saya mengklik subtitle, tampilan langsung lompat ke subtitle
   * bawahnya, jadi saya harus menggulir lagi ke atas".
   */
  /**
   * POSISI GULIR DAFTAR DIPERTAHANKAN SELAMA MENYUNTING.
   *
   * Dilaporkan pemiliknya 5 Oktober 2026: "saat saya mengedit subtitle selalu
   * terscroll ke bawah, jadi saya harus scroll lagi ke atas untuk melihat
   * subtitle yang saya edit". Dicoba ditiru di Firefox — video berjalan,
   * mengetik di baris paling atas — dan TIDAK tereproduksi: `scrollTop` tetap
   * nol. Jadi sebabnya belum diketahui pasti.
   *
   * Yang tidak perlu menunggu sebabnya diketahui: posisi gulirnya sendiri.
   * Selama ada yang diketik di dalam daftar ini, posisi itu milik orang yang
   * mengetik — bukan milik efek mana pun, bukan milik peramban yang menjepit
   * `scrollTop` saat tinggi isinya berubah sesaat. Nilainya dicatat tiap kali
   * orangnya menggulir sendiri, dan dikembalikan sesudah tiap penggambaran
   * ulang yang bukan ulahnya.
   *
   * `useLayoutEffect`, bukan `useEffect`: pengembaliannya harus terjadi sebelum
   * peramban menggambar, kalau tidak yang terlihat tetap satu kedipan lompat.
   */
  /**
   * Tinggi textarea menyesuaikan isinya — SEKALI saat dipasang, lalu tiap kali
   * isinya berubah lewat `onChange`.
   *
   * Dulu dikerjakan dari ref callback, yang React jalankan ulang pada SETIAP
   * penggambaran: dua puluh empat textarea masing-masing disetel `height:auto`
   * lalu dibaca `scrollHeight`-nya, dua puluh empat kali memaksa peramban
   * menghitung ulang tata letak. Dan di antara "auto" dan tinggi yang baru,
   * seluruh isi daftar memendek sesaat — saat itulah peramban berhak menjepit
   * `scrollTop`, dan posisi guliran orang yang sedang mengetik hilang.
   */
  const pasangTinggi = useCallback((el) => {
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, []);

  // Berganti klip memakai elemen textarea yang SAMA dengan isi yang berbeda,
  // jadi tinggi yang dipasang saat elemennya lahir sudah tidak cocok lagi.
  // Dipasang ulang di sini, sekali per pergantian — bukan tiap penggambaran.
  useLayoutEffect(() => {
    const kotak = listRef.current;
    if (!kotak) return;
    for (const ta of kotak.querySelectorAll('textarea')) {
      ta.style.height = 'auto';
      ta.style.height = `${ta.scrollHeight}px`;
    }
  }, [clip?.clip_id, (clip?.subtitles ?? []).length]);

  const gulirRef = useRef(0);
  const padaGulir = useCallback(() => {
    const kotak = listRef.current;
    if (kotak) gulirRef.current = kotak.scrollTop;
  }, []);

  useLayoutEffect(() => {
    const kotak = listRef.current;
    if (!kotak) return;
    const menyunting = kotak.contains(document.activeElement)
      && document.activeElement !== document.body;
    if (!menyunting) return;
    if (Math.abs(kotak.scrollTop - gulirRef.current) > 1) {
      kotak.scrollTop = gulirRef.current;
    }
  });

  useEffect(() => {
    const kotak = listRef.current;
    const baris = selectedLine == null ? null : rowsRef.current.get(selectedLine);
    if (!kotak || !baris) return;
    // Ada yang sedang diketik di dalam daftar ini: jangan disentuh.
    if (kotak.contains(document.activeElement)
        && document.activeElement !== document.body) return;
    // DIUKUR DARI KOTAKNYA, bukan dari `offsetTop`.
    //
    // Inilah sebab lompatan yang dua kali gagal saya tiru, dan baru tertangkap
    // 6 Oktober 2026 dengan menirukan KLIKNYA: digulir ke 420, klik baris yang
    // sedang terlihat, dan daftarnya melompat ke 1328.
    //
    // `offsetTop` diukur dari leluhur ber-`position` terdekat. Kotak daftar ini
    // tidak punya `position`, jadi angkanya datang dari suatu tempat jauh di
    // atas halaman — jauh lebih besar daripada jangkauan gulir kotaknya
    // sendiri. Menggulir ke angka itu berarti menggulir sampai mentok ke bawah,
    // dan baris yang baru saja diklik justru hilang dari pandangan.
    //
    // `getBoundingClientRect` tidak peduli siapa leluhurnya: selisih dua tepi
    // ditambah posisi gulir sekarang selalu memberi jarak yang benar.
    const kotakRect = kotak.getBoundingClientRect();
    const barisRect = baris.getBoundingClientRect();
    const atas = kotak.scrollTop + (barisRect.top - kotakRect.top);
    const bawah = atas + barisRect.height;
    // Yang sudah terlihat seluruhnya dibiarkan: menggulir ke tempat yang sama
    // tidak menambah apa pun, dan tiap gulir adalah kesempatan untuk salah.
    if (atas >= kotak.scrollTop && bawah <= kotak.scrollTop + kotak.clientHeight) return;
    if (atas < kotak.scrollTop) kotak.scrollTop = atas - 6;
    else kotak.scrollTop = bawah - kotak.clientHeight + 6;
  }, [selectedLine]);

  if (!clip) return null;
  const lines = clip.subtitles ?? [];

  if (!lines.length) {
    return (
      <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
        {t('sub.kosong')}
      </p>
    );
  }

  const palette = style?.speaker_colors ?? DEFAULT_SPEAKER_COLORS;
  const colorOf = (i) => palette[i] ?? style?.primary ?? '#FFFFFF';
  // Langit-langit nomor orang TIDAK dikunci ke jumlah hasil deteksi.
  //
  // Sebelumnya ia persis sama dengan `speakerCount`, jadi ketika pemisahan
  // suara menjawab "2", tombol nomor hanya berputar 1-2 dan orang ketiga
  // sampai kelima tidak bisa ditandai sama sekali — bahkan secara manual.
  // Itu membuat satu-satunya jalan keluar dari tebakan yang meleset ikut
  // tertutup oleh tebakan itu sendiri.
  //
  // Sekarang selalu ada satu slot cadangan di atas nomor tertinggi yang sudah
  // terpakai, jadi orang keempat dan kelima bisa dicapai hanya dengan terus
  // mengklik, tanpa mendeteksi ulang lebih dulu.
  // Langit-langitnya adalah jumlah penutur yang benar-benar terdeteksi.
  //
  // Versi sebelumnya menambahkan satu slot cadangan di atas nomor tertinggi
  // yang sudah terpakai, supaya orang keempat dan kelima bisa dicapai ketika
  // pemisahan suara masih terkunci di dua. Sejak jumlah yang diminta pengguna
  // dituruti, cadangan itu berubah jadi cacat: video berpenutur lima
  // menawarkan nomor sampai tujuh, dan dua nomor terakhir tidak menunjuk
  // siapa pun. Kalau jumlahnya memang kurang, yang benar adalah mendeteksi
  // ulang dengan angka yang tepat — bukan menambah nomor hantu di sini.
  const usedMax = lines.reduce((m, l) => Math.max(m, l.speaker || 0), 0);
  const total = Math.min(8, Math.max(2, speakerCount || 2, usedMax + 1));
  const tally = lines.reduce((acc, l) => {
    const i = l.speaker || 0;
    acc[i] = (acc[i] || 0) + 1;
    return acc;
  }, {});

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
      <p style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5 }}>
        {t('sub.ket_a', { n: lines.length })} <b>{t('sub.ket_b')}</b> {t('sub.ket_c')}{' '}
        <b>{t('sub.ket_d')}</b> {t('sub.ket_e')}
      </p>

      <div style={{
        padding: '10px 11px', borderRadius: 'var(--radius-sm)',
        background: 'var(--bg-glass)', border: '1px solid var(--border-color)',
      }}>
        <div style={{ fontSize: '0.75rem', fontWeight: 700, marginBottom: '4px' }}>
          {speakerConfident === null ? t('sub.penanda')
            : speakerConfident
              ? t('sub.terdeteksi', { n: speakerCount })
              : t('sub.sulit')}
        </div>
        <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.55 }}>
          {speakerConfident === false
            ? t('sub.sulit_ket')
            : t('sub.tebak_ket')}
        </p>

        {onRedetect && <SpeakerCountPicker current={speakerCount} busy={redetecting}
                                          onRedetect={onRedetect} />}

        <button className="btn-secondary" onClick={() => onAutoSpeakers?.(clip.clip_id)}
                disabled={redetecting}
                style={{ fontSize: '0.72rem', padding: '6px 9px', marginTop: '8px' }}>
          {t('sub.dari_jeda')}
        </button>
        <p style={{ fontSize: '0.65rem', color: 'var(--text-muted)', margin: '5px 0 0', lineHeight: 1.5 }}>
          {t('sub.dari_jeda_ket')}
        </p>
      </div>

      {/* Warna tiap orang, di tempat orangnya ditandai.
          Dulu satu-satunya tempat mengaturnya adalah tab Gaya → Warna, bagian
          yang tertutup dan jauh dari baris-baris yang ditandai, pengguna yang
          mencari "warna untuk orang ini" mencarinya di sini, di sebelah
          penandanya. Keduanya menulis ke palet yang sama. */}
      <WarnaTiapOrang
        jumlah={Array.from({ length: total }, (_, i) => i)
          .filter((i) => tally[i] || i < Math.max(1, speakerCount || 1))}
        tally={tally} palette={palette} style={style} onStyle={onStyle} />

      <div ref={listRef}
           onScroll={padaGulir}
           style={{ position: 'relative', display: 'flex', flexDirection: 'column',
                    gap: '8px', maxHeight: '380px', overflowY: 'auto' }}>
        {lines.map((line, i) => {
          const speaker = line.speaker || 0;
          const on = selectedLine === i;
          const bebas = Number.isFinite(line.x) && Number.isFinite(line.y);
          return (
            <div key={i}
                 ref={(el) => {
                   if (el) rowsRef.current.set(i, el);
                   else rowsRef.current.delete(i);
                 }}
                 onPointerDown={() => onSelectLine?.(i)}
                 style={{
                   display: 'grid', gridTemplateColumns: '52px 22px 1fr 26px', gap: '7px',
                   // Rata ATAS, bukan tengah: kotak teksnya kini tumbuh ke
                   // bawah mengikuti panjang kalimat, dan waktu serta penanda
                   // penuturnya harus tetap sebaris dengan baris pertamanya.
                   alignItems: 'start',
                   // Sorotan yang sama dengan yang dipakai linimasa: pengguna
                   // yang menyeret sebuah baris di bawah harus bisa menemukan
                   // teksnya di sini tanpa mencari.
                   background: on ? 'var(--hl-wash)' : 'transparent',
                   boxShadow: on ? 'inset 0 0 0 1.5px var(--hl)' : 'none',
                   borderRadius: 'var(--r-sm)',
                   padding: on ? '3px 4px' : '3px 4px',
                 }}>
              <button onClick={() => onSeekLine?.(line.start)}
                      title={t('sub.putar_baris')}
                      style={{
                        background: 'none', border: 'none', padding: 0, textAlign: 'left',
                        cursor: onSeekLine ? 'pointer' : 'default',
                        fontFamily: 'inherit', fontSize: '0.7rem',
                        color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums',
                        paddingTop: '9px',
                      }}>
                {line.start.toFixed(1)}s
              </button>
              <button
                onClick={() => onUpdate(clip.clip_id, i, { speaker: (speaker + 1) % total })}
                title={t('sub.orang_klik', { n: speaker + 1, total })}
                aria-label={t('sub.ganti_penanda')}
                style={{
                  width: '20px', height: '20px', borderRadius: '50%', cursor: 'pointer',
                  background: colorOf(speaker), border: '2px solid var(--border-color)',
                  padding: 0, fontSize: '0.6rem', fontWeight: 900, color: '#00121a',
                }}
              >{speaker + 1}</button>
              {/* Textarea, bukan input satu baris.
                  Kalimat subtitle rutin melewati enam puluh karakter,
                  sedangkan kolomnya selebar sisa kisi, jadi dengan <input>
                  sebagian besar kalimat tidak pernah terlihat utuh, dan
                  menyunting kata di tengah berarti menggeser isi kotak dulu
                  untuk mencari tempatnya. Tingginya menyesuaikan isi, jadi
                  baris pendek tetap setinggi satu baris. */}
              <textarea
                value={line.text}
                rows={1}
                ref={pasangTinggi}
                onChange={(e) => {
                  e.target.style.height = 'auto';
                  e.target.style.height = `${e.target.scrollHeight}px`;
                  onUpdate(clip.clip_id, i, { text: e.target.value });
                }}
                style={{
                  ...field, fontSize: '0.8rem', padding: '7px 9px',
                  resize: 'none', overflow: 'hidden', lineHeight: 1.4,
                  fontFamily: 'inherit', minHeight: '32px',
                  // Warna penutur dipakai di kotak isian supaya menandai satu
                  // baris terlihat hasilnya saat itu juga — tapi hanya bila ia
                  // lolos kontras di atas pelat. Warna subtitle dipilih untuk
                  // teks di ATAS video; pastel seperti #FFB3C7 tampil 1,3:1 di
                  // atas kertas. Yang tidak lolos memakai tinta, dan titik di
                  // sebelahnya yang membawa identitas penuturnya.
                  color: inkSafe(colorOf(speaker)),
                  fontWeight: speaker ? 700 : 400,
                }}
              />
              {/* Memecah baris tepat di tempat kursor berada.
                  Kursor, bukan tengah: yang tahu di mana kalimatnya patah
                  adalah orang yang sedang membacanya, dan ia sudah menaruh
                  kursornya di situ untuk mengetik. Tanpa kursor — tombolnya
                  ditekan tanpa menyentuh teksnya dulu — dipakai tengahnya. */}
              {/* Melepaskan baris ini dari gaya klip: ia dapat letaknya
                  sendiri di kanvas, dan sejak itu bisa diseret di pratinjau.
                  Ditekan lagi, ia kembali mengikuti gaya klipnya. */}
              <button onClick={() => onUpdate(clip.clip_id, i, bebas
                        ? { x: null, y: null }
                        : { x: style?.pos_x ?? 50,
                            y: style?.position === 'top' ? 15
                               : style?.position === 'middle' ? 50 : 85 })}
                      aria-label={bebas ? t('sub.kembalikan_gaya') : t('sub.letak_sendiri')}
                      title={bebas
                        ? t('sub.letak_bebas_judul')
                        : t('sub.letak_sendiri_judul')}
                      style={{ background: 'none', border: 'none', cursor: 'pointer',
                               color: bebas ? 'var(--reh)' : 'var(--text-muted)',
                               display: 'flex' }}>
                <Move size={14} />
              </button>
              {onSplit && (
                <button onClick={(e) => {
                          const ta = e.currentTarget.parentElement
                            ?.querySelector('textarea');
                          const teks = line.text || '';
                          const pos = (ta && ta.selectionStart > 0
                                       && ta.selectionStart < teks.length)
                            ? ta.selectionStart : Math.floor(teks.length / 2);
                          // Posisi huruf -> nomor kata.
                          const kata = teks.slice(0, pos).trim().split(/\s+/)
                            .filter(Boolean).length;
                          onSplit(clip.clip_id, i, kata);
                        }}
                        aria-label={t('sub.pecah')}
                        title={t('sub.pecah_judul')}
                        style={{ background: 'none', border: 'none', cursor: 'pointer',
                                 color: 'var(--text-muted)', display: 'flex' }}>
                  <Scissors size={14} />
                </button>
              )}
              <button onClick={() => onRemove(clip.clip_id, i)} aria-label={t('sub.hapus_baris')}
                      style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex' }}>
                <Trash2 size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Warna yang tetap terbaca di atas video apa pun, dengan garis tepi hitam.
const WARNA_ORANG = ['#FFFFFF', '#FFE500', '#7CFFB2', '#5BC8FF', '#FFB3C7',
                     '#B39DFF', '#FF9F1C', '#FF6B6B'];

/**
 * Keping "Orang N · sekian baris" yang sekaligus pemilih warnanya.
 *
 * Memilih warna juga menyalakan kembali warna per orang bila sedang diseragamkan:
 * orang yang sengaja memberi Orang 2 warna hijau jelas ingin melihatnya hijau,
 * dan diam-diam tidak terjadi apa-apa adalah jawaban terburuk.
 */
function WarnaTiapOrang({ jumlah, tally, palette, style, onStyle: onStyleProp }) {
  const t = useT();
  const [buka, setBuka] = useState(null);
  const [sibuk, setSibuk] = useState(false);
  const boleh = useWarnaPenutur();
  // Sakelar induk mati berarti panel ini hanya menghitung baris. Tombol yang
  // menyalakan sesuatu yang tetap tidak akan dirender lebih buruk daripada
  // tidak ada tombol sama sekali.
  const onStyle = boleh ? onStyleProp : null;
  const seragam = style?.per_speaker_colors === false;

  /**
   * Sakelarnya ada DI SINI, bukan hanya di Pengaturan.
   *
   * Warna per penutur adalah keputusan per video, bukan setelan yang dipasang
   * sekali seumur hidup: podcast dua orang bersuara jelas berbeda pantas
   * diwarnai, podcast tiga orang yang suaranya mirip tidak. Menyuruh orang
   * meninggalkan Studio, membuka Pengaturan, lalu kembali, untuk keputusan
   * yang hanya bisa dinilai sambil melihat klipnya, adalah jalan memutar yang
   * tidak ada gunanya. Sakelar di Pengaturan tetap ada beserta angka ujinya.
   */
  const ubahSakelar = async (nilai) => {
    setSibuk(true);
    try {
      await setelWarnaPenutur(nilai);
      if (onStyleProp) onStyleProp({ ...style, per_speaker_colors: nilai });
    } catch {
      /* gagal menyimpan: sakelar kembali sendiri karena nilainya dari server */
    } finally {
      setSibuk(false);
    }
  };
  const warnaDari = (i) => palette[i] ?? DEFAULT_SPEAKER_COLORS[i] ?? '#FFFFFF';

  const setel = (i, c) => {
    const next = [...(style?.speaker_colors ?? DEFAULT_SPEAKER_COLORS)];
    while (next.length <= i) next.push(DEFAULT_SPEAKER_COLORS[next.length] ?? '#FFFFFF');
    next[i] = c.toUpperCase();
    onStyle({ ...style, speaker_colors: next, per_speaker_colors: true });
  };

  return (
    <div>
      <div style={{ ...label, fontSize: '0.7rem', marginBottom: '6px' }}>
        {t('warna.judul')}
      </div>
      {onStyleProp && (
        <label style={{
          display: 'flex', alignItems: 'center', gap: '9px', cursor: sibuk ? 'default' : 'pointer',
          padding: '7px 9px', marginBottom: '8px', borderRadius: 'var(--radius-sm)',
          background: boleh ? 'var(--hl-wash)' : 'transparent',
          border: `1px solid ${boleh ? 'var(--hl)' : 'var(--border-color)'}`,
          opacity: sibuk ? 0.6 : 1,
        }}>
          <input type="checkbox" checked={boleh} disabled={sibuk}
                 onChange={(e) => ubahSakelar(e.target.checked)}
                 style={{ width: '15px', height: '15px', accentColor: 'var(--accent-cyan)',
                          flex: 'none' }} />
          <span style={{ fontSize: '0.73rem', fontWeight: 700, color: 'var(--ink)' }}>
            {t('warna.sakelar')}
          </span>
        </label>
      )}
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
        {jumlah.map((i) => (
          <div key={i}>
            <button
              onClick={() => onStyle && setBuka(buka === i ? null : i)}
              disabled={!onStyle}
              title={onStyle ? t('warna.pilih_untuk', { n: i + 1 }) : undefined}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: '6px', padding: '4px 9px',
                borderRadius: '99px', fontSize: '0.7rem', fontWeight: 700, fontFamily: 'inherit',
                cursor: onStyle ? 'pointer' : 'default', color: 'var(--text-primary)',
                background: buka === i ? 'var(--hl-wash)' : 'var(--bg-glass)',
                border: `1px solid ${buka === i ? 'var(--hl)' : 'var(--border-color)'}`,
                opacity: seragam ? 0.55 : 1,
              }}>
              <span style={{
                width: '13px', height: '13px', borderRadius: '50%',
                background: warnaDari(i), border: '1px solid rgba(0,0,0,0.45)',
              }} />
              {t('warna.orang_baris', { n: i + 1, baris: tally[i] || 0 })}
              {onStyle && <Palette size={11} style={{ color: 'var(--text-muted)' }} />}
            </button>
          </div>
        ))}
      </div>
      {/* Terbuka di bawah deretan keping, selebar panel, bukan melayang di
          bawah kepingnya. Keping orang kedua ke kanan berada di tepi panel
          yang sempit, dan kotak melayang di sana terpotong separuh. */}
      {buka !== null && (
        <div style={{
          marginTop: '7px', padding: '9px 10px', borderRadius: 'var(--radius-sm)',
          background: 'var(--bg-glass)', border: '1px solid var(--border-color)',
        }}>
          <div style={{ fontSize: '0.68rem', fontWeight: 700, color: 'var(--text-secondary)',
                        marginBottom: '7px' }}>
            {t('warna.untuk', { n: buka + 1 })}
          </div>
          <div style={{ display: 'flex', gap: '7px', flexWrap: 'wrap', alignItems: 'center' }}>
            {WARNA_ORANG.map((c) => {
              const on = warnaDari(buka).toUpperCase() === c;
              return (
                <button key={c} onClick={() => { setel(buka, c); setBuka(null); }}
                        title={c} aria-label={t('warna.hex', { c })}
                        style={{
                          width: '26px', height: '26px', borderRadius: '50%', cursor: 'pointer',
                          background: c, padding: 0,
                          border: on ? '2px solid var(--accent-cyan)' : '1px solid rgba(0,0,0,0.45)',
                        }} />
              );
            })}
            <label title={t('warna.lain')} style={{ display: 'inline-flex', alignItems: 'center', gap: '5px',
                                               fontSize: '0.68rem', color: 'var(--text-secondary)',
                                               fontWeight: 700, cursor: 'pointer' }}>
              <input type="color" value={warnaDari(buka)}
                     onChange={(e) => setel(buka, e.target.value)}
                     style={{ width: '30px', height: '26px', padding: 0, border: 'none',
                              background: 'none', cursor: 'pointer' }} />
              {t('warna.lainnya')}
            </label>
          </div>
        </div>
      )}
      {!boleh && onStyleProp && (
        <p style={{ fontSize: '0.66rem', color: 'var(--text-muted)', margin: '6px 0 0', lineHeight: 1.5 }}>
          {t('warna.mati_ket')}
        </p>
      )}
      {seragam && onStyle && (
        <p style={{ fontSize: '0.66rem', color: 'var(--text-muted)', margin: '6px 0 0', lineHeight: 1.5 }}>
          {t('warna.seragam')}{' '}
          <button onClick={() => onStyle({ ...style, per_speaker_colors: true })}
                  style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                           color: 'var(--accent-cyan)', fontWeight: 700, fontSize: 'inherit',
                           fontFamily: 'inherit' }}>
            {t('warna.nyalakan')}
          </button>
        </p>
      )}
    </div>
  );
}

/**
 * Memberitahukan jumlah narasumber kepada sistem.
 *
 * Menebak jumlah kelompok adalah bagian paling rapuh dari pemisahan suara
 * otomatis — jauh lebih rapuh daripada menentukan siapa bicara kapan begitu
 * jumlahnya diketahui. Pengguna sudah menonton videonya dan tahu jawabannya,
 * jadi membiarkannya menjawab menghapus separuh kesulitannya.
 */
function SpeakerCountPicker({ current, busy, onRedetect }) {
  const t = useT();
  const [value, setValue] = useState(Math.max(1, Math.min(6, current || 2)));
  return (
    <div style={{ marginTop: '10px' }}>
      <div style={{ ...label, fontSize: '0.66rem', marginBottom: '6px' }}>
        {t('narasumber.jumlah')}
      </div>
      <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap' }}>
        {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
          <button key={n} onClick={() => setValue(n)} disabled={busy}
                  style={{
                    width: '30px', height: '30px', borderRadius: '7px',
                    cursor: busy ? 'default' : 'pointer', fontWeight: 800, fontSize: '0.8rem',
                    border: value === n ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                    background: value === n ? 'var(--hl-wash)' : 'transparent',
                    color: value === n ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                  }}>{n}</button>
        ))}
      </div>
      <div style={{ display: 'flex', gap: '6px', marginTop: '8px', flexWrap: 'wrap' }}>
        <button className="btn-primary" disabled={busy}
                onClick={() => onRedetect(value)}
                style={{ fontSize: '0.73rem', padding: '6px 10px' }}>
          {busy ? <Loader2 size={13} className="animate-spin" /> : <Users size={13} />}
          {t('narasumber.deteksi', { n: value })}
        </button>
        <button className="btn-secondary" disabled={busy}
                onClick={() => onRedetect(null)}
                style={{ fontSize: '0.73rem', padding: '6px 10px' }}>
          {t('narasumber.tebak')}
        </button>
      </div>
      <p style={{ fontSize: '0.65rem', color: 'var(--text-muted)', margin: '6px 0 0', lineHeight: 1.5 }}>
        {t('narasumber.ket')}
      </p>
    </div>
  );
}

// --- Gaya teks ----------------------------------------------------------------


// Preset gaya: tiap preset adalah satu MODEL tampilan (font, garis, bayangan,
// cara menyorot, animasi), dan warnanya diatur terpisah lewat "Warna aksen".
//
// Diminta pemilik 17 Oktober 2026: banyak preset lama "sama hanya beda warna"
// (Kotak kuning/hijau/merah/ungu, Neon biru/pink, Tebal/Naik/Papan/Ceria).
// Sekarang satu model satu preset, dan `aksen` menyebut bidang mana yang
// diwarnai oleh baris Warna aksen. Model-model baru memakai kemampuan render
// yang ditambahkan hari yang sama: warna garis luar, pendar, huruf miring,
// jarak huruf, dan kemiringan baris (backend services/subtitles.py).
//
// `label`, `hint`, dan `kategori` adalah kunci kamus. Id lama dipetakan ke
// model baru + warnanya di ALIAS_TEMA, supaya saran tema yang tersimpan dan
// tema yang dipilih AI dari daftar lama tetap bisa dipasang.
const GAYA_DASAR = {
  sorot: null, highlight_words: true, bg: false, outline_px: 7, shadow_px: 3,
  bayang_warna: '#000000', garis_warna: '#000000', pendar: 0, miring: false,
  spasi_huruf: 0, kemiringan: 0, primary: '#FFFFFF', position: 'bottom', margin_v: 300,
};

export const STYLE_PRESETS = [
  // --- Populer ---------------------------------------------------------------
  { id: 'kotak_sorot', kategori: 'gs.k_populer', label: 'tema_sub.kotak_sorot', hint: 'tema_sub.kotak_sorot_ket',
    aksen: ['kotak_warna', 'highlight'],
    patch: { size: 86, highlight: '#FFE500', font: 'Montserrat', uppercase: true, animation: 'pop_in',
             outline_px: 7, sorot: 'kotak', kotak_warna: '#FFE500', kotak_teks: '#101010' } },
  { id: 'kotak_pantul', kategori: 'gs.k_populer', label: 'tema_sub.kotak_pantul', hint: 'tema_sub.kotak_pantul_ket',
    aksen: ['kotak_warna', 'highlight'],
    patch: { size: 84, highlight: '#FF3B5C', font: 'Archivo Black', uppercase: true, animation: 'pantul',
             outline_px: 7, sorot: 'kotak_pop', kotak_warna: '#FF3B5C', kotak_teks: '#FFFFFF' } },
  { id: 'tebal', kategori: 'gs.k_populer', label: 'tema_sub.tebal', hint: 'tema_sub.tebal_ket',
    aksen: ['highlight'],
    patch: { size: 96, highlight: '#FFE500', font: 'Montserrat', uppercase: true, animation: 'karaoke_pop',
             outline_px: 7 } },
  { id: 'bayang_tegas', kategori: 'gs.k_populer', label: 'tema_sub.bayang_tegas', hint: 'tema_sub.bayang_tegas_ket',
    aksen: ['highlight'],
    patch: { size: 98, highlight: '#00E676', font: 'Montserrat', uppercase: true, animation: 'pop_in',
             outline_px: 0, shadow_px: 7, bayang_warna: '#000000', sorot: 'pop' } },
  { id: 'satu_kata', kategori: 'gs.k_populer', label: 'tema_sub.satu_kata', hint: 'tema_sub.satu_kata_ket',
    aksen: ['highlight'],
    patch: { size: 150, highlight: '#FFE500', font: 'Anton', uppercase: true, animation: 'satu_kata',
             position: 'middle', outline_px: 9, margin_v: 300 } },
  // --- Nyala -----------------------------------------------------------------
  { id: 'neon', kategori: 'gs.k_nyala', label: 'tema_sub.neon', hint: 'tema_sub.neon_ket',
    aksen: ['highlight'],
    patch: { size: 100, highlight: '#00E5FF', font: 'Anton', uppercase: true, animation: 'blur_masuk',
             outline_px: 7, sorot: 'glow' } },
  { id: 'pendar', kategori: 'gs.k_nyala', label: 'tema_sub.pendar', hint: 'tema_sub.pendar_ket',
    aksen: ['garis_warna'],
    patch: { size: 90, highlight: '#FFFFFF', font: 'Poppins', uppercase: false, animation: 'fade',
             outline_px: 6, shadow_px: 0, garis_warna: '#FF3DCB', pendar: 10, highlight_words: false,
             sorot: 'mati' } },
  { id: 'garis_warna', kategori: 'gs.k_nyala', label: 'tema_sub.garis_warna', hint: 'tema_sub.garis_warna_ket',
    aksen: ['garis_warna'],
    patch: { size: 94, highlight: '#FFE500', font: 'Lilita One', uppercase: true, animation: 'pop_in',
             outline_px: 10, shadow_px: 0, garis_warna: '#7B2CFF', sorot: 'warna' } },
  // --- Pelat -----------------------------------------------------------------
  { id: 'apple', kategori: 'gs.k_pelat', label: 'tema_sub.apple', hint: 'tema_sub.apple_ket',
    aksen: ['bg_color'],
    patch: { size: 76, highlight: '#FFFFFF', font: 'Poppins', uppercase: false, animation: 'fade',
             outline_px: 0, highlight_words: false, sorot: 'mati', bg: true, bg_color: '#000000',
             bg_opacity: 0.55, bg_pad: 14 } },
  { id: 'sinema', kategori: 'gs.k_pelat', label: 'tema_sub.sinema', hint: 'tema_sub.sinema_ket',
    aksen: ['primary'],
    patch: { size: 64, highlight: '#FFFFFF', font: 'Rubik', uppercase: false, animation: 'none',
             outline_px: 0, highlight_words: false, sorot: 'mati', bg: true, bg_color: '#000000',
             bg_opacity: 0.72, bg_pad: 10 } },
  { id: 'stiker', kategori: 'gs.k_pelat', label: 'tema_sub.stiker', hint: 'tema_sub.stiker_ket',
    aksen: ['bg_color'], kontras: true,
    patch: { size: 84, primary: '#101010', highlight: '#101010', font: 'Lilita One', uppercase: true,
             animation: 'pop_in', outline_px: 0, highlight_words: false, sorot: 'mati', bg: true,
             bg_color: '#FFE500', bg_opacity: 0.95, bg_pad: 16 } },
  { id: 'label_miring', kategori: 'gs.k_pelat', label: 'tema_sub.label_miring', hint: 'tema_sub.label_miring_ket',
    aksen: ['bg_color'], kontras: true,
    patch: { size: 86, primary: '#FFFFFF', highlight: '#FFFFFF', font: 'Anton', uppercase: true,
             animation: 'pop_in', outline_px: 0, highlight_words: false, sorot: 'mati', bg: true,
             bg_color: '#FF3B5C', bg_opacity: 1, bg_pad: 16, miring: true, kemiringan: 4 } },
  // --- Gaya huruf ------------------------------------------------------------
  { id: 'retro', kategori: 'gs.k_huruf', label: 'tema_sub.retro', hint: 'tema_sub.retro_ket',
    aksen: ['bayang_warna'],
    patch: { size: 88, highlight: '#FFE500', font: 'Lilita One', uppercase: true, animation: 'putar',
             outline_px: 0, shadow_px: 9, bayang_warna: '#FF00AA', sorot: 'warna' } },
  { id: 'elegan', kategori: 'gs.k_huruf', label: 'tema_sub.elegan', hint: 'tema_sub.elegan_ket',
    aksen: ['primary'],
    patch: { size: 84, primary: '#FFF6E0', highlight: '#FFF6E0', font: 'Playfair Display', uppercase: false,
             animation: 'fade', outline_px: 0, shadow_px: 3, miring: true, highlight_words: false,
             sorot: 'mati' } },
  { id: 'lebar', kategori: 'gs.k_huruf', label: 'tema_sub.lebar', hint: 'tema_sub.lebar_ket',
    aksen: ['primary'],
    patch: { size: 104, highlight: '#FFFFFF', font: 'Bebas Neue', uppercase: true, animation: 'fade',
             outline_px: 5, spasi_huruf: 10, highlight_words: false, sorot: 'mati' } },
  { id: 'komik', kategori: 'gs.k_huruf', label: 'tema_sub.komik', hint: 'tema_sub.komik_ket',
    aksen: ['highlight'],
    patch: { size: 92, highlight: '#FF9F1C', font: 'Luckiest Guy', uppercase: true, animation: 'pantul',
             outline_px: 9, kemiringan: -3, sorot: 'warna' } },
  { id: 'miring_cepat', kategori: 'gs.k_huruf', label: 'tema_sub.miring_cepat', hint: 'tema_sub.miring_cepat_ket',
    aksen: ['highlight'],
    patch: { size: 96, highlight: '#B8FF3A', font: 'Anton', uppercase: true, animation: 'geser_kiri',
             outline_px: 7, miring: true, sorot: 'warna' } },
  { id: 'garis_bawah', kategori: 'gs.k_huruf', label: 'tema_sub.garis_bawah', hint: 'tema_sub.garis_bawah_ket',
    aksen: ['highlight'],
    patch: { size: 80, highlight: '#FFE500', font: 'Poppins', uppercase: false, animation: 'fade',
             outline_px: 6, sorot: 'garis_bawah' } },
  { id: 'ramping', kategori: 'gs.k_huruf', label: 'tema_sub.ramping', hint: 'tema_sub.ramping_ket',
    aksen: ['highlight'],
    patch: { size: 118, highlight: '#00F5D4', font: 'Teko', uppercase: true, animation: 'karaoke_wipe',
             outline_px: 6 } },
  // --- Gerak -----------------------------------------------------------------
  { id: 'ketik', kategori: 'gs.k_gerak', label: 'tema_sub.ketik', hint: 'tema_sub.ketik_ket',
    aksen: ['primary'],
    patch: { size: 92, highlight: '#FFE500', font: 'Montserrat', uppercase: true, animation: 'typewriter',
             outline_px: 7, highlight_words: false, sorot: 'mati' } },
  { id: 'lembut', kategori: 'gs.k_gerak', label: 'tema_sub.lembut', hint: 'tema_sub.lembut_ket',
    aksen: ['highlight'],
    patch: { size: 84, highlight: '#FFD166', font: 'Poppins', uppercase: false, animation: 'fade',
             outline_px: 5, sorot: 'warna' } },
  { id: 'fokus', kategori: 'gs.k_gerak', label: 'tema_sub.fokus', hint: 'tema_sub.fokus_ket',
    aksen: ['highlight'],
    patch: { size: 88, highlight: '#FFD166', font: 'Rubik', uppercase: false, animation: 'blur_masuk',
             outline_px: 6, sorot: 'pop' } },
  { id: 'getar', kategori: 'gs.k_gerak', label: 'tema_sub.getar', hint: 'tema_sub.getar_ket',
    aksen: ['highlight'],
    patch: { size: 84, highlight: '#FF4D5E', font: 'Bungee', uppercase: true, animation: 'getar',
             outline_px: 8, sorot: 'pop' } },
  { id: 'bersih', kategori: 'gs.k_gerak', label: 'tema_sub.bersih', hint: 'tema_sub.bersih_ket',
    aksen: ['primary'],
    patch: { size: 88, highlight: '#FFFFFF', font: 'Rubik', uppercase: false, animation: 'none',
             outline_px: 5, highlight_words: false, sorot: 'mati' } },
];
// Gabungkan dasar ke tiap patch: preset selalu mulai dari keadaan yang sama.
STYLE_PRESETS.forEach((p) => { p.patch = { ...GAYA_DASAR, ...p.patch }; });

// Id tema lama -> [model baru, warna aksen]. Lihat catatan di atas.
export const ALIAS_TEMA = {
  kotak_kuning: ['kotak_sorot', '#FFE500'], kotak_hijau: ['kotak_sorot', '#00E676'],
  kotak_merah: ['kotak_pantul', '#FF3B5C'], kotak_ungu: ['kotak_sorot', '#9B5CFF'],
  neon_biru: ['neon', '#00E5FF'], neon_pink: ['neon', '#FF3DCB'],
  pantul: ['tebal', '#FFE500'], putar: ['tebal', '#5BC8FF'], geser: ['miring_cepat', '#B8FF3A'],
  naik: ['tebal', '#7CFF6B'], papan: ['tebal', '#FF4D5E'], ceria: ['komik', '#FF9F1C'],
};

/** Warna teks yang terbaca di atas warna `hex`: gelap di atas terang, putih di atas gelap. */
function kontrasDari(hex) {
  // Rasio kontras WCAG, bukan kecerahan saja: hijau #00E676 tampak "sedang"
  // menurut rumus kecerahan dan mendapat huruf putih yang nyaris tak terbaca.
  // Putih tetap dipilih selama kontrasnya 3:1 (teks besar), karena huruf putih
  // di atas ungu atau pink adalah rupa yang lazim di klip pendek. Kembarannya
  // `_kontras` di backend/app/services/tema_judul.py.
  return (contrastRatio(hex, '#FFFFFF') ?? 21) >= 3 ? '#FFFFFF' : '#101010';
}

/** Patch untuk mewarnai `preset` dengan warna aksen `c`. */
export function warnaiPreset(preset, c) {
  const patch = {};
  for (const f of preset.aksen || ['highlight']) patch[f] = c;
  if ((preset.aksen || []).includes('kotak_warna')) patch.kotak_teks = kontrasDari(c);
  if (preset.kontras) {
    patch.primary = kontrasDari(c);
    patch.highlight = patch.primary;
  }
  return patch;
}

/** Patch lengkap untuk id tema (baru atau lama), atau null. */
export function patchTema(id) {
  const [baru, warna] = ALIAS_TEMA[id] || [id, null];
  const p = STYLE_PRESETS.find((x) => x.id === baru);
  if (!p) return null;
  return { ...p.patch, tema: p.id, ...(warna ? warnaiPreset(p, warna) : {}) };
}

/** Warna aksen gaya yang sedang dipakai, untuk menandai keping yang aktif. */
function aksenKini(preset, style) {
  const f = (preset?.aksen || ['highlight'])[0];
  return style?.[f];
}

const WARNA_AKSEN = ['#FFE500', '#FF9F1C', '#FF3B5C', '#FF3DCB', '#9B5CFF', '#5BC8FF',
                     '#00E5FF', '#00E676', '#B8FF3A', '#FFFFFF', '#101010'];

/**
 * Contoh sebuah preset, digambar memakai gaya preset itu sendiri.
 *
 * Daftar berbentuk teks tidak pernah menjawab pertanyaan yang sebenarnya
 * ditanyakan pengguna — "yang mana yang kelihatannya bagus?" — dan menjawabnya
 * dengan mencoba satu per satu berarti melewati render tiap kali. Petak ini
 * memakai nilai preset yang persis sama dengan yang dikirim ke ffmpeg.
 */
/** Mode sorot preset — cermin dari `_normalkan` di backend. */
function modeSorot(p) {
  if (p.sorot) return p.sorot;
  if (p.highlight_words === false || p.animation === 'none' || p.animation === 'block') {
    return 'mati';
  }
  return p.animation === 'karaoke_pop' ? 'pop' : 'warna';
}


function PresetTile({ preset, active, onPick }) {
  const t = useT();
  const p = preset.patch;
  const contoh = [t('tema_sub.contoh_a'), t('tema_sub.contoh_b')];
  const words = p.uppercase ? contoh.map((w) => w.toUpperCase()) : contoh;
  return (
    <button onClick={onPick} title={t(preset.hint)}
            style={{
              padding: 0, cursor: 'pointer', overflow: 'hidden',
              borderRadius: 'var(--radius-sm)',
              border: active ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
              background: 'transparent',
            }}>
      <div style={{
        // Latar gelap sedikit bergradasi meniru bingkai video: teks putih di
        // atas putih tidak akan memberi tahu apa pun tentang keterbacaannya.
        background: 'linear-gradient(160deg, #1d2430 0%, #0d1119 100%)',
        padding: '15px 8px', display: 'flex', alignItems: 'center',
        justifyContent: 'center', minHeight: '58px',
      }}>
        <span style={{
          display: 'inline-flex', gap: '0.28em', alignItems: 'baseline',
          fontFamily: fontStack(p.font), fontWeight: 800, fontSize: '0.92rem',
          lineHeight: 1.1, letterSpacing: '0.01em',
          // Pelat digambar di sini juga, kalau tidak petak contoh akan
          // menjanjikan garis luar untuk gaya yang sebenarnya berpelat.
          ...(p.bg ? {
            background: hexAlpha(p.bg_color ?? '#000000', p.bg_opacity ?? 0.55),
            padding: `${(p.bg_pad ?? 14) * 0.22}px ${(p.bg_pad ?? 14) * 0.4}px`,
            borderRadius: '4px',
          } : {
            WebkitTextStroke: p.outline_px === 0 ? 'none'
              : `${Math.max(0.5, (p.outline_px ?? 7) * 0.16)}px ${p.garis_warna || '#000'}`,
            paintOrder: 'stroke fill',
            textShadow: bayanganTeks(p, 0.12, 15),
          }),
          fontStyle: p.miring ? 'italic' : 'normal',
          ...(p.spasi_huruf ? { letterSpacing: `${p.spasi_huruf * 0.12}px` } : {}),
          ...(p.kemiringan ? { transform: `rotate(${-p.kemiringan}deg)` } : {}),
        }}>
          <span style={{ color: p.primary }}>{words[0]}</span>
          {/* Kata kedua digambar dengan fungsi yang SAMA dengan pratinjau dan
              hasil render. Petak yang menjanjikan kotak lalu mengeluarkan
              warna saja adalah petak yang berbohong. */}
          <span style={gayaKata(true, modeSorot(p), {
            highlight: p.highlight, dasar: p.primary,
            kotak: p.kotak_warna ?? '#FFE500', kotakTeks: p.kotak_teks ?? '#101010',
          })}>
            {words[1]}
          </span>
        </span>
      </div>
      <div style={{
        padding: '5px 7px 6px', textAlign: 'left',
        background: active ? 'var(--hl-wash)' : 'transparent',
      }}>
        <div style={{
          fontSize: '0.74rem', fontWeight: 800,
          color: active ? 'var(--accent-cyan)' : 'var(--text-primary)',
        }}>{t(preset.label)}</div>
        <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', lineHeight: 1.3 }}>
          {t(preset.hint)}
        </div>
      </div>
    </button>
  );
}

// Cara BARIS masuk. Sorotan per kata diatur terpisah, karena keduanya memang
// dua hal yang berbeda: satu mengatur bagaimana baris datang, satu lagi
// bagaimana kata yang sedang diucapkan ditandai.
// Label = kunci kamus; diterjemahkan pemanggil sebelum diberikan ke <Segmented>.
const ANIMATIONS = [
  ['karaoke_pop', 'anim.karaoke_pop'],
  ['karaoke_wipe', 'anim.karaoke_wipe'],
  ['fade', 'anim.fade'],
  ['slide_up', 'anim.slide_up'],
  ['pop_in', 'anim.pop_in'],
  ['pantul', 'anim.pantul'],
  ['putar', 'anim.putar'],
  ['geser_kiri', 'anim.geser_kiri'],
  ['geser_kanan', 'anim.geser_kanan'],
  ['blur_masuk', 'anim.blur_masuk'],
  ['getar', 'anim.getar'],
  ['typewriter', 'anim.typewriter'],
  ['satu_kata', 'anim.satu_kata'],
  ['none', 'anim.none'],
];

// Cara KATA yang sedang diucapkan ditandai.
const SOROT = [
  ['warna', 'sorot.warna'],
  ['pop', 'sorot.pop'],
  ['kotak', 'sorot.kotak'],
  ['kotak_pop', 'sorot.kotak_pop'],
  ['glow', 'sorot.glow'],
  ['garis_bawah', 'sorot.garis_bawah'],
  ['mati', 'sorot.mati'],
];

function Segmented({ options, value, onChange, columns = 3, size = '0.76rem' }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: `repeat(${columns}, 1fr)`, gap: '6px' }}>
      {options.map(([v, teks]) => (
        <button key={v} onClick={() => onChange(v)}
                style={{
                  padding: '9px 2px', fontSize: size, fontWeight: 700, cursor: 'pointer',
                  borderRadius: 'var(--radius-sm)',
                  border: value === v ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                  background: value === v ? 'var(--hl-wash)' : 'transparent',
                  color: value === v ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                }}>{teks}</button>
      ))}
    </div>
  );
}

function Swatch({ color, selected, onClick, size = 26, title }) {
  const t = useT();
  // Tanpa `onClick` ia hanya keping warna, bukan kendali — dan digambar sebagai
  // <span>. Sebagai <button> ia dipakai juga di dalam judul Section, yang
  // sendirinya sebuah <button>: tombol di dalam tombol adalah HTML tidak sah,
  // dan React memperingatkannya di konsol setiap kali panel Gaya dibuka.
  const Tag = onClick ? 'button' : 'span';
  return (
    <Tag {...(onClick ? { onClick, type: 'button', 'aria-label': t('warna.hex', { c: color }) } : {})}
            title={title || color}
            style={{
              display: 'inline-block',
              width: `${size}px`, height: `${size}px`, borderRadius: '50%',
              cursor: onClick ? 'pointer' : 'default', background: color,
              padding: 0, flex: 'none',
              border: selected ? '3px solid var(--accent-cyan)'
                : '1px solid rgba(255,255,255,0.25)',
              boxShadow: selected ? '0 0 0 2px var(--hl-wash)' : 'none',
            }} />
  );
}

/**
 * Pemilih warna: palet rekomendasi, favorit, riwayat, dan warna bebas.
 *
 * Ketiga baris teratas ada karena alasan berbeda. Palet menjawab "warna apa
 * yang aman terbaca di atas video"; favorit menjawab "warna merek saya";
 * riwayat menjawab "warna yang barusan saya pakai di klip sebelah" — dan
 * ketiganya hilang kalau yang tersedia hanya enam bulatan tetap.
 */
function ColorPicker({ value, onChange }) {
  const t = useT();
  const [favs, toggleFav] = useFavoriteColors();
  const [recent, remember] = useRecentColors();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(value);

  useEffect(() => setDraft(value), [value]);

  const pick = (c) => {
    const hex = normalizeHex(c);
    if (!hex) return;
    onChange(hex);
    remember(hex);
  };

  const isFav = favs.includes(normalizeHex(value) || '');

  return (
    <div style={{
      border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)',
      background: 'var(--bg-glass)', padding: '8px 9px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <Swatch color={value} selected size={24} />
        <code style={{ fontSize: '0.74rem', color: 'var(--text-secondary)', flex: 1 }}>
          {value}
        </code>
        <button onClick={() => toggleFav(value)} title={isFav ? t('pilihwarna.hapus_fav') : t('pilihwarna.simpan_fav')}
                aria-label={t('pilihwarna.fav_aria')}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer', display: 'flex',
                  color: isFav ? '#FFD166' : 'var(--text-muted)', padding: '2px',
                }}>
          <Star size={15} fill={isFav ? '#FFD166' : 'none'} />
        </button>
        <button onClick={() => setOpen((v) => !v)}
                style={{
                  background: 'none', border: '1px solid var(--border-color)',
                  borderRadius: '6px', cursor: 'pointer', fontSize: '0.7rem',
                  padding: '3px 8px', color: 'var(--text-secondary)', fontWeight: 700,
                }}>
          {open ? t('pilihwarna.tutup') : t('pilihwarna.pilih')}
        </button>
      </div>

      {open && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '9px', marginTop: '10px' }}>
          {favs.length > 0 && (
            <Row title={t('pilihwarna.favorit')} colors={favs} value={value} onPick={pick} />
          )}
          {recent.length > 0 && (
            <Row title={t('pilihwarna.terakhir')} colors={recent} value={value} onPick={pick} />
          )}
          {COLOR_GROUPS.map((g) => (
            <Row key={g.name} title={t(g.name)} colors={g.colors} value={value} onPick={pick} />
          ))}

          <div>
            <div style={{ ...label, fontSize: '0.66rem', marginBottom: '5px' }}>{t('pilihwarna.bebas')}</div>
            <div style={{ display: 'flex', gap: '7px', alignItems: 'center' }}>
              <input type="color" value={normalizeHex(value) || '#FFFFFF'}
                     onChange={(e) => pick(e.target.value)}
                     aria-label={t('pilihwarna.bebas_aria')}
                     style={{
                       width: '38px', height: '32px', padding: 0, cursor: 'pointer',
                       background: 'none', border: '1px solid var(--border-color)',
                       borderRadius: '6px',
                     }} />
              <input
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                onBlur={() => (normalizeHex(draft) ? pick(draft) : setDraft(value))}
                onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
                placeholder="#FFE500"
                style={{ ...field, fontSize: '0.78rem', padding: '7px 9px', flex: 1 }}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ title, colors, value, onPick }) {
  return (
    <div>
      <div style={{ ...label, fontSize: '0.66rem', marginBottom: '5px' }}>{title}</div>
      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
        {colors.map((c) => (
          <Swatch key={c} color={c} selected={normalizeHex(c) === normalizeHex(value)}
                  onClick={() => onPick(c)} size={24} />
        ))}
      </div>
    </div>
  );
}

/** Satu bagian panel gaya. Hanya satu yang terbuka, supaya kolomnya tetap pendek. */
function Section({ id, title, note, openId, setOpenId, children }) {
  const open = openId === id;
  return (
    <div style={{
      border: '1px solid var(--border-color)', borderRadius: 'var(--radius-sm)',
      overflow: 'hidden', background: open ? 'var(--bg-glass)' : 'transparent',
    }}>
      <button onClick={() => setOpenId(open ? null : id)}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: '8px',
                padding: '10px 11px', cursor: 'pointer', background: 'none',
                border: 'none', textAlign: 'left', color: 'inherit',
              }}>
        <ChevronRight size={14} style={{
          flex: 'none', color: 'var(--text-muted)',
          transform: open ? 'rotate(90deg)' : 'none', transition: 'transform 120ms',
        }} />
        <span style={{ fontSize: '0.79rem', fontWeight: 800, flex: 1 }}>{title}</span>
        {note && (
          <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>{note}</span>
        )}
      </button>
      {open && (
        <div style={{ padding: '2px 11px 13px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {children}
        </div>
      )}
    </div>
  );
}

/** Panel gaya teks — semua nilai di sini benar-benar sampai ke ffmpeg. */
/**
 * Meminta AI memilih tema untuk klip ini, lalu menerapkannya.
 *
 * Dua puluh enam tema membuat memilih jadi pekerjaan tersendiri, dan pada video
 * yang menghasilkan lima belas klip itu lima belas tebakan. Yang menentukan tema
 * mana yang cocok adalah isi klipnya, dan isi klipnya sudah diketahui sistem.
 *
 * Alasannya ikut ditampilkan, bukan hanya hasilnya: pilihan yang tidak bisa
 * dibantah adalah pilihan yang tidak bisa diperbaiki.
 */
function PilihTemaAI({ klip, presets, set }) {
  const t = useT();
  const [sibuk, setSibuk] = useState(false);
  const [hasil, setHasil] = useState(null);
  const [galat, setGalat] = useState(null);

  const minta = async (segarkan) => {
    setSibuk(true);
    setGalat(null);
    try {
      const r = await apiPost('/clip-gaya', { ...klip, segarkan }, { timeout: 120000 });
      // Id lama (sebelum katalog 17 Oktober 2026) dipetakan ke model barunya.
      const patchAi = patchTema(r.tema);
      const preset = presets.find((p) => p.id === patchAi?.tema);
      if (!preset || !patchAi) throw new Error(t('temaai.tak_dikenal', { tema: r.tema }));
      // Usul model soal warna per penutur hanya berlaku bila sakelar induknya
      // menyala. Model menilai transkrip, bukan ketepatan pemisahan suaranya,
      // jadi ia tidak berhak menyalakan sesuatu yang sedang dimatikan.
      const bolehWarna = await muatWarnaPenutur();
      set({ ...patchAi,
            per_speaker_colors: bolehWarna && !!r.warna_per_penutur });
      setHasil({ ...r, label: t(preset.label),
                 warna_per_penutur: bolehWarna && !!r.warna_per_penutur });
    } catch (e) {
      setGalat(e.message);
    } finally {
      setSibuk(false);
    }
  };

  return (
    <div style={{ marginBottom: '10px' }}>
      <button className="btn-secondary" disabled={sibuk} onClick={() => minta(false)}
              style={{ width: '100%', fontSize: '0.78rem', display: 'inline-flex',
                       alignItems: 'center', justifyContent: 'center', gap: '7px',
                       color: 'var(--accent-cyan)' }}>
        {sibuk ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
        {sibuk ? t('temaai.membaca') : t('temaai.pilihkan')}
      </button>
      {hasil && (
        <p style={{ fontSize: '0.69rem', color: 'var(--text-muted)', lineHeight: 1.5,
                    margin: '7px 0 0' }}>
          <b style={{ color: 'var(--text-secondary)' }}>{hasil.label}</b>
          {hasil.alasan ? ` - ${hasil.alasan}` : ''}
          {hasil.warna_per_penutur ? t('temaai.per_orang') : ''}
          {hasil.sumber === 'lokal' ? t('temaai.lokal') : ''}{' '}
          <button onClick={() => minta(true)} disabled={sibuk}
                  style={{ background: 'none', border: 0, padding: 0, cursor: 'pointer',
                           color: 'var(--accent-cyan)', font: 'inherit' }}>
            {t('temaai.ulang')}
          </button>
        </p>
      )}
      {galat && (
        <p style={{ fontSize: '0.69rem', color: 'var(--accent-red)', margin: '7px 0 0',
                    display: 'flex', gap: '6px', alignItems: 'center' }}>
          <AlertTriangle size={13} /> {galat}
        </p>
      )}
    </div>
  );
}


export function StylePanel({
  style, onChange, aspectRatio, onAspectChange,
  showHook, onShowHookChange, hookText, onHookTextChange,
  speakerCount = 2,
  // Bahan untuk "Pilihkan AI": isi klip yang sedang dibuka. Tanpa ini tombolnya
  // disembunyikan, bukan ditampilkan lalu gagal saat ditekan.
  klipUntukTema = null,
  // Bagian yang terbuka saat panel dibuka. Bisa disetel dari luar supaya uji
  // asap bisa merender isi tiap bagian — isi bagian yang tertutup tidak pernah
  // dijalankan, jadi kesalahan di dalamnya tidak akan tertangkap.
  defaultSection = 'preset',
}) {
  const t = useT();
  const [openId, setOpenId] = useState(defaultSection);
  const [fonts, setFonts] = useState(cachedFonts);

  useEffect(() => { loadFonts().then(setFonts); }, []);

  const set = (patch) => onChange({ ...style, ...patch });
  // Preset aktif dikenali dari id temanya (disimpan saat dipilih), karena
  // warnanya boleh diubah sesudah itu; gaya lama tanpa id dicocokkan isinya.
  const activePreset = STYLE_PRESETS.find((p) => p.id === (ALIAS_TEMA[style.tema]?.[0] ?? style.tema))
    ?? STYLE_PRESETS.find((p) => Object.entries(p.patch).every(([k, v]) => style[k] === v));
  const speakers = Math.max(1, Math.min(8, speakerCount || 1));
  const palette = style.speaker_colors ?? DEFAULT_SPEAKER_COLORS;
  const bolehWarnaPenutur = useWarnaPenutur();
  // Sakelar induk menang. Gaya lama yang tersimpan di peramban masih menyimpan
  // `true`, dan tanpa baris ini kotak centangnya akan terlihat mati sementara
  // yang dirender tetap satu warna.
  const seragam = !bolehWarnaPenutur || style.per_speaker_colors === false;
  const fontLabel = fonts.find((f) => f.family === style.font)?.label ?? style.font;

  // Tak disetel = menyala, supaya klip lama tidak mendadak kehilangan teksnya.
  const subtitleAktif = style.aktif !== false;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '7px' }}>
      {/* Saklar ini berdiri di luar seluruh bagian lain, dan memang harus:
          ia bukan salah satu setelan gaya melainkan penentu apakah gaya itu
          dipakai sama sekali. Ditaruh di dalam salah satu bagian, ia akan
          tersembunyi di balik bagian yang kebetulan tertutup. */}
      <button type="button"
              onClick={() => set({ aktif: !subtitleAktif })}
              style={{
                display: 'flex', alignItems: 'center', gap: '10px', width: '100%',
                padding: '11px 13px', cursor: 'pointer', textAlign: 'left',
                borderRadius: 'var(--radius-md)',
                border: subtitleAktif ? '1px solid var(--border-color)'
                                      : '2px solid var(--accent-cyan)',
                background: subtitleAktif ? 'transparent' : 'var(--hl-wash)',
              }}>
        <span style={{
          width: '38px', height: '22px', flexShrink: 0, borderRadius: '11px',
          background: subtitleAktif ? 'var(--accent-cyan)' : 'var(--border-color)',
          position: 'relative', transition: 'background 140ms ease',
        }}>
          <span style={{
            position: 'absolute', top: '3px', width: '16px', height: '16px',
            borderRadius: '50%', background: '#fff',
            left: subtitleAktif ? '19px' : '3px', transition: 'left 140ms ease',
          }} />
        </span>
        <span>
          <span style={{ display: 'block', fontSize: '0.84rem', fontWeight: 800,
                         color: 'var(--text-primary)' }}>
            {subtitleAktif ? t('gs.sub_nyala') : t('gs.sub_mati')}
          </span>
          <span style={{ display: 'block', fontSize: '0.7rem', lineHeight: 1.45,
                         color: 'var(--text-secondary)' }}>
            {subtitleAktif
              ? t('gs.sub_nyala_ket')
              : t('gs.sub_mati_ket')}
          </span>
        </span>
      </button>

      <Section id="preset" title={t('gs.siap_pakai')} note={activePreset ? t(activePreset.label) : t('gs.ubahan')}
               openId={openId} setOpenId={setOpenId}>
        {klipUntukTema && (
          <PilihTemaAI klip={klipUntukTema} presets={STYLE_PRESETS} set={set} />
        )}
        {/* Warna aksen: mewarnai model yang sedang dipilih. Satu model, warna
            bebas (diminta pemilik 17 Oktober 2026). Tanpa model (gaya lama atau
            ubahan sendiri) warnanya jatuh ke kata sorot. */}
        <div>
          <div style={{ ...label, marginBottom: '6px' }}>{t('gs.warna_aksen')}</div>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', alignItems: 'center' }}>
            {WARNA_AKSEN.map((c) => (
              <Swatch key={c} color={c} size={22}
                      selected={String(aksenKini(activePreset, style) || '').toUpperCase() === c}
                      onClick={() => set(activePreset ? warnaiPreset(activePreset, c) : { highlight: c })} />
            ))}
            <input type="color" value={aksenKini(activePreset, style) || '#FFE500'}
                   title={t('gs.warna_bebas')}
                   onChange={(e) => { const c = e.target.value.toUpperCase(); set(activePreset ? warnaiPreset(activePreset, c) : { highlight: c }); }}
                   style={{ width: 26, height: 24, padding: 0, border: 0, background: 'none', cursor: 'pointer' }} />
          </div>
        </div>
        {[...new Set(STYLE_PRESETS.map((p) => p.kategori))].map((kat) => (
          <div key={kat}>
            <div style={{ ...label, margin: '6px 0' }}>{t(kat)}</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '7px' }}>
              {STYLE_PRESETS.filter((p) => p.kategori === kat).map((p) => (
                <PresetTile key={p.id} preset={p} active={activePreset?.id === p.id}
                            onPick={() => set({ ...p.patch, tema: p.id })} />
              ))}
            </div>
          </div>
        ))}
        <p style={{ fontSize: '0.67rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>
          {t('gs.contoh_ket')}
        </p>
      </Section>

      <Section id="warna" title={t('gs.warna')} openId={openId} setOpenId={setOpenId}
               note={<span style={{ display: 'inline-flex', gap: '3px' }}>
                 <Swatch color={style.primary} size={13} />
                 <Swatch color={style.highlight} size={13} />
               </span>}>
        <div>
          <div style={{ ...label, marginBottom: '7px' }}>{t('gs.pasangan')}</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
            {COLOR_PAIRS.map((c) => {
              const on = style.primary === c.primary && style.highlight === c.highlight;
              return (
                <button key={c.id}
                        onClick={() => set({ primary: c.primary, highlight: c.highlight })}
                        style={{
                          display: 'flex', alignItems: 'center', gap: '7px', cursor: 'pointer',
                          padding: '6px 8px', borderRadius: 'var(--radius-sm)',
                          border: on ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                          background: on ? 'var(--hl-wash)' : 'transparent',
                        }}>
                  <span style={{ display: 'flex' }}>
                    <span style={{
                      width: '14px', height: '14px', borderRadius: '50%',
                      background: c.primary, border: '1px solid rgba(0,0,0,0.4)',
                    }} />
                    <span style={{
                      width: '14px', height: '14px', borderRadius: '50%', marginLeft: '-5px',
                      background: c.highlight, border: '1px solid rgba(0,0,0,0.4)',
                    }} />
                  </span>
                  <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-secondary)' }}>
                    {t(c.name)}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <div style={{ ...label, marginBottom: '6px' }}>{t('gs.warna_teks')}</div>
          <ColorPicker value={style.primary ?? '#FFFFFF'} onChange={(c) => set({ primary: c })} />
        </div>

        <div>
          <div style={{ ...label, marginBottom: '6px' }}>{t('gs.warna_aktif')}</div>
          <ColorPicker value={style.highlight ?? '#FFE500'} onChange={(c) => set({ highlight: c })} />
        </div>

        <div>
          <div style={{ ...label, marginBottom: '6px' }}>
            {t('gs.per_narasumber')}
          </div>
          {/* Sakelar keluar.
              Menebak siapa bicara kapan adalah bagian paling rapuh dari alur
              ini, dan saat ia meleset warnanya berganti di tengah kalimat
              orang yang sama, lebih mengganggu daripada satu warna untuk
              semuanya. Paletnya tidak dihapus saat dimatikan, hanya tidak
              dipakai, jadi menyalakannya kembali mengembalikan setelan lama. */}
          <label style={{
            display: 'flex', alignItems: 'center', gap: '9px', cursor: 'pointer',
            padding: '8px 10px', marginBottom: '9px', borderRadius: 'var(--r-sm)',
            background: seragam ? 'var(--hl-wash)' : 'transparent',
            border: `1px solid ${seragam ? 'var(--hl)' : 'var(--border-color)'}`,
          }}>
            <input
              type="checkbox"
              checked={seragam}
              disabled={!bolehWarnaPenutur}
              onChange={(e) => set({ per_speaker_colors: !e.target.checked })}
              style={{ width: '15px', height: '15px', accentColor: 'var(--accent-cyan)', flex: 'none' }}
            />
            <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--ink)' }}>
              {t('gs.satu_warna')}
            </span>
          </label>
          <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', margin: '0 0 9px', lineHeight: 1.5 }}>
            {!bolehWarnaPenutur
              ? <>{t('gs.penutur_mati_a')} <strong>{t('tab.subtitle')}</strong>{t('gs.penutur_mati_b')}</>
              : seragam
              ? <>{t('gs.seragam_a')} <strong>{t('gs.warna_teks')}</strong> {t('gs.seragam_b')}</>
              : <>{t('gs.berlaku_a')} <strong>{t('tab.subtitle')}</strong>{t('gs.berlaku_b')}</>}
          </p>
          <div style={{ opacity: seragam ? 0.4 : 1, pointerEvents: seragam ? 'none' : 'auto' }}>
          {Array.from({ length: speakers }, (_, i) => (
            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '9px', marginBottom: '7px' }}>
              <span style={{
                fontSize: '0.74rem', width: '58px', flex: 'none',
                color: 'var(--text-secondary)', fontWeight: 700,
              }}>
                {t('gs.orang_n', { n: i + 1 })}
              </span>
              <div style={{ flex: 1 }}>
                <ColorPicker
                  value={palette[i] ?? DEFAULT_SPEAKER_COLORS[i] ?? '#FFFFFF'}
                  onChange={(c) => {
                    const next = [...(style.speaker_colors ?? DEFAULT_SPEAKER_COLORS)];
                    while (next.length <= i) next.push(DEFAULT_SPEAKER_COLORS[next.length] ?? '#FFFFFF');
                    next[i] = c;
                    set({ speaker_colors: next });
                  }}
                />
              </div>
            </div>
          ))}
          <button className="btn-secondary"
                  onClick={() => set({ speaker_colors: [...DEFAULT_SPEAKER_COLORS] })}
                  style={{ fontSize: '0.73rem', padding: '6px 9px', marginTop: '4px' }}>
            {t('gs.warna_bawaan')}
          </button>
          </div>
        </div>
      </Section>

      <Section id="font" title={t('gs.font_ukuran')} note={fontLabel}
               openId={openId} setOpenId={setOpenId}>
        <div>
          <div style={{ ...label, marginBottom: '7px' }}>{t('gs.font_n', { n: fonts.length })}</div>
          <div style={{
            display: 'flex', flexDirection: 'column', gap: '5px',
            maxHeight: '250px', overflowY: 'auto', paddingRight: '3px',
          }}>
            {fonts.map((f) => {
              const on = style.font === f.family;
              return (
                <button key={f.family} onClick={() => set({ font: f.family })}
                        style={{
                          display: 'flex', alignItems: 'baseline', gap: '8px', cursor: 'pointer',
                          padding: '7px 9px', textAlign: 'left', borderRadius: 'var(--radius-sm)',
                          border: on ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                          background: on ? 'var(--hl-wash)' : 'transparent',
                        }}>
                  {/* Nama font digambar DENGAN font itu sendiri: bedanya harus
                      terlihat sebelum dipilih, bukan setelah dirender. */}
                  <span style={{
                    fontFamily: fontStack(f.family), fontSize: '0.98rem', fontWeight: 800,
                    color: on ? 'var(--accent-cyan)' : 'var(--text-primary)',
                    textTransform: 'uppercase', letterSpacing: '0.01em',
                  }}>{f.label}</span>
                  <span style={{ fontSize: '0.63rem', color: 'var(--text-muted)' }}>{f.note}</span>
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <div style={{ ...label, marginBottom: '8px' }}>{t('gs.ukuran_n', { n: style.size })}</div>
          <input type="range" min="44" max="190" step="2" value={style.size}
                 onChange={(e) => set({ size: Number(e.target.value) })}
                 style={{ width: '100%', accentColor: 'var(--accent-cyan)' }} />
          <p style={{ fontSize: '0.67rem', color: 'var(--text-muted)', margin: '5px 0 0' }}>
            {t('gs.ukuran_ket')}
          </p>
        </div>

        <div>
          {/* Jarak antar kata.
              Angkanya pernah dipatok mati, dan patokan itu selalu salah untuk
              sebagian orang: font yang lebih lebar butuh jarak lebih rapat,
              dan seleranya sendiri berbeda beda. Yang dijaga tetap sama, yaitu
              HASILNYA: pratinjau dan render memakai angka yang sama walau
              lebar spasi bawaan tiap font berbeda dua kali lipat. */}
          <div style={{ ...label, marginBottom: '8px' }}>
            {t('gs.jarak_n', { n: jarakKata(style).toFixed(2) })}
          </div>
          <input type="range" min={JARAK_KATA_MIN} max={JARAK_KATA_MAKS} step="0.02"
                 value={jarakKata(style)}
                 onChange={(e) => set({ jarak_kata: Number(e.target.value) })}
                 style={{ width: '100%', accentColor: 'var(--accent-cyan)' }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '5px' }}>
            <p style={{ fontSize: '0.67rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.5, flex: 1 }}>
              {t('gs.jarak_ket')}
            </p>
            {jarakKata(style) !== JARAK_KATA && (
              <button onClick={() => set({ jarak_kata: JARAK_KATA })}
                      style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                               color: 'var(--accent-cyan)', fontWeight: 700,
                               fontSize: '0.67rem', fontFamily: 'inherit', flex: 'none' }}>
                {t('gs.kembali_ke', { n: JARAK_KATA })}
              </button>
            )}
          </div>
        </div>

        <div>
          <div style={{ ...label, marginBottom: '8px' }}>
            {t('gs.garis_n', { n: style.outline_px ?? 7 })}
          </div>
          <input type="range" min="0" max="14" step="1" value={style.outline_px ?? 7}
                 onChange={(e) => set({ outline_px: Number(e.target.value) })}
                 style={{ width: '100%', accentColor: 'var(--accent-cyan)' }} />
          <p style={{ fontSize: '0.67rem', color: 'var(--text-muted)', margin: '5px 0 0', lineHeight: 1.5 }}>
            {t('gs.garis_ket')}
          </p>
        </div>

        {/* Gaya huruf tambahan (17 Oktober 2026): warna garis, pendar, jarak
            huruf, kemiringan, miring. Semuanya dirender libass apa adanya. */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
          <span style={{ ...label, margin: 0 }}>{t('gs.warna_garis')}</span>
          {['#000000', '#FFFFFF', '#FF3DCB', '#7B2CFF', '#00E5FF', '#FF3B5C', '#FFE500'].map((c) => (
            <Swatch key={c} color={c} size={18}
                    selected={String(style.garis_warna || '#000000').toUpperCase() === c}
                    onClick={() => set({ garis_warna: c })} />
          ))}
          <input type="color" value={style.garis_warna || '#000000'} title={t('gs.warna_bebas')}
                 onChange={(e) => set({ garis_warna: e.target.value.toUpperCase() })}
                 style={{ width: 24, height: 22, padding: 0, border: 0, background: 'none', cursor: 'pointer' }} />
        </div>
        {[
          ['pendar', 'gs.pendar_n', 0, 16, 1, 0],
          ['spasi_huruf', 'gs.spasi_huruf_n', 0, 24, 1, 0],
          ['kemiringan', 'gs.kemiringan_n', -15, 15, 1, 0],
        ].map(([f, kunci, min, max, step, dasar]) => (
          <div key={f}>
            <div style={{ ...label, marginBottom: '6px' }}>{t(kunci, { n: style[f] ?? dasar })}</div>
            <input type="range" min={min} max={max} step={step} value={style[f] ?? dasar}
                   onChange={(e) => set({ [f]: Number(e.target.value) })}
                   style={{ width: '100%', accentColor: 'var(--accent-cyan)' }} />
          </div>
        ))}
        <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', fontSize: '0.84rem' }}>
          <input type="checkbox" checked={!!style.miring}
                 onChange={(e) => set({ miring: e.target.checked })}
                 style={{ accentColor: 'var(--accent-cyan)', width: '16px', height: '16px' }} />
          {t('gs.miring')}
        </label>

        <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer', fontSize: '0.84rem' }}>
          <input type="checkbox" checked={style.uppercase}
                 onChange={(e) => set({ uppercase: e.target.checked })}
                 style={{ accentColor: 'var(--accent-cyan)', width: '16px', height: '16px' }} />
          {t('gs.kapital')}
        </label>
      </Section>

      <Section id="posisi" title={t('gs.posisi_animasi')} openId={openId} setOpenId={setOpenId}
               note={t(ANIMATIONS.find(([v]) => v === style.animation)?.[1] ?? '')}>
        <div>
          <div style={{ ...label, marginBottom: '8px' }}>{t('gs.jangkar')}</div>
          <Segmented columns={3} options={[['top', t('gaya.atas')], ['middle', t('gaya.tengah')], ['bottom', t('gaya.bawah')]]}
                     value={style.position} onChange={(v) => set({ position: v })} />
        </div>

        {style.position !== 'middle' && (
          <div>
            <div style={{ ...label, marginBottom: '8px' }}>
              {t(style.position === 'top' ? 'gs.jarak_atas_n' : 'gs.jarak_bawah_n', { n: style.margin_v ?? 300 })}
            </div>
            <input type="range" min="60" max="1200" step="10" value={style.margin_v ?? 300}
                   onChange={(e) => set({ margin_v: Number(e.target.value) })}
                   style={{ width: '100%', accentColor: 'var(--accent-cyan)' }} />
            <p style={{ fontSize: '0.67rem', color: 'var(--text-muted)', margin: '5px 0 0' }}>
              {t('gs.seret_ket')}
            </p>
          </div>
        )}

        <div>
          <div style={{ ...label, marginBottom: '8px' }}>
            {t('gs.lebar_n', { n: Math.round(style.box_w ?? 84) })}
          </div>
          <input type="range" min="20" max="100" step="1" value={style.box_w ?? 84}
                 onChange={(e) => set({ box_w: Number(e.target.value) })}
                 style={{ width: '100%', accentColor: 'var(--accent-cyan)' }} />
          <p style={{ fontSize: '0.67rem', color: 'var(--text-muted)', margin: '5px 0 0', lineHeight: 1.5 }}>
            {t('gs.lebar_ket')}
          </p>
        </div>

        <div>
          <div style={{ ...label, marginBottom: '8px' }}>
            {t('gs.mendatar_n', { n: Math.round(style.pos_x ?? 50) })}
          </div>
          <input type="range" min="0" max="100" step="1" value={style.pos_x ?? 50}
                 onChange={(e) => set({ pos_x: Number(e.target.value) })}
                 style={{ width: '100%', accentColor: 'var(--accent-cyan)' }} />
        </div>

        <div>
          <div style={{ ...label, marginBottom: '8px' }}>{t('gs.animasi')}</div>
          <Segmented columns={2} options={ANIMATIONS.map(([v, k]) => [v, t(k)])} value={style.animation}
                     onChange={(v) => set({ animation: v })} />

          <div style={{ ...label, marginTop: '14px' }}>{t('gs.sorotan')}</div>
          <Segmented columns={2} options={SOROT.map(([v, k]) => [v, t(k)])} value={modeSorot(style)}
                     onChange={(v) => set({ sorot: v, highlight_words: v !== 'mati' })} />

          {(modeSorot(style) === 'kotak' || modeSorot(style) === 'kotak_pop') && (
            <div style={{ marginTop: '12px' }}>
              <div style={label}>{t('gs.warna_kotak')}</div>
              <div style={{ display: 'flex', gap: '7px', flexWrap: 'wrap' }}>
                {[['#FFE500', '#101010'], ['#00E676', '#06210F'], ['#FF3B5C', '#FFFFFF'],
                  ['#9B5CFF', '#FFFFFF'], ['#00E5FF', '#04222A'], ['#FFFFFF', '#101010'],
                  ['#101010', '#FFFFFF']].map(([kotak, teks]) => (
                  <button key={kotak} onClick={() => set({ kotak_warna: kotak, kotak_teks: teks })}
                          title={kotak}
                          style={{
                            width: '30px', height: '24px', borderRadius: '6px', cursor: 'pointer',
                            background: kotak, color: teks, fontSize: '0.6rem', fontWeight: 900,
                            border: (style.kotak_warna ?? '#FFE500') === kotak
                              ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                          }}>Aa</button>
                ))}
              </div>
            </div>
          )}
        </div>
      </Section>

      <Section id="judul" title={t('gs.judul_video')} openId={openId} setOpenId={setOpenId}
               note={showHook ? t('gs.aktif') : t('gs.mati')}>
        <label style={{
          display: 'flex', alignItems: 'center', gap: '10px', cursor: 'pointer',
          fontSize: '0.84rem',
        }}>
          <input type="checkbox" checked={showHook}
                 onChange={(e) => onShowHookChange(e.target.checked)}
                 style={{ accentColor: 'var(--accent-cyan)', width: '16px', height: '16px' }} />
          {t('gs.tampil_judul')}
        </label>
        {showHook ? (
          <div>
            <textarea value={hookText} rows={2}
                      onChange={(e) => onHookTextChange(e.target.value)}
                      placeholder={t('gs.judul_placeholder')}
                      style={{ ...field, resize: 'vertical', lineHeight: 1.4 }} />
            <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', margin: '6px 0 0', lineHeight: 1.5 }}>
              {t('gs.judul_ket')}
            </p>
          </div>
        ) : (
          <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', margin: 0, lineHeight: 1.5 }}>
            {t('gs.judul_mati_ket')}
          </p>
        )}
      </Section>

      {/* Tanda air.
          Ikut GAYA, bukan ikut klip: ini nama kanal, dan mengetiknya ulang di
          tiap klip adalah pekerjaan tanpa guna. Sekali disetel, ia ikut ke
          setiap klip yang dirender sesudahnya. */}
      <Section id="tanda-air" title={t('gs.tanda_air')}
               note={(style?.watermark || '').trim() || t('gs.mati')}
               openId={openId} setOpenId={setOpenId}>
        <input value={style?.watermark ?? ''}
               onChange={(e) => onChange({ ...style, watermark: e.target.value.slice(0, 40) })}
               placeholder="@namakanal"
               style={{ ...field, fontSize: '0.85rem' }} />
        <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', margin: '6px 0 10px', lineHeight: 1.5 }}>
          {t('gs.tanda_air_ket')}
          <br /><strong>{t('gs.tanda_air_seret')}</strong>
        </p>

        {(style?.watermark || '').trim() && (
          <>
            <div style={{ ...label, marginBottom: '6px' }}>{t('gaya.font')}</div>
            <select value={style?.wm_font ?? ''}
                    onChange={(e) => onChange({ ...style, wm_font: e.target.value })}
                    style={{ ...field, fontSize: '0.82rem', marginBottom: '10px' }}>
              <option value="">{t('gs.ikut_font')}</option>
              {fonts.map((f) => (
                <option key={f.family} value={f.family}>{f.label ?? f.family}</option>
              ))}
            </select>

            <div style={{ ...label, marginBottom: '6px' }}>{t('gaya.warna')}</div>
            <div style={{ marginBottom: '10px' }}>
              <ColorPicker value={style?.wm_color ?? '#FFFFFF'}
                           onChange={(c) => onChange({ ...style, wm_color: c })} />
            </div>

            <div style={{ ...label, marginBottom: '4px' }}>
              {t('gs.ukuran_wm_n', { n: style?.wm_size ?? 34 })}
            </div>
            <input type="range" min="12" max="160" step="2"
                   value={style?.wm_size ?? 34}
                   onChange={(e) => onChange({ ...style, wm_size: Number(e.target.value) })}
                   style={{ width: '100%', marginBottom: '10px' }} />

            <div style={{ ...label, marginBottom: '4px' }}>
              {t('gs.tembus_n', { n: Math.round((style?.wm_opacity ?? 0.62) * 100) })}
            </div>
            <input type="range" min="5" max="100" step="5"
                   value={Math.round((style?.wm_opacity ?? 0.62) * 100)}
                   onChange={(e) => onChange({ ...style, wm_opacity: Number(e.target.value) / 100 })}
                   style={{ width: '100%', marginBottom: '10px' }} />

            <div style={{ ...label, marginBottom: '4px' }}>
              {t('gs.garis_wm_n', { n: style?.wm_outline ?? 2 })}
            </div>
            <input type="range" min="0" max="10" step="1"
                   value={style?.wm_outline ?? 2}
                   onChange={(e) => onChange({ ...style, wm_outline: Number(e.target.value) })}
                   style={{ width: '100%', marginBottom: '10px' }} />

            {/* Sembilan sudut sebagai jalan pintas. Menyeret di pratinjau tetap
                yang paling cepat, tapi sudut yang persis sulit dikenai dengan
                tangan, dan pojok adalah tempat tanda air paling sering ditaruh. */}
            <div style={{ ...label, marginBottom: '6px' }}>{t('gs.tempat_cepat')}</div>
            <div style={{
              display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '4px',
              marginBottom: '8px',
            }}>
              {[[8, 8], [50, 8], [92, 8],
                [8, 50], [50, 50], [92, 50],
                [8, 92], [50, 92], [92, 92]].map(([x, y]) => {
                const on = Math.abs((style?.wm_x ?? 92) - x) < 3
                  && Math.abs((style?.wm_y ?? 95) - y) < 4;
                return (
                  <button key={`${x}-${y}`}
                          onClick={() => onChange({ ...style, wm_x: x, wm_y: y })}
                          title={t('gs.taruh_di', { x, y })}
                          style={{
                            height: '26px', cursor: 'pointer', borderRadius: '4px',
                            border: on ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                            background: on ? 'var(--hl-wash)' : 'transparent',
                          }} />
                );
              })}
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
              {t('gs.sekarang_di', { x: Math.round(style?.wm_x ?? 92), y: Math.round(style?.wm_y ?? 95) })}
            </div>
          </>
        )}
      </Section>

      <Section id="rasio" title={t('gs.rasio')} note={aspectRatio}
               openId={openId} setOpenId={setOpenId}>
        <Segmented columns={4} options={[['9:16', '9:16'], ['1:1', '1:1'], ['4:5', '4:5'], ['16:9', '16:9']]}
                   value={aspectRatio} onChange={onAspectChange} />
      </Section>
    </div>
  );
}
