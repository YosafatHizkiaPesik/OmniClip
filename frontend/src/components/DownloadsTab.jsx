import React, { useState, useEffect } from 'react';
import { Download, Film, Music, Trash2, RefreshCw, Search, Play, X, CheckCircle, Loader2 } from 'lucide-react';

function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
}

function formatDate(timestamp) {
  if (!timestamp) return '';
  return new Date(timestamp * 1000).toLocaleDateString('id-ID', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
  });
}

// Video Player Modal
function VideoPlayerModal({ item, onClose }) {
  const src = `http://localhost:8000${item.web_url}`;
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div onClick={e => e.stopPropagation()} style={{
        background: '#000', borderRadius: '16px', overflow: 'hidden',
        maxWidth: '800px', width: '100%', position: 'relative',
      }}>
        <button onClick={onClose} style={{
          position: 'absolute', top: '10px', right: '10px', zIndex: 10,
          width: '32px', height: '32px', borderRadius: '50%',
          background: 'rgba(0,0,0,0.7)', border: 'none', color: '#fff',
          cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}><X size={16} /></button>
        {item.type === 'audio'
          ? <audio src={src} controls autoPlay style={{ width: '100%', padding: '40px 20px 20px' }} />
          : <video src={src} controls autoPlay style={{ width: '100%', maxHeight: '70vh', display: 'block' }} />
        }
        <div style={{ padding: '12px 16px', background: 'rgba(22,28,45,0.95)' }}>
          <div style={{ fontWeight: 700, fontSize: '0.9rem', color: '#fff', wordBreak: 'break-all' }}>{item.file_name}</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            {formatBytes(item.file_size)} • {item.type.toUpperCase()} • {formatDate(item.created_at)}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function DownloadsTab() {
  const [downloads, setDownloads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [deleting, setDeleting] = useState(null); // filename being deleted
  const [previewItem, setPreviewItem] = useState(null);
  const [selectedItems, setSelectedItems] = useState(new Set());
  const [bulkDeleting, setBulkDeleting] = useState(false);
  const [filter, setFilter] = useState('all'); // 'all' | 'video' | 'audio'

  const fetchDownloads = async () => {
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8000/api/downloads');
      const data = await res.json();
      setDownloads(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error(err);
      setDownloads([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDownloads(); }, []);

  const handleDelete = async (filename) => {
    if (!window.confirm(`Hapus file "${filename}"?`)) return;
    setDeleting(filename);
    try {
      const res = await fetch(`http://localhost:8000/api/downloads/${encodeURIComponent(filename)}`, { method: 'DELETE' });
      if (res.ok) {
        setDownloads(prev => prev.filter(d => d.file_name !== filename));
        setSelectedItems(prev => { const s = new Set(prev); s.delete(filename); return s; });
      } else {
        alert('Gagal menghapus file.');
      }
    } catch { alert('Error saat menghapus file.'); }
    finally { setDeleting(null); }
  };

  const handleBulkDelete = async () => {
    if (selectedItems.size === 0) return;
    if (!window.confirm(`Hapus ${selectedItems.size} file yang dipilih?`)) return;
    setBulkDeleting(true);
    for (const fname of selectedItems) {
      try {
        await fetch(`http://localhost:8000/api/downloads/${encodeURIComponent(fname)}`, { method: 'DELETE' });
      } catch {}
    }
    setSelectedItems(new Set());
    await fetchDownloads();
    setBulkDeleting(false);
  };

  const handleProxyDownload = async (fileName) => {
    try {
      const res = await fetch(`http://localhost:8000/api/file/local_downloads/${encodeURIComponent(fileName)}`);
      if (!res.ok) throw new Error('File tidak ditemukan');
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = fileName;
      document.body.appendChild(a); a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch (err) { alert(`Gagal: ${err.message}`); }
  };

  const toggleSelect = (fname) => {
    setSelectedItems(prev => {
      const s = new Set(prev);
      if (s.has(fname)) s.delete(fname); else s.add(fname);
      return s;
    });
  };

  // Filter + Search
  const filtered = downloads.filter(d => {
    const matchFilter = filter === 'all' || d.type === filter;
    const matchSearch = !searchQuery || d.file_name.toLowerCase().includes(searchQuery.toLowerCase());
    return matchFilter && matchSearch;
  });

  const totalSize = downloads.reduce((acc, d) => acc + d.file_size, 0);

  return (
    <div>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Download size={24} style={{ color: 'var(--accent-cyan)' }} />
            Downloads
          </h2>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
            {downloads.length} file • Total: {formatBytes(totalSize)}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          {selectedItems.size > 0 && (
            <button
              onClick={handleBulkDelete}
              disabled={bulkDeleting}
              className="btn-secondary"
              style={{ color: '#ef4444', borderColor: 'rgba(239,68,68,0.3)', background: 'rgba(239,68,68,0.08)', fontSize: '0.82rem' }}
            >
              {bulkDeleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
              Hapus {selectedItems.size} Terpilih
            </button>
          )}
          <button className="btn-secondary" onClick={fetchDownloads} style={{ fontSize: '0.82rem' }}>
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      {/* Search + Filter Bar */}
      <div style={{ display: 'flex', gap: '10px', marginBottom: '16px', flexWrap: 'wrap' }}>
        {/* Search Input */}
        <div style={{ flex: 1, minWidth: '200px', position: 'relative', display: 'flex', alignItems: 'center' }}>
          <Search size={16} style={{ position: 'absolute', left: '12px', color: 'var(--text-muted)' }} />
          <input
            type="text"
            placeholder="Cari file unduhan..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            style={{
              width: '100%', padding: '9px 12px 9px 36px',
              background: 'rgba(30,41,59,0.6)', border: '1px solid var(--border-color)',
              borderRadius: '10px', color: '#fff', outline: 'none', fontSize: '0.85rem',
            }}
          />
          {searchQuery && (
            <button onClick={() => setSearchQuery('')} style={{
              position: 'absolute', right: '10px', background: 'none', border: 'none',
              color: 'var(--text-muted)', cursor: 'pointer', padding: '2px',
            }}><X size={14} /></button>
          )}
        </div>

        {/* Filter Chips */}
        <div style={{ display: 'flex', gap: '6px' }}>
          {[['all', 'Semua'], ['video', '🎬 Video'], ['audio', '🎵 Audio']].map(([val, label]) => (
            <button key={val} onClick={() => setFilter(val)} style={{
              padding: '8px 14px', borderRadius: '20px', border: 'none', fontWeight: 600, fontSize: '0.8rem', cursor: 'pointer',
              background: filter === val ? '#fff' : 'rgba(255,255,255,0.1)',
              color: filter === val ? '#000' : 'var(--text-primary)',
            }}>{label}</button>
          ))}
        </div>
      </div>

      {loading ? (
        <div style={{ padding: '60px', textAlign: 'center' }}>
          <Loader2 size={32} className="animate-spin" style={{ color: 'var(--accent-cyan)', margin: '0 auto' }} />
        </div>
      ) : filtered.length === 0 ? (
        <div style={{ padding: '60px 20px', textAlign: 'center', background: 'var(--bg-card)', borderRadius: '16px', border: '1px dashed var(--border-color)' }}>
          <Download size={48} style={{ color: 'var(--text-muted)', marginBottom: '12px' }} />
          <h3 style={{ fontWeight: 700 }}>
            {downloads.length === 0 ? 'Belum Ada File Diunduh' : 'Tidak ada hasil pencarian'}
          </h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '4px' }}>
            {downloads.length === 0
              ? 'Gunakan tab Search untuk download video atau audio.'
              : `Tidak ada file yang cocok dengan "${searchQuery}"`}
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          {filtered.map((item) => (
            <div
              key={item.file_name}
              style={{
                display: 'flex', alignItems: 'center', gap: '12px',
                background: selectedItems.has(item.file_name) ? 'rgba(0,242,254,0.06)' : 'var(--bg-card)',
                border: selectedItems.has(item.file_name) ? '1px solid rgba(0,242,254,0.3)' : '1px solid var(--border-color)',
                borderRadius: '12px', padding: '12px 14px',
                transition: 'all 0.15s ease',
              }}
            >
              {/* Checkbox */}
              <div
                onClick={() => toggleSelect(item.file_name)}
                style={{
                  width: '18px', height: '18px', borderRadius: '4px', cursor: 'pointer', flexShrink: 0,
                  border: selectedItems.has(item.file_name) ? '2px solid var(--accent-cyan)' : '2px solid var(--border-color)',
                  background: selectedItems.has(item.file_name) ? 'var(--accent-cyan)' : 'transparent',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}
              >
                {selectedItems.has(item.file_name) && <CheckCircle size={12} style={{ color: '#000' }} />}
              </div>

              {/* Icon */}
              <div style={{
                width: '44px', height: '44px', borderRadius: '10px', flexShrink: 0,
                background: item.type === 'audio' ? 'rgba(255,8,68,0.12)' : 'rgba(0,242,254,0.12)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: item.type === 'audio' ? 'var(--accent-pink)' : 'var(--accent-cyan)',
              }}>
                {item.type === 'audio' ? <Music size={22} /> : <Film size={22} />}
              </div>

              {/* Info */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontWeight: 600, fontSize: '0.88rem', color: '#fff',
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'
                }}>{item.file_name}</div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '2px', display: 'flex', gap: '8px' }}>
                  <span>{formatBytes(item.file_size)}</span>
                  <span>•</span>
                  <span style={{ textTransform: 'uppercase', color: item.type === 'audio' ? 'var(--accent-pink)' : 'var(--accent-cyan)' }}>{item.type}</span>
                  <span>•</span>
                  <span>{formatDate(item.created_at)}</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
                <button
                  onClick={() => setPreviewItem(item)}
                  className="btn-secondary"
                  style={{ padding: '6px 10px', fontSize: '0.78rem' }}
                  title="Putar"
                >
                  <Play size={13} />
                </button>
                <button
                  onClick={() => handleProxyDownload(item.file_name)}
                  className="btn-secondary"
                  style={{ padding: '6px 10px', fontSize: '0.78rem', color: 'var(--accent-cyan)', borderColor: 'rgba(0,242,254,0.25)' }}
                  title="Simpan ke perangkat"
                >
                  <Download size={13} />
                </button>
                <button
                  onClick={() => handleDelete(item.file_name)}
                  disabled={deleting === item.file_name}
                  className="btn-secondary"
                  style={{ padding: '6px 10px', fontSize: '0.78rem', color: '#ef4444', borderColor: 'rgba(239,68,68,0.25)' }}
                  title="Hapus"
                >
                  {deleting === item.file_name
                    ? <Loader2 size={13} className="animate-spin" />
                    : <Trash2 size={13} />}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Preview Modal */}
      {previewItem && <VideoPlayerModal item={previewItem} onClose={() => setPreviewItem(null)} />}
    </div>
  );
}
