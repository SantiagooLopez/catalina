import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig(({mode}) => {
  const env = loadEnv(mode, process.cwd(), '');
  return {
    plugins: [react()],
    server: {port: 5173, strictPort: true, proxy: {
      '/api': { target: env.CATALINA_API_TARGET || 'https://192.168.20.140', changeOrigin: true,
        secure: env.CATALINA_ALLOW_SELF_SIGNED !== 'true', proxyTimeout: 240000, timeout: 240000 }
    }}
  };
});
