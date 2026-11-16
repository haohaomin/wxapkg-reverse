#!/usr/bin/env python3
"""wxapkg 探针：判加密形态 + 用不变量自检。

用法: python3 probe.py a.wxapkg [b.wxapkg ...]
"""
import struct
import sys


def inspect(path):
    d = open(path, "rb").read()
    print(f"{path}")
    print(f"  size={len(d)}  head={d[:16].hex(' ')}")

    if d[:2] == b"\xbe\xed":
        idx_len, body_len = struct.unpack(">II", d[6:14])
        cnt = struct.unpack(">I", d[15:19])[0]
        expect = 19 + idx_len + body_len
        ok = "OK" if expect == len(d) else f"MISMATCH(expect {expect})"
        print(f"  PLAINTEXT  fileCount={cnt} idxLen={idx_len} bodyLen={body_len}  [{ok}]")
        return True

    if d[:6] == b"V1MMWX":
        print(f"  PC-ENCRYPTED  key=0x{d[6]:02x}  -> 先解密再解包")
        return False

    print("  UNKNOWN 形态，别硬解：走内存 dump 或换解密实现")
    return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: probe.py <file.wxapkg> [...]")
    results = [inspect(p) for p in sys.argv[1:]]
    sys.exit(0 if all(results) else 1)
