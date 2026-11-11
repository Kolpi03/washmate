import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const target = process.env.API_TARGET || 'http://127.0.0.1:5000'
const proxy = { '/api': { target, changeOrigin: false } }

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy },
  preview: { port: 4173, proxy },
  build: { outDir: 'dist', sourcemap: false },
})
