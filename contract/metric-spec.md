<!-- metric_spec_version: "1.0" -->
# 固定指标体系（v1.0）

本文档定义 `eval-pdf-extract` 的**全部**评分指标。所有 adapter 在所有 fixture 上都会被计算同一组指标。

配套阅读：

- Adapter 调用协议：[`adapter-protocol.md`](./adapter-protocol.md)
- 结果输出 schema：[`result-schema.json`](./result-schema.json)

---

## 1. 设计原则

1. **固定集合**：本项目不暴露自定义指标接口。如需新指标，**必须**升本文件 version 号，并在 orchestrator 同步实现。
2. **同结构对比**：ground truth 与 adapter 输出使用**同一 schema**（`result-schema.json`），因此评分器以结构化方式工作，而非脆弱的字符串正则。
3. **指标不可加权**：orchestrator **不**输出"总分"。聚合只在 webui 里以"自定义权重视图"呈现，**不**写入持久化结果。
4. **缺失字段的处理**：adapter 无法判定某字段时填 `null` 或省略；评分器跳过该字段对应的指标，并记录到 fixture 级 `skipped_metrics[]`。
5. **聚合策略**：每个类别内 macro-average；同时记录 overall 与 per-category；详见 §4。

---

## 2. 指标清单

| 类别     | ID                                | 类型     | 范围      | 越高越好 |
| -------- | --------------------------------- | -------- | --------- | -------- |
| 文本     | `text_cer`                        | float    | [0, ∞)    | 否       |
| 文本     | `text_wer`                        | float    | [0, ∞)    | 否       |
| 文本     | `text_exact_page_match_ratio`     | float    | [0, 1]    | 是       |
| 结构     | `table_detection_f1`              | float    | [0, 1]    | 是       |
| 结构     | `table_cell_value_f1`             | float    | [0, 1]    | 是       |
| 结构     | `heading_detection_f1`            | float    | [0, 1]    | 是       |
| 结构     | `reading_order_kendall_tau`       | float    | [-1, 1]   | 是       |
| 性能     | `wall_time_ms`                    | int      | ≥ 0       | 否       |
| 性能     | `peak_memory_mb`                  | float    | ≥ 0       | 否       |
| 性能     | `output_size_kb`                  | float    | ≥ 0       | 否       |
| 鲁棒性   | `success`                         | bool     | 0/1       | 是       |
| 鲁棒性   | `partial_completion_ratio`        | float    | [0, 1]    | 是       |
| 鲁棒性   | `error_category`                  | enum     | —         | n/a      |

共 **13** 个指标。任何跑批都会产生这 13 个值（或对缺失字段标记 skipped）。

---

## 3. 各指标定义与算法

### 3.1 文本准确性

#### `text_cer` — Character Error Rate

- 输入：`expected.pages[i].text` 与 `result.pages[i].text`，按 `page_number` 对齐。
- 归一化（两边都做）：
  - 合并连续空白为单个空格
  - 去除首尾空白
  - 引号标准化：`""'' → "`，`—– → -`
- 计算：Levenshtein 距离 `d`，`cer = d / len(reference)`。
- 若 reference 为空：`cer = 0.0 if hypothesis 为空 else 1.0`。
- 聚合：每页 cer 求 macro 平均。

#### `text_wer` — Word Error Rate

- 与 `cer` 相同的归一化 + 分词（以 `\s+` 分词）。
- `wer = levenshtein(tokens_ref, tokens_hyp) / len(tokens_ref)`。
- reference 为空时同上规则。

#### `text_exact_page_match_ratio`

- 归一化后逐字符完全相等则该页记 1，否则记 0。
- ratio = 匹配页数 / 评估页数。

### 3.2 结构

#### `table_detection_f1`

- 在 ground truth 含至少 1 个表的 fixture 上计算；否则 skipped。
- 把每页的 `tables[].bbox` 视为检测框。
- 匹配规则：bbox IoU ≥ **0.5** 视为匹配。
- 用贪心匹配计算 TP / FP / FN，再算 precision / recall / F1。
- 返回 F1（macro across pages）。

#### `table_cell_value_f1`

- 仅对**已检测正确**的表（IoU ≥ 0.5）计算。
- 键的构建**不依赖 `table.id`**（id 在 schema 中是可选字段），
  改用 IoU 匹配确定的配对顺序：`(match_index, row, col) → text`，
  其中 `match_index` 是该配对在所有匹配对中的顺序。
- 计算匹配键集合与 reference 键集合的 F1（文本完全相等）。
- 缺失格子按 `""` 处理。

#### `heading_detection_f1`

- 在 ground truth 含至少 1 个 heading 的 fixture 上计算。
- 用 `blocks[].type == "heading"` 作为检测结果；按 `bbox` IoU ≥ 0.5 匹配。
- 计算 F1（与表格检测同算法）。

#### `reading_order_kendall_tau`

- 输入：page 内所有 blocks 的 `reading_order` 序列（按其**真实顺序**排出），与 reference 的对应序列。
- 实现：Kendall's tau-b（处理 ties）。
- 范围 [-1, 1]。参考值：相同序 = 1，完全逆序 = -1。
- 无 block 的页：skipped。

### 3.3 性能

#### `wall_time_ms`

- 由 orchestrator 用 `time.monotonic()` 在 subprocess 外层测量，包含进程启动 + adapter 启动 + 实际工作 + 退出。
- 单位毫秒，取整。

#### `peak_memory_mb`

- v1 优先级方案：
  1. 优先读取 `meta.json.execution.peak_memory_mb_self`（adapter 自报）。
  2. 否则 orchestrator 用 `psutil` / `resource.getrusage` 测量子进程峰值 RSS。
  3. 跨平台实现不可靠时，记录 `null` 并跳过（**不**报错）。

#### `output_size_kb`

- `<output-dir>` 全部文件总字节数 / 1024。

### 3.4 鲁棒性

#### `success`

- `true` 当且仅当：
  - 退出码 == 0
  - `result.json` 存在
  - `result.json` 通过 `result-schema.json` 校验
  - `len(result.json.pages) == expected.metadata.page_count`

#### `partial_completion_ratio`

- `result.pages[].page_number` 集合大小 / `expected.metadata.page_count`。
- 完全失败 → 0；完全成功 → 1。

#### `error_category`

- 枚举：`none | bad_args | unsupported | parse_error | oom | timeout | crash`
- 退出码 → 类别映射见 [`adapter-protocol.md` §3](./adapter-protocol.md#3-退出码)。
- 当 `success == true` 时固定为 `none`。

### 3.5 零页 / 空文档

fixture 是空 PDF（`expected.metadata.page_count == 0` 且 `expected.pages == []`）时，
adapter 正确行为是返回 `result.pages == []` 与 `result.metadata.page_count == 0`。
这是 7 类 edge fixture 的核心鉴别点之一：库要能识别"空"，而不是崩溃或伪造。

各指标在零页情形下的取值规则：

| 指标                          | result=0 页（正确）        | result≥1 页（错误）                |
| ----------------------------- | -------------------------- | ---------------------------------- |
| `text_cer`                    | `0.0`                      | `1.0`                              |
| `text_wer`                    | `0.0`                      | `1.0`                              |
| `text_exact_page_match_ratio` | `1.0`（vacuous，0/0）        | `0.0`                              |
| `table_detection_f1`          | skipped                    | skipped（GT 无表）                  |
| `table_cell_value_f1`         | skipped                    | skipped                            |
| `heading_detection_f1`        | skipped                    | skipped                            |
| `reading_order_kendall_tau`   | skipped                    | skipped                            |
| `wall_time_ms`                | 正常测量                    | 正常测量                            |
| `peak_memory_mb`              | 正常测量                    | 正常测量                            |
| `output_size_kb`              | 正常测量                    | 正常测量                            |
| `success`                     | `true`                     | `false`                            |
| `partial_completion_ratio`    | `1.0`（vacuous）            | `0.0`                              |
| `error_category`              | `none`                     | `none`（执行成功但语义错）          |

补充说明：

- **`success`**：`len(result.json.pages) == expected.metadata.page_count` 在 0/0 时成立，0 页正确处理视为成功。这是 §3.4 条件的自然延伸。
- **`partial_completion_ratio`**：当 `expected.page_count == 0` 时，定义见下表（避免 0/0 歧义）：

  | expected | result | partial_completion_ratio |
  | -------- | ------ | ------------------------ |
  | 0        | 0      | 1.0（vacuous）            |
  | 0        | N ≥ 1  | 0.0                      |
  | N ≥ 1    | M      | `min(M, N) / N`          |

- **CER / WER**：reference 为空时的既有规则（`cer = 0.0 if hypothesis 为空 else 1.0`）覆盖零页情形。

---

## 4. 聚合策略

orchestrator 持久化**长表**（一行 = 一个 `(run, adapter, fixture, metric, value)`），
聚合计算在 webui 实时进行，但 orchestrator 也写一份 `summary.json`：

```jsonc
{
  "per_adapter": {
    "<adapter_id>": {
      "per_category": {
        "text":   { "text_cer": 0.05, "text_wer": 0.12, ... },
        "structure": { ... },
        "performance": { ... },
        "robustness":   { ... }
      },
      "per_metric_overall": { "text_cer": 0.06, ... }
    }
  }
}
```

聚合方式：

- **macro**：同一 metric 在同类别的多个 fixture 上取算术平均。
- **overall**：跨所有 fixture 算 macro（不按类别大小加权）。
- 若某 metric 在某 fixture 上 skipped，则不计入平均（**不**按 0 替代）。
- 性能类指标（`wall_time_ms` 等）**单独**算 overall，不混入结构/文本平均。

---

## 5. 不做的事

明确**不**做，避免被误以为是隐含承诺：

- 不做 BLEU / ROUGE（PDF 文本提取不是生成任务）。
- 不做 OCR Confidence（由各 library 内部决定，本项目不强制要求输出）。
- 不做"渲染相似度"（PDF 提取本质是文本/结构任务，非像素重建）。
- 不做总分加权（见 §1.3）。
- 不做指标的运行时配置（CLI 参数），如需调整需改本文件并 bump version。

---

## 6. 版本策略

- 本文件变更必须 bump `metric-spec` 的 version（位于本文件顶部）。
- 旧 run 的结果**不**回填新指标；新指标只对未来 run 生效。
- orchestrator 在 `run.json` 里记录使用的 `metric-spec` 版本，便于复现对比。
