import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import Components from 'unplugin-vue-components/vite'
import { AntDesignVueResolver } from 'unplugin-vue-components/resolvers'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig(({ mode }) => {
  // eslint-disable-next-line no-undef
  const env = loadEnv(mode, process.cwd(), '')
  const isDemo = mode === 'demo'

  return {
    plugins: [
      vue(),
      // Antd 组件按需引入：模板中的 a-* 组件由 resolver 自动转换为具名导入；
      // ant-design-vue 4.x 样式为 cssinjs 运行时注入，importStyle 无需开启
      Components({
        resolvers: [AntDesignVueResolver({ importStyle: false })],
        dts: false
      }),
      // PWA：断网可用 + 可“安装”到桌面/手机主屏。
      // 清单与服务工作线程都由插件生成，路径随 base 自动变化（桌面版 base=/，GitHub Pages 版 base=/silver-guardian-v2/demo/）。
      VitePWA({
        registerType: 'autoUpdate',
        includeAssets: ['favicon.png', 'apple-touch-icon.png'],
        manifest: {
          name: '银发智伴',
          short_name: '银发智伴',
          description: '智慧养老 AI 助手：健康咨询、用药提醒、家人关怀',
          lang: 'zh-CN',
          start_url: 'elder',
          scope: '.',
          display: 'standalone',
          orientation: 'portrait',
          background_color: '#f8fafa',
          theme_color: '#e8712a',
          icons: [
            { src: 'icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
            { src: 'icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' }
          ]
        },
        workbox: {
          // 只预缓存「应用外壳」：页面、样式、入口 JS、图标。
          // 全量预缓存曾达 476 个文件 / 16.4MB（含 394 个懒加载 chunk 与语法包），
          // 会与首屏抢带宽，隧道下能把首访拖到十几秒；懒加载 chunk 改由运行时缓存兜住。
          globPatterns: ['**/*.{css,html,ico,png,svg,webmanifest}', 'assets/index-*.js'],
          // 图片与其余懒加载 chunk 走运行时缓存：看过一次就离线可用，不占用首访带宽
          runtimeCaching: [
            {
              // generateSW 只能序列化字符串 / 正则，这里用后缀匹配
              urlPattern: /\.(?:png|jpe?g|svg|gif|webp|ico)$/i,
              handler: 'CacheFirst',
              options: {
                cacheName: 'images',
                expiration: { maxEntries: 60, maxAgeSeconds: 30 * 24 * 60 * 60 }
              }
            },
            {
              urlPattern: /\.(?:js|css|woff2?|ttf)$/i,
              handler: 'StaleWhileRevalidate',
              options: { cacheName: 'assets', expiration: { maxEntries: 300 } }
            }
          ],
          // 前端用 history 路由，深链接离线时回落到首页
          navigateFallback: 'index.html',
          cleanupOutdatedCaches: true,
          clientsClaim: true,
          skipWaiting: true
        }
      })
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },
    // Demo 模式部署到 GitHub Pages 的 /silver-guardian-v2/demo/ 路径下
    base: isDemo ? '/silver-guardian-v2/demo/' : '/',
    // Demo 模式输出到 docs/demo 目录（匹配 base 路径 /demo/）
    build: {
      ...(isDemo ? { outDir: '../docs/demo', emptyOutDir: true } : {})
    },
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
      allowedHosts: [
        '.serveousercontent.com',
        '.serveo.net',
        '.cpolar.cn',
        '.cpolar.top',
        '.cpolar.io',
        '.openfrp.top',
        '.openfrp.io',
        '.ofalias.com',
        '.natfrp.com'
      ],
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
      allowedHosts: [
        '.serveousercontent.com',
        '.serveo.net',
        '.cpolar.cn',
        '.cpolar.top',
        '.cpolar.io',
        '.openfrp.top',
        '.openfrp.io',
        '.ofalias.com',
        '.natfrp.com'
      ],
    }
  }
})
