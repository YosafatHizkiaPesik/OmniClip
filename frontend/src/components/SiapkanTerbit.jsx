import React, { useEffect, useState } from 'react';
import {
  AlertTriangle, Check, Clipboard, Copy, Download, ExternalLink, FolderOpen,
  Loader2, RefreshCw, Send, X,
} from 'lucide-react';
import {
  apiPost, dijalankanDiKomputerIni, downloadToDisk, kategoriKlip,
} from '../lib/api';
import PeringatanIzin from './PeringatanIzin';

/**
 * Menyiapkan satu klip untuk diterbitkan dengan tangan.
 *
 * Pilihan yang disengaja, bukan kekurangan. Unggah otomatis ke TikTok,
 * Instagram, dan Facebook menuntut pendaftaran aplikasi, peninjauan berminggu-
 * minggu, dan badan usaha — sementara yang dihemat cuma dua menit per klip.
 * Lebih buruk lagi: unggahan lewat API tidak bisa memakai sound yang sedang
 * tren, stiker, atau efek, padahal di TikTok dan Reels justru itu yang sering
 * menentukan.
 *
 * Jadi OmniClip mengerjakan semuanya SAMPAI SATU LANGKAH sebelum terbit:
 * berkasnya siap, captionnya ditulis, tagarnya dipilih sesuai isi klip dan
 * sesuai batas tiap platform. Yang tersisa: seret berkas, tempel caption,
 * pilih sound, terbit.
 */
export default function SiapkanTerbit({ clip, onClose, onSelesai }) {
  const [data, setData] = useState(null);
  const [galat, setGalat] = useState(null);
  const [aktif, setAktif] = useState('tiktok');
  const [caption, setCaption] = useState('');
  const [judul, setJudul] = useState('');
  const [disalin, setDisalin] = useState(null);
  const [sibuk, setSibuk] = useState(false);
  const [terbit, setTerbit] = useState(clip.metadata?.terbit ?? []);

  /**
   * Caption dan tagar untuk klip ini.
   *
   * TANPA AI saat dibuka. Judul dan tagar klipnya sudah ada di sidecar — dibuat
   * saat auto-klip — jadi memanggil model lagi hanya untuk merangkainya berarti
   * menunggu lama dan membakar kuota untuk hal yang sudah ada di cakram.
   * Dilaporkan pemiliknya 5 Oktober 2026: "saat saya klik masih loading lama
   * sedangkan judul, hastag bukannya sudah langsung tersedia".
   *
   * AI tetap ada, tapi atas permintaan: tombol "Tulis ulang dengan AI" di
   * bawah. Yang membedakan keduanya terlihat di label sumber, jadi tidak ada
   * yang perlu menebak caption ini datang dari mana.
   */
  const muat = async (pakaiAi = false) => {
    setSibuk(true);
    setGalat(null);
    try {
      const r = await apiPost('/clip-keterangan', {
        clip_name: clip.file_name, pakai_ai: pakaiAi, segarkan: pakaiAi,
      }, { timeout: 240000 });
      setData(r);
    } catch (e) {
      setGalat(e.message);
    } finally {
      setSibuk(false);
    }
  };
  useEffect(() => { muat(); /* eslint-disable-next-line */ }, [clip.file_name]);

  // Daftar periksa sebelum unggah. Dihitung dari sidecar klipnya — tanpa model,
  // tanpa jaringan — jadi ia tidak pernah membuat orang menunggu dan tidak
  // memakan kuota apa pun.
  const [periksa, setPeriksa] = useState(null);
  useEffect(() => {
    apiPost('/clip-periksa', { clip_name: clip.file_name })
      .then(setPeriksa).catch(() => setPeriksa(null));
  }, [clip.file_name]);

  // Caption yang tampil mengikuti platform yang dipilih, tapi suntingan tangan
  // dipertahankan sampai pengguna berpindah platform.
  const paket = data?.platform?.find((p) => p.platform === aktif);
  useEffect(() => {
    if (!paket) return;
    setCaption(paket.caption);
    setJudul(paket.judul ?? '');
  }, [paket?.platform, data]);   // eslint-disable-line react-hooks/exhaustive-deps

  const salin = async (teks, tanda) => {
    try {
      await navigator.clipboard.writeText(teks);
      setDisalin(tanda);
      setTimeout(() => setDisalin(null), 1800);
    } catch {
      setGalat('Peramban menolak menyalin. Tandai teksnya lalu salin sendiri.');
    }
  };

  const tandai = async (sudah) => {
    try {
      const r = await apiPost('/clip-terbit', {
        clip_name: clip.file_name, platform: aktif, sudah,
      });
      setTerbit(r.terbit || []);
      onSelesai?.();
    } catch (e) {
      setGalat(e.message);
    }
  };

  const sudahTerbit = terbit.includes(aktif);
  const diKomputerIni = dijalankanDiKomputerIni();

  /**
   * Menunjuk berkasnya di pengelola berkas, lalu membuka halaman unggah.
   *
   * Inilah langkah yang selama ini hilang. Dilaporkan pemiliknya 9 Oktober
   * 2026: "sering saat upload saya harus cari foldernya dahulu, jika tidak
   * maka saya mendownload ulang hasil klip". Mengunduh ulang berkas yang sudah
   * ada bukan cuma lambat, ia melahirkan salinan kedua dengan nama berbeda,
   * dan dari situlah video tertukar saat diunggah.
   *
   * Dua jendela terbuka berdampingan: pengelola berkas dengan berkasnya sudah
   * tersorot, dan halaman unggah platformnya. Tinggal diseret.
   */
  const tunjukLaluBuka = async (url) => {
    setSibuk(true); setGalat(null);
    try {
      await apiPost('/berkas/tunjuk',
                    { kategori: kategoriKlip(), nama: clip.file_name });
      if (url) window.open(url, '_blank', 'noopener');
    } catch (e) {
      setGalat(e.message);
    } finally { setSibuk(false); }
  };

  /**
   * Menaruh BERKAS videonya di papan klip, supaya kotak unggah bisa diisi
   * dengan Ctrl+V tanpa menelusuri folder sama sekali.
   *
   * Yang melakukannya server, bukan halaman ini: peramban tidak boleh menaruh
   * berkas sembarangan di papan klip maupun mengisi kotak unggah situs lain.
   * Itu batas keamanan peramban, bukan kekurangan yang bisa diakali.
   */
  const salinBerkas = async () => {
    setSibuk(true); setGalat(null);
    try {
      await apiPost('/berkas/salin',
                    { kategori: kategoriKlip(), nama: clip.file_name });
      setDisalin('berkas');
      setTimeout(() => setDisalin(null), 2200);
    } catch (e) {
      setGalat(e.message);
    } finally { setSibuk(false); }
  };

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, zIndex: 80, background: 'rgba(3,7,14,.66)',
      display: 'grid', placeItems: 'center', padding: '18px',
    }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        width: 'min(680px, 100%)', maxHeight: '90vh', overflowY: 'auto',
        background: 'var(--plate)', border: '1px solid var(--rule-2)',
        borderRadius: 'var(--radius-lg)', padding: '18px',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
          <Send size={18} style={{ color: 'var(--reh)' }} />
          <b style={{ fontSize: '0.96rem', flex: 1 }}>Siapkan terbit</b>
          <button onClick={onClose} aria-label="Tutup"
                  style={{ background: 'none', border: 0, cursor: 'pointer',
                           color: 'var(--text-secondary)', display: 'flex' }}>
            <X size={18} />
          </button>
        </div>
        <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', margin: '0 0 14px',
                    lineHeight: 1.5 }}>
          Semuanya sudah siap kecuali satu langkah terakhir. Tekan
          <b> Tunjuk berkasnya</b>, dan pengelola berkas terbuka dengan video
          ini sudah tersorot, jadi tinggal diseret ke kotak unggah. Tidak perlu
          mencari folder, dan tidak perlu mengunduh ulang: dua salinan dengan
          nama berbeda justru yang membuat video tertukar. Di platformnya Anda
          masih bisa memilih sound dan efek, yang tidak bisa dilakukan lewat
          unggahan otomatis.
        </p>

        {/* Izin kanal sumber (JOB-2 F0-3). Unggahan lewat halaman platform pun
            terkena klaim Content ID yang sama. Tidak memblokir. */}
        <PeringatanIzin clipName={clip.file_name} />

        {/* Platform */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginBottom: '12px' }}>
          {(data?.platform ?? []).map((p) => (
            <button key={p.platform} onClick={() => setAktif(p.platform)}
                    className={`chip${aktif === p.platform ? ' is-on' : ''}`}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: '5px',
                             cursor: 'pointer' }}>
              {terbit.includes(p.platform) && <Check size={12} />}
              {p.label}
            </button>
          ))}
        </div>

        {sibuk && !data && (
          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)',
                      display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Loader2 size={15} className="animate-spin" />
            Menulis caption dari isi klipnya…
          </p>
        )}

        {paket && (
          <>
            {paket.judul !== undefined && (
              <>
                <div style={{ ...label, marginBottom: '4px' }}>
                  Judul video <span style={{ fontWeight: 500, color: 'var(--text-muted)' }}>
                    (di YouTube ini yang paling menentukan)
                  </span>
                </div>
                <div style={{ display: 'flex', gap: '7px', marginBottom: '12px' }}>
                  <input value={judul} onChange={(e) => setJudul(e.target.value)}
                         maxLength={100} style={{ ...kotak, flex: 1 }} />
                  <button className="btn-secondary" onClick={() => salin(judul, 'judul')}
                          style={{ whiteSpace: 'nowrap' }}>
                    {disalin === 'judul' ? <Check size={14} /> : <Copy size={14} />}
                  </button>
                </div>
              </>
            )}

            <div style={{ ...label, marginBottom: '4px', display: 'flex',
                          justifyContent: 'space-between', alignItems: 'center' }}>
              <span>Caption</span>
              <span style={{ fontWeight: 500, color: 'var(--text-muted)' }}>
                {paket.tagar.length}/{paket.maks_tagar} tagar
              </span>
            </div>
            <textarea value={caption} onChange={(e) => setCaption(e.target.value)} rows={7}
                      style={{ ...kotak, width: '100%', resize: 'vertical', lineHeight: 1.55 }} />

            <div style={{ display: 'flex', gap: '7px', flexWrap: 'wrap', marginTop: '10px' }}>
              <button className="btn-primary" onClick={() => salin(caption, 'caption')}>
                {disalin === 'caption' ? <Check size={14} /> : <Copy size={14} />}
                {disalin === 'caption' ? ' Tersalin' : ' Salin caption'}
              </button>
              <button className="btn-secondary"
                      onClick={() => downloadToDisk(kategoriKlip(), clip.file_name)}>
                <Download size={14} /> Simpan berkas
              </button>
              {diKomputerIni && (
                <>
                  <button className="btn-secondary" disabled={sibuk}
                          title="Buka folder dengan berkas ini sudah tersorot"
                          onClick={() => tunjukLaluBuka(null)}>
                    <FolderOpen size={14} /> Tunjuk berkasnya
                  </button>
                  <button className="btn-secondary" disabled={sibuk}
                          title="Taruh berkas videonya di papan klip, lalu tempel dengan Ctrl+V"
                          onClick={salinBerkas}>
                    {disalin === 'berkas' ? <Check size={14} /> : <Clipboard size={14} />}
                    {disalin === 'berkas' ? 'Berkas siap ditempel' : 'Salin berkasnya'}
                  </button>
                </>
              )}
              <a className="btn-secondary" href={paket.unggah} target="_blank" rel="noreferrer"
                 style={{ display: 'inline-flex', alignItems: 'center', gap: '6px',
                          textDecoration: 'none' }}>
                <ExternalLink size={14} /> Buka {paket.label}
              </a>
              <button className="btn-secondary" onClick={() => muat(true)} disabled={sibuk}
                      title="Menulis ulang captionnya dengan AI. Memakai kuota model."
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                {sibuk ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                Tulis ulang dengan AI
              </button>
            </div>

            <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', lineHeight: 1.5,
                        margin: '12px 0 0' }}>
              {paket.catatan}
            </p>

            <label style={{
              display: 'flex', alignItems: 'center', gap: '9px', marginTop: '14px',
              paddingTop: '12px', borderTop: '1px solid var(--rule-2)', cursor: 'pointer',
              fontSize: '0.8rem',
            }}>
              <input type="checkbox" checked={sudahTerbit}
                     onChange={(e) => tandai(e.target.checked)}
                     style={{ accentColor: 'var(--accent-cyan)', width: '16px', height: '16px' }} />
              Sudah saya terbitkan ke {paket.label}
            </label>

            {periksa?.catatan && (
              <div style={{ marginTop: '14px', borderTop: '1px solid var(--border-color)',
                            paddingTop: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px',
                              fontSize: '0.78rem', fontWeight: 800 }}>
                  <span>Sebelum diunggah</span>
                  <span style={{
                    marginLeft: 'auto', fontVariantNumeric: 'tabular-nums',
                    color: periksa.skor >= 85 ? 'var(--entry)'
                      : periksa.skor >= 60 ? 'var(--reh)' : 'var(--accent-red)',
                  }}>{periksa.skor}/100</span>
                </div>
                {periksa.catatan.length === 0 ? (
                  <p style={{ fontSize: '0.74rem', color: 'var(--text-secondary)',
                              margin: '8px 0 0', lineHeight: 1.6 }}>
                    Tidak ada yang mencurigakan di daftar ini.
                  </p>
                ) : (
                  <ul style={{ margin: '8px 0 0', paddingLeft: '16px',
                               fontSize: '0.74rem', lineHeight: 1.65,
                               color: 'var(--text-secondary)' }}>
                    {periksa.catatan.map((c, i) => (
                      <li key={i} style={{ marginBottom: '6px' }}>
                        <b style={{ color: c.berat === 'berat' ? 'var(--accent-red)'
                          : c.berat === 'sedang' ? 'var(--reh)' : 'var(--ink-2)' }}>
                          {c.judul}
                        </b>
                        <span style={{ display: 'block' }}>{c.saran}</span>
                      </li>
                    ))}
                  </ul>
                )}
                <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)',
                            margin: '10px 0 0', lineHeight: 1.55 }}>
                  {periksa.catatan_kaki}
                </p>
              </div>
            )}

            {data?.sumber && (
              <p style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '10px' }}>
                Caption disusun {data.sumber === 'lokal'
                  ? 'mesin lokal dari kalimat klipnya sendiri (tanpa kunci AI)'
                  : data.sumber}
                {data.dari_simpanan ? ' · diambil dari hasil sebelumnya' : ''}
              </p>
            )}
          </>
        )}

        {galat && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '7px', marginTop: '12px',
                        fontSize: '0.78rem', color: 'var(--accent-red)' }}>
            <AlertTriangle size={15} />{galat}
          </div>
        )}
      </div>
    </div>
  );
}

const label = { fontSize: '0.74rem', fontWeight: 800, color: 'var(--text-secondary)' };
const kotak = {
  padding: '9px 11px', borderRadius: 'var(--radius-sm)',
  border: '1px solid var(--border-color)', background: 'var(--bg-glass)',
  color: 'var(--text-primary)', fontSize: '0.82rem', fontFamily: 'inherit',
};
