import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'assets',
    emptyOutDir: false,
    rollupOptions: {
      input: path.resolve(import.meta.dirname, 'src/main.jsx'),
      output: {
        format: 'iife',
        name: 'JasvaApp',
        entryFileNames: 'app.js',
        assetFileNames: '[name].[ext]'
      }
    }
  }
})
