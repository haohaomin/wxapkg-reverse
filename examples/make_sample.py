#!/usr/bin/env python3
"""造一个合成的 wxapkg（主包 + 分包），用于验证解包链路。

不是微信真实产物 —— 只是按 wxapkg 的大端结构拼出来的合法包，
让 probe / unpack / extract 三个脚本有东西可跑。
真实包请用 KillWxapkg 或 unveilr 解。
"""
import os
import struct
import sys

APP_CONFIG = """{
  "pages": ["pages/index/index", "pages/order/list"],
  "window": { "navigationBarTitleText": "sample" },
  "networkTimeout": { "request": 10000 },
  "requestDomain": ["https://api.example.com", "https://cdn.example.com"],
  "subPackages": [{ "root": "pages/detail", "pages": ["detail"] }]
}"""

APP_SERVICE = """var BASE_URL = "https://api.example.com";
function getSign(ts) {
  return md5("GET" + ts + "SECRET_KEY_PLACEHOLDER");
}
function loadOrders(page) {
  wx.request({
    url: BASE_URL + "/v1/order/list",
    method: "POST",
    data: { page: page, ts: Date.now(), sign: getSign(page) },
    header: { "x-token": "Bearer_REPLACE_ME" }
  });
}
Page({
  onLoad: function () {
    loadOrders(1);
    if (wx.cloud) { wx.cloud.callFunction({ name: "getUserProfile", data: {} }); }
  }
});
"""

PAGE_FRAME = "<!DOCTYPE html><html><body><view class=\"box\">{{title}}</view></body></html>"

APP_WXSS = ".box{display:flex;align-items:center;padding:24rpx}"

SUB_DETAIL_JS = """Page({ data: { id: 0 }, onLoad: function (q) {
  wx.request({ url: "https://api.example.com/v1/order/detail", data: { id: q.id } });
} });"""

SUB_DETAIL_WXML = "<view class=\"detail\">{{id}}</view>"


def build(files: dict, out_path: str) -> int:
    idx, body = b"", b""
    base = 0x13 + sum(4 + len(name.encode()) + 8 for name in files)
    for name, data in files.items():
        nb = name.encode()
        idx += struct.pack(">I", len(nb)) + nb + struct.pack(">II", base + len(body), len(data))
        body += data
    head = (
        b"\xbe\xed"
        + struct.pack(">III", 0, len(idx), len(body))
        + b"\xed"
        + struct.pack(">I", len(files))
    )
    blob = head + idx + body
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "wb") as fh:
        fh.write(blob)
    return len(blob)


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else "sample"

    main_pkg = {
        "./app-config.json": APP_CONFIG.encode(),
        "./app-service.js": APP_SERVICE.encode(),
        "./page-frame.html": PAGE_FRAME.encode(),
        "./app-wxss.wxss": APP_WXSS.encode(),
    }
    sub_pkg = {
        "./pages/detail/detail.js": SUB_DETAIL_JS.encode(),
        "./pages/detail/detail.wxml": SUB_DETAIL_WXML.encode(),
    }

    n1 = build(main_pkg, os.path.join(outdir, "__APP__.wxapkg"))
    n2 = build(sub_pkg, os.path.join(outdir, "sub_detail.wxapkg"))
    print(f"  {outdir}/__APP__.wxapkg      {n1} B  ({len(main_pkg)} files)")
    print(f"  {outdir}/sub_detail.wxapkg   {n2} B  ({len(sub_pkg)} files)")


if __name__ == "__main__":
    main()
