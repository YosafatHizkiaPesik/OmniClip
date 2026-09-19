import React, { useCallback, useEffect, useState } from 'react';
import {
  ArrowDownToLine, CheckCircle2, Loader2, RefreshCw, AlertTriangle, Info,
} from 'lucide-react';
import { apiGet, apiPost } from '../lib/api';
import { useJobRunner } from '../hooks/useJob';

/**
 * Pembaruan aplikasi.
 *
 * Yang ditampilkan berbeda menurut apa yang benar-benar mungkin di komputer
 * ini, bukan menurut satu tampilan untuk semua keadaan: aplikasi yang dijalankan
 * dari kode sumber tidak diberi tombol pasang sama sekali, dan begitu pula
 * aplikasi yang folder induknya tidak bisa ditulis. Tombol yang pasti gagal
 * lebih buruk daripada tombol yang tidak ada.
 */
export default function UpdateCard({ card, sectionTitle, helpText }) {
  const [info, setInfo] = useState(null);
  const [memeriksa, setMemeriksa] = useState(false);
  const [galat, setGalat] = useState(null);
  const pekerjaan = useJobRunner();

  const muat = useCallback(async (paksa = false) => {
    setMemeriksa(true);
    setGalat(null);
    try {
      setInfo(await apiGet(`/update${paksa ? '?paksa=true' : ''}`));
    } catch (err) {
      setGalat(err.message);
    } finally {
      setMemeriksa(false);
    }
  }, []);

  useEffect(() => { muat(); }, [muat]);

  const pasang = () => {
    setGalat(null);
    pekerjaan.run('/update/pasang');
  };

  const sedangPasang = pekerjaan.active;
  const ada = info?.ada_pembaruan;

  return (
    <div style={card}>
      <div style={sectionTitle}>
        <ArrowDownToLine size={18} style={{ color: 'var(--reh)' }} />
        Pembaruan aplikasi
      </div>

      <p style={helpText}>
        OmniClip yang sudah terpasang tidak berubah sendiri saat kodenya
        diperbaiki — versinya dibekukan saat dibangun. Di sini ia menanyakan ke
        GitHub apakah ada versi yang lebih baru.
      </p>

      <div style={{ ...helpText, marginTop: '12px', display: 'flex',
                    alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
        {ada ? (
          <>
            <ArrowDownToLine size={15} style={{ color: 'var(--reh)' }} />
            <span>
              Versi <strong>{info.versi_terbaru}</strong> tersedia — Anda memakai{' '}
              <code>{info.versi_sekarang}</code>
              {info.ukuran ? ` · ${(info.ukuran / 1e6).toFixed(0)} MB` : ''}
            </span>
          </>
        ) : info?.versi_terbaru ? (
          <>
            <CheckCircle2 size={15} style={{ color: 'var(--entry)' }} />
            Sudah versi terbaru (<code>{info.versi_sekarang}</code>).
          </>
        ) : (
          <>
            <Info size={15} style={{ color: 'var(--text-muted)' }} />
            Versi terpasang <code>{info?.versi_sekarang || '—'}</code>
            {info?.galat ? ` · ${info.galat}` : ''}
          </>
        )}
      </div>

      {ada && info.catatan && (
        <details style={{ marginTop: '11px' }}>
          <summary style={{ ...helpText, cursor: 'pointer', fontWeight: 700,
                            color: 'var(--text-primary)' }}>
            Apa yang berubah
          </summary>
          <pre style={{
            ...helpText, marginTop: '8px', whiteSpace: 'pre-wrap',
            fontFamily: 'inherit', maxHeight: '220px', overflow: 'auto',
            padding: '10px 12px', borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-color)',
          }}>{info.catatan}</pre>
        </details>
      )}

      {sedangPasang && (
        <div style={{ marginTop: '13px' }}>
          <div style={{ ...helpText, display: 'flex', gap: '8px',
                        alignItems: 'center', marginBottom: '7px' }}>
            <Loader2 size={15} className="animate-spin" />
            {pekerjaan.message || 'Menyiapkan…'}
          </div>
          <div style={{ height: '5px', borderRadius: '3px',
                        background: 'var(--border-color)', overflow: 'hidden' }}>
            <div style={{
              height: '100%', width: `${Math.round(pekerjaan.progress * 100)}%`,
              background: 'var(--reh)', transition: 'width 0.3s ease',
            }} />
          </div>
          {pekerjaan.job?.stage === 'selesai' && (
            <p style={{ ...helpText, marginTop: '9px' }}>
              Jendela OmniClip akan menutup sendiri, lalu terbuka kembali pada
              versi baru. Klip dan setelan Anda tidak tersentuh.
            </p>
          )}
        </div>
      )}

      <div style={{ display: 'flex', gap: '8px', marginTop: '13px', flexWrap: 'wrap' }}>
        <button onClick={() => muat(true)} disabled={memeriksa || sedangPasang}
                style={{ ...ghost, opacity: memeriksa || sedangPasang ? 0.5 : 1 }}>
          {memeriksa ? <Loader2 size={14} className="animate-spin" />
                     : <RefreshCw size={14} />}
          Periksa sekarang
        </button>

        {ada && info.bisa_pasang_sendiri && (
          <button className="btn-primary" onClick={pasang} disabled={sedangPasang}
                  style={{ opacity: sedangPasang ? 0.5 : 1 }}>
            <ArrowDownToLine size={15} /> Unduh dan pasang
          </button>
        )}

        {ada && (
          <a href={info.halaman} target="_blank" rel="noreferrer" style={ghost}>
            Buka halaman rilis
          </a>
        )}
      </div>

      {ada && !info.bisa_pasang_sendiri && info.alasan_tidak_bisa && (
        <p style={{ ...helpText, marginTop: '11px', display: 'flex', gap: '7px',
                    alignItems: 'flex-start' }}>
          <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: '2px',
                                            color: 'var(--text-muted)' }} />
          <span>Pemasangan otomatis tidak tersedia di sini: {info.alasan_tidak_bisa}</span>
        </p>
      )}

      {(galat || pekerjaan.error) && (
        <p style={{ ...helpText, marginTop: '11px', display: 'flex', gap: '7px',
                    alignItems: 'flex-start',
                    color: 'var(--accent-red, var(--danger))' }}>
          <AlertTriangle size={15} style={{ flexShrink: 0, marginTop: '2px' }} />
          <span>{galat || pekerjaan.error || 'Pemasangan gagal.'}</span>
        </p>
      )}

      <PustakaOtomatis helpText={helpText} />
    </div>
  );
}

/**
 * Pustaka yang memperbarui dirinya sendiri, terpisah dari versi aplikasi.
 *
 * Ditampilkan karena ia menjelaskan sesuatu yang kalau tidak akan tampak
 * seperti keanehan: OmniClip bisa memperbaiki unduhan YouTube yang rusak tanpa
 * versinya berubah sama sekali. Bukan karena ada yang perlu dikerjakan di
 * sini — tombolnya hanya mempercepat pemeriksaan yang memang sudah berjalan
 * sendiri tiap dua belas jam.
 */
function PustakaOtomatis({ helpText }) {
  const [data, setData] = useState(null);
  const [sibuk, setSibuk] = useState(false);
  const [kabar, setKabar] = useState(null);

  const muat = async () => {
    try { setData(await apiGet('/settings/pustaka')); } catch { /* diam */ }
  };
  useEffect(() => { muat(); }, []);

  const periksa = async () => {
    setSibuk(true); setKabar(null);
    try {
      const r = await apiPost('/settings/pustaka/periksa', {});
      const dipasang = (r.hasil || []).filter((h) => h.dipasang);
      setKabar(dipasang.length
        ? `${dipasang.map((h) => `${h.paket} ${h.terbaru}`).join(', ')} dipasang. `
          + 'Berlaku setelah OmniClip dijalankan ulang.'
        : 'Semua pustaka sudah mutakhir.');
      await muat();
    } catch (err) {
      setKabar(err.message);
    } finally { setSibuk(false); }
  };

  if (!data?.paket?.length) return null;

  return (
    <div style={{ marginTop: '16px', paddingTop: '14px',
                  borderTop: '1px solid var(--rule-2, var(--border-color))' }}>
      <strong style={{ fontSize: '0.82rem' }}>Pustaka YouTube &amp; suara</strong>
      <p style={{ ...helpText, margin: '4px 0 9px' }}>
        Diperbarui sendiri tiap dua belas jam. Inilah yang menjaga unduhan tetap
        bekerja saat YouTube berubah — perbaikannya datang dari pustakanya, bukan
        dari versi OmniClip.
      </p>
      <div style={{ display: 'flex', gap: '14px', flexWrap: 'wrap', fontSize: '0.78rem' }}>
        {data.paket.map((p) => (
          <span key={p.nama} style={{ color: 'var(--text-secondary)' }}>
            {p.nama} <code>{p.versi || '—'}</code>
            {p.dari_pembaruan && (
              <em style={{ color: 'var(--text-muted)', fontStyle: 'normal' }}> (hasil pembaruan)</em>
            )}
          </span>
        ))}
      </div>
      <button style={{ ...ghost, marginTop: '10px', fontSize: '0.78rem', padding: '7px 11px' }}
              onClick={periksa} disabled={sibuk}>
        {sibuk ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
        Periksa pustaka sekarang
      </button>
      {kabar && <p style={{ ...helpText, marginTop: '8px' }}>{kabar}</p>}
    </div>
  );
}

const ghost = {
  display: 'inline-flex', alignItems: 'center', gap: '7px',
  padding: '9px 13px', borderRadius: 'var(--radius-md)',
  border: '1px solid var(--border-color)', background: 'transparent',
  color: 'var(--text-secondary)', cursor: 'pointer', textDecoration: 'none',
  fontSize: '0.82rem', fontWeight: 700, fontFamily: 'inherit',
};
