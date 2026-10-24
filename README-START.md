# 银发守护 本地启动手册

> 项目路径：`D:\SilverMate`
> 版本：v0.7.1.beta1
> 部署日期：2026-10-20

---

## 一、日常启动（三步）

### 1. 打开代理软件

必须。整套镜像拉取和后续拉取都依赖它监听 `127.0.0.1:7897`。

### 2. 启动端口转发（只有需要拉新镜像时才必需）

Docker 的虚拟机访问不到宿主机回环地址上的代理，需要这个转发把
`172.24.64.1:7898` 映射到 `127.0.0.1:7897`：

```powershell
cd D:\SilverMate
python tools\proxy_forward.py
```

看到 `[ok] 172.24.64.1:7898 -> 127.0.0.1:7897` 就是正常。这个窗口不要关。

> 只是启动已有容器、不拉新镜像时，这一步可以跳过。

### 3. 启动容器与前端

```powershell
cd D:\SilverMate
docker compose up -d

cd web
pnpm dev
```

访问 **http://127.0.0.1:5173**

> 用 `127.0.0.1` 不要用 `localhost`：Windows 上 localhost 优先解析到 IPv6，
> 而 Docker 的端口映射只监听 IPv4，会超时。

> **pnpm 版本**：由 `web/package.json` 的 `packageManager` 锁定为 `10.11.0`。
> 首次拉代码后执行一次 `corepack enable`，然后用 `corepack pnpm --version`
> 确认输出 `10.11.0`。不要因为一次本地安装把 pnpm 升到 11——锁文件会大面积变动。

> Docker CLI 不在 PATH 时，`dev.ps1` 会自动探测
> `%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin`，普通终端仍需自行添加或改用 `dev.ps1`。

---

## 二、停止

```powershell
cd D:\SilverMate
docker compose down      # 停容器（数据保留在 docker/volumes/）
```

前端窗口 `Ctrl+C`，转发窗口 `Ctrl+C`。

---

## 三、当前配置速查

| 项 | 值 |
|---|---|
| 前端 | http://127.0.0.1:5173 |
| 后端 API | http://127.0.0.1:5050 |
| API 健康检查 | http://127.0.0.1:5050/api/system/health |
| PostgreSQL | localhost:**5433**（刻意避开本机 5432） |
| Redis | localhost:**6380**（本机 6379 已被 redis-server.exe 占用） |
| MinIO | http://localhost:9000（控制台 9001） |
| Milvus | localhost:19530 |
| 沙箱管理 | localhost:8002 |
| 超管账号 | 由 `YUXI_SUPER_ADMIN_UID` 决定 |

初始账号信息全部走环境变量，`backend/scripts/seed_initial_users.py` 里没有任何默认值。
首次初始化前在 `.env` 中补齐这 5 个变量，缺任何一个脚本都会直接失败：

```dotenv
YUXI_SUPER_ADMIN_UID=
YUXI_SUPER_ADMIN_NAME=
YUXI_SUPER_ADMIN_PHONE_NUMBER=
YUXI_SUPER_ADMIN_PASSWORD=
YUXI_DEFAULT_USER_PASSWORD=
```

> 如果你是用旧版本初始化的环境，管理员密码曾经以明文写在脚本里并进过 Git 历史，
> 视为已泄露，请立刻改密码。轮换时先在本地 `.env` 设置新的
> `YUXI_SUPER_ADMIN_PASSWORD`，再执行：

```powershell
docker compose exec api uv run --no-sync --no-dev python scripts/rotate_admin_password.py
```

脚本只会轮换超级管理员密码，不会输出密码内容。

---

## 四、几个必须知道的约定

### 1. MinIO 用的是 Bitnami 遗产镜像，不是官方镜像

MinIO 官方 2025 年起下架了 Docker Hub 镜像，`dl.min.io` 二进制也返回 410。
现在用的是 `bitnamilegacy/minio:latest`（MinIO 2025.5.24 打包版）。

差异已经写在 `docker-compose.override.yml` 里：
- 清空了 `command`（Bitnami 由 entrypoint 自行启动）
- 用 `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`（不认官方的 `MINIO_ACCESS_KEY`）
- 数据目录 `/bitnami/minio/data`（不是 `/minio_data`）

**不要**手动改成官方镜像，会直接拉不到。

### 2. 不要用 `LITE_MODE=true`

它会把知识库、图谱、评估的所有路由注销，养老核心功能直接消失。

### 3. 后端不要裸跑在 Windows 上

`DEPLOYMENT.md` 自己标注了"Windows 有事件循环兼容问题"。始终用 Docker。

### 4. Git Bash 里的路径转换

用 `docker run -e VAR=/some/path` 时，Git Bash 会把 `/some/path` 改写成 Git 的安装目录。
加 `MSYS_NO_PATHCONV=1` 前缀：

```bash
MSYS_NO_PATHCONV=1 docker run -e MINIO_DATA_DIR=/data ...
```

`docker compose` 不受影响（读 yml 文件，不经过 shell）。

---

## 五、常见问题

### Q: docker pull 报 `connection refused` / 超时

代理没开，或端口转发没起。按「日常启动」的第 1、2 步检查。

### Q: 前端能打开但接口全 404

检查 `web/.env.local` 里 `VITE_API_URL` 是否为 `http://127.0.0.1:5050`。

### Q: api 容器一直 unhealthy

```powershell
docker logs api-dev --tail 100
```

常见原因是 postgres/minio 没起来，看 `docker compose ps`。

### Q: 想重置所有数据

```powershell
docker compose down
Remove-Item -Recurse -Force docker\volumes
docker compose up -d
docker compose exec api uv run python scripts/seed_initial_users.py
```

**注意**：删 `docker/volumes` 会清空数据库、MinIO 文件、Milvus 向量数据，不可恢复。

### Q: Dify 怎么恢复

容器清单备份在 `.dify-containers-backup.txt`：

```powershell
docker start $(Get-Content .dify-containers-backup.txt)
```

注意内存：本机 Docker VM 只有 8GB，Dify 15 个容器和本项目不建议同时跑。

---

## 六、二次开发入口

| 想改什么 | 改哪里 |
|---|---|
| 品牌名 / Logo / 副标题 | `backend/package/yuxi/config/static/info.local.yaml` |
| 适老化字号 / 配色 | `web/src/assets/css/elderly-friendly.css` |
| 紧急关键词 | `web/src/utils/emergencyDetector.js` |
| SOS 按钮 | `web/src/components/ElderlyEmergencyButton.vue` |
| 新增技能 | `backend/package/yuxi/agents/skills/buildin/<slug>/SKILL.md` + 注册到 `buildin/__init__.py` |
| 新增智能体后端 | `backend/package/yuxi/agents/<name>/`，继承 `BaseAgent` |
| 知识库文档 | `knowledge_docs/*.md`（改完需在界面重新上传） |
| 后端接口 | `server/routers/` + `web/src/apis/` |

**4 个养老智能体不在代码里**，需要在管理界面手工创建。这是项目最大的缺口。
