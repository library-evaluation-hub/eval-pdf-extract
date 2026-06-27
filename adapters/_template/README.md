# Adapter 模板（Python）

复制本目录并替换 `<lang>-<lib>` 来创建一个新 adapter：

```bash
cp -r adapters/_template adapters/python-mylib
# 修改 name、command、实现 src/adapter/__main__.py
```

## 目录结构（建议）

```
python-mylib/
├── pyproject.toml          # 自身依赖（被测库 + 必要辅助）
├── README.md               # 说明：版本锁、已知不支持的特性、如何本地运行
├── src/
│   └── adapter/
│       ├── __init__.py
│       └── __main__.py     # 入口；可被 `python -m adapter` 调用
└── tests/
    └── test_contract.py    # 跑一份 fixture 验证 result.json 合法
```

## `__main__.py` 最小骨架

```python
import argparse
import json
import sys
from pathlib import Path

def extract(input_pdf: Path, output_dir: Path, config: dict) -> int:
    # 1. 调用被测库
    # 2. 把输出转成 result-schema.json 规定的结构
    # 3. 写入 output_dir/result.json
    # 4. 写入 output_dir/meta.json
    ...
    return 0  # 成功

def main() -> int:
    p = argparse.ArgumentParser(prog="python-mylib")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("--input", required=True, type=Path)
    e.add_argument("--output-dir", required=True, type=Path)
    e.add_argument("--config", default="{}")
    e.add_argument("--timeout", type=int, default=60)
    args = p.parse_args()

    if args.cmd == "extract":
        try:
            return extract(args.input, args.output_dir, json.loads(args.config))
        except FileNotFoundError:
            print(f"input not found: {args.input}", file=sys.stderr)
            return 64
        except Exception as exc:
            print(f"extract failed: {exc}", file=sys.stderr)
            return 65
    return 2

if __name__ == "__main__":
    sys.exit(main())
```

## 安装与注册

1. `pip install -e adapters/python-mylib/`
2. 在 `pyproject.toml` 里加 console script：`adapter = "adapter.__main__:main"`
3. 在 `adapters/registry.json` 里登记一行
4. `make lint-adapter ADAPTER=python-mylib@<ver>`

## 硬约束速查

详见 [`contract/adapter-protocol.md`](../../contract/adapter-protocol.md)：

- stdout 纯净（日志走 stderr）
- 不写 `--output-dir` 之外的文件
- 不访问网络
- 失败时返回语义化退出码（64/65/66/124/其他）
- `result.json` 必须含 `schema_version` 字段
