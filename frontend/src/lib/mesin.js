/**
 * Nama mesin pemilih klip untuk ditampilkan (`engine` di hasil analisis).
 *
 * Sejak 17 Oktober 2026 pemilihnya bisa koneksi AI mana pun (backend
 * services/koneksi_ai.py); `heuristic` tetap berarti mesin lokal tanpa AI.
 */
import { t as tr } from './i18n';

const NAMA = {
  gemini: 'Gemini', openrouter: 'OpenRouter', anthropic: 'Claude', openai: 'OpenAI',
  groq: 'Groq', mistral: 'Mistral', deepseek: 'DeepSeek', cerebras: 'Cerebras',
};

export function namaMesin(engine, model) {
  if (engine === 'lokal') return tr('koneksi.p_lokal') + (model ? ` (${model})` : '');
  if (engine === 'kustom') return tr('mesin.kustom') + (model ? ` (${model})` : '');
  if (NAMA[engine]) return NAMA[engine] + (model ? ` (${model})` : '');
  return tr('partitur.mesin_lokal');
}
