# GitHub 发布材料

这份文档用于把当前目录整理成一个可以直接公开发布的 GitHub 项目。

## 1. 推荐仓库名

首选：

`xiaomi-miloco-wsl-deploy`

这个名字的优点：

- 直接点明 `Xiaomi Miloco`
- 明确目标环境是 `WSL`
- 明确仓库定位是 `deploy`

可选备选名：

- `miloco-wsl-native-docker`
- `xiaomi-camera-wsl-rtsp-stack`
- `miloco-micam-go2rtc-wsl`

如果你希望名字更像“部署增强版”而不是“全新产品”，首选第一个最稳。


## 2. 推荐仓库描述

### 2.1 GitHub 仓库短描述

推荐直接使用：

`Deployment-focused Windows WSL distribution for Xiaomi Miloco + Micam + go2rtc with native Docker and documented fixes.`

如果你想更偏中文语境，也可以用：

`一个面向 Windows WSL 的 Xiaomi Miloco + Micam + go2rtc 可运行部署增强版。`


### 2.2 README 开头一句话

可用这一句：

`A deployment-oriented, WSL-tested distribution for running Xiaomi Miloco, Micam and go2rtc with native Docker on Windows.`


## 3. 推荐 GitHub Topics

建议放这些：

- `xiaomi`
- `miloco`
- `micam`
- `go2rtc`
- `wsl`
- `docker`
- `rtsp`
- `camera`
- `windows`
- `ubuntu`

如果 GitHub topics 数量想控制在 6 到 8 个，优先保留：

- `xiaomi`
- `miloco`
- `micam`
- `go2rtc`
- `wsl`
- `docker`
- `rtsp`


## 4. 推荐首个版本号

建议：

`v0.1.0`

原因：

- 这是第一版公开发布
- 当前项目已经可用，但仍属于“部署增强版”而不是长期稳定 API 产品
- 用 `0.x` 更符合现阶段成熟度


## 5. 推荐 Release 标题

推荐：

`v0.1.0 - First public WSL deployment release`

如果你想更偏中文：

`v0.1.0 - 首个可公开复现的 WSL 部署版`


## 6. 发布前建议执行的 Git 命令

在仓库根目录执行：

```bash
git branch -m main
git status --ignored
git add .
git status
git commit -m "chore: initial public release"
```

说明：

- `git branch -m main` 是把默认分支从 `master` 改成 `main`
- `git status --ignored` 用来再确认 `.env` 和 `miloco/` 仍然没有被纳入提交
- `git add .` 在当前 `.gitignore` 下是安全的


## 7. 发布到 GitHub 的最短顺序

1. 在 GitHub 上新建空仓库
2. 仓库名填 `xiaomi-miloco-wsl-deploy`
3. Description 使用本页的推荐描述
4. Topics 按本页建议填写
5. 本地执行：

```bash
git remote add origin <your-github-repo-url>
git push -u origin main
```

6. 在 GitHub 页面创建 `v0.1.0` release
7. Release 文案直接使用 [`首个Release文案-v0.1.0.md`](./首个Release文案-v0.1.0.md)


## 8. 仓库首页建议强调的点

建议在 GitHub 首页和 README 中统一强调：

- 这是部署增强版，不是对上游许可证的替代
- 推荐运行环境是 `Windows + WSL Ubuntu 24.04 + native Docker`
- `Docker Desktop` 不应接管该 WSL 发行版
- 当前版本已经修复 WSL 部署链路和前端半边画面问题


## 9. 公开发布时的口径建议

建议用这个定位：

`This repository packages a reproducible deployment path and environment-specific fixes for running Xiaomi Miloco with Micam and go2rtc on Windows WSL.`

不建议用这个定位：

- “official”
- “upstream replacement”
- “fully independent implementation”

因为这会让来源关系变模糊，也容易带来不必要的许可证理解风险。
