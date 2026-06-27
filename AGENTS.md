# AGENTS.md

> 给 AI 协作者 / 新接手者的指引。读完本文件 + `ARCHITECTURE.md` 后再动手。

## 项目定位

`eval-pdf-extract` 是一个**基准评测项目**，不是 PDF 解析工具本身。它的核心是：

1. 一组**固定**的 PDF 测试样本（`corpus/`）
2. 一组**固定**的评分指标（`contract/metric-spec.md`）
3. 一套**标准**的 CLI 适配契约（`contract/adapter-protocol.md` + `contract/result-schema.json`）
4. 一个**主控**（`orchestrator/`）调度各种语言的 adapter，落地结果
5. 一个**只读** web UI（`webui/`）让用户对比浏览

## 不要做的事

- **不要**新增自定义指标接口。本项目指标固定。如果觉得需要新指标，先在 `contract/metric-spec.md` 升 version 并在 PR 里说明动机。
- **不要**让 adapter 直接写 stdout（调试信息一律走 stderr）。stdout 是契约保留通道。
- **不要**让 adapter 访问网络、读 `~/.config`、写 `--output-dir` 之外的文件。
- **不要**在 `result.json` 里塞时间戳、临时路径等不可重入字段。
- **不要**让 orchestrator 解析 adapter 内部的 library API；只信 `result.json` + `meta.json`。
- **不要**为单个 adapter 做特殊优化路径；要么遵守契约，要么改契约。
- **不要**新增总分 / 加权机制。聚合只能在 webui 里以"自定义视图"呈现，不进存储。

## 编码规范

- Python（orchestrator / webui）：类型注解必填；`ruff` + `mypy` 必过。
- 跨语言 adapter：各自项目的 README 注明版本锁；CI 里 `make lint-adapter` 检查契约。
- 所有 JSON 配置文件：用仓库内的 `*.schema.json` 校验。
- 提交前必须跑：`make lint && make test`。

## 常见任务清单

### 跑批失败排查

1. 看 `results/<run_id>/<adapter>/<fixture>/stderr.log`
2. 看 `timings.json` —— 是否超时
3. 看 `result.json` —— 是否 schema 校验失败
4. 用 `make lint-adapter ADAPTER=<id>` 验证契约

### 添加 fixture

1. 选类别（plain_text / multi_column / table / form / scanned / multilang / edge）
2. 命名：`corpus/fixtures/<NN>_<category>__<slug>/`
3. 三个文件：`input.pdf`、`expected.json`（与 result.json 同 schema）、`meta.json`（含 sha256）
4. 更新 `corpus/manifest.json`
5. `make validate-corpus`

### 添加 adapter

见 `ARCHITECTURE.md` §9。**先写 contract/ 里的 RFC**，再写代码。

### 修改契约

1. 在 `ARCHITECTURE.md` §10 加 ADR 条目
2. bump 受影响 schema 的 version
3. 更新所有现存 adapter（grep 一下）
4. bump `metric-spec.md` / `adapter-protocol.md` / `result-schema.json` 的版本
5. 在 PR description 里说明破坏性影响

## 目录导航

| 想看什么              | 看哪里                                       |
| --------------------- | -------------------------------------------- |
| 整体怎么工作          | `ARCHITECTURE.md`                            |
| Adapter 怎么被调用    | `contract/adapter-protocol.md`               |
| Result 长什么样       | `contract/result-schema.json`                |
| 怎么打分              | `contract/metric-spec.md`                    |
| 跑了哪些 library      | `adapters/registry.json`                     |
| 测试样本              | `corpus/manifest.json` + `corpus/fixtures/`  |
| 上次跑的结果          | `results/<run_id>/summary.json`              |
| Web UI 怎么用         | `webui/README.md`                            |

## 测试

- `make test` —— 跑 Python 单元测试（orchestrator / scorer / metrics）
- `make integration-test` —— 跑真实 adapter × fixture（耗时）
- `make lint-adapter ADAPTER=<id>` —— 单 adapter 契约静态校验
- `make validate-corpus` —— 校验 fixture 与 manifest 一致性
