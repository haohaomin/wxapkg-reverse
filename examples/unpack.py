#!/usr/bin/env python3
"""wxapkg 解包器：无依赖，20 行逻辑 + 必要的边界检查。

用法: python3 unpack.py <file.wxapkg> <outdir>
"""
import os
import struct
import sys


def unpack(path, outdir):
    outdir = os.path.abspath(outdir)
    d = open(path, "rb").read()

    if d[:2] != b"\xbe\xed":
        if d[:6] == b"V1MMWX":
            sys.exit(f"{path}: PC 加密包，先解密（见 references/wxapkg-format.md）")
        sys.exit(f"{path}: 不是明文 wxapkg（头部 {d[:2].hex()}）")

    idx_len, body_len = struct.unpack(">II", d[6:14])
    cnt = struct.unpack(">I", d[15:19])[0]
    expect = 19 + idx_len + body_len
    if expect != len(d):
        sys.exit(f"{path}: 结构自检失败 19+{idx_len}+{body_len}={expect} != {len(d)}")

    p, files = 0x13, []
    for _ in range(cnt):
        nl = struct.unpack(">I", d[p : p + 4])[0]
        p += 4
        name = d[p : p + nl].decode("utf-8", "replace")
        p += nl
        off, size = struct.unpack(">II", d[p : p + 8])
        p += 8
        files.append((name, off, size))

    written = 0
    for name, off, size in files:
        rel = name.lstrip("/")
        if rel.startswith("./"):
            rel = rel[2:]
        if not rel or ".." in rel.split("/"):
            print(f"  SKIP  path traversal: {name}")
            continue
        target = os.path.join(outdir, rel)
        os.makedirs(os.path.dirname(target) or outdir, exist_ok=True)
        with open(target, "wb") as fh:
            fh.write(d[off : off + size])
        print(f"  {name:<34} {size:>7} B")
        written += 1

    print(f"  -> {written}/{cnt} files  =>  {outdir}")
    return written


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: unpack.py <file.wxapkg> <outdir>")
    unpack(sys.argv[1], sys.argv[2])
