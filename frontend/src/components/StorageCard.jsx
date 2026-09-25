import React, { useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle, CheckCircle2, FolderOpen, HardDrive, Loader2, RefreshCw,
} from 'lucide-react';
import { apiGet, apiPost } from '../lib/api';
import { useJobRunner } from '../hooks/useJob';
import FolderPicker from './FolderPicker';
import JobProgress from './JobProgress';

function ukuran(bita) {
  if (!bita) return '0 MB';
  const gb = bita / 1073741824;
  return gb >= 1 ? `${gb.toFixed(1)} GB` : `${(bita / 1048576).toFixed(0)} MB`;
}

/**
 * Tempat klip, unduhan, dan basis data disimpan.
 *
 * Ada di sini karena jawabannya tidak bisa ditebak dari luar: saat dibungkus,
 * penyimpanan sengaja TIDAK berada di dalam folder aplikasi — folder itu
 * ditukar seluruhnya setiap kali aplikasi memperbarui dirinya, jadi apa pun di
 * dalamnya akan ikut hilang. Akibatnya klip berakhir di folder yang tidak
 * pernah dibuka siapa pun, dan satu-satunya cara mengeluarkannya adalah
 * mengunduhnya satu per satu lewat peramban.
 */
export default function StorageCard({ card, sectionTitle, helpText }) {
  const [info, setInfo] = useState(null);
  const [sibuk, setSibuk] = useState(false);
  const [galat, setGalat] = useState(null);
  const [pesan, setPesan] = useState(null);
  // Folder yang sedang dipilih lewat dialog: { jenis, judul, awal } atau null.
  const [memilih, setMemilih] = useState(null);
  const [judulPindah, setJudulPindah] = useState('');
  const pekerjaan = useJobRunner();

  const muat = useCallback(async () => {
    try {
      setInfo(await apiGet('/settings/penyimpanan'));
    } catch (err) {
      setGalat(err.message);
    }
  }, []);

  useEffect(() => { muat(); }, [muat]);

  // Angka ukuran folder hanya benar setelah pemindahannya berhenti.
  const statusPindah = pekerjaan.job?.status;
  useEffect(() => {
    if (statusPindah === 'done' || statusPindah === 'failed' || statusPindah === 'cancelled') {
      muat();
    }
  }, [statusPindah, muat]);

  const buka = async () => {
    setGalat(null);
    try {
      await apiPost('/settings/penyimpanan/buka', {});
    } catch (err) {
      setGalat(err.message);
    }
  };

  const bukaFolder = async (jenis) => {
    setGalat(null);
    try {
      await apiPost('/settings/penyimpanan/folder/buka', { jenis });
    } catch (err) {
      setGalat(err.message);
    }
  };

  // Dialog penjelajah, bukan `window.prompt`. Versi sebelumnya meminta jalur
  // diketik penuh, "/media/ynot/744E3DDC4E3D97B6/Projek Coding/...", yang
  // praktis hanya bisa benar kalau disalin dari tempat lain, dan salah ketiknya
  // baru ketahuan setelah tombol ditekan.
  //
  // Berkasnya benar-benar dipindahkan, dan pemindahannya punya persentase.
  // Sebelum ini tombolnya hanya menulis penunjuk folder: dari luar tidak ada
  // bedanya dengan tombol yang rusak.
  const simpanFolder = async (jenis, judul, folder) => {
    setMemilih(null);
    setGalat(null);
    setPesan(null);
    setSibuk(true);
    try {
      const r = await apiPost('/settings/penyimpanan/folder',
        { jenis, folder: (folder || '').trim() });
      if (r.sudah_di_sana) {
        setPesan(`${judul} memang sudah ada di folder itu.`);
      } else if (r.job_id) {
        setJudulPindah(judul);
        pekerjaan.follow(r.job_id);
      } else {
        setPesan(`${judul} diarahkan ke ${r.folder}. Jalankan ulang OmniClip agar berlaku.`);
      }
      await muat();
    } catch (err) {
      setGalat(err.message);
    } finally {
      setSibuk(false);
    }
  };

  const pindah = async (folder) => {
    setSibuk(true);
    setGalat(null);
    setPesan(null);
    try {
      const r = await apiPost('/settings/penyimpanan', { folder });
      setPesan(r.perlu_restart
        ? `Akan dipindahkan ke ${r.folder} saat OmniClip dijalankan lagi. Tutup dan buka aplikasinya.`
        : 'Folder sudah dipakai.');
      await muat();
    } catch (err) {
      setGalat(err.message);
    } finally {
      setSibuk(false);
    }
  };

  if (!info) return null;

  return (
    <div style={card}>
      <h3 style={sectionTitle}><HardDrive size={15} /> Tempat penyimpanan</h3>
      <p style={helpText}>
        Semua unduhan, klip jadi, dan basis data tinggal di satu folder ini.
      </p>

      <div style={{
        padding: '10px 12px', borderRadius: 'var(--radius-sm, 8px)',
        background: 'var(--plate-3, rgba(255,255,255,0.04))',
        border: '1px solid var(--border-color)', margin: '10px 0',
        fontSize: '0.78rem', wordBreak: 'break-all', lineHeight: 1.5,
      }}>
        <code>{info.folder}</code>
        <div style={{ color: 'var(--text-muted)', fontSize: '0.72rem', marginTop: '5px' }}>
          Sisa ruang: {ukuran(info.sisa_ruang)}
        </div>
      </div>

      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <button className="btn-secondary" onClick={buka} style={{ fontSize: '0.8rem' }}>
          <FolderOpen size={14} /> Buka folder
        </button>
        <button className="btn-secondary" onClick={muat} style={{ fontSize: '0.8rem' }}>
          <RefreshCw size={14} /> Segarkan
        </button>
      </div>

      {/* Dua folder yang isinya paling besar, masing-masing bisa ditaruh
          di tempat lain. Ukuran dan jumlah berkasnya ditampilkan supaya
          membersihkannya jadi keputusan, bukan tebakan. */}
      <p style={{ ...helpText, marginTop: '14px', marginBottom: 0 }}>
        Memindahkan salah satunya akan MEMINDAHKAN berkas yang sudah ada, bukan
        hanya menunjuk tempat baru. Berlaku langsung, tanpa menjalankan ulang
        OmniClip.
      </p>
      <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {[['unduhan', 'Video sumber terunduh', info.unduhan],
          ['klip', 'Klip jadi', info.klip]].map(([jenis, judul, d]) => d && (
          <div key={jenis} style={{
            padding: '10px 12px', borderRadius: 'var(--radius-sm, 8px)',
            background: 'var(--plate-3, rgba(255,255,255,0.04))',
            border: '1px solid var(--border-color)',
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between',
                          alignItems: 'baseline', gap: '10px', flexWrap: 'wrap' }}>
              <strong style={{ fontSize: '0.78rem' }}>{judul}</strong>
              <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                {d.jumlah} berkas · {ukuran(d.ukuran)}
              </span>
            </div>
            <code style={{ display: 'block', fontSize: '0.71rem', marginTop: '5px',
                           wordBreak: 'break-all', color: 'var(--text-secondary)' }}>
              {d.folder}
            </code>
            <div style={{ display: 'flex', gap: '7px', marginTop: '8px', flexWrap: 'wrap' }}>
              <button className="btn-secondary" style={{ fontSize: '0.75rem', padding: '5px 9px' }}
                      onClick={() => bukaFolder(jenis)}>
                <FolderOpen size={13} /> Buka
              </button>
              <button className="btn-secondary" style={{ fontSize: '0.75rem', padding: '5px 9px' }}
                      disabled={sibuk || pekerjaan.active}
                      onClick={() => setMemilih({ jenis, judul, awal: d.folder })}>
                Pindahkan ke…
              </button>
              <button className="btn-secondary" style={{ fontSize: '0.75rem', padding: '5px 9px' }}
                      disabled={sibuk || pekerjaan.active}
                      onClick={() => simpanFolder(jenis, judul, '')}>
                Kembali ke bawaan
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Berkasnya sedang berpindah. Nama berkas dan persentasenya datang dari
          server, bukan dikarang di sini. */}
      {(pekerjaan.active || pekerjaan.job) && (
        <div style={{ marginTop: '12px' }}>
          <div style={{ fontSize: '0.75rem', fontWeight: 700, marginBottom: '6px' }}>
            Memindahkan {judulPindah.toLowerCase()}
          </div>
          <JobProgress job={pekerjaan.job} error={pekerjaan.error}
                       onCancel={pekerjaan.cancel} />
          {pekerjaan.job?.status === 'running' && (
            <p style={{ ...helpText, marginTop: '6px' }}>
              Boleh dibatalkan kapan saja. Berkas yang sudah pindah tetap di
              tempat barunya, dan menekan tombol yang sama nanti melanjutkan
              dari situ.
            </p>
          )}
        </div>
      )}

      {info.dari_sumber && (
        <p style={{ ...helpText, marginTop: '10px' }}>
          Dijalankan dari kode sumber, jadi <em>akar</em> penyimpanan mengikuti
          folder proyek. Kedua folder di atas tetap bisa ditaruh di mana saja.
        </p>
      )}

      {info.dikunci_env && (
        <p style={{ ...helpText, marginTop: '10px' }}>
          Lokasi sedang dipaksa lewat <code>OMNICLIP_STORAGE</code>.
        </p>
      )}

      {info.saran && !info.menunggu_pindah && (
        <div style={{ marginTop: '12px' }}>
          <p style={{ ...helpText, marginBottom: '8px' }}>
            Bisa dipindahkan ke sebelah aplikasi, supaya berkasnya langsung
            terlihat saat foldernya dibuka, tanpa perlu mengunduh satu per satu:
          </p>
          <code style={{ fontSize: '0.74rem', wordBreak: 'break-all' }}>{info.saran}</code>
          <div style={{ marginTop: '9px' }}>
            <button className="btn-secondary" disabled={sibuk}
                    onClick={() => pindah(info.saran)}
                    style={{ fontSize: '0.8rem', color: 'var(--accent-cyan)' }}>
              {sibuk ? <Loader2 size={14} className="animate-spin" /> : <HardDrive size={14} />}
              Pindahkan ke sana
            </button>
          </div>
        </div>
      )}

      {info.menunggu_pindah && (
        <div style={{
          display: 'flex', gap: '9px', alignItems: 'flex-start', marginTop: '12px',
          padding: '10px 12px', borderRadius: 'var(--radius-sm, 8px)', fontSize: '0.78rem',
          background: 'color-mix(in srgb, var(--accent-cyan) 12%, transparent)',
          border: '1px solid color-mix(in srgb, var(--accent-cyan) 32%, transparent)',
        }}>
          <CheckCircle2 size={15} style={{ flexShrink: 0, color: 'var(--accent-cyan)' }} />
          <span>
            Pemindahan sudah dijadwalkan. Tutup OmniClip lalu buka lagi. Berkasnya
            dipindahkan sebelum aplikasi menyala, dan yang sudah pindah tidak
            diulang kalau sempat terputus.
          </span>
        </div>
      )}

      {pesan && (
        <p style={{ ...helpText, marginTop: '10px', color: 'var(--accent-cyan)' }}>{pesan}</p>
      )}
      {galat && (
        <div style={{
          display: 'flex', gap: '9px', alignItems: 'center', marginTop: '10px',
          fontSize: '0.78rem', color: 'var(--danger)',
        }}>
          <AlertTriangle size={15} style={{ flexShrink: 0 }} /> {galat}
        </div>
      )}

      {memilih && (
        <FolderPicker
          judul={`Pilih folder untuk ${memilih.judul}`}
          awal={memilih.awal}
          onTutup={() => setMemilih(null)}
          onPilih={(jalur) => simpanFolder(memilih.jenis, memilih.judul, jalur)}
        />
      )}
    </div>
  );
}
