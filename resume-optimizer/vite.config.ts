import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    // Critical for proper module loading
    assetsInlineLimit: 4096,
    rollupOptions: {
      output: {
        // This helps with module loading
        format: 'es',
        // Proper file naming
        chunkFileNames: 'assets/[name]-[hash].js',
        entryFileNames: 'assets/[name]-[hash].js',
      },
    },
  },
  // Ensure proper base path
  base: './',
  // Optimize dependencies
  optimizeDeps: {
    include: ['react', 'react-dom'],
  },
})