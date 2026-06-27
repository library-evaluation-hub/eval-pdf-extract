# `eval-pdf-extract`

跨编程语言、跨实现的 PDF 提取库**标准化基准评测**项目。

> 在同一份测试集与同一组指标下，横向对比 PyMuPDF / PDFBox / Tika / pdf-parse / pdfjs / pdf-extract / PdfPig / iText / MuPDF 等 library。

详细设计见 [`ARCHITECTURE.md`](./ARCHITECTURE.md)；契约规范在 [`contract/`](./contract/)。

---

## 项目结构

```
eval-pdf-extract/
├── ARCHITECTURE.md        ← 架构总览
├── contract/              ← 三份契约（adapter 协议 / result schema / 固定指标）
├── corpus/                ← 测试语料（PDF + ground truth）
├── adapters/              ← 各被测 library 的 CLI 适配器
├── src/                   ← Python 源码（src-layout）
│   ├── orchestrator/      ← 主控：调度、评分、落盘
│   └── webui/backend/     ← FastAPI 后端
├── webui/frontend/        ← 静态前端
├── tests/                 ← 单元测试
├── results/               ← 跑批产物（git 忽略）
└── scripts/               ← 辅助脚本（.sh + .ps1 双轨）
```

## 快速开始

```bash
# 1. 安装 orchestrator + webui 依赖
uv sync --extra dev --extra webui

# 2. 检查环境：所有语言的运行时是否齐备
make check-env

# 3. 跑一次基准（默认所有 adapter × 所有 fixture）
make run

# 4. 启动 webui 浏览结果
make webui
# → http://localhost:8765
```

## 添加一个被测 library

参见 [`ARCHITECTURE.md` §9](./ARCHITECTURE.md#9-添加新-adapter-的流程)：

1. `cp -r adapters/_template adapters/<lang>-<lib>/`
2. 实现 `extract` 子命令，按 [`contract/result-schema.json`](./contract/result-schema.json) 输出
3. 在 [`adapters/registry.json`](./adapters/registry.json) 注册
4. `make lint-adapter ADAPTER=<lang>-<lib>`
5. 提交 PR

## 指标

固定 13 个指标，分 4 类：文本准确性、结构、性能、鲁棒性。详见 [`contract/metric-spec.md`](./contract/metric-spec.md)。

> **注意**：本项目不接受自定义指标。如需新指标，请提 RFC 并升级 `metric-spec.md` 版本。

## 贡献

- Bug / 文档：直接 PR
- 新 fixture：放 `corpus/fixtures/<NN>_<category>__<slug>/`，更新 `corpus/manifest.json`
- 新 adapter：见上
- 契约变更：在 [`ARCHITECTURE.md`](./ARCHITECTURE.md) 中记录 ADR 后再改代码

## License

TBD
