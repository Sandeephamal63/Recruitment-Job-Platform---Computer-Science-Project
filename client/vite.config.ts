import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";
import path from "path";

export default defineConfig(({ mode }) => {
  const proxyTarget =
    loadEnv(mode, process.cwd(), "VITE_").VITE_PROXY_TARGET ?? "http://localhost:5000";

  return {
    plugins: [react()],
    resolve: {
      extensions: ['.mjs', '.js', '.ts', '.jsx', '.tsx', '.json'],
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      host: true,
      port: 5173,
      allowedHosts: [".trycloudflare.com"],
      proxy: {
        "/api": {
          target: proxyTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
