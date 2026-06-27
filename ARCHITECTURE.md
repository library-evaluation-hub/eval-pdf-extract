# `eval-pdf-extract` — 架构设计

> 用于评估 PDF 提取库的标准化基准项目。
> 目标：在同一测试集与同一指标体系下，横向对比不同编程语言、不同实现原理的 PDF 提取库。

---

## 1. 设计目标与非目标

### 1.1 目标

| 目标             | 说明                                                                                                       |
| ---------------- | ---------------------------------------------------------------------------------------------------------- |
| **语言无关**     | 不偏向 Python/Java/Node/Go/Rust/.NET/C++ 任何一方；任意语言都能作为被评估方加入。                            |
| **指标固定**     | 评测指标是**写死**的固定集合（见 §5），不做插件式扩展。需要新指标必须改规范版本。                            |
| **测试集固定**   | 所有 library 在完全相同的 PDF 集与 ground truth 上运行，结果可直接对比。                                    |
| **结果可复现**   | 每个 adapter 锁版本、每个 fixture 内容寻址、每次 run 留独立物。                                             |
| **单机一键跑**   | 不依赖 Docker/K8s/云服务；只要本地装好各语言运行时即可。                                                    |
| **结果可浏览**   | 提供本地 Web UI，对比、查看 diff、查看错误日志。                                                            |

### 1.2 非目标（v1 不做）

- 分布式调度 / 容器编排
- 在线提交 / 协作评分平台
- OCR 模型本身的训练与评测（被测 library 内部可以有 OCR，但本项目只评估它**最终输出**的质量）
- 任意自定义指标 / 任意自定义报告（违反"指标固定"原则）

---

## 2. 顶层架构

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         eval-pdf-extract                                 │
│                                                                          │
│  ┌─────────────┐       ┌───────────────────────────────────────────┐     │
│  │  corpus/    │       │  adapters/  (一库一目录，独立子项目)        │     │
│  │  PDF + GT   │       │  ├─ python-pymupdf/                       │     │
│  │             │       │  ├─ python-pdfplumber/                    │     │
│  │  manifest   │       │  ├─ python-pdfminer/                      │     │
│  └──────┬──────┘       │  ├─ java-pdfbox/                          │     │
│         │              │  ├─ java-tika/                            │     │
│         │              │  ├─ nodejs-pdf-parse/                     │     │
│         │              │  ├─ nodejs-pdfjs/                         │     │
│         │              │  ├─ go-ledongthuc/                        │     │
│         │              │  ├─ rust-pdf-extract/                     │     │
│         │              │  ├─ dotnet-pdfpig/                        │     │
│         │              │  ├─ dotnet-itext/                         │     │
│         │              │  └─ cpp-mupdf/                            │     │
│         │              └──────────────────┬────────────────────────┘     │
│         │                                 │ CLI sub-process (JSON over   │
│         │                                 │   stdout, artifacts to dir)  │
│         ▼                                 ▼                              │
│  ┌───────────────────────────────────────────────────────────────┐       │
│  │  orchestrator/  (Python)                                      │       │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐    │       │
│  │  │  Runner  │──▶│  Scorer  │──▶│  Store   │──▶│  Report  │  │       │
│  │  └──────────┘   └──────────┘   └──────────┘   └──────────┘    │       │
│  └─────────────────────────────────┬─────────────────────────────┘       │
│                                    │                                     │
│                                    ▼                                     │
│  ┌─────────────────────────┐    ┌──────────────────────────┐             │
│  │  results/<run_id>/      │    │  webui/                  │             │
│  │  ├─ scores.csv          │    │  FastAPI + 静态前端      │              │
│  │  ├─ scores.db (sqlite)  │◀───│  只读浏览 / 对比         │              │
│  │  └─ <adapter>/<fx>/...  │    └──────────────────────────┘             │
│  └─────────────────────────┘                                             │
└──────────────────────────────────────────────────────────────────────────┘
```

**关键边界**：

- **orchestrator** 与 **adapter** 之间只通过 CLI + 文件系统 + JSON 通信。orchestrator 不知道也不关心 adapter 是用哪种语言写的。
- **orchestrator** 与 **webui** 之间只通过 `results/` 目录（sqlite + json 文件）通信。webui 是只读的。
- **adapter** 与 **corpus** 没有直接关系。orchestrator 负责把 fixture 路径喂给 adapter。

---

## 3. 目录结构

```
eval-pdf-extract/
├── ARCHITECTURE.md             ← 本文件
├── README.md
├── AGENTS.md                   ← 给 AI 协作者 / 接手者的指引
├── Makefile                    ← 一键入口：install / run / ui / lint
├── pyproject.toml              ← 项目元数据 + 依赖（src-layout）
│
├── src/                        ← Python 源码（src-layout，标准）
│   ├── orchestrator/           ←  主控
│   │   ├── __init__.py
│   │   ├── __main__.py         ←  python -m orchestrator run
│   │   ├── cli.py              ←  Click CLI 入口（run / validate-corpus / lint-adapter）
│   │   ├── runner.py           ←  调度 adapter CLI（planned）
│   │   ├── scorer.py           ←  调 metrics 计算（planned）
│   │   ├── metrics/            ←  固定指标实现（planned）
│   │   │   └── .gitkeep        ←  占位
│   │   ├── store.py            ←  sqlite + 文件落地（planned）
│   │   └── report.py           ←  summary.json 生成（planned）
│   └── webui/                  ←  本地浏览界面
│       ├── __init__.py
│       └── backend/            ←  FastAPI（只读）
│           ├── __init__.py
│           └── main.py         ←  python -m webui.backend.main
│
├── contract/                   ← 三份"宪法"，所有 adapter 必须遵守
│   ├── adapter-protocol.md     ←  CLI 调用契约
│   ├── result-schema.json      ←  result.json 的 JSON Schema
│   └── metric-spec.md          ←  固定指标的定义与算法
│
├── corpus/                     ← 评测语料（fixture 集合）
│   ├── manifest.json
│   ├── manifest.schema.json
│   └── fixtures/
│       └── <NN>_<category>__<slug>/
│           ├── input.pdf
│           ├── expected.json          ← ground truth，与 result.json 同 schema
│           ├── expected.example.json   ← （可选）样例
│           ├── meta.json              ← 类别、来源、license、sha256
│           └── meta.example.jsonc     ← （可选）meta 模板（含 # 注释）
│
├── adapters/                   ← 每个被评估 library 一个子目录
│   ├── registry.json           ←  adapter 注册表
│   ├── registry.schema.json
│   ├── _template/              ←  新 adapter 模板
│   ├── python-pymupdf/
│   │   ├── pyproject.toml
│   │   ├── README.md
│   │   └── src/adapter/__main__.py
│   ├── python-pdfplumber/
│   ├── ...
│   └── cpp-mupdf/
│       ├── CMakeLists.txt
│       └── src/main.cpp
│
├── webui/                      ← 静态前端（与 src/webui 区分）
│   └── frontend/               ←  静态 SPA
│
├── tests/                      ← 单元测试（pytest 扫这里）
│
├── results/                    ← 跑批产物（git 忽略，仅保留 sample/）
│   └── .gitkeep
│
└── scripts/
    ├── check-env.sh            ←  bash: 检查各语言运行时
    ├── check-env.ps1           ←  pwsh: 同上
    ├── lint-adapter.sh         ←  bash: 薄壳，转交 lint_adapter.py
    ├── lint-adapter.ps1        ←  pwsh: 同上
    ├── lint_adapter.py         ←  真正做契约校验（R1/R2/G1/C1/C2）
    └── clean.py                ←  跨平台清理
```

---

## 4. 核心契约（详见 `contract/`）

### 4.1 Adapter CLI 协议

每个 adapter 必须暴露一个可执行入口（命令名在 `adapters/registry.json` 中注册）：

```bash
<adapter-command> extract \
    --input   <pdf-path>            # 必填，输入 PDF
    --output-dir  <dir>             # 必填，产物输出目录（必须可写、可创建）
    --config  '<json-string>'       # 可选，library 专属参数
    --timeout <seconds, default 60> # 可选，软超时（adapter 应自检 + 自杀）
```

**输出契约**（写在 `--output-dir` 下）：

| 文件         | 必需 | 说明                                                                          |
| ------------ | ---- | ----------------------------------------------------------------------------- |
| `result.json` | ✅   | 提取结果，**必须**符合 `contract/result-schema.json`。                         |
| `meta.json`   | 〇   | adapter 自报的元信息：library 版本、内部耗时、是否触发 OCR 等。               |
| `stderr.log`  | 〇   | 进度/诊断信息（orchestrator 自动捕获到 `results/.../stderr.log`）。            |

**退出码**：

| Code | 含义                                  | orchestrator 行为                |
| ---- | ------------------------------------- | -------------------------------- |
| 0    | 成功（即使 result 为空也算）          | 进入评分                          |
| 64   | 输入不可读 / 格式不支持                | 记 `success=false, error=unsupported` |
| 65   | 内部解析错误                          | 记 `success=false, error=parse_error`  |
| 66   | 资源耗尽（OOM 等）                    | 记 `success=false, error=oom`          |
| 124  | 超时                                  | 记 `success=false, error=timeout`      |
| 其他 | 未分类失败                            | 记 `success=false, error=crash`        |

**硬约束**：

- adapter **不得**向 stdout 写非结构化内容（stdout 留给 result 以外的可选汇总，未来用于 in-band 协议）。
- adapter 必须是**纯函数式**：同样的 input + config 必须产出确定性的 result（同次构建内）。
- adapter 不允许访问网络（v1 假设完全离线）。

### 4.2 Result Schema（`result.json`）

顶层结构：

```jsonc
{
  "schema_version": "1.0.0",
  "pages": [
    {
      "page_number": 1,                 // 1-based
      "width": 612.0,                   // PDF user space units (pt)
      "height": 792.0,
      "text": "整页拼接后的纯文本",       // 阅读顺序
      "blocks": [
        {
          "id": "p1-b3",                // adapter 自取，仅需 page 内唯一
          "type": "heading|paragraph|list_item|table|image|caption|header|footer|unknown",
          "bbox": [x0, y0, x1, y1],     // PDF 坐标系，原点在左下
          "content": "文本内容（图块可空）",
          "reading_order": 5,           // 越小越靠前
          "children": []                // 嵌套块（如 list_item 的子项）
        }
      ],
      "tables": [
        {
          "id": "p1-t1",
          "bbox": [x0, y0, x1, y1],
          "rows": [["a","b"],["c","d"]],
          "headers": ["列1", "列2"]      // 可空
        }
      ]
    }
  ],
  "metadata": {
    "title": null,
    "author": null,
    "page_count": 1,
    "ocr_used": false
  }
}
```

完整字段定义与约束见 `contract/result-schema.json`。

**Ground truth（`expected.json`）使用同一 schema**——这让评分器可以做结构化 diff，而不是脆弱的字符串正则。

adapter 无法判定的字段填 `null` 或省略；评分器对 `null` 字段做"该指标不参与该 fixture 评分"的处理。

### 4.3 Adapter 注册表（`adapters/registry.json`）

```jsonc
{
  "adapters": [
    {
      "id": "python-pymupdf@1.24.0",       // 唯一 id，必须含版本
      "language": "python",
      "command": "python-pymupdf",         // 在 PATH 中可找到
      "description": "PyMuPDF (fitz) for Python",
      "homepage": "https://github.com/pymupdf/PyMuPDF",
      "timeout_seconds": 60
    },
    {
      "id": "java-pdfbox@3.0.2",
      "language": "java",
      "command": "java-pdfbox",
      "description": "Apache PDFBox",
      "homepage": "https://pdfbox.apache.org/",
      "timeout_seconds": 90
    }
  ]
}
```

orchestrator 只看 `command` 与 `id`，不解析 `language` 字段（仅作展示用）。

---

## 5. 固定指标体系（详见 `contract/metric-spec.md`）

### 5.1 一级指标（每对 adapter×fixture 都计算）

| 类别       | 指标 ID                       | 类型     | 取值范围 | 越高越好？ |
| ---------- | ----------------------------- | -------- | -------- | ---------- |
| 文本准确性 | `text_cer`                    | float    | [0, ∞)   | 否         |
| 文本准确性 | `text_wer`                    | float    | [0, ∞)   | 否         |
| 文本准确性 | `text_exact_page_match_ratio` | float    | [0, 1]   | 是         |
| 结构       | `table_detection_f1`          | float    | [0, 1]   | 是         |
| 结构       | `table_cell_value_f1`         | float    | [0, 1]   | 是         |
| 结构       | `heading_detection_f1`        | float    | [0, 1]   | 是         |
| 结构       | `reading_order_kendall_tau`   | float    | [-1, 1]  | 是         |
| 性能       | `wall_time_ms`                | int      | ≥0       | 否         |
| 性能       | `peak_memory_mb`              | float    | ≥0       | 否         |
| 性能       | `output_size_kb`              | float    | ≥0       | 否         |
| 鲁棒性     | `success`                     | bool     | 0/1      | 是         |
| 鲁棒性     | `partial_completion_ratio`    | float    | [0, 1]   | 是         |
| 鲁棒性     | `error_category`              | enum     | —        | n/a        |

### 5.2 算法概要

- **CER / WER**：归一化后（合并空白、统一引号）做 Levenshtein；WER 以空白分词。
- **Exact page match**：去掉所有空白后逐字符相等。
- **Table detection F1**：以 `bbox + IoU ≥ 0.5` 匹配；无表 fixture 的不参与聚合。
- **Table cell value F1**：在检测正确的表里对 `(row, col) → text` 做集合 F1。
- **Heading detection F1**：把 `type=heading` 的 block 与 GT heading 比对，`bbox + IoU ≥ 0.5` 视为匹配。
- **Reading order**：用块级 `reading_order` 序列与 GT 序列算 Kendall's tau。
- **Wall time / peak memory**：orchestrator 用 `time.monotonic` + `psutil`/`resource` 测量。
- **Success / partial ratio**：成功 = 退出码 0 + `result.json` 合法；partial = 已解析的页数 / 总页数。

### 5.3 聚合方式

- 跨 fixture 聚合：每个指标对**同类别**的 fixture 算均值（macro-average），并同时给出 micro / overall。
- 跨 adapter 排序：每个类别内独立排名，不出"总分"（避免人为加权；如需加权，在 webui 里提供"自定义权重视图"，但不参与存储）。

### 5.4 为什么"固定"

用户明确要求**只关注固定的几个评估指标**。所以：

- 不做指标插件接口；
- 不允许 adapter 自报指标；
- 新增指标需要 `metric-spec.md` 升 version、orchestrator 同步实现，旧结果不参与新指标计算但仍保留。

---

## 6. 测试语料（Corpus）

### 6.1 Fixture 类别（写死）

| ID    | 类别           | 数量目标 | 目的                          |
| ----- | -------------- | -------- | ----------------------------- |
| `01`  | 纯文本          | 3        | 基线 CER/WER                  |
| `02`  | 多栏排版         | 3        | 阅读顺序 / 列合并还原         |
| `03`  | 表格            | 3        | 表格检测 + 单元格值            |
| `04`  | 表单            | 2        | 结构化字段识别                |
| `05`  | 扫描件 / OCR    | 2        | 鲁棒性（OCR 路径）             |
| `06`  | 多语言（CJK 等） | 2        | 字体 / 编码鲁棒性              |
| `07`  | 边缘 case       | 3        | 加密、损坏、超大文件、空文档    |

每个 fixture 一个目录：`corpus/fixtures/<id>__<slug>/{input.pdf, expected.json, meta.json}`。

### 6.2 Ground Truth 制作流程

1. 选 PDF 来源（公开文档 / 自合成 / 已有数据集）。
2. 用 PyMuPDF + 人工校对生成 `expected.json`（与 result.json 同 schema）。
3. 计算 `meta.json` 中的 `sha256` 校验。
4. 提交 PR 评审后合并。

**禁止**用被测 library 之一单独生成 ground truth（避免对那个库过拟合）。

### 6.3 Manifest

`corpus/manifest.json`：

```jsonc
{
  "schema_version": "1.0",
  "fixtures": [
    {
      "id": "01_plain_text__lorem",
      "path": "fixtures/01_plain_text__lorem/input.pdf",
      "category": "plain_text",
      "tags": ["english", "single_column"],
      "difficulty": "easy",
      "expected_page_count": 1,
      "sha256": "..."
    }
  ]
}
```

---

## 7. 跑批与产物

### 7.1 Run 入口

```bash
# 跑所有 adapter
python -m orchestrator run --corpus corpus/ --adapters all

# 跑指定 adapter
python -m orchestrator run --adapters python-pymupdf@1.24.0,java-pdfbox@3.0.2

# 跑指定 fixture
python -m orchestrator run --fixture-glob '03_table__*'
```

### 7.2 产物布局

```
results/<run_id>/
├── run.json                              # run 配置、开始/结束时间、git SHA（可选）
├── scores.csv                            # 长表：run, adapter, fixture, metric, value
├── scores.db                             # sqlite（scores.csv + 索引 + summary 视图）
├── summary.json                          # 每个 adapter 的聚合指标
└── <adapter_id>/
    └── <fixture_id>/
        ├── result.json                   # adapter 输出
        ├── meta.json                     # adapter 报告
        ├── stdout.log
        ├── stderr.log
        ├── timings.json                  # orchestrator 实测：wall / mem
        └── score.json                    # 该对的全部指标值
```

### 7.3 并发

orchestrator 默认按 **adapter × fixture** 维度并发（线程池即可，subprocess 各自独立）；可加 `--workers N` 调。

GPU / IO 敏感 adapter 可通过 `--serialize <adapter_id>` 单独排队。

---

## 8. Web UI

技术选型：**FastAPI + 静态 HTML/JS**（不引入前端框架，避免体积膨胀；如未来需要再考虑 Preact / Svelte）。

页面：

| 路由                          | 功能                                                                          |
| ----------------------------- | ----------------------------------------------------------------------------- |
| `/`                           | 仪表盘：上次 run 的 leaderboard（每个指标一列排名），可切换 run                |
| `/runs`                       | 历史 run 列表，选择进入                                                        |
| `/adapters`                   | adapter 注册表 + 版本                                                          |
| `/fixtures`                   | 语料列表，按类别过滤                                                           |
| `/compare?fixtures=…&adapters=…` | 关键页面：选择 N 个 adapter × M 个 fixture，并排显示 ground truth vs 各结果（文本 diff + 结构 diff） |
| `/fixture/<id>`               | 单 fixture 全 adapter 对比详情                                                 |
| `/adapter/<id>`               | 单 adapter 全 fixture 详情 + 错误日志列表                                      |

只读，不写 `results/`；未来如要加"人工标注 / 重新评分"功能，作为 v2。

---

## 9. 添加新 Adapter 的流程

1. 复制 `adapters/_template/` 为 `adapters/<lang>-<lib>/`。
2. 编写适配代码，把 library 的输出转成 `result.json`（参考已有 adapter）。
3. 在 `adapters/<lang>-<lib>/README.md` 写明：被包装的 library、版本、已知不支持的特性。
4. 添加到 `adapters/registry.json`。
5. 跑 `make lint-adapter` 校验契约。
6. 跑 `python -m orchestrator run --adapters <id> --fixture-glob '01_*'` 冒烟。
7. 提交 PR。

**约束**：

- adapter 不许改 orchestrator 代码；如发现契约不足，先在 `contract/` 提 RFC。
- 每个 adapter 锁版本：CI 里跑"版本漂移检查"，提醒升级。

---

## 10. 关键技术决策记录（ADR 摘要）

| 决策                                       | 选择                          | 原因                                                                                  |
| ------------------------------------------ | ----------------------------- | ------------------------------------------------------------------------------------- |
| Orchestrator 语言                          | Python                        | 评测/分析生态最丰富；subprocess 与 JSON 处理便利；不要求被测方也用 Python。            |
| Adapter 调用方式                            | CLI 子进程                     | 语言无关、易部署、易隔离、CI 友好；微秒级 IPC 性能损失对 PDF 评测场景可忽略。          |
| 通信介质                                    | 文件 + JSON                   | 比 stdout 流式协议更鲁棒；崩溃时仍能看到部分结果。                                    |
| 指标体系                                    | 固定集合，不做插件             | 用户明确要求"只关注固定的几个指标"；减少维度爆炸与不可对比性。                        |
| Ground truth 格式                           | 与 result.json **同 schema**   | 让评分器做结构 diff 而非脆弱正则；统一心智模型。                                      |
| Web UI                                     | FastAPI + 静态 SPA            | 体积小、零构建、单文件可分发；如未来需要复杂交互再升级。                              |
| 持久化                                      | 文件树 + sqlite                | 文件树便于 diff / 归档；sqlite 便于 webui 查询。                                      |
| 并发                                        | 线程池调度 subprocess          | 简单可靠；adapter 自身已是独立进程，无需 asyncio。                                    |

---

## 11. 演进路线

- **v1（本次设计目标）**：上述全部。
- **v2 候选**（不在本次范围）：
  - OCR / 扫描件专项指标（Chars Confidence）
  - 渲染对比（adapter 输出渲染为图，与 PDF 原图做 SSIM）
  - 大文件流式处理与内存上限
  - Adapter Marketplace / 在线 leaderboard
  - 跨机器分布式跑批
