import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  // eslint-disable-next-line no-undef
  const env = loadEnv(mode, process.cwd(), '')
  const isDemo = mode === 'demo'

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },
    // Demo 模式部署到 GitHub Pages 的 /silver-guardian-v2/demo/ 路径下
    base: isDemo ? '/silver-guardian-v2/demo/' : '/',
    // Demo 模式输出到 docs/demo 目录（匹配 base 路径 /demo/）
    build: isDemo ? {
      outDir: '../docs/demo',
      emptyOutDir: true
    } : undefined,
    server: {
      proxy: {
        '^/api': {
          target: env.VITE_API_URL || 'http://api:5050',
          changeOrigin: true
        }
      },
      watch: {
        usePolling: true,
        ignored: ['**/node_modules/**', '**/dist/**'],
      },
      // 同时监听 IPv4 与 IPv6：Windows 上 localhost 常被解析成 ::1，
      // 而隧道工具（如 open-tunnel/serveo）用 localhost 作为转发目标时会连不上纯 IPv4 的监听。
      host: '::',
      // 允许内网穿透域名访问开发服务器，否则 Vite 会以 "Blocked request" 拦截。
      // 只放通后缀，具体子域名每次连接都会变。
      allowedHosts: ['.serveousercontent.com', '.serveo.net'],
    },
    // 生产构建预览：内网穿透时建议用 preview 而不是 dev server。
    // dev 模式会把依赖打成体积很大的单文件，serveo 的 HTTP/2 会报 ERR_HTTP2_PROTOCOL_ERROR 导致白屏；
    // 构建产物是分块压缩的静态文件，体积小得多，也更接近真实部署形态。
    preview: {
      proxy: {
        '^/api': {
          target: env.VITE_API_URL || 'http://127.0.0.1:5050',
          changeOrigin: true
        }
      },
      host: '::',
      port: 4173,
      allowedHosts: ['.serveousercontent.com', '.serveo.net'],
    }
  }
})
