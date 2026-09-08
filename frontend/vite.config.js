import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // strictPort penting: tanpa ini Vite diam-diam pindah ke 5174 saat 5173
    // terpakai, sementara backend hanya mengizinkan CORS untuk 5173 — gejalanya
    // adalah request yang gagal tanpa penjelasan.
    strictPort: true,
    proxy: {
      // Semua panggilan API relatif (/api/...) diteruskan ke backend, sehingga
      // tidak ada satupun URL backend yang perlu di-hardcode di kode frontend.
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
  },
})
