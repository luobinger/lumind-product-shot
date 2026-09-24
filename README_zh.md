<div align="center">

[English](./README.md) | **简体中文**

# Lumind Product Shot

**帮你一键生成高转化的跨境电商主图与商品详情页（PDP）**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10+-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Tested On](https://img.shields.io/badge/Tested_on-OpenClaw_|_Hermes_|_Codex_|_Claude_Code_|_WorkBuddy-2ea44f?style=for-the-badge&logo=openai&logoColor=white)](#)
[![AI Agent Ready](https://img.shields.io/badge/AI_Agent-Ready-8A2BE2?style=for-the-badge&logo=probot&logoColor=white)](#)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

</div>

---

> **Lumind Product Shot** 是一个专为 AI Agent 设计的跨境电商图像生成工具。
>
> 你只需要告诉它“卖什么产品”和“受众是谁”，它就会帮你写好英文营销文案、规划好排版结构，并直接调用 AI 生图工具，把**一套可以直接上架的商品图包（主图 + 详情页图）**交给你。

## 核心特性

- **端到端一键出图**：根据简单描述自动生成 5 张主图 + 7~9 张详情页图片（默认），全自动交付。
- **高效批量并发流水线**：单命令支持 `--batch-dir`（扫描目录）或 `--batch-file`（任务清单），内置多线程并发池（`-c/--concurrency`），自动识别主图/长图尺寸并输出结构化清单报告 `batch-summary.json`，告别低效外部 bash 循环。
- **智能连接池与指数退避重试**：纯标准库实现 Keep-Alive 长连接复用，遇到 HTTP 429/500/502/503/504 等临时抖动自动指数退避重试，大幅提升高并发与跨国调用韧性。
- **多图视觉一致性与风格锁**：内置成熟的跨境电商多图视觉对齐机制（中性演播室底色、单强调色、纯矢量图标规范），确保整套图包视觉统一，拒绝拼凑感。
- **转化导向的文案与结构**：自带爆款逻辑，自动生成原汁原味 English (US) 文案，适配 Amazon 等渠道。
- **广泛的框架兼容**：专为 Agent 打造，已在 OpenClaw、Hermes、Codex、Claude Code、WorkBuddy 等环境验证。

---

## 真实效果展示

样例图包：一款面向亚马逊美国站的 360° 纯记忆棉护颈旅行枕，从一句产品简报端到端生成。

**主图图包 —— 5 张，同一套锁定的风格系统**

![主图图包：5 张共享同一风格锁的亚马逊商品图](assets/showcase/02-main-pack.jpg)

**详情页图包 —— 7 屏竖版 A+ 页面，每屏 1024x1536**

![详情页图包：7 张 1024x1536 竖版详情页，从客舱首屏场景到无忧质保收口](assets/showcase/04-detail-pack.jpg)

**客单价（AOV）组合扩展包 —— 3 套增量组合图，每张 1024x1024**

![组合套装图：3 套专为提升客单价（AOV）打造的高转化商品组合图](assets/showcase/05-combo-pack.jpg)

**请注意三件事，别只看图：** 
1. **核心转化帧 vs 支撑帧结构：** 上述 7 屏详情页中，真正承担核心转化冲击力的是 3 屏 —— 三万英尺客舱真实睡眠体验承诺、普通 C 型枕 vs 360° 下巴支架的痛点对照矩阵（直击长途飞行“点头晃脑”痛点）、以及颈椎人机工学受力分解；其余 4 屏为支撑与信任交付（多场景差旅实拍、3 步快速收纳指南、50,000+ 差旅人群口碑证言卡、以及全套配件清单与 3 年质保）。
2. **组合装驱动客单价（AOV）裂变：** 新增的 3 张组合图分别聚焦“4合1 深度睡眠完整套装”、“2-Pack 情侣/双人出行礼盒装”与“颈椎+腰椎全脊椎人机工学双重支撑”，精准击穿礼品赠送与客单价提升需求。
3. **真实商家审核守则：** 本图包为完整的工业级视觉演示框架。图中所含示例声称（如具体首发价、质保年限或认证徽章）在正式上架投放前，须根据真实供应链规格进行校验或替换。

> 查看全分辨率精选单图：
> [主图首图](assets/showcase/01-hero-main.jpg) ·
> [详情页首屏](assets/showcase/03-detail-hero.jpg) ·
> [AOV 套装组合全览](assets/showcase/05-combo-pack.jpg)

---

## 快速开始

最快的入口是让 Agent 自己完成安装与配置 —— 把 [安装 · 第 0 步](#安装) 的指令块粘给它。想自己动手的话，手动步骤在同一节。

*(注意：若未配置 API，系统将仅输出可执行的生图 Prompt。)*

**直接发给 Agent 的示例指令：**
```text
用 lumind-product-shot 给这款产品做 Amazon US PDP 图包：
输出 5 张主图 + 7 张详情页图。
```

---

## 安装

**推荐路线：直接交给你的 Agent。** 把第 0 步的指令块粘进 Codex、WorkBuddy 或 Claude Code，它会替你完成克隆、配置与验证。只有当你想自己动手，或 Agent 没有网络与文件系统权限时，才从第 1 步走手动路线。

### 0. 让 Agent 自动安装（推荐）

```text
帮我安装技能 "lumind-product-shot"，并证明它真的可用。

1. 把 https://github.com/luobinger/lumind-product-shot.git 克隆到你自己运行时
   真正读取的技能目录（Codex 是 ~/.codex/skills/，WorkBuddy 是
   ~/.workbuddy/skills/）。不要猜路径——先确认你从哪个目录枚举技能。

2. 如果我需要这个技能在第二个宿主中可见，用软链桥接，不要保留两份副本。

3. 用 scripts/generate_image.py --about 证明安装成功，并把原始输出贴给我。
   不要只因为目录存在就报告成功。

4. 然后向我要 IMG_BASE_URL、IMG_MODEL、IMG_API_KEY，写入 .env，确认 .env 已被
   gitignore 忽略，并且不要把密钥回显给我。

5. 重启会话，确认 "lumind-product-shot" 出现在你的可用技能列表中。如果没有，
   直接告诉我。
```

正确结果长什么样，以及什么时候该驳回：

| 检查项 | 期望 | 出现以下情况请驳回 |
| --- | --- | --- |
| 安装路径 | 落在宿主自己的技能目录内 | Agent 写到你不加载技能的别处 |
| 验真 | `--about` 打印版本号与工具版权信息 | Agent 没跑命令就声称成功 |
| 凭证 | 存于 `.env`，且该文件被 gitignore | 密钥被贴进对话或被提交 |
| 会话 | 重启后技能出现在宿主可用技能列表中 | Agent 把「目录存在」当成本身已加载 |

两点值得坚持：验真的口径是 `--about` 的输出而不是「文件夹建好了」；密钥绝不允许回显进对话。

下面是手动路线。以下每条命令都在本仓库实测执行过，可直接复制粘贴。

### 1. 环境要求

| 要求 | 版本 | 说明 |
| --- | --- | --- |
| Python | 3.10 及以上 | `scripts/generate_image.py` 只导入标准库，**无需 `pip install`** |
| Git | 任意较新版本 | 仅克隆路线需要；rsync 路线不需要 |
| 具备技能目录的 Agent | 不限 | Codex、WorkBuddy、Claude Code、OpenClaw、Hermes，或纯终端 |

```bash
python3 --version
```

生图调用是用 `urllib` 拼的普通 HTTPS 请求，没有依赖树可被破坏。

### 2. 先确认宿主真正读取的技能目录

技能按宿主分别加载。磁盘上存在目录不算数，必须等到宿主把它枚举出来。

| 宿主 | 技能目录 |
| --- | --- |
| Codex | `~/.codex/skills/` |
| WorkBuddy | `~/.workbuddy/skills/` |
| Claude Code | `~/.claude/skills/` |

技能**不跨端互通**。装进 `~/.codex/skills/` 不会让它在 WorkBuddy 中可见。

### 3. 安装

**路线 A —— 直接克隆到技能目录（推荐，便于日后更新）：**

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/luobinger/lumind-product-shot.git ~/.codex/skills/lumind-product-shot
```

把 `.git` 留在技能目录里没有副作用，反而让你日后只需一句 `git pull` 就能更新。

**路线 B —— 从本地检出 rsync 同步：**

```bash
cd /path/to/lumind-product-shot
mkdir -p ~/.codex/skills/lumind-product-shot
rsync -a --exclude .git --exclude .env --exclude "generated-images/" ./ ~/.codex/skills/lumind-product-shot/
```

### 4. 装到第二个宿主，但不要留两份副本

用软链桥接，让两个宿主读同一份文件：

```bash
mkdir -p ~/.workbuddy/skills
ln -s ~/.codex/skills/lumind-product-shot ~/.workbuddy/skills/lumind-product-shot
```

若确实需要独立副本，把第 3 步的目标路径换成另一个宿主目录重跑一次即可。

### 5. 验证安装

```bash
python3 ~/.codex/skills/lumind-product-shot/scripts/generate_image.py --about
```

期望输出：

```text
lumind-product-shot v1.3.0
An AI Agent tool for cross-border ecommerce product shots & PDP generation.
Copyright (c) 2026 Luoluo Wuchen
```

随后**重启宿主会话**，确认技能出现在宿主的可用技能列表中。不要把「目录存在」当作「已加载」的凭据。

### 6. 配置生图 API

```bash
cd ~/.codex/skills/lumind-product-shot
cp .env.example .env
```

编辑 `.env` 填入你的凭证：

```dotenv
IMG_BASE_URL=https://api.openai.com/v1
IMG_MODEL=gpt-image-1.5
IMG_API_KEY=your-api-key
```

变量解析规则 —— 按顺序取第一个非空值：

| 配置项 | 可接受的变量名（按优先级） |
| --- | --- |
| 接口地址 | `IMG_BASE_URL` → `OPENAI_BASE_URL` → `OPENAI_API_BASE` → `BASE_URL` |
| 模型 | `IMG_MODEL` → `OPENAI_IMAGE_MODEL` → `IMAGE_MODEL` → `OPENAI_MODEL` |
| 密钥 | `IMG_API_KEY` → `OPENAI_API_KEY` → `API_KEY` |

`.env` 查找顺序：若传了 `--env-file` 则用它，否则脚本从当前工作目录逐级向上查找 `.env`。**真实环境变量的优先级高于 `.env` 内的值。**

`.env` 已被 `/.env` 与 `/.env.*` 两条规则忽略，而 `.env.example` 被显式保留。切勿提交真实密钥。

### 7. 端到端验证 API

```bash
cd ~/.codex/skills/lumind-product-shot
python3 scripts/generate_image.py \
  --mode image \
  --prompt "clean ecommerce test frame, white studio background, single matte grey object, centered" \
  --job-dir generated-images/smoke-test \
  --asset-type main \
  --size 1024x1024
```

成功会打印 `生成完成：` 及写入的文件路径。若看到 `图片 API 配置未完整` 或 `image 模式需要完整图片 API 配置。缺少配置：...`，说明凭证没加载成功，回到第 6 步排查。

### 8. 更新与卸载

```bash
# 更新 git 安装
git -C ~/.codex/skills/lumind-product-shot pull

# 更新 rsync 安装（--delete 会清掉上游已删除的文件，.env 被保留）
rsync -a --delete --exclude .env --exclude "generated-images/" ./ ~/.codex/skills/lumind-product-shot/

# 卸载
rm -r ~/.codex/skills/lumind-product-shot
rm ~/.workbuddy/skills/lumind-product-shot   # 如果你建过软链
```

### 9. 命令参考

```text
usage: lumind-product-shot [-h]
                           [--prompt PROMPT | --prompt-file PROMPT_FILE | --batch-dir BATCH_DIR | --batch-file BATCH_FILE]
                           [--about] [--mode {auto,prompt,image}]
                           [--job-dir JOB_DIR]
                           [--asset-type {angle,angle-sheet,main,hero,detail,pdp-detail,extra,extras,custom}]
                           [--output-dir OUTPUT_DIR] [--env-file ENV_FILE]
                           [--size SIZE] [--quality QUALITY]
                           [--format {png,jpeg,webp}] [--n N] [--image IMAGE]
                           [--concurrency CONCURRENCY]
                           [--max-retries MAX_RETRIES]
                           [--retry-delay RETRY_DELAY] [--timeout TIMEOUT]
```

| 参数 | 取值 / 默认 | 作用 |
| --- | --- | --- |
| `-h`、`--help` | 开关 | 打印完整参数说明后退出 |
| `--prompt` | 字符串 | 直接传入 Prompt，与 `--prompt-file`、`--batch-dir`、`--batch-file` 互斥 |
| `--prompt-file` | 路径 | 从文件读取 Prompt，长 Prompt 用这个 |
| `--batch-dir`、`--prompts-dir` | 路径 | 包含多个 Prompt 文本文件的目录，按文件名顺序批量并发执行 |
| `--batch-file`、`--manifest` | 路径 | 批量任务清单文件（支持 JSON 数组、JSONL 或按行列表） |
| `--about` | 开关 | 打印工具版本与版权信息后退出，无需 Prompt |
| `--mode` | `auto`（默认）/ `prompt` / `image` | `auto` 配置齐全则生图、缺失则只打印 Prompt；`prompt` 绝不调用接口；`image` 要求配置完整 |
| `--job-dir` | 路径 | 单次任务根目录。资产写入 `<job-dir>/<资产目录>/`，Prompt 写入 `<job-dir>/prompts/`，汇总写入 `<job-dir>/batch-summary.json` |
| `--asset-type` | `custom`（默认） | 选择输出子目录，批量模式下若文件名含 `main`/`detail` 会自动推导覆盖 |
| `--output-dir` | `generated-images` | 旧版扁平输出目录，仅在未传 `--job-dir` 时生效 |
| `--env-file` | 路径 | 指定 `.env`，跳过逐级向上查找 |
| `--size` | `1024x1024` | 请求尺寸；批量模式下若未显式指定，`detail` 自动适配为 `1024x1536` |
| `--quality` | 未设置 | 服务商质量参数，如 `low`、`medium`、`high` |
| `--format` | `png`（默认） | `png`、`jpeg` 或 `webp` |
| `--n` | `1` | 单次生成张数，必须大于等于 1，小于 1 会被直接拒绝 |
| `--image` | 路径 | 产品参考图。传入后改用图片编辑接口，以锁定产品一致性 |
| `-c`、`--concurrency` | `3`（默认，范围 1-32） | 批量生成时的多线程并发工作线程数 |
| `--max-retries` | `3`（默认） | 接口遇到 429、500、502、503、504 或网络中断时的最大重试次数，设为 0 禁用重试 |
| `--retry-delay` | `2.0`（默认，秒） | 指数退避重试的基础退避等待时间 |
| `--timeout` | `120.0`（默认，秒） | 单次网络请求与下载超时时间 |

`--asset-type` 到目录的映射：

| `--asset-type` | 写入目录 |
| --- | --- |
| `angle`、`angle-sheet` | `<job-dir>/angle-sheet/` |
| `main`、`hero` | `<job-dir>/main/` |
| `detail`、`pdp-detail` | `<job-dir>/detail/` |
| `extra`、`extras` | `<job-dir>/extras/` |
| `custom` | `<job-dir>/custom/` |

既不传 Prompt 也不传 `--about`，会直接报错退出。这是刻意设计：缺 Prompt 必须响亮失败，而不是静默生成一张默认图。

### 10. 常用配方

**A. 只出 Prompt，无需 API 密钥**

```bash
python3 scripts/generate_image.py \
  --mode prompt \
  --prompt "premium Amazon main image for a portable blender, clean white background, large product, concise benefit label" \
  --job-dir generated-images/portable-blender-pack-20260509-120000 \
  --asset-type main \
  --size 1024x1024
```

**B. 从 Prompt 目录一键并发批量出整套图包（推荐）**

```bash
JOB="generated-images/travel-pillow-pack-$(date +%Y%m%d-%H%M%S)"

python3 scripts/generate_image.py \
  --batch-dir prompts/ \
  --job-dir "$JOB" \
  --concurrency 3
```

- **自动识别与尺寸适配**：脚本按文件名自然顺序排序，自动根据文件名或子目录（`main/`、`detail/`、`angle/`）推导资产类别；详情页自动匹配 `1024x1536`，主图自动匹配 `1024x1024`。
- **连接复用与故障隔离**：多线程共享 HTTP Keep-Alive 连接池，单张图失败不会打断整个批处理任务。
- **审计报告自动生成**：生成完毕后自动在 `<job-dir>/batch-summary.json` 中保存每张图片的耗时、重试次数、Prompt 文件路径与生成产物路径。

*注：传统单文件串行方式（兼容保留）：*
```bash
for f in prompts/main-*.txt; do
  python3 scripts/generate_image.py --prompt-file "$f" --job-dir "$JOB" --asset-type main --size 1024x1024
done
```

**C. 用参考图锁定产品一致性**

```bash
python3 scripts/generate_image.py \
  --prompt-file prompts/angle-sheet.txt \
  --image product.png \
  --job-dir "$JOB" \
  --asset-type angle-sheet
```

`--image` 会把请求切到 `/images/edits`，并以 multipart 上传本地文件。支持的参考图格式：`png`、`jpg`、`jpeg`、`webp`。

**D. 指定独立凭证文件**

```bash
python3 scripts/generate_image.py \
  --env-file ~/.config/lumind/.env \
  --prompt-file prompts/main-01.txt \
  --job-dir "$JOB" --asset-type main
```

### 11. 故障排查

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `图片 API 配置未完整，已按 auto 模式只输出 Prompt。` | 凭证不完整 | 完成第 6 步，或确认就是要只出 Prompt |
| `image 模式需要完整图片 API 配置。缺少配置：...` | 配置不完整却用了 `--mode image` | 刻意硬失败，避免你要图却静默拿到 Prompt |
| `图片接口返回 HTTP <状态码>：...` | 服务商拒绝请求 | 响应体会原样打印。检查模型名、尺寸支持、额度与密钥权限。若返回 `502` 且内容含 `connection refused`，说明你的接口地址可达但后端上游不通 |
| `无法连接图片接口：...` | 网络或接口地址问题 | 在同一台机器上确认 `IMG_BASE_URL` 可达 |
| `不支持的参考图片格式：.gif，仅支持 png/jpg/jpeg/webp。` | `--image` 扩展名不支持 | 转成上述四种之一 |
| `参考图片不存在：<路径>` | `--image` 路径写错 | 相对路径按当前工作目录解析 |
| `无法读取 prompt 文件：...` | `--prompt-file` 路径写错 | 修正路径，或改用 `--prompt` |
| Prompt 已保存但没有图片 | `auto` 模式且无凭证 | 预期行为，见第 6 步 |
| 宿主列表里没有这个技能 | 技能目录不对，或会话未重启 | 回到第 2 步确认目录，修好后重启宿主 |

`--size 1024x1536` 并非所有服务商都支持。若接口拒绝该尺寸，请请求最接近的可用尺寸，并相应调整你的版式 —— 本技能默认的详情页比例是 2:3。

---

## 实战场景与用法

### 零代码自然语言调用
在 AI Agent 中以对话形式发起任务：

```text
用 lumind-product-shot 给这款便携榨汁杯做 Amazon US PDP 图包：
目标人群是健身和通勤人群，卖点是 20 秒打碎、USB-C 充电、便携防漏。
输出 5 张主图 + 8 张详情页图，先给 Prompt；如果本地 API 配置齐全就直接出图。
```

### 进阶命令行调用

<details>
<summary><b>点击查看更多高级用法</b></summary>

**仅输出 Prompt 策略文件：**
```bash
python3 scripts/generate_image.py \
  --mode prompt \
  --prompt "premium Amazon main image for a portable blender, clean white background, large product, concise benefit label" \
  --job-dir generated-images/portable-blender-pack-20260509-120000 \
  --asset-type main \
  --size 1024x1024
```

**从预设文件自动生成：**
```bash
python3 scripts/generate_image.py \
  --prompt-file prompts/main-01.txt \
  --job-dir generated-images/portable-blender-pack-20260509-120000 \
  --asset-type main
```

**基于产品参考图生成一致性资产（Product Angle Sheet）：**
```bash
python3 scripts/generate_image.py \
  --prompt-file prompts/angle-sheet.txt \
  --image product.png \
  --job-dir generated-images/portable-blender-pack-20260509-120000 \
  --asset-type angle-sheet
```

</details>

---

## 核心引擎与工作流

### 智能执行链路
1. **多级上下文补齐**：自动按权重补全信息缺失（用户输入 > 附件上下文 > 自动联网研究 > 逻辑推理 > 默认假设）。
2. **转化驱动洞察**：智能剖析当前商品属于 Visual-Driven、Pain-Driven 还是 Emotion-Value-Driven。
3. **策略卡输出**：生成 `Buyer Reason Card`（购买理由卡），定调英文基准文案与核心 CTA。
4. **视觉风格锁定**：建立全局 `Campaign Style Lock`，确保几十张套图风格严丝合缝。
5. **按需直接交付**：用户明确指令且 API 就绪时，直接调用内部脚本渲染出完整资产图包。

### 智能合规偏好（Compliance Engine）
系统默认**关闭**合规审查以保证创意自由度。若您要求“开启合规 / 风险审查”：
- 将严格过滤功效承诺、医疗暗示、绝对化用语及不当比较。
- 强制要求数据、认证、销量及用户真实评价来源合法且可验证。
- 没有真实素材时，自动以功能解析 / FAQ / 场景代替评价区块。

### 主动提问与容错机制
当核心信息（如产品本体、核心受众、目标平台等）缺失时，Agent 会发起不超过 3-5 个核心提问。若得到“你看着办”或“快速出图”的授权，系统将自动启用**假设与推断**能力继续流程，并在输出末尾高亮提示 `Assumptions / Defaults Used`，充分保证流程通畅。

---

## 输出交付规范

系统会为每一次产出规划清晰的任务流目录结构，方便后续人工审核及 A/B 测试：

```text
generated-images/<product-slug>-pack-<yyyymmdd-hhmmss>/
  ├── angle-sheet/  # 临时产品角度基准图（用于一致性控制）
  ├── main/         # 主图组（1024x1024）
  ├── detail/       # 详情页长图组（1024x1536）
  ├── prompts/      # 每张资产图的独立执行 Prompt
  ├── extras/       # 接口额外生成的变体或备选图
  └── custom/       # 临时调试与自定义生成图
```

### 图片包黄金法则
只要提到“详情页 / PDP / 主图堆栈 / 整套商品图”，Skill 默认遵循以下交付模型：
- **5 张主图**：首图卖点 → 机制解析 → 利益证明 → 场景对比 → 优惠保障。
- **7-9 张详情图**：首屏承接 → 痛点放大 → 机制解释 → 步骤场景 → 竞品对比 → 好评背书 → 风险逆转 (CTA)。
- 每张图**独立 Prompt** 生成，拒绝劣质拼图，强制应用全局 Style Lock。

---

## 三大转化驱动模型（Conversion Drivers）

| 驱动模式 | 适用场景 | 策略重心 |
| --- | --- | --- |
| **Visual-Driven** | 外观、质感、礼品感强、前后对比明显的产品 | 极致的视觉主张、质感放大、场景匹配、扫读利益点 |
| **Pain-Driven** | 解决反复烦恼、降低风险、提升效率的产品 | 痛点挖掘 → 机制解析 → 利益证明 → 信任背书 → CTA |
| **Emotion-Value** | 表达自我身份、归属感、社交地位或冲动消费品 | 情绪钩子、身份叙事、社交信号放大、低摩擦引导 |

---

## 局限性说明
- **生图能力边界**：当前支持文本生图与单张产品参考图生图，暂不支持基于 mask 的精准局部重绘。
- **外部接口依赖**：高度依赖 OpenAI 兼容的 Images API。图像质量、连贯性与耗时取决于您配置的底层模型（如 DALL·E 3 / Flux 等）及服务商。
- **转化归因**：本 Skill 输出为高转化潜力的策略与创意基线，真实商业回报（CTR/CVR/AOV）仍受限于您的产品力、市场定价与流量采买策略。
- **图内声称未经核验**：合规审查默认关闭，因此生成的图可能包含虚构的价格、徽章、保障承诺、评价数量与用户好评。请把这类元素一律当作占位符。上架前替换为真实、可核验的商家数据，是使用者自己的责任；Amazon、Shopify、TikTok Shop 的平台合规同样由使用者承担。

---

## 许可证

本项目基于 MIT License 开源发布，版权归 2026 落落无尘（Luoluo Wuchen）所有。完整文本见 [LICENSE](LICENSE)。
