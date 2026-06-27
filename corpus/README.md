# Corpus 目录

> 评测语料：固定的 PDF fixture 集合 + 手写 ground truth。

## 目录约定

```
corpus/
├── manifest.json                       # fixture 清单（受 manifest.schema.json 约束）
├── manifest.schema.json
├── tools/                              # 生成/校验 fixture 的辅助脚本
└── fixtures/
    └── <NN>_<category>__<slug>/
        ├── input.pdf                   # 测试 PDF（建议 ≤ 5 MB）
        ├── expected.json               # ground truth，符合 contract/result-schema.json
        ├── expected.example.json       # （可选）给 fixture 维护者参考的示例
        ├── meta.json                   # fixture 元信息：来源、license、sha256
        ├── meta.example.jsonc          # （可选）meta.json 的模板（含 # 注释）
        └── notes.md                    # （可选）人读注释
```

> 命名约定：所有 `.example.json` / `.example.jsonc` 是**模板/示例**，
> 不会被 `make validate-corpus` 当作真实 fixture 读取。`.jsonc`
> 表示文件含 JSONC 风格的 `#` 行注释，复制时直接保留即可。

## 类别（写死，与 `manifest.schema.json` 对齐）

| ID    | category        | 数量目标 | 验证什么                       |
| ----- | --------------- | -------- | ------------------------------ |
| 01    | `plain_text`    | 3        | CER / WER / 整页精确匹配        |
| 02    | `multi_column`  | 3        | 阅读顺序 / 列切分                |
| 03    | `table`         | 3        | 表格检测 + 单元格值              |
| 04    | `form`          | 2        | 表单字段识别                    |
| 05    | `scanned`       | 2        | 鲁棒性（OCR 路径）              |
| 06    | `multilang`     | 2        | 字体 / 编码鲁棒性                |
| 07    | `edge`          | 3        | 加密、损坏、空文档、超大文件     |

## 制作流程

1. 选来源（公开文档 / 自合成 / 现有数据集），确认 license 允许。
2. 用 PyMuPDF（或其他参考实现）生成初版 `expected.json`。
3. **必须**人工逐页校对 ground truth。
4. 计算 `input.pdf` 的 sha256，填入 `meta.json`。
5. 同步更新 `corpus/manifest.json`。
6. 跑 `make validate-corpus` 确认一致性。

## 硬约束

- 不要**只用**一个被测 library 来生成 ground truth（会过拟合到那个库）。
- 真实文档注意脱敏（PII、机密）。
- `expected.json` 一旦发布进 `main` 分支即视为"权威 ground truth"；修改需新 PR + 在 `meta.json` 的 `revisions` 里记录。
- `meta.json` 是**严格 JSON**（支持 `json.load`），不能含 `#` 注释。需要注释请用 `meta.example.jsonc` 模板形式给出。
