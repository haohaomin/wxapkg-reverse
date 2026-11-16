#!/usr/bin/env python3
"""从解包产物里提域名、接口、云函数、签名线索。

用法:
  python3 extract.py <解包目录>            # 人读摘要
  python3 extract.py <解包目录> --json     # 机器格式
"""
import json
import os
import re
import sys

URL_RE = re.compile(r"https?://[A-Za-z0-9._~:/?#@!$&*+,;=%\-]+")
PATH_RE = re.compile(r"[\"'](/[a-zA-Z0-9_\-/]{3,80})[\"']")
TPL_RE = re.compile(r"`\$\{[^}]+\}(/[a-zA-Z0-9_\-/{}$.]{2,80})`")
CF_RE = re.compile(r"callFunction\s*\(\s*\{[^}]*name\s*:\s*[\"']([^\"']+)")
SIGN_RE = re.compile(
    r"(sign|signature|getSign|calcSign|encrypt|sm2|sm4|aes|rsa|hmac|md5|sha256)", re.I
)


def scan(root):
    urls, paths, cfs, signs, domains = set(), set(), set(), set(), set()

    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            full = os.path.join(dirpath, fn)

            if fn == "app-config.json":
                try:
                    cfg = json.load(open(full, encoding="utf-8", errors="replace"))
                    domains.update(x for x in cfg.get("requestDomain", []) if isinstance(x, str))
                except Exception:
                    pass

            if not fn.endswith((".js", ".json", ".wxml")):
                continue
            try:
                txt = open(full, encoding="utf-8", errors="replace").read()
            except Exception:
                continue

            urls.update(URL_RE.findall(txt))
            paths.update(PATH_RE.findall(txt))
            paths.update(TPL_RE.findall(txt))
            cfs.update(CF_RE.findall(txt))
            for line in txt.splitlines():
                if SIGN_RE.search(line):
                    compact = " ".join(line.strip().split())
                    if compact:
                        signs.add(compact[:140])

    return {
        "domains": sorted(domains),
        "urls": sorted(urls),
        "paths": sorted(paths),
        "cloud_functions": sorted(cfs),
        "sign_candidates": sorted(signs)[:50],
    }


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: extract.py <unpacked-dir> [--json]")
    root, as_json = sys.argv[1], "--json" in sys.argv
    data = scan(root)

    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    def block(title, items, limit=12):
        print(f"\n{title}  ({len(items)})")
        if not items:
            print("  -")
            return
        for x in items[:limit]:
            print(f"  {x}")
        if len(items) > limit:
            print(f"  ... 还有 {len(items) - limit} 条")

    block("requestDomain（接口白名单）", data["domains"])
    block("URL", data["urls"])
    block("接口路径", data["paths"])
    block("云函数", data["cloud_functions"])
    block("签名线索", data["sign_candidates"], limit=6)


if __name__ == "__main__":
    main()
