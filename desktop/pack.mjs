import { packager } from '@electron/packager'

// 打包脚本用 API 而不是命令行参数：路径里的正则含 | 和括号，经 Windows 命令行会被截断。
const paths = await packager({
  dir: import.meta.dirname,
  name: 'SilverMate',
  platform: 'win32',
  arch: 'x64',
  out: 'out',
  overwrite: true,
  icon: 'build/icon.ico',
  electronZipDir: 'cache',
  appVersion: '1.0.0',
  // pnpm 的严格 node_modules 布局会让依赖遍历器（flora-colossus）解析失败；
  // 本应用没有运行时依赖，直接关闭 prune 并忽略 node_modules。
  prune: false,
  // `.userdata*` / `.ud*` 是调试时产生的 Chromium profile 目录（几十 MB），
  // 只匹配精确的 `.userdata` 会把它们打进 asar，体积从 15MB 涨到 74MB。
  ignore: [
    /^\/(node_modules|out|cache)$/,
    /^\/\.(userdata|ud)[^/]*$/,
    /^\/run_(out|err)\.txt$/,
    /^\/app\/.*\.map$/
  ],
  win32metadata: {
    ProductName: '银发智伴',
    FileDescription: '银发智伴 · 智慧养老 AI 助手（离线演示）',
    CompanyName: 'SilverMate'
  }
})

console.log('packaged:', paths)