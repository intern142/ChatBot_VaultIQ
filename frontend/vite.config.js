import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/__tests__/setup.js',
    include: ['src/**/*.test.{js,jsx,ts,tsx}'],
    globals: true,
  },
})