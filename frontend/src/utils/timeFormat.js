/**
 * Utility untuk konversi timestamp dari detik ke format Jam:Menit:Detik (HH:MM:SS / MM:SS)
 */

export function formatTime(totalSeconds) {
  if (totalSeconds === undefined || totalSeconds === null || isNaN(totalSeconds)) {
    return '00:00';
  }
  const secs = Math.floor(Math.abs(totalSeconds));
  const hours = Math.floor(secs / 3600);
  const minutes = Math.floor((secs % 3600) / 60);
  const seconds = secs % 60;

  if (hours > 0) {
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  }
  return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
}

export function parseTimeString(timeStr) {
  if (!timeStr || typeof timeStr !== 'string') return 0;
  const parts = timeStr.trim().split(':').map(Number);
  if (parts.some(isNaN)) return 0;

  if (parts.length === 3) {
    return parts[0] * 3600 + parts[1] * 60 + parts[2];
  } else if (parts.length === 2) {
    return parts[0] * 60 + parts[1];
  } else if (parts.length === 1) {
    return parts[0];
  }
  return 0;
}

export function formatDurationHuman(seconds) {
  if (!seconds || isNaN(seconds)) return '0s';
  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  if (hrs > 0) {
    return `${hrs} jam ${mins} mnt`;
  }
  if (mins > 0) {
    return `${mins} mnt ${secs} dtk`;
  }
  return `${secs} dtk`;
}

/**
 * Waktu dengan pecahan detik, untuk penggaris linimasa yang diperbesar.
 *
 * `formatTime` membulatkan ke detik penuh. Pada perbesaran tinggi seluruh
 * penggaris lalu membaca "00:12" berulang-ulang di sepuluh tanda berturut-turut
 * — angka yang benar dan sama sekali tidak berguna, karena yang sedang dicari
 * justru letak di dalam detik itu.
 */
export function formatTimeFine(totalSeconds, decimals = 1) {
  if (totalSeconds === undefined || totalSeconds === null || isNaN(totalSeconds)) {
    return decimals > 0 ? `00:00.${'0'.repeat(decimals)}` : '00:00';
  }
  if (decimals <= 0) return formatTime(totalSeconds);
  const t = Math.abs(totalSeconds);
  const whole = Math.floor(t);
  const frac = (t - whole).toFixed(decimals).slice(1);   // ".25"
  return `${formatTime(whole)}${frac}`;
}
