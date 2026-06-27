# Adapter CLI 协议（v1.0）

本文档是 `contract/` 下三份契约之一，定义 **orchestrator ↔ adapter** 之间的调用接口。
任何 adapter **必须**严格遵守本协议，否则 `make lint-adapter` 校验将失败。

配套阅读：

- 结果输出格式：[`result-schema.json`](./result-schema.json)
- 评分指标定义：[`metric-spec.md`](./metric-spec.md)

---

## 1. 可执行入口

每个 adapter 在 `adapters/registry.json` 里登记一条记录，其中 `command` 字段必须是**在 PATH 中可直接调用**的可执行名（或带路径的可执行文件）。

```jsonc
{
  "id": "python-pymupdf@1.24.0",
  "command": "python-pymupdf",       // ← 必须是 PATH 中可解析
  "language": "python"               // 仅展示用
}
```

入口实现可以是：

- 原生二进制（Go / Rust / C++ / C# AOT）
- 解释器 + 脚本：`python -m my_adapter`、`node ./main.js`、`java -jar adapter.jar`
- shell wrapper：`my-adapter.sh`

只要 `command` 在 PATH 里能被 orchestrator 直接 exec 即可。

---

## 2. 子命令

### 2.1 `extract`（必需）

```text
<command> extract \
    --input <pdf-path> \
    --output-dir <dir> \
    [--config <json-string>] \
    [--timeout <seconds>]
```

| 参数          | 类型     | 必需 | 默认值 | 说明                                              |
| ------------- | -------- | ---- | ------ | ------------------------------------------------- |
| `--input`     | path     | ✅   | —      | 输入 PDF 绝对路径；文件存在且可读。                |
| `--output-dir`| path     | ✅   | —      | 产物输出目录；orchestrator 会**先创建并清空**。     |
| `--config`    | json str | 〇   | `{}`   | library 专属参数；见 §2.3。                        |
| `--timeout`   | int      | 〇   | 60     | 软超时秒数；adapter 自行检测并尽快退出。          |

任何未知参数 → 打印 usage 到 stderr，退出码 `2`。

### 2.2 输出（写于 `--output-dir`）

```
<output-dir>/
├── result.json     ← 必需，符合 result-schema.json
├── meta.json       ← 推荐，自报 library 元信息（schema 见 §2.4）
└── (可选) 其他产物文件，由 adapter 自行决定；orchestrator 不解析
```

orchestrator 在调用结束后额外写：

```
<run-results>/<adapter>/<fixture>/
├── stdout.log             ← 捕获的 stdout
├── stderr.log             ← 捕获的 stderr
├── timings.json           ← orchestrator 实测
└── score.json             ← 该对的全部指标值
```

### 2.3 `--config` 字段约定

config 是 JSON 字符串，schema **不**做强制约束（让 adapter 自由发挥），但建议约定如下以便复用：

```jsonc
{
  "ocr": {
    "enabled": false,           // 是否允许触发 OCR
    "languages": ["en"]         // OCR 语言
  },
  "pages": [1, 2, 3],           // 仅处理指定页（null = 全部）
  "max_pages": null,            // 限制页数（冒烟用）
  "extract": {
    "text": true,
    "tables": true,
    "images": false,
    "metadata": true
  }
}
```

orchestrator 默认传 `{"ocr":{"enabled":true}}`，允许 adapter 自行判断是否真的触发。

### 2.4 `meta.json` 建议 schema

```jsonc
{
  "library": {
    "name": "PyMuPDF",
    "version": "1.24.0",
    "language": "python"
  },
  "execution": {
    "ocr_used": false,
    "ocr_engine": null,
    "wall_time_ms_self": 42.1,    // adapter 自报的内部耗时
    "peak_memory_mb_self": 18.7   // 可选
  },
  "warnings": []
}
```

orchestrator **不**强制验证该文件，但会用 `library.version` 做适配性检查（与 registry 中登记的版本是否一致）。

---

## 3. 退出码

| Code  | 语义                                | orchestrator 记录为 `error_category` |
| ----- | ----------------------------------- | ------------------------------------ |
| `0`   | 成功                                | `none`                               |
| `2`   | 命令行参数错误                       | `bad_args`                           |
| `64`  | 输入不可读 / 不支持的文件格式        | `unsupported`                        |
| `65`  | 内部解析错误（PDF 损坏、解析异常）   | `parse_error`                        |
| `66`  | 资源耗尽（OOM 等）                  | `oom`                                |
| `124` | 超时                                | `timeout`                            |
| 其他  | 未分类失败                          | `crash`                              |

adapter **应**尽量使用语义化退出码；orchestrator 会把任何非 0 视为失败。

---

## 4. 硬约束（Hard Constraints）

以下约束由 `make lint-adapter` 静态校验：

1. **stdout 纯净**：除可选的 JSON 汇总（v1 暂未使用）外，**不得**写非结构化文本到 stdout。
   所有日志、调试信息、进度提示一律走 stderr。
2. **可重入**：同一 input + config 在同一次构建中必须产生 byte-identical 的 `result.json`。
   （OS 时间戳、临时文件路径等不能进 result。）
3. **无副作用**：adapter 不得写 `--output-dir` 之外的任何文件、不得访问网络、不得 fork daemon。
4. **沙箱友好**：不依赖 GUI、不依赖特定用户、不读 `~/.config` 等隐式配置。
5. **错误不退化**：解析失败时必须返回退出码 `65`，**不要**返回空 `result.json` + 退出码 `0`。
6. **schema_version**：result.json 顶层 `schema_version` 字段必须存在且形如 `\d+\.\d+\.\d+`。

---

## 5. 编排流程示例

orchestrator 内部对一个 `(adapter, fixture)` 调用的伪代码：

```python
def run_one(adapter_cmd, fixture, timeout):
    out_dir = f"results/{run_id}/{adapter_id}/{fixture_id}"
    shutil.rmtree(out_dir, ignore_errors=True)
    Path(out_dir).mkdir(parents=True)

    start = time.monotonic()
    proc = subprocess.run(
        [adapter_cmd, "extract",
         "--input", fixture.input_pdf,
         "--output-dir", out_dir,
         "--config", json.dumps(default_config),
         "--timeout", str(timeout)],
        capture_output=True, text=True, timeout=timeout + 5,  # +5s grace
    )
    wall_ms = int((time.monotonic() - start) * 1000)

    (Path(out_dir) / "stdout.log").write_text(proc.stdout)
    (Path(out_dir) / "stderr.log").write_text(proc.stderr)

    return ParsedRun(
        exit_code=proc.returncode,
        wall_time_ms=wall_ms,
        has_result=(Path(out_dir) / "result.json").exists(),
        error_category=classify_exit_code(proc.returncode, (Path(out_dir) / "result.json").exists()),
    )
```

---

## 6. 调试技巧

- 手动调用：`python-pymupdf extract --input corpus/fixtures/01_plain_text__lorem/input.pdf --output-dir /tmp/r1`
- 看结果：`cat /tmp/r1/result.json | jq .`
- 校验契约：`make lint-adapter ADAPTER=python-pymupdf`
