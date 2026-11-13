const { app, BrowserWindow, Menu, shell } = require('electron')
const http = require('node:http')
const fs = require('node:fs')
const path = require('node:path')

const APP_DIR = path.join(__dirname, 'app')

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.webmanifest': 'application/manifest+json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.map': 'application/json'
}

// 前端用 history 路由（createWebHistory），file:// 下无法工作，
// 所以内置一个只读的本地静态服务，并用 index.html 兜底未知路径。
function resolveFile(urlPath) {
  const clean = decodeURIComponent(String(urlPath).split('?')[0].split('#')[0])
  const target = path.normalize(path.join(APP_DIR, clean))
  if (!target.startsWith(APP_DIR)) return null
  return target
}

function startStaticServer() {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      let file = resolveFile(req.url === '/' ? '/index.html' : req.url)
      const miss = !file || !fs.existsSync(file) || fs.statSync(file).isDirectory()
      if (miss) file = path.join(APP_DIR, 'index.html')

      const ext = path.extname(file).toLowerCase()
      res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' })
      fs.createReadStream(file).pipe(res)
    })
    server.on('error', reject)
    server.listen(0, '127.0.0.1', () => resolve(server.address().port))
  })
}

let appUrl = null

function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: '银发智伴',
    backgroundColor: '#f7f5f2',
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true
    }
  })

  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  win.loadURL(appUrl)
  return win
}

if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  app.on('second-instance', () => {
    const [win] = BrowserWindow.getAllWindows()
    if (win) {
      if (win.isMinimized()) win.restore()
      win.focus()
    }
  })

  app.whenReady().then(async () => {
    Menu.setApplicationMenu(null)
    const port = await startStaticServer()
    appUrl = `http://127.0.0.1:${port}/`
    createWindow()

    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow()
    })
  })

  app.on('window-all-closed', () => app.quit())
}