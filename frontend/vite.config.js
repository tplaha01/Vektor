import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { 
    port: 9000, 
    host: '127.0.0.1',
    // Disable HMR in production for better latency
    hmr: process.env.NODE_ENV === 'production' ? false : true,
    // Increase max request body
    middlewareMode: false,
  },
  build: {
    // Code splitting for faster first load
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (id.includes('node_modules')) {
            if (id.includes('react')) return 'vendor-react';
            return 'vendor';
          }
        }
      }
    },
    // Minify + compress
    minify: 'terser',
    terserOptions: {
      compress: {
        drop_console: true,
      }
    },
    // Enable source maps for debugging
    sourcemap: false,
  },
  // Optimize dependencies
  optimizeDeps: {
    include: ['react', 'react-dom'],
  }
})

