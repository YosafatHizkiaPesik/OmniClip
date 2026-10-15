import React from 'react';
import { AlertTriangle, RotateCcw } from 'lucide-react';
import { t } from '../lib/i18n';

/**
 * Penahan galat render.
 *
 * React membongkar SELURUH pohon komponen ketika satu komponen melempar galat
 * saat render. Tanpa penahan, satu pemanggilan fungsi yang belum di-import di
 * dalam kartu video membuat seluruh halaman jadi putih kosong — tanpa pesan,
 * tanpa navigasi, tanpa petunjuk bagian mana yang rusak. Itu persis yang
 * terjadi, dan itu jauh lebih buruk daripada kartu yang gagal sendirian.
 *
 * Harus berupa komponen kelas: getDerivedStateFromError dan componentDidCatch
 * tidak punya padanan dalam hook.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    // Tetap dicatat ke konsol: pesan di layar sengaja ringkas, sedangkan
    // jejak tumpukannya yang menunjukkan berkas dan barisnya.
    console.error('Komponen gagal dirender:', error, info?.componentStack);
  }

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div style={{
        margin: '30px auto', maxWidth: '540px', padding: '22px 24px',
        background: 'var(--bg-card)', border: '1px solid var(--border-color)',
        borderRadius: 'var(--radius-md)', textAlign: 'center',
      }}>
        <AlertTriangle size={30} style={{ color: 'var(--accent-red, var(--danger))', marginBottom: '10px' }} />
        <h3 style={{ fontWeight: 800, marginBottom: '8px' }}>{t('galat.judul')}</h3>
        <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.6, margin: '0 0 6px' }}>
          {t('galat.saran')}
        </p>
        <code style={{
          display: 'block', fontSize: '0.74rem', color: 'var(--text-muted)',
          margin: '12px 0 16px', wordBreak: 'break-word',
        }}>
          {String(error?.message || error)}
        </code>
        <button className="btn-secondary" onClick={() => this.setState({ error: null })}>
          <RotateCcw size={14} /> {t('galat.coba_lagi')}
        </button>
      </div>
    );
  }
}
