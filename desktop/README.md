# SilverMate 桌面版（离线演示）

把 `web` 的 demo 构建（mock 数据，不连后端）装进 Electron 壳，双击即可体验。

## 构建

```powershell
cd desktop
pnpm install
pnpm demo:build   # 生成 app/（web 的 --mode demo 构建，base=/）
node pack.mjs     # 生成 out/SilverMate-win32-x64/
```

产物：`out/SilverMate-win32-x64/SilverMate.exe`（整个文件夹可直接拷贝分发）。

## 本地运行（不打包）

```powershell
pnpm demo:build
pnpm start
```

## 说明

- 演示数据来自 `web/src/demo/mockData.js`，只覆盖部分接口；未覆盖的接口会返回 “Demo mode: endpoint not mocked”。
- `main.js` 内置了一个只读的本地静态服务（随机端口），因为前端用 history 路由，`file://` 下无法工作。
- Electron 二进制走镜像下载失败时，可手动把 `electron-v<version>-win32-x64.zip` 放进 `cache/`，再解压到 `node_modules/electron/dist` 并写入 `node_modules/electron/path.txt`（内容为 `electron.exe`）。