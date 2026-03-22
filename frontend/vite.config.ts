import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: '/',
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/webhook': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/logout': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
  },
})
