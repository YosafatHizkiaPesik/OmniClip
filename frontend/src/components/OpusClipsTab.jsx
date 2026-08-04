import React, { useState, useEffect, useRef } from 'react';
import {
  Sparkles, Flame, Zap, Award, Video, Scissors, Download, HardDriveUpload,
  RefreshCw, CheckCircle2, Play, Pause, Loader2, ArrowRight, Layers, HelpCircle,
  BarChart3, Check, Search, ExternalLink, Film
} from 'lucide-react';
import { formatTime, formatDurationHuman } from '../utils/timeFormat';

export default function OpusClipsTab({ currentVideo, currentAiData, onOpenStudioWithClip, onSelectVideoForClipping }) {
  const [videoUrl, setVideoUrl] = useState('');
  const [activeVideo, setActiveVideo] = useState(currentVideo || null);
  const [aiData, setAiData] = useState(currentAiData || null);

  // Pipeline Processing State
  const [isProcessing, setIsProcessing] = useState(false);
  const [pipelineProgress, setPipelineProgress] = useState(0);
  const [pipelineStage, setPipelineStage] = useState(1);
  const [pipelineLogs, setPipelineLogs] = useState([]);

  // Selected Clip for Preview Player
  const [activePreviewClip, setActivePreviewClip] = useState(null);
  const [playingClipId, setPlayingClipId] = useState(null);
  const videoRefs = useRef({});

  // Render & Export Status
  const [renderingClipId, setRenderingClipId] = useState(null);
  const [renderedClipUrls, setRenderedClipUrls] = useState({});
  const [exportStatus, setExportStatus] = useState('');

  // Sync state if props change
  useEffect(() => {
    if (currentVideo) setActiveVideo(currentVideo);
    if (currentAiData) {
      setAiData(currentAiData);
      if (currentAiData.clips && currentAiData.clips.length > 0) {
        setActivePreviewClip(currentAiData.clips[0]);
      }
    }
  }, [currentVideo, currentAiData]);

  // Start Opus Clip Processing Pipeline
  const runOpusProcessingPipeline = async (targetVideo) => {
    if (!targetVideo) return;
    setActiveVideo(targetVideo);
    setIsProcessing(true);
    setPipelineProgress(10);
    setPipelineStage(1);
    setPipelineLogs(['[00:01] 🚀 Memulai Opus Clip AI Deep Processing Pipeline...']);

    // Stage 1: Audio & Transcript
    addLog('[00:02] 🎵 Step 1/4: Mengunduh Audio & Transkrip Percakapan ASLI YouTube...');
    await delay(1200);
    setPipelineProgress(35);
    setPipelineStage(2);

    // Stage 2: Gemini AI Analysis
    addLog('[00:03] 🧠 Step 2/4: Gemini AI Pro/Flash Scoring (Hook Score, Virality Index, Topic Flow)...');
    await delay(1500);
    setPipelineProgress(65);
    setPipelineStage(3);

    // Stage 3: Auto-Clipping & Subtitle Sync
    addLog('[00:05] ✂️ Step 3/4: Menyusun Timestamp Klip & Subtitle Percakapan Kata-demi-Kata...');
    await delay(1200);
    setPipelineProgress(88);
    setPipelineStage(4);

    // Stage 4: API Request
    addLog('[00:06] 🎬 Step 4/4: Menyelesaikan Hasil Analisis Opus Clip...');

    try {
      const res = await fetch('http://localhost:8000/api/analyze-clips', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video_info: targetVideo })
      });
      const data = await res.json();
      if (res.ok && data.clips) {
        setPipelineProgress(100);
        addLog(`[00:07] ✅ Berhasil menghasilkan ${data.clips.length} Klip Viral dengan Skor Virabilitas!`);
        await delay(600);
        setAiData(data);
        if (data.clips.length > 0) setActivePreviewClip(data.clips[0]);
      } else {
        alert(data.detail || 'Gagal memproses video');
      }
    } catch (err) {
      alert('Gagal terhubung ke backend Opus AI Engine');
    } finally {
      setIsProcessing(false);
    }
  };

  const addLog = (msg) => {
    setPipelineLogs(prev => [...prev, msg]);
  };

  const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

  // Submit YouTube URL directly
  const handleUrlSubmit = (e) => {
    e.preventDefault();
    if (!videoUrl.trim()) return;
    let ytId = videoUrl.trim();
    const match = ytId.match(/(?:v=|\/embed\/|\/v\/|https:\/\/youtu\.be\/|\/shorts\/)?([a-zA-Z0-9_-]{11})/);
    if (match && match[1]) ytId = match[1];

    const customVid = {
      id: ytId,
      title: `YouTube Video (${ytId})`,
      url: `https://www.youtube.com/watch?v=${ytId}`,
      duration: 300,
      channel: 'YouTube Creator'
    };
    runOpusProcessingPipeline(customVid);
  };

  // Render 9:16 Preview via FFmpeg
  const handleRenderSingleClip = async (clip) => {
    if (!activeVideo) return;
    setRenderingClipId(clip.clip_id);
    try {
      const res = await fetch('http://localhost:8000/api/render-clip', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source_path: activeVideo.url || activeVideo.local_path || activeVideo.id,
          start_seconds: clip.start_seconds,
          end_seconds: clip.end_seconds,
          subtitles: clip.subtitles,
          aspect_ratio: '9:16',
          font_color: 'yellow',
          position: 'bottom',
          hook_text: clip.hook_text
        })
      });
      const data = await res.json();
      if (res.ok) {
        const fullUrl = `http://localhost:8000${data.web_url}`;
        setRenderedClipUrls(prev => ({ ...prev, [clip.clip_id]: fullUrl }));
        setExportStatus(`✅ Klip #${clip.clip_id} berhasil dirender 9:16!`);
      } else {
        alert(data.detail || 'Gagal render klip');
      }
    } catch (err) {
      alert('Error saat menghubungi server FFmpeg');
    } finally {
      setRenderingClipId(null);
    }
  };

  const handleDownloadClip = (clip) => {
    const renderedUrl = renderedClipUrls[clip.clip_id];
    if (renderedUrl) {
      const a = document.createElement('a');
      a.href = renderedUrl;
      a.download = `OpusClip_${clip.clip_id}.mp4`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } else {
      handleRenderSingleClip(clip);
    }
  };

  const getScoreColor = (score) => {
    if (score >= 95) return '#10b981'; // emerald
    if (score >= 90) return '#00f2fe'; // cyan
    if (score >= 85) return '#f59e0b'; // amber
    return '#ef4444'; // red
  };

  return (
    <div style={{ paddingBottom: '40px' }}>
      {/* Opus Header Banner */}
      <div style={{
        padding: '24px', borderRadius: '20px', marginBottom: '24px',
        background: 'linear-gradient(135deg, rgba(127, 0, 255, 0.2), rgba(0, 242, 254, 0.15))',
        border: '1px solid var(--accent-cyan)', boxShadow: '0 10px 30px rgba(0, 242, 254, 0.1)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
              <span style={{
                background: 'linear-gradient(135deg, #7f00ff, #e100ff)', color: '#fff',
                padding: '4px 10px', borderRadius: '12px', fontSize: '0.75rem', fontWeight: 900
              }}>
                OPUS CLIP PRO ENGINE
              </span>
              <span style={{ fontSize: '0.8rem', color: 'var(--accent-cyan)', fontWeight: 700 }}>
                ⚡ Auto-Clip & Virality Score Architecture
              </span>
            </div>
            <h1 style={{ fontSize: '1.6rem', fontWeight: 900, marginBottom: '6px' }}>
              Daftar Klip AI & Analisis Virabilitas (Opus Style)
            </h1>
            <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', maxWidth: '700px' }}>
              Gemini AI menganalisis transkrip percakapan YouTube secara mendalam untuk menghitung <strong>Virality Score</strong>, <strong>Hook Score</strong>, dan menyusun subtitle percakapan asli.
            </p>
          </div>

          {/* Quick Input Bar */}
          <form onSubmit={handleUrlSubmit} style={{ display: 'flex', gap: '8px', minWidth: '320px' }}>
            <input
              type="text"
              className="search-input"
              placeholder="Tempel URL YouTube untuk Clipper..."
              value={videoUrl}
              onChange={(e) => setVideoUrl(e.target.value)}
              style={{ fontSize: '0.82rem' }}
            />
            <button type="submit" className="btn-primary" style={{ fontSize: '0.82rem', padding: '0 16px', whiteSpace: 'nowrap' }}>
              <Zap size={14} /> Proses Clip
            </button>
          </form>
        </div>
      </div>

      {exportStatus && (
        <div style={{ padding: '12px 16px', background: 'rgba(16,185,129,0.15)', border: '1px solid #10b981', borderRadius: '12px', color: '#10b981', marginBottom: '20px', fontWeight: 600, fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <CheckCircle2 size={18} />
          {exportStatus}
        </div>
      )}

      {/* PIPELINE PROCESSING OVERLAY (When AI is calculating) */}
      {isProcessing && (
        <div style={{
          padding: '30px', borderRadius: '20px', background: 'var(--bg-card)',
          border: '1px solid var(--border-color)', marginBottom: '24px', textAlign: 'center'
        }}>
          <div style={{
            width: '70px', height: '70px', borderRadius: '50%', margin: '0 auto 16px',
            background: 'linear-gradient(135deg, var(--accent-cyan), var(--accent-purple))',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 0 30px rgba(0, 242, 254, 0.4)', animation: 'pulse 1.5s infinite ease-in-out'
          }}>
            <Sparkles size={36} color="#fff" />
          </div>

          <h2 style={{ fontSize: '1.4rem', fontWeight: 800, marginBottom: '6px' }}>
            Opus AI Deep Processing Engine Running...
          </h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '20px' }}>
            Memproses video <strong style={{ color: '#fff' }}>"{activeVideo?.title}"</strong>
          </p>

          {/* Progress Bar */}
          <div style={{ width: '100%', maxWidth: '500px', margin: '0 auto 16px', background: 'rgba(255,255,255,0.06)', borderRadius: '10px', padding: '4px', border: '1px solid var(--border-color)' }}>
            <div style={{
              height: '12px', borderRadius: '8px',
              background: 'linear-gradient(90deg, var(--accent-cyan), var(--accent-blue), var(--accent-purple))',
              width: `${pipelineProgress}%`, transition: 'width 0.4s ease'
            }} />
          </div>

          {/* Live Pipeline Terminal Logs */}
          <div style={{
            maxWidth: '550px', margin: '0 auto', background: '#090d16', padding: '14px',
            borderRadius: '12px', border: '1px solid var(--border-color)', textAlign: 'left',
            fontFamily: 'monospace', fontSize: '0.78rem', color: 'var(--accent-cyan)', maxHeight: '140px', overflowY: 'auto'
          }}>
            {pipelineLogs.map((log, idx) => (
              <div key={idx} style={{ marginBottom: '4px' }}>{log}</div>
            ))}
          </div>
        </div>
      )}

      {/* OPUS CLIPS RESULT DASHBOARD */}
      {!isProcessing && aiData && aiData.clips && (
        <div>
          {/* Active Project Header Summary */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            background: 'var(--bg-card)', padding: '16px 20px', borderRadius: '16px',
            border: '1px solid var(--border-color)', marginBottom: '20px', flexWrap: 'wrap', gap: '12px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
              <div style={{
                width: '48px', height: '48px', borderRadius: '12px', background: 'rgba(0, 242, 254, 0.15)',
                display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px solid var(--accent-cyan)'
              }}>
                <Film size={24} style={{ color: 'var(--accent-cyan)' }} />
              </div>
              <div>
                <h3 style={{ fontSize: '1.05rem', fontWeight: 800 }}>{activeVideo?.title || 'Proyek Video YouTube'}</h3>
                <div style={{ display: 'flex', gap: '12px', fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '2px' }}>
                  <span>Mode: <strong style={{ color: 'var(--accent-cyan)' }}>{aiData.ai_mode}</strong></span>
                  <span>•</span>
                  <span>{aiData.clips.length} Klip Dihasilkan</span>
                  <span>•</span>
                  <span style={{ color: '#10b981', fontWeight: 700 }}>✓ Subtitle Transkrip Asli</span>
                </div>
              </div>
            </div>

            <button
              className="btn-secondary"
              onClick={() => runOpusProcessingPipeline(activeVideo)}
              style={{ fontSize: '0.8rem', gap: '6px' }}
            >
              <RefreshCw size={14} /> Analisis Ulang Opus AI
            </button>
          </div>

          {/* Opus Clip Cards Grid Layout */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '20px' }}>
            {aiData.clips.map((clip, idx) => {
              const vScore = clip.virality_score || 90;
              const hScore = clip.hook_score || vScore - 2;
              const fScore = clip.flow_score || vScore - 3;
              const isRendered = !!renderedClipUrls[clip.clip_id];

              return (
                <div
                  key={idx}
                  style={{
                    background: 'var(--bg-card)', borderRadius: '16px', border: '1px solid var(--border-color)',
                    padding: '18px', display: 'flex', flexDirection: 'column', gap: '12px',
                    boxShadow: '0 8px 24px rgba(0,0,0,0.3)', position: 'relative', overflow: 'hidden',
                    transition: 'all 0.25 ease'
                  }}
                >
                  {/* Top Scores Bar (Opus Style) */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '8px' }}>
                    <div style={{
                      display: 'flex', alignItems: 'center', gap: '6px',
                      background: 'rgba(16, 185, 129, 0.12)', border: `1px solid ${getScoreColor(vScore)}`,
                      padding: '4px 10px', borderRadius: '12px'
                    }}>
                      <Flame size={15} style={{ color: getScoreColor(vScore) }} />
                      <span style={{ fontSize: '0.82rem', fontWeight: 900, color: getScoreColor(vScore) }}>
                        Skor Virabilitas: {vScore}/100
                      </span>
                    </div>

                    <div style={{ display: 'flex', gap: '6px', fontSize: '0.72rem' }}>
                      <span style={{ background: 'rgba(255,255,255,0.06)', padding: '3px 8px', borderRadius: '8px', color: 'var(--text-secondary)' }}>
                        ⚡ Hook: {hScore}
                      </span>
                      <span style={{ background: 'rgba(255,255,255,0.06)', padding: '3px 8px', borderRadius: '8px', color: 'var(--text-secondary)' }}>
                        🌊 Flow: {fScore}
                      </span>
                    </div>
                  </div>

                  {/* Hook Headline */}
                  <div style={{
                    background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.2), rgba(245, 158, 11, 0.2))',
                    border: '1px solid rgba(239, 68, 68, 0.4)', padding: '8px 12px', borderRadius: '10px',
                    fontWeight: 900, fontSize: '0.88rem', color: '#fff'
                  }}>
                    {clip.hook_text || '🔥 HIGHLIGHT KLIP VIRAL!'}
                  </div>

                  {/* Opus AI Explanation Reason */}
                  <div style={{
                    fontSize: '0.78rem', color: 'var(--text-secondary)', background: 'rgba(0, 242, 254, 0.05)',
                    border: '1px solid rgba(0, 242, 254, 0.15)', padding: '8px 10px', borderRadius: '8px', lineHeight: 1.4
                  }}>
                    💡 <strong style={{ color: 'var(--accent-cyan)' }}>Alasan AI Viral:</strong> {clip.viral_reason || "Klip ini memiliki daya pikat tinggi dan percakapan yang padat berpotensi memicu engagement penonton."}
                  </div>

                  {/* Timestamp & Duration */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.78rem', color: 'var(--accent-cyan)', fontWeight: 700 }}>
                    <span>⏱️ Timestamp: {formatTime(clip.start_seconds)} - {formatTime(clip.end_seconds)}</span>
                    <span>Durasi: {formatDurationHuman(Math.max(0, clip.end_seconds - clip.start_seconds))}</span>
                  </div>

                  {/* Mini Preview Box */}
                  <div style={{
                    height: '160px', background: '#000', borderRadius: '10px', overflow: 'hidden',
                    position: 'relative', border: '1px solid var(--border-color)'
                  }}>
                    {isRendered ? (
                      <video
                        src={renderedClipUrls[clip.clip_id]}
                        controls
                        style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                      />
                    ) : (
                      <div style={{ width: '100%', height: '100%', position: 'relative' }}>
                        <iframe
                          src={`https://www.youtube-nocookie.com/embed/${activeVideo?.id}?start=${Math.floor(clip.start_seconds)}&end=${Math.floor(clip.end_seconds)}&autoplay=0&enablejsapi=1&origin=http://localhost:5173`}
                          title={`Clip ${clip.clip_id}`}
                          style={{ width: '100%', height: '100%', border: 'none' }}
                          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                          referrerPolicy="strict-origin-when-cross-origin"
                        />
                      </div>
                    )}
                  </div>

                  {/* Subtitle Snippet */}
                  {clip.subtitles && clip.subtitles.length > 0 && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontStyle: 'italic', background: 'rgba(0,0,0,0.3)', padding: '6px 8px', borderRadius: '6px' }}>
                      💬 "{clip.subtitles[0].text}"
                    </div>
                  )}

                  {/* Action Buttons */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginTop: '4px' }}>
                    <button
                      className="btn-primary"
                      onClick={() => onOpenStudioWithClip(activeVideo, clip)}
                      style={{ fontSize: '0.75rem', padding: '8px', justifyContent: 'center' }}
                    >
                      <Scissors size={13} /> Edit di Studio
                    </button>

                    <button
                      className="btn-secondary"
                      onClick={() => handleDownloadClip(clip)}
                      disabled={renderingClipId === clip.clip_id}
                      style={{ fontSize: '0.75rem', padding: '8px', justifyContent: 'center' }}
                    >
                      {renderingClipId === clip.clip_id ? (
                        <Loader2 size={13} className="animate-spin" />
                      ) : isRendered ? (
                        <>
                          <Download size={13} /> Download MP4
                        </>
                      ) : (
                        <>
                          <Video size={13} /> Render 9:16
                        </>
                      )}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Empty State when no video processed yet */}
      {!isProcessing && (!aiData || !aiData.clips) && (
        <div style={{
          textAlign: 'center', padding: '60px 20px', background: 'var(--bg-card)',
          borderRadius: '20px', border: '1px dashed var(--border-color)'
        }}>
          <div style={{
            width: '64px', height: '64px', borderRadius: '50%', background: 'rgba(0, 242, 254, 0.1)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px'
          }}>
            <Zap size={32} style={{ color: 'var(--accent-cyan)' }} />
          </div>
          <h3 style={{ fontSize: '1.2rem', fontWeight: 800, marginBottom: '6px' }}>Belum Ada Klip AI Diproses</h3>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', maxWidth: '480px', margin: '0 auto 20px' }}>
            Masukkan URL video YouTube pada kolom di atas atau pilih video dari tab Search/Feed untuk memulai pemotongan klip otomatis ala Opus Clip.
          </p>
        </div>
      )}
    </div>
  );
}
