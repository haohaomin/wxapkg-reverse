#!/usr/bin/env bash
# 一键验证整条链路：造包 -> 探针 -> 解包 -> 提取
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || { echo "需要 python3（Windows 上通常是 python）"; exit 1; }

rm -rf sample out

echo "▶ 1/4  造样例包（主包 + 分包）"
"$PY" make_sample.py sample

echo
echo "▶ 2/4  探针：判加密形态 + 结构自检"
for f in sample/*.wxapkg; do "$PY" probe.py "$f"; echo; done

echo "▶ 3/4  解包（主包和分包都要解，实战里漏分包是头号错误）"
for f in sample/*.wxapkg; do
  name="$(basename "$f" .wxapkg)"
  echo "  [$name]"
  "$PY" unpack.py "$f" "out/$name"
done

echo
echo "▶ 4/4  提取域名 / 接口 / 云函数 / 签名线索"
"$PY" extract.py out

echo
echo "✔ 全链路通过：造包 → 探针 → 解包 → 提取"
echo "  产物在 $(pwd)/out ，可以自己打开看"
