import React, { useState, useEffect, useRef } from 'react';
import {
  Scissors, Play, Pause, Save, HardDriveUpload, CheckSquare, Square,
  Sparkles, Type, Sliders, Monitor, CheckCircle, Loader2, Video, Plus,
  Trash2, Copy, RefreshCw, Layers, Wand2, Film, Palette, Award, Split,
  Maximize2, ZoomIn, ZoomOut, Check, SlidersHorizontal
} from 'lucide-react';
import { formatTime, parseTimeString, formatDurationHuman } from '../utils/timeFormat';

export default function StudioEditor({ video, aiData }) {
  // AI Loading & Data State
  const [loadingAI, setLoadingAI] = useState(!aiData || !aiData.clips);
  const [loadingProgress, setLoadingProgress] = useState(15);
  const [loadingStepText, setLoadingStepText] = useState('⚡ Membaca Transkrip ASLI YouTube...');
  const [clipList, setClipList] = useState(aiData?.clips || []);
  const [aiMode, setAiMode] = useState(aiData?.ai_mode || 'Gemini Pro/Flash');
  const [hasRealTranscript, setHasRealTranscript] = useState(aiData?.has_real_transcript || false);
  const [selectedClipIndex, setSelectedClipIndex] = useState(0);

  const currentClip = clipList[selectedClipIndex] || null;

  // Active Clip Trim Bounds
  const [startSec, setStartSec] = useState(currentClip?.start_seconds || 0);
  const [endSec, setEndSec] = useState(currentClip?.end_seconds || 30);
  const [hookText, setHookText] = useState(currentClip?.hook_text || '🔥 MOMEN PALING VIRAL!');
  const [subtitles, setSubtitles] = useState(currentClip?.subtitles || []);

  // Styling & Customization Options (CapCut Features)
  const [aspectRatio, setAspectRatio] = useState('9:16');
  const [fontColor, setFontColor] = useState('yellow');
  const [fontSize, setFontSize] = useState(24);
  const [position, setPosition] = useState('bottom');
  const [fontFamily, setFontFamily] = useState('Outfit');
  const [textTransform, setTextTransform] = useState('none'); // 'none' | 'uppercase' | 'capitalize'
  const [videoFilter, setVideoFilter] = useState('normal'); // 'normal' | 'vibrant' | 'cyberpunk' | 'vintage' | 'bw'
  const [watermarkText, setWatermarkText] = useState('');

  // Video Playback State
  const videoRef = useRef(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(startSec);
  const [activeSubtitleText, setActiveSubtitleText] = useState('');

  // Rendered FFmpeg Preview URL & Export state
  const [renderedPreviewUrl, setRenderedPreviewUrl] = useState(null);
  const [renderingPreview, setRenderingPreview] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportStatus, setExportStatus] = useState(null);

  // Active Control Panel Tab: 'trim' | 'subtitles' | 'style' | 'filter' | 'clips'
  const [activeTab, setActiveTab] = useState('trim');

  // Auto-analyze video if aiData is null on initial mount
  useEffect(() => {
    if (!aiData || !aiData.clips) {
      autoAnalyzeVideo();
    } else {
      setClipList(aiData.clips);
      setAiMode(aiData.ai_mode || 'Gemini Pro/Flash');
      setHasRealTranscript(aiData.has_real_transcript || false);
      setLoadingAI(false);
    }
  }, [video]);

  // Local Video Playback URL
  const [localVideoUrl, setLocalVideoUrl] = useState(aiData?.local_url || video?.local_url || null);

  const autoAnalyzeVideo = async () => {
    if (!video) return;
    setLoadingAI(true);
    setLoadingProgress(15);
    setLoadingStepText('⚡ Step 1/3: Mengunduh File Video MP4 ke Penyimpanan Lokal (yt-dlp)...');

    const timer1 = setTimeout(() => {
      setLoadingProgress(50);
      setLoadingStepText('🤖 Step 2/3: Menganalisis Momen Viral & Transkrip Percakapan ASLI dengan Gemini AI...');
    }, 2500);

    const timer2 = setTimeout(() => {
      setLoadingProgress(85);
      setLoadingStepText('✂️ Step 3/3: Menyusun Subtitle Kata-Demi-Kata & Frame 9:16...');
    }, 5500);

    try {
      const res = await fetch('http://localhost:8000/api/analyze-clips', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_info: video })
      });
      const data = await res.json();
      if (res.ok && data.clips) {
        setLoadingProgress(100);
        setClipList(data.clips);
        setAiMode(data.ai_mode || 'Gemini Pro/Flash');
        setHasRealTranscript(data.has_real_transcript || false);
        if (data.local_url) setLocalVideoUrl(data.local_url);
      }
    } catch (err) {
      alert('Gagal melakukan analisis otomatis Gemini AI');
    } finally {
      clearTimeout(timer1);
      clearTimeout(timer2);
      setLoadingAI(false);
    }
  };

  // Sync editor values when switching clips
  useEffect(() => {
    if (currentClip) {
      setStartSec(currentClip.start_seconds || 0);
      setEndSec(currentClip.end_seconds || 30);
      setHookText(currentClip.hook_text || '🔥 MOMEN PALING VIRAL!');
      setSubtitles(currentClip.subtitles || []);
      setRenderedPreviewUrl(null);
      setCurrentTime(currentClip.start_seconds || 0);
    }
  }, [selectedClipIndex, clipList]);

  // Sync active subtitle overlay line during playback
  useEffect(() => {
    if (subtitles && subtitles.length > 0) {
      const activeLine = subtitles.find(s => currentTime >= s.start && currentTime <= s.end);
      if (activeLine) {
        let txt = activeLine.text;
        if (textTransform === 'uppercase') txt = txt.toUpperCase();
        setActiveSubtitleText(txt);
      } else {
        setActiveSubtitleText(subtitles[0]?.text || '');
      }
    } else {
      setActiveSubtitleText('');
    }
  }, [currentTime, subtitles, textTransform]);

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      const cur = videoRef.current.currentTime;
      setCurrentTime(cur);
      if (cur >= endSec) {
        videoRef.current.currentTime = startSec;
      }
    }
  };

  const togglePlayPause = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        if (videoRef.current.currentTime < startSec || videoRef.current.currentTime >= endSec) {
          videoRef.current.currentTime = startSec;
        }
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  // Nudge trim time adjusters (+/- seconds)
  const adjustTime = (type, amount) => {
    if (type === 'start') {
      const nextStart = Math.max(0, Math.min(endSec - 3, startSec + amount));
      setStartSec(nextStart);
      if (videoRef.current) videoRef.current.currentTime = nextStart;
    } else {
      const maxDuration = video?.duration || 3600;
      const nextEnd = Math.min(maxDuration, Math.max(startSec + 3, endSec + amount));
      setEndSec(nextEnd);
    }
  };

  // Split Clip at current Playhead position
  const handleSplitClipAtPlayhead = () => {
    const splitPoint = round1(currentTime);
    if (splitPoint <= startSec + 2 || splitPoint >= endSec - 2) {
      alert('Posisi playhead terlalu dekat dengan batas awal/akhir klip');
      return;
    }
    const newClip1 = {
      ...currentClip,
      end_seconds: splitPoint,
      hook_text: `${hookText} (Part 1)`
    };
    const newClip2 = {
      ...currentClip,
      clip_id: clipList.length + 1,
      start_seconds: splitPoint,
      end_seconds: endSec,
      hook_text: `${hookText} (Part 2)`,
      is_manual: true
    };
    const updated = [...clipList];
    updated[selectedClipIndex] = newClip1;
    updated.splice(selectedClipIndex + 1, 0, newClip2);
    setClipList(updated);
    setEndSec(splitPoint);
  };

  // Add Manual Clip
  const handleAddManualClip = () => {
    const newId = clipList.length + 1;
    const newClip = {
      clip_id: newId,
      start_seconds: 0,
      end_seconds: Math.min(30, video?.duration || 30),
      virality_score: 92,
      hook_text: `✂️ KLIP MANUAL #${newId}`,
      subtitles: [
        { start: 0, end: 10, text: "Caption pertama klip baru" },
        { start: 10, end: 20, text: "Caption kedua klip baru" },
        { start: 20, end: 30, text: "Caption ketiga klip baru" }
      ],
      suggested_title: `Manual Clip ${newId}`,
      is_manual: true
    };
    const updated = [...clipList, newClip];
    setClipList(updated);
    setSelectedClipIndex(updated.length - 1);
  };

  // Duplicate Clip
  const handleDuplicateClip = () => {
    if (!currentClip) return;
    const newId = clipList.length + 1;
    const dup = {
      ...currentClip,
      clip_id: newId,
      hook_text: `${currentClip.hook_text} (Copy)`,
      is_manual: true
    };
    const updated = [...clipList, dup];
    setClipList(updated);
    setSelectedClipIndex(updated.length - 1);
  };

  const handleDeleteClip = (indexToDelete) => {
    if (clipList.length <= 1) {
      alert('Minimal harus ada 1 klip di editor');
      return;
    }
    const updated = clipList.filter((_, idx) => idx !== indexToDelete);
    setClipList(updated);
    setSelectedClipIndex(Math.max(0, indexToDelete - 1));
  };

  // Subtitle Handlers
  const handleSubtitleChange = (index, field, value) => {
    const updated = [...subtitles];
    updated[index] = { ...updated[index], [field]: value };
    setSubtitles(updated);
  };

  const handleAddSubtitleLine = () => {
    const lastEnd = subtitles.length > 0 ? subtitles[subtitles.length - 1].end : startSec;
    const newLine = {
      start: round1(lastEnd + 0.5),
      end: round1(lastEnd + 4.5),
      text: "Baris caption baru..."
    };
    setSubtitles([...subtitles, newLine]);
  };

  const handleDeleteSubtitleLine = (index) => {
    setSubtitles(subtitles.filter((_, i) => i !== index));
  };

  const handleAutoDistributeSubtitles = () => {
    if (!subtitles || subtitles.length === 0) return;
    const duration = Math.max(3, endSec - startSec);
    const step = duration / subtitles.length;
    const redistributed = subtitles.map((sub, i) => ({
      ...sub,
      start: round1(startSec + i * step),
      end: round1(startSec + (i + 1) * step - 0.2)
    }));
    setSubtitles(redistributed);
  };

  const round1 = (val) => Math.round(val * 10) / 10;

  // FFmpeg Render Preview Handler
  const handleGeneratePreview = async () => {
    if (!video) return;
    setRenderingPreview(true);
    setExportStatus(null);
    try {
      const res = await fetch('http://localhost:8000/api/render-clip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_path: video.url || video.local_path || video.id,
          start_seconds: startSec,
          end_seconds: endSec,
          subtitles: subtitles,
          aspect_ratio: aspectRatio,
          font_color: fontColor,
          font_size: fontSize,
          position: position,
          hook_text: hookText
        })
      });
      const data = await res.json();
      if (res.ok) {
        setRenderedPreviewUrl(`http://localhost:8000${data.web_url}`);
      } else {
        alert(data.detail || 'Gagal merender preview');
      }
    } catch (err) {
      alert('Gagal terhubung ke server FFmpeg');
    } finally {
      setRenderingPreview(false);
    }
  };

  // Export Clip
  const handleExport = async (target = 'local') => {
    if (!video) return;
    setExporting(true);
    setExportStatus(null);
    try {
      const renderRes = await fetch('http://localhost:8000/api/render-clip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_path: video.url || video.local_path || video.id,
          start_seconds: startSec,
          end_seconds: endSec,
          subtitles: subtitles,
          aspect_ratio: aspectRatio,
          font_color: fontColor,
          font_size: fontSize,
          position: position,
          hook_text: hookText
        })
      });
      const renderData = await renderRes.json();
      if (!renderRes.ok) throw new Error(renderData.detail || 'Render gagal');

      setRenderedPreviewUrl(`http://localhost:8000${renderData.web_url}`);

      if (target === 'drive') {
        const driveRes = await fetch('http://localhost:8000/api/drive/upload', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ file_path: renderData.clip_path })
        });
        const driveData = await driveRes.json();
        setExportStatus(`✅ Merender & Mengunggah klip '${renderData.clip_name}' ke Google Drive (${driveData.record.account_email})`);
      } else {
        setExportStatus(`✅ Klip '${renderData.clip_name}' selesai dirender! Mengunduh file...`);
        const a = document.createElement('a');
        a.href = `http://localhost:8000${renderData.web_url}`;
        a.download = renderData.clip_name;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      }
    } catch (err) {
      alert(`Error Export: ${err.message}`);
    } finally {
      setExporting(false);
    }
  };

  // CSS Filter overlay styling for canvas
  const getFilterStyle = () => {
    if (videoFilter === 'vibrant') return 'contrast(125%) saturate(140%) brightness(105%)';
    if (videoFilter === 'cyberpunk') return 'contrast(130%) hue-rotate(180deg) saturate(150%)';
    if (videoFilter === 'vintage') return 'sepia(45%) contrast(110%) brightness(95%)';
    if (videoFilter === 'bw') return 'grayscale(100%) contrast(120%)';
    return 'none';
  };

  const getSubtitleOverlayStyle = () => {
    let color = '#ffffff';
    let textShadow = '-2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 2px 2px 0 #000';
    let bg = 'transparent';

    if (fontColor === 'yellow') {
      color = '#facc15';
      textShadow = '-2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 2px 2px 0 #000, 0 4px 12px rgba(0,0,0,0.9)';
    } else if (fontColor === 'cyan') {
      color = '#38bdf8';
      textShadow = '0 0 14px #0284c7, -2px -2px 0 #000, 2px -2px 0 #000';
    } else if (fontColor === 'black_box') {
      color = '#ffffff';
      bg = 'rgba(0,0,0,0.85)';
      textShadow = 'none';
    }

    let posStyle = { bottom: '35px' };
    if (position === 'top') posStyle = { top: '60px' };
    if (position === 'middle') posStyle = { top: '50%', transform: 'translateY(-50%)' };

    return {
      position: 'absolute',
      left: '12px',
      right: '12px',
      textAlign: 'center',
      color: color,
      fontSize: `${Math.max(14, fontSize * 0.72)}px`,
      fontWeight: 800,
      fontFamily: fontFamily,
      textShadow: textShadow,
      background: bg,
      padding: bg !== 'transparent' ? '8px 12px' : '4px',
      borderRadius: '8px',
      zIndex: 10,
      lineHeight: 1.3,
      pointerEvents: 'none',
      ...posStyle
    };
  };

  // === RENDER CAPCUT FULL-SCREEN LOADING OVERLAY ===
  if (loadingAI) {
    return (
      <div style={{
        minHeight: '75vh', display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', textAlign: 'center',
        padding: '40px 20px', background: 'var(--bg-card)', borderRadius: '20px',
        border: '1px solid var(--border-color)', boxShadow: 'var(--shadow-card)'
      }}>
        <div style={{
          width: '80px', height: '80px', borderRadius: '50%',
          background: 'linear-gradient(135deg, var(--accent-cyan), var(--accent-purple))',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginBottom: '20px', boxShadow: '0 0 30px rgba(0, 242, 254, 0.4)',
          animation: 'pulse 1.8s infinite ease-in-out'
        }}>
          <Sparkles size={40} color="#fff" />
        </div>

        <h2 style={{ fontSize: '1.5rem', fontWeight: 800, marginBottom: '8px' }}>
          CapCut AI Auto-Clipper Studio
        </h2>
        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', maxWidth: '500px', marginBottom: '24px' }}>
          Sedang memproses video <strong style={{ color: '#fff' }}>"{video?.title}"</strong> menggunakan Gemini Pro/Flash AI & Transkrip Percakapan ASLI...
        </p>

        {/* Progress Bar */}
        <div style={{ width: '100%', maxWidth: '460px', background: 'rgba(255,255,255,0.06)', borderRadius: '10px', padding: '4px', marginBottom: '14px', border: '1px solid var(--border-color)' }}>
          <div style={{
            height: '10px', borderRadius: '8px',
            background: 'linear-gradient(90deg, var(--accent-cyan), var(--accent-blue), var(--accent-purple))',
            width: `${loadingProgress}%`, transition: 'width 0.4s ease'
          }} />
        </div>

        <div style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--accent-cyan)', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Loader2 size={16} className="animate-spin" />
          {loadingStepText}
        </div>
      </div>
    );
  }

  // === MAIN CAPCUT STUDIO EDITOR VIEW ===
  return (
    <div className="studio-page">
      {/* Studio Header Toolbar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h2 style={{ fontSize: '1.35rem', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Scissors size={22} style={{ color: 'var(--accent-cyan)' }} />
              CapCut Studio Editor (9:16 Shorts/TikTok)
            </h2>
            <span style={{
              fontSize: '0.72rem', fontWeight: 700, padding: '3px 10px', borderRadius: '12px',
              background: 'rgba(0,242,254,0.15)', border: '1px solid var(--accent-cyan)',
              color: 'var(--accent-cyan)', display: 'flex', alignItems: 'center', gap: '4px'
            }}>
              <Sparkles size={12} /> {aiMode}
            </span>
            {hasRealTranscript && (
              <span style={{
                fontSize: '0.7rem', fontWeight: 700, padding: '3px 8px', borderRadius: '12px',
                background: 'rgba(16,185,129,0.2)', border: '1px solid #10b981', color: '#10b981'
              }}>
                ✓ Subtitle Transkrip Asli
              </span>
            )}
          </div>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
            Video: <strong style={{ color: '#fff' }}>{video?.title || 'Video YouTube'}</strong>
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <button className="btn-secondary" onClick={autoAnalyzeVideo} style={{ fontSize: '0.8rem' }}>
            <RefreshCw size={14} /> Analisis Ulang AI
          </button>

          <button className="btn-secondary" onClick={() => handleExport('local')} disabled={exporting} style={{ fontSize: '0.8rem' }}>
            {exporting ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            Download Klip Lokal
          </button>

          <button
            className="btn-primary"
            onClick={() => handleExport('drive')}
            disabled={exporting}
            style={{ background: 'linear-gradient(135deg, #7f00ff, #e100ff)', fontSize: '0.8rem' }}
          >
            {exporting ? <Loader2 size={14} className="animate-spin" /> : <HardDriveUpload size={14} />}
            Upload ke Google Drive
          </button>
        </div>
      </div>

      {exportStatus && (
        <div style={{ padding: '12px 16px', background: 'rgba(0, 242, 254, 0.12)', border: '1px solid var(--accent-cyan)', borderRadius: '12px', color: 'var(--accent-cyan)', marginBottom: '16px', fontWeight: 600, fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <CheckCircle size={18} />
          {exportStatus}
        </div>
      )}

      {/* Clips Strip Carousel */}
      <div style={{ marginBottom: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
          <span style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Layers size={14} /> Relevansi Klip Berpotensi Viral ({clipList.length} klip)
          </span>
          <button className="btn-secondary" onClick={handleAddManualClip} style={{ padding: '4px 10px', fontSize: '0.75rem' }}>
            <Plus size={13} /> Tambah Klip Manual
          </button>
        </div>

        <div style={{ display: 'flex', gap: '10px', overflowX: 'auto', paddingBottom: '8px' }}>
          {clipList.map((clip, idx) => (
            <div
              key={idx}
              onClick={() => setSelectedClipIndex(idx)}
              style={{
                flex: '0 0 230px',
                padding: '12px',
                borderRadius: '12px',
                background: selectedClipIndex === idx ? 'rgba(0, 242, 254, 0.12)' : 'var(--bg-card)',
                border: selectedClipIndex === idx ? '2px solid var(--accent-cyan)' : '1px solid var(--border-color)',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px'
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontWeight: 800, fontSize: '0.82rem', color: selectedClipIndex === idx ? 'var(--accent-cyan)' : '#fff' }}>
                  Klip #{clip.clip_id || idx + 1} {clip.is_manual ? '(Manual)' : ''}
                </span>
                <span className="badge-virality" style={{ fontSize: '0.7rem' }}>
                  Viral: {clip.virality_score || 90}%
                </span>
              </div>

              <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#fff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {clip.hook_text || 'Highlight'}
              </div>

              <div style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)', fontWeight: 600 }}>
                ⏱️ {formatTime(clip.start_seconds)} - {formatTime(clip.end_seconds)} ({formatDurationHuman(Math.max(0, clip.end_seconds - clip.start_seconds))})
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Main Workspace Grid: Viewport Canvas + CapCut Multi-Tab Controls */}
      <div className="studio-container">
        {/* LEFT: Live Canvas Viewport Player */}
        <div className="studio-preview-box" style={{ padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%', marginBottom: '8px' }}>
            <span style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-secondary)' }}>
              Canvas Preview CapCut ({aspectRatio})
            </span>
            <span style={{ fontSize: '0.75rem', color: 'var(--accent-cyan)' }}>
              {isPlaying ? '▶️ Playing' : '⏸️ Paused'}
            </span>
          </div>

          <div
            className="preview-media-wrapper"
            style={{
              width: aspectRatio === '9:16' ? '240px' : aspectRatio === '1:1' ? '280px' : '100%',
              height: aspectRatio === '9:16' ? '420px' : aspectRatio === '1:1' ? '280px' : '240px',
              border: '2px solid var(--border-active)',
              borderRadius: '16px',
              overflow: 'hidden',
              background: '#000',
              position: 'relative',
              boxShadow: '0 10px 30px rgba(0,0,0,0.8)'
            }}
          >
            {renderedPreviewUrl ? (
              /* FFmpeg Final Rendered Preview Player */
              <video
                src={renderedPreviewUrl}
                controls
                autoPlay
                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
              />
            ) : (
              /* Interactive Live Source Player with Real-Time Subtitle, Filter, and Hook Overlay */
              <div style={{ width: '100%', height: '100%', position: 'relative' }}>
                {(localVideoUrl || video?.local_url || video?.url?.endsWith('.mp4')) ? (
                  <video
                    ref={videoRef}
                    src={localVideoUrl || video?.local_url || video?.url}
                    onTimeUpdate={handleTimeUpdate}
                    controls
                    style={{ width: '100%', height: '100%', objectFit: 'contain', filter: getFilterStyle() }}
                  />
                ) : (
                  <iframe
                    src={`https://www.youtube-nocookie.com/embed/${video?.id || 'dQw4w9WgXcQ'}?start=${Math.floor(startSec)}&end=${Math.floor(endSec)}&autoplay=0&enablejsapi=1&origin=http://localhost:5173`}
                    title="Clip Source Preview"
                    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                    allowFullScreen
                    referrerPolicy="strict-origin-when-cross-origin"
                    style={{ width: '100%', height: '100%', border: 'none', filter: getFilterStyle() }}
                  />
                )}

                {/* Top Hook Headline Overlay */}
                {hookText && (
                  <div style={{
                    position: 'absolute',
                    top: '14px',
                    left: '10px',
                    right: '10px',
                    textAlign: 'center',
                    background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.95), rgba(245, 158, 11, 0.95))',
                    color: '#fff',
                    fontWeight: 900,
                    fontSize: '0.82rem',
                    padding: '6px 10px',
                    borderRadius: '8px',
                    boxShadow: '0 4px 12px rgba(0,0,0,0.5)',
                    zIndex: 10,
                    pointerEvents: 'none'
                  }}>
                    {hookText}
                  </div>
                )}

                {/* Custom Branding Watermark */}
                {watermarkText && (
                  <div style={{
                    position: 'absolute',
                    top: '48px',
                    right: '12px',
                    fontSize: '0.72rem',
                    fontWeight: 800,
                    color: 'rgba(255,255,255,0.85)',
                    background: 'rgba(0,0,0,0.6)',
                    padding: '2px 8px',
                    borderRadius: '6px',
                    pointerEvents: 'none',
                    zIndex: 10
                  }}>
                    {watermarkText}
                  </div>
                )}

                {/* Active Subtitle Line Overlay Preview */}
                {activeSubtitleText && (
                  <div style={getSubtitleOverlayStyle()}>
                    {activeSubtitleText}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Render Preview Button */}
          <div style={{ marginTop: '14px', width: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
            <button
              onClick={handleGeneratePreview}
              disabled={renderingPreview}
              className="btn-primary"
              style={{ width: '100%', background: 'linear-gradient(135deg, var(--accent-cyan), var(--accent-blue))', fontSize: '0.85rem' }}
            >
              {renderingPreview ? (
                <>
                  <Loader2 size={16} className="animate-spin" /> Merender FFmpeg (9:16 + Subtitle)...
                </>
              ) : (
                <>
                  <Video size={16} /> Render Preview Video FFmpeg ({aspectRatio})
                </>
              )}
            </button>
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
              Render 9:16 + Subtitle Burned-In CapCut Frame
            </span>
          </div>
        </div>

        {/* RIGHT: CapCut Multi-Tab Controls Workspace */}
        <div className="studio-panel">
          {/* Workspace Tabs Header */}
          <div style={{ display: 'flex', gap: '4px', borderBottom: '1px solid var(--border-color)', paddingBottom: '8px', marginBottom: '12px', overflowX: 'auto' }}>
            {[
              ['trim', <Sliders size={13} />, 'Trim Waktu'],
              ['subtitles', <Type size={13} />, 'Subtitle'],
              ['style', <Monitor size={13} />, 'Gaya Teks'],
              ['filter', <Palette size={13} />, 'Filter Video'],
              ['clips', <Layers size={13} />, 'Klip']
            ].map(([tabKey, icon, label]) => (
              <button
                key={tabKey}
                onClick={() => setActiveTab(tabKey)}
                className={activeTab === tabKey ? 'btn-primary' : 'btn-secondary'}
                style={{ padding: '6px 10px', fontSize: '0.75rem', gap: '4px', whiteSpace: 'nowrap' }}
              >
                {icon} {label}
              </button>
            ))}
          </div>

          {/* TAB 1: TRIM & TIMELINE */}
          {activeTab === 'trim' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div className="panel-title">
                <Sliders size={16} /> Trim Waktu & Potong Klip (Split)
              </div>

              {/* Start & End Input Fields */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div style={{ background: 'rgba(30,41,59,0.5)', padding: '10px', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
                  <label style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                    Waktu Mulai (MM:SS)
                  </label>
                  <input
                    type="text"
                    value={formatTime(startSec)}
                    onChange={(e) => setStartSec(parseTimeString(e.target.value))}
                    style={{ width: '100%', padding: '6px 8px', background: 'rgba(15,23,42,0.8)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--accent-cyan)', fontWeight: 800, fontSize: '0.9rem' }}
                  />
                  <div style={{ display: 'flex', gap: '4px', marginTop: '6px' }}>
                    <button className="btn-secondary" onClick={() => adjustTime('start', -5)} style={{ flex: 1, padding: '3px', fontSize: '0.68rem' }}>-5s</button>
                    <button className="btn-secondary" onClick={() => adjustTime('start', -1)} style={{ flex: 1, padding: '3px', fontSize: '0.68rem' }}>-1s</button>
                    <button className="btn-secondary" onClick={() => adjustTime('start', 1)} style={{ flex: 1, padding: '3px', fontSize: '0.68rem' }}>+1s</button>
                    <button className="btn-secondary" onClick={() => adjustTime('start', 5)} style={{ flex: 1, padding: '3px', fontSize: '0.68rem' }}>+5s</button>
                  </div>
                </div>

                <div style={{ background: 'rgba(30,41,59,0.5)', padding: '10px', borderRadius: '10px', border: '1px solid var(--border-color)' }}>
                  <label style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                    Waktu Selesai (MM:SS)
                  </label>
                  <input
                    type="text"
                    value={formatTime(endSec)}
                    onChange={(e) => setEndSec(parseTimeString(e.target.value))}
                    style={{ width: '100%', padding: '6px 8px', background: 'rgba(15,23,42,0.8)', border: '1px solid var(--border-color)', borderRadius: '6px', color: 'var(--accent-cyan)', fontWeight: 800, fontSize: '0.9rem' }}
                  />
                  <div style={{ display: 'flex', gap: '4px', marginTop: '6px' }}>
                    <button className="btn-secondary" onClick={() => adjustTime('end', -5)} style={{ flex: 1, padding: '3px', fontSize: '0.68rem' }}>-5s</button>
                    <button className="btn-secondary" onClick={() => adjustTime('end', -1)} style={{ flex: 1, padding: '3px', fontSize: '0.68rem' }}>-1s</button>
                    <button className="btn-secondary" onClick={() => adjustTime('end', 1)} style={{ flex: 1, padding: '3px', fontSize: '0.68rem' }}>+1s</button>
                    <button className="btn-secondary" onClick={() => adjustTime('end', 5)} style={{ flex: 1, padding: '3px', fontSize: '0.68rem' }}>+5s</button>
                  </div>
                </div>
              </div>

              {/* Split Action Button */}
              <button
                className="btn-secondary"
                onClick={handleSplitClipAtPlayhead}
                style={{ width: '100%', justifyContent: 'center', fontSize: '0.8rem', gap: '6px', borderColor: 'var(--accent-cyan)', color: 'var(--accent-cyan)' }}
              >
                <Split size={14} /> Potong / Split Klip pada Posisi Waktu saat ini ({formatTime(currentTime)})
              </button>

              {/* Duration Info */}
              <div style={{ padding: '10px', background: 'rgba(0,242,254,0.08)', border: '1px solid rgba(0,242,254,0.2)', borderRadius: '8px', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                ⏱️ Durasi Klip: <strong style={{ color: 'var(--accent-cyan)' }}>{formatDurationHuman(Math.max(0, endSec - startSec))}</strong>
                <span style={{ color: 'var(--text-muted)', marginLeft: '8px' }}>({formatTime(startSec)} s/d {formatTime(endSec)})</span>
              </div>
            </div>
          )}

          {/* TAB 2: SUBTITLE EDITOR */}
          {activeTab === 'subtitles' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div className="panel-title" style={{ marginBottom: 0 }}>
                  <Type size={16} /> Subtitle ASLI Transkrip ({subtitles.length} baris)
                </div>
                <div style={{ display: 'flex', gap: '4px' }}>
                  <button className="btn-secondary" onClick={handleAutoDistributeSubtitles} style={{ fontSize: '0.7rem', padding: '4px 8px' }}>
                    <Wand2 size={12} /> Auto-Sync
                  </button>
                  <button className="btn-primary" onClick={handleAddSubtitleLine} style={{ fontSize: '0.7rem', padding: '4px 8px' }}>
                    <Plus size={12} /> + Line
                  </button>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '280px', overflowY: 'auto', paddingRight: '4px' }}>
                {subtitles.map((sub, i) => (
                  <div key={i} className="subtitle-item" style={{ background: 'rgba(30,41,59,0.6)', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <div style={{ display: 'flex', gap: '6px', alignItems: 'center', fontSize: '0.72rem', color: 'var(--accent-cyan)' }}>
                        <span>⏱️</span>
                        <input
                          type="text"
                          value={formatTime(sub.start)}
                          onChange={(e) => handleSubtitleChange(i, 'start', parseTimeString(e.target.value))}
                          style={{ width: '50px', background: 'none', border: '1px solid var(--border-color)', color: '#fff', borderRadius: '4px', fontSize: '0.72rem', padding: '2px 4px', textAlign: 'center' }}
                        />
                        <span>-</span>
                        <input
                          type="text"
                          value={formatTime(sub.end)}
                          onChange={(e) => handleSubtitleChange(i, 'end', parseTimeString(e.target.value))}
                          style={{ width: '50px', background: 'none', border: '1px solid var(--border-color)', color: '#fff', borderRadius: '4px', fontSize: '0.72rem', padding: '2px 4px', textAlign: 'center' }}
                        />
                      </div>
                      <button onClick={() => handleDeleteSubtitleLine(i)} style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer' }}>
                        <Trash2 size={13} />
                      </button>
                    </div>
                    <input
                      type="text"
                      className="subtitle-input"
                      value={sub.text}
                      onChange={(e) => handleSubtitleChange(i, 'text', e.target.value)}
                      placeholder="Caption..."
                      style={{ width: '100%', padding: '6px 8px', background: 'rgba(15,23,42,0.8)', border: '1px solid var(--border-color)', borderRadius: '6px', color: '#fff', fontSize: '0.82rem' }}
                    />
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 3: STYLE & CANVAS */}
          {activeTab === 'style' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div className="panel-title">
                <Monitor size={16} /> Gaya Subtitle & Canvas Frame
              </div>

              {/* Hook Header & Watermark */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div>
                  <label style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                    🔥 Banner Hook Atas
                  </label>
                  <input
                    type="text"
                    value={hookText}
                    onChange={(e) => setHookText(e.target.value)}
                    placeholder="Contoh: 🔥 PERNYATAAN VIRAL!"
                    style={{ width: '100%', padding: '6px 8px', background: 'rgba(30,41,59,0.8)', border: '1px solid var(--border-color)', borderRadius: '6px', color: '#fff', fontSize: '0.8rem' }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                    🏷️ Watermark Channel
                  </label>
                  <input
                    type="text"
                    value={watermarkText}
                    onChange={(e) => setWatermarkText(e.target.value)}
                    placeholder="@nama_channel"
                    style={{ width: '100%', padding: '6px 8px', background: 'rgba(30,41,59,0.8)', border: '1px solid var(--border-color)', borderRadius: '6px', color: '#fff', fontSize: '0.8rem' }}
                  />
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                <div>
                  <label style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                    Format Canvas
                  </label>
                  <select
                    value={aspectRatio}
                    onChange={(e) => setAspectRatio(e.target.value)}
                    style={{ width: '100%', padding: '6px 8px', background: 'rgba(30,41,59,0.8)', border: '1px solid var(--border-color)', borderRadius: '6px', color: '#fff', fontSize: '0.8rem' }}
                  >
                    <option value="9:16">9:16 Vertikal (Shorts/TikTok)</option>
                    <option value="16:9">16:9 Widescreen Original</option>
                    <option value="1:1">1:1 Square (Instagram)</option>
                    <option value="4:5">4:5 Portrait Feed</option>
                  </select>
                </div>

                <div>
                  <label style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                    Warna Subtitle CapCut
                  </label>
                  <select
                    value={fontColor}
                    onChange={(e) => setFontColor(e.target.value)}
                    style={{ width: '100%', padding: '6px 8px', background: 'rgba(30,41,59,0.8)', border: '1px solid var(--border-color)', borderRadius: '6px', color: '#fff', fontSize: '0.8rem' }}
                  >
                    <option value="yellow">🟨 Kuning Neon (CapCut Classic)</option>
                    <option value="white">⬜ Putih Bold (TikTok Style)</option>
                    <option value="cyan">🟦 Syan Glow (Cyber Style)</option>
                    <option value="black_box">⬛ Black Box Highlight</option>
                  </select>
                </div>

                <div>
                  <label style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                    Posisi Subtitle
                  </label>
                  <select
                    value={position}
                    onChange={(e) => setPosition(e.target.value)}
                    style={{ width: '100%', padding: '6px 8px', background: 'rgba(30,41,59,0.8)', border: '1px solid var(--border-color)', borderRadius: '6px', color: '#fff', fontSize: '0.8rem' }}
                  >
                    <option value="bottom">Bawah Standard</option>
                    <option value="middle">Tengah Frame</option>
                    <option value="top">Atas (Bawah Hook)</option>
                  </select>
                </div>

                <div>
                  <label style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', display: 'block', marginBottom: '4px' }}>
                    Kapitalisasi Teks
                  </label>
                  <select
                    value={textTransform}
                    onChange={(e) => setTextTransform(e.target.value)}
                    style={{ width: '100%', padding: '6px 8px', background: 'rgba(30,41,59,0.8)', border: '1px solid var(--border-color)', borderRadius: '6px', color: '#fff', fontSize: '0.8rem' }}
                  >
                    <option value="none">Sesuai Transkrip</option>
                    <option value="uppercase">HURUF BESAR (UPPERCASE)</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: FILTER VIDEO */}
          {activeTab === 'filter' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div className="panel-title">
                <Palette size={16} /> Filter & Color Grading Video CapCut
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                {[
                  ['normal', 'Normal Original', '#00f2fe'],
                  ['vibrant', 'Vibrant Boost (CapCut Pop)', '#f59e0b'],
                  ['cyberpunk', 'Cyberpunk Glow', '#ec4899'],
                  ['vintage', 'Vintage Sepia', '#d97706'],
                  ['bw', 'Monochrome B&W', '#94a3b8']
                ].map(([fKey, fName, fColor]) => (
                  <button
                    key={fKey}
                    onClick={() => setVideoFilter(fKey)}
                    style={{
                      padding: '10px', borderRadius: '8px', cursor: 'pointer', fontWeight: 700, fontSize: '0.78rem',
                      border: videoFilter === fKey ? `2px solid ${fColor}` : '1px solid var(--border-color)',
                      background: videoFilter === fKey ? `${fColor}18` : 'rgba(30,41,59,0.6)',
                      color: videoFilter === fKey ? fColor : 'var(--text-primary)',
                      textAlign: 'left', display: 'flex', alignItems: 'center', justifyContent: 'space-between'
                    }}
                  >
                    {fName}
                    {videoFilter === fKey && <Check size={14} />}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* TAB 5: KLIP MANAGEMENT */}
          {activeTab === 'clips' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div className="panel-title">
                <Layers size={16} /> Manajemen Klip
              </div>

              <div style={{ display: 'flex', gap: '8px' }}>
                <button className="btn-primary" onClick={handleAddManualClip} style={{ flex: 1, fontSize: '0.78rem' }}>
                  <Plus size={14} /> Klip Baru
                </button>
                <button className="btn-secondary" onClick={handleDuplicateClip} style={{ flex: 1, fontSize: '0.78rem' }}>
                  <Copy size={14} /> Duplikat Klip
                </button>
                <button className="btn-secondary" onClick={() => handleDeleteClip(selectedClipIndex)} style={{ color: '#ef4444', borderColor: 'rgba(239,68,68,0.3)', fontSize: '0.78rem' }}>
                  <Trash2 size={14} /> Hapus
                </button>
              </div>

              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', lineHeight: 1.5, marginTop: '8px' }}>
                💡 <strong>Transkrip Percakapan ASLI:</strong> OmniClip AI mengekstrak perkataan asli pembicara dari YouTube, memilih momen yang paling berpotensi viral via Gemini Pro/Flash AI, dan menyusun timestamp subtitle secara akurat.
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
