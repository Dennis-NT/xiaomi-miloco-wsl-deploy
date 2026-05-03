# 小米摄像机洗漱行为监督系统

基于 **小米智能摄像机 3** + **Miloco** + **go2rtc** 的洗漱行为自动分析与评分系统。系统仅在每天早晚两个固定时间窗内分析视频，判断孩子是否认真刷牙和洗脸，并输出 `未完成/差/中/好` 评级，结果通过邮件自动推送。

> 本项目从 `Xiaomi Miloco WSL Deploy` 演进而来，在原有的视频桥接能力（Phase 0）之上，新增了完整的 AI 行为分析链路（Phase 1-3）。

---

## 系统架构

```
小米智能摄像机 3
        │
        ▼
Micam（WebSocket → RTSP 桥接）
        │
        ▼
go2rtc（RTSP 分发）
        │
        ▼
analyzer（行为分析服务）
 ├─ 调度器：06:30–07:30 / 21:30–22:30 自动触发
 ├─ 视频采集：RTSP 拉流，2 FPS 抽样
 ├─ 姿态检测：MediaPipe Pose Heavy + Hands 双模型
 ├─ 行为识别：指尖到嘴部/面部距离判定
 ├─ 评分引擎：未完成 / 差 / 中 / 好
 ├─ 证据生成：最佳关键帧 + 动作片段
 ├─ SQLite 落库
 └─ 邮件推送（SMTP）
```

---

## 已实现功能

| 阶段 | 功能 | 状态 |
|------|------|------|
| **Phase 0** | 小米摄像机桥接为 RTSP，网页可预览 | ✅ |
| **Phase 1** | 定时调度、视频采集、SQLite 存储、邮件通知 | ✅ |
| **Phase 2** | MediaPipe Pose Heavy + Hands 双模型行为识别、评分引擎 | ✅ |
| **Phase 3** | 最佳关键帧选择、ffmpeg 截取证据片段、邮件发附件 | ✅ |
| Phase 4 | 长期稳定运行、阈值调参、误报优化 | 🔄 待观察 |

### 行为识别逻辑

- **刷牙判定**：食指/中指指尖到嘴部距离 < 0.10（归一化坐标），回退到手腕距离 < 0.15
- **洗脸判定**：≥4 个指尖到面部距离 < 0.12，回退到双手腕到面部 < 0.18
- **动作中断容忍**：2 秒内没检测到仍视为连续

### 评分标准

| 行为 | 未完成 | 差 | 中 | 好 |
|------|--------|----|----|----|
| 刷牙 | <20s | 20–45s | 45–90s | ≥90s |
| 洗脸 | <8s | 8–15s | 15–30s | ≥30s |

---

## 硬件要求

推荐配置（已验证）：

- **CPU**：AMD Ryzen 9 9950X（或同级别）
- **内存**：16GB+（推荐 32GB 以上）
- **GPU**：无需独显，CPU 推理即可
- **磁盘**：SSD，约 500MB/天时间窗录像缓存
- **运行方式**：24 小时开机

> 本项目最初为无独显 Mini PC 设计（AMD Ryzen 5 3500U），迁移到主力电脑后升级了 MediaPipe Heavy 模型以获得更高精度。CPU 推理单帧约 30ms，2 FPS 分析完全流畅。

---

## 快速开始

### 1. 环境准备

- Windows 11 + WSL Ubuntu 24.04
- WSL 网络模式：`mirrored`
- WSL 内原生 Docker（非 Docker Desktop 接管）
- 未安装 Docker 时先执行：`./setup-native-docker.sh`

### 2. 配置

```bash
# 复制配置模板
cp .env.example .env
```

编辑 `.env`，填入你的环境信息：

```bash
# Miloco / Micam
MILOCO_BASE_URL=https://localhost:8000
MILOCO_PASSWORD=你的密码md5值
CAMERA_ID=摄像机DID
RTSP_URL=rtsp://localhost:8554/your_stream1
VIDEO_CODEC=hevc
MIOT_LAN_TARGETS=192.168.1.x

# 邮件通知（126/163/QQ/Gmail 均可）
SMTP_HOST=smtp.126.com
SMTP_PORT=465          # 126/163 推荐 465；QQ/Gmail 可用 587
SMTP_USER=你的邮箱@126.com
SMTP_PASSWORD=SMTP授权码    # 不是邮箱密码！
EMAIL_FROM=你的邮箱@126.com
EMAIL_TO=收件人@example.com
SMTP_USE_TLS=false     # 465 端口填 false；587 端口填 true
```

### 3. 下载 AI 模型

```bash
bash scripts/download_models.sh
```

这会下载：
- `analyzer/models/pose_landmarker_lite.task`（备用）
- `analyzer/models/hand_landmarker.task`

Heavy 模型（推荐）需手动下载：

```bash
curl -L -o analyzer/models/pose_landmarker_heavy.task \
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_heavy/float16/latest/pose_landmarker_heavy.task"
```

然后修改 `config.yaml`：

```yaml
analysis:
  pose_model: "heavy"   # lite / full / heavy
```

### 4. 启动

```bash
# 全部服务一起启动
docker compose up -d --build

# 或只启动分析器（其他已在运行）
docker compose up -d --build analyzer
```

### 5. 验证

```bash
# 立即跑一次 60 秒测试分析
python3 scripts/test_analysis.py
```

如果邮件配置正确，你会收到一封带附件的测试邮件。

---

## 目录结构

```text
.
├── .env                      # 本地敏感配置（不提交）
├── .env.example              # 配置模板
├── config.yaml               # 分析参数配置（时间窗、阈值、ROI）
├── docker-compose.yml        # 服务编排
├── Dockerfile                # Micam 桥接服务
├── Dockerfile.analyzer       # 分析服务
├── Dockerfile.miloco         # Miloco 接入服务
├── requirements.txt          # Python 依赖
│
├── analyzer/                 # 行为分析服务（Phase 1-3）
│   ├── __init__.py
│   ├── main.py               # 入口
│   ├── scheduler.py          # 时间窗调度器
│   ├── stream_reader.py      # RTSP 拉流与抽帧
│   ├── pose_detector.py      # MediaPipe Pose 封装
│   ├── hands_detector.py     # MediaPipe Hands 封装
│   ├── behavior_rules.py     # 刷牙/洗脸规则引擎
│   ├── behavior_analyzer.py  # 分析整合器
│   ├── scoring.py            # 评分引擎
│   ├── roi.py                # ROI 配置模块
│   ├── db.py                 # SQLite 存储
│   ├── notifier_email.py     # 邮件通知
│   └── models/               # AI 模型文件（不提交）
│
├── scripts/                  # 工具脚本
│   ├── capture_reference_frame.py   # ROI 标定辅助
│   ├── download_models.sh           # 模型下载
│   └── test_analysis.py             # 一键测试
│
├── micam/                    # WebSocket → RTSP 桥接（Phase 0）
├── go2rtc/                   # RTSP 流媒体服务
├── miloco/                   # 米家设备接入服务
├── docs/                     # 部署文档
└── data/                     # 运行时数据（不提交）
    ├── frames/               # 关键帧
    ├── clips/                # 证据片段
    └── db/                   # SQLite 数据库
```

---

## 配置调参

所有阈值都外置在 `config.yaml`，无需改代码：

```yaml
# 时间窗
timezone: Asia/Shanghai
windows:
  - name: morning
    start: "06:30"
    end: "07:30"
  - name: evening
    start: "21:30"
    end: "22:30"

# 行为识别阈值
hands:
  brush_finger_threshold: 0.10
  face_finger_threshold: 0.12

# 评分阈值
analysis:
  toothbrush_min_seconds_done: 20
  toothbrush_min_seconds_medium: 45
  toothbrush_min_seconds_good: 90
  facewash_min_seconds_done: 8
  facewash_min_seconds_medium: 15
  facewash_min_seconds_good: 30

# ROI（可选）
roi:
  enabled: false
  sink_area: [0.2, 0.3, 0.8, 0.9]
```

---

## 开发阶段表

| 阶段 | 目标 | 状态 |
|------|------|------|
| Phase 0 | 接流验证：小米摄像机 → RTSP → 网页可预览 | ✅ |
| Phase 1 | 分析主链路：调度、抽帧、SQLite、邮件通知 | ✅ |
| Phase 2 | 规则引擎：ROI + 刷牙/洗脸判断 + 评分 | ✅ |
| Phase 3 | 证据附件：关键帧、短视频、邮件附件 | ✅ |
| Phase 4 | 调参与稳定化：7 天连续运行、阈值优化 | 🔄 |

---

## 许可证

请先阅读 [`NOTICE.md`](./NOTICE.md)。

本项目是部署增强版，不会替代或覆盖上游项目的许可证与使用条款。发布、再分发或商用前，请分别核对相关上游仓库的要求，尤其是 `XiaoMi/xiaomi-miloco`。
