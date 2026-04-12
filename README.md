# Xiaomi Miloco WSL Deploy

一个面向 `Windows + WSL Ubuntu 24.04` 的可运行分发版，用来把小米摄像机接入 `Miloco + Micam + go2rtc`，并输出稳定的网页预览与 RTSP 流。

这个仓库不是单纯 mirror 某个上游，而是把下面几部分整理成了一套能实际跑通的工程：

- `miiot/micam` 的整体项目骨架与转流思路
- `XiaoMi/xiaomi-miloco` 的服务端与前端
- `go2rtc` 的 RTSP 桥接
- 针对 `WSL mirrored + native Docker` 的部署修补、文档和兼容性调整

## 为什么有这个仓库

原始上游项目各自有价值，但直接拿来在 `Windows + WSL` 环境里部署时，我们踩到了不少坑，包括：

- `Docker Desktop` 接管 WSL 后的网络问题
- `WSL NAT` 导致的摄像头离线和 `PPCS_Connect errorcode: -3`
- `Windows / Hyper-V` 防火墙导致的本地流建立失败
- `Micam` 中 `VIDEO_CODEC` 环境变量被默认参数覆盖
- `Miloco` 前端放大视频时只显示半边画面

这个仓库的目标不是做“大而全”的二次开发，而是把这条部署链路整理成别人能复现、能维护、能再次部署的版本。

## 当前验证过的环境

- Windows 11
- WSL `Ubuntu-24.04`
- WSL 网络模式：`mirrored`
- Docker：WSL 内原生 `docker.io` + `docker compose`
- 浏览器：`Chrome` 优先

## 快速开始

1. 先看 [`docs/5分钟快速部署版.md`](./docs/5分钟快速部署版.md)
2. 需要完整背景、坑点和排障时看 [`docs/再次部署指南.md`](./docs/再次部署指南.md)
3. 准备发 GitHub 前看 [`docs/公开发布前检查清单.md`](./docs/公开发布前检查清单.md)
4. 准备仓库名、描述、topics 和 release 文案时看 [`docs/GitHub发布材料.md`](./docs/GitHub发布材料.md)
5. 如果新环境没有安装 WSL 原生 Docker，执行 [`setup-native-docker.sh`](./setup-native-docker.sh)
6. 复制 [`.env.example`](./.env.example) 为本地 `.env`，按你的环境填写
7. 运行：

```bash
docker compose build miloco
docker compose up -d
```

## 仓库结构

```text
.
├── .env.example
├── Dockerfile
├── Dockerfile.miloco
├── docker-compose.yml
├── docs/
│   ├── 5分钟快速部署版.md
│   ├── GitHub发布材料.md
│   ├── 公开发布前检查清单.md
│   ├── 首个Release文案-v0.1.0.md
│   └── 再次部署指南.md
├── go2rtc/
│   └── go2rtc.yaml
├── micam/
│   ├── __init__.py
│   └── __main__.py
├── NOTICE.md
└── setup-native-docker.sh
```

## 这个仓库里包含了哪些修补

### 1. WSL 部署路径收口

- 明确要求 `WSL mirrored`
- 明确要求 `native Docker`
- 明确要求 `Docker Desktop` 不接管当前发行版

### 2. Miloco 构建修补

`Dockerfile.miloco` 会在构建时拉取 `XiaoMi/xiaomi-miloco` 源码，并打入这类环境相关修补：

- 默认开启音频
- 默认使用更高视频质量
- 支持 `MIOT_LAN_TARGETS`
- 修补 `FastMCP` 参数兼容
- 刷新摄像机列表前主动刷新状态
- 修补放大视频时 canvas 尺寸错误导致的“只显示半边”

### 3. Micam 运行修补

- 修复 `VIDEO_CODEC` 环境变量被 argparse 默认值覆盖的问题
- 当前已验证 `VIDEO_CODEC=hevc` 可正常工作

## 配置入口

推荐只改 `.env`，不要直接改 `docker-compose.yml`。

关键变量：

- `MILOCO_BASE_URL`: 推荐 `https://localhost:8000`
- `MILOCO_PASSWORD`: Miloco WebUI 密码的 md5 小写值
- `CAMERA_ID`: 摄像机 DID
- `RTSP_URL`: 例如 `rtsp://localhost:8554/your_stream1`
- `VIDEO_CODEC`: 当前环境推荐 `hevc`
- `MIOT_LAN_TARGETS`: 摄像机局域网 IP

示例配置见 [`.env.example`](./.env.example)。

## 使用建议

- 本机 Windows 访问 Miloco 时优先用 `https://localhost:8000`
- 局域网其他设备访问时用 `https://<Windows-LAN-IP>:8000`
- 如果 Chrome 放大画面还显示旧样式，先 `Ctrl + F5`
- 如果 Edge 报解码失败，优先先用 Chrome 验证链路

## 不建议直接公开提交的文件

下面这些属于本地运行态数据，不建议提交到公开仓库：

- `.env`
- `miloco/miloco.db`
- `miloco/cert/*`
- `miloco/log/*`
- `miloco/miot_cache/*`

这些路径已经写进 [`.gitignore`](./.gitignore)。

## 上游来源与许可说明

请先阅读 [`NOTICE.md`](./NOTICE.md)。

这个仓库是部署增强版，不会替代或覆盖上游项目的许可证与使用条款。发布、再分发或商用前，请分别核对相关上游仓库的要求，尤其是 `XiaoMi/xiaomi-miloco`。
