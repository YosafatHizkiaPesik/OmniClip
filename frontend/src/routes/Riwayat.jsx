import React, { useEffect, useState } from 'react';
import { Loader2, Trash2, X } from 'lucide-react';
import { apiDelete, apiGet } from '../lib/api';
import { useT } from '../lib/i18n';
import KisiVideo from '../components/KisiVideo';

/** Video yang pernah dibuka di halaman tonton, per akun (JOB-3 J3-7). */
export default function Riwayat() {
  const t = useT();
  const [video, setVideo] = useState(null);

  useEffect(() => {
    apiGet('/riwayat-tonton').then((r) => setVideo(r.video ?? [])).catch(() => setVideo([]));
  }, []);

  const hapus = async (id) => {
    const r = await apiDelete(`/riwayat-tonton${id ? `?video_id=${encodeURIComponent(id)}` : ''}`);
    setVideo(r.video ?? []);
  };

  return (
    <div className="page">
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '4px 0 16px' }}>
        <h1 style={{ fontSize: '1.6rem', fontWeight: 800, margin: 0 }}>{t('nav.riwayat')}</h1>
        {video?.length > 0 && (
          <button className="btn-secondary" style={{ marginLeft: 'auto', display: 'inline-flex', gap: 6 }}
                  onClick={() => window.confirm(t('riwayat.yakin')) && hapus('')}>
            <Trash2 size={14} /> {t('riwayat.hapus_semua')}
          </button>
        )}
      </div>
      {!video ? <div style={{ padding: 40, textAlign: 'center' }}><Loader2 className="animate-spin" size={22} /></div>
        : video.length === 0
          ? <div style={{ padding: 40, textAlign: 'center', color: 'var(--ink-3)' }}>{t('riwayat.kosong')}</div>
          : <KisiVideo video={video} aksiKartu={(v) => (
              <button title={t('riwayat.hapus_satu')} onClick={() => hapus(v.id)}
                      style={{ position: 'absolute', top: 8, right: 8, zIndex: 2, width: 26, height: 26,
                               borderRadius: 7, border: '1px solid rgba(255,255,255,.35)',
                               background: 'rgba(0,0,0,.55)', color: '#fff', cursor: 'pointer',
                               display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <X size={14} />
              </button>
            )} />}
    </div>
  );
}
