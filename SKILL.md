---
name: miniprogram-reverse
description: 微信/支付宝/抖音小程序逆向：wxapkg 解不开、包找不到、sign 算不出。含三种加密形态判定、devtools 开启、Frida 内存 dump、接口与签名提取、失败排查表。当目标是小程序而不是 Web/原生 App，或已抓到接口但需要还原签名时使用。
whenToUse: 手上有 .wxapkg 但解不开；不知道小程序包存在哪；要看小程序的真实请求；要 sign 或参数加密的算法；要批量提取小程序后端接口
---

# 小程序逆向

> 包在哪、为什么解不开、sign 怎么算 —— 这三件事吃掉 90% 的时间。剩下的 10% 才是工具。

## 10 秒最快路径

```bash
# 1. 扫缓存 + 解密 + 解包（工具自己找路径，别手拼）
KillWxapkg -in <微信数据目录> -out ./dump -appid

# 2. 单包解（分包也要解，见下面的坑 2）
unveilr ./dump/wx*/__APP__.wxapkg -o ./out

# 3. 后端资产清单，第一手
jq -r '.requestDomain[]' ./out/app-config.json
```

工具没装 → [references/repos.md](references/repos.md)，全在 release 里下单个二进制，不用编译。

## 你会得到什么

```
out/
├── app-config.json     页面路由 + requestDomain（接口白名单）+ subPackages
├── app-service.js      全部业务逻辑（编译产物，不是源码）
├── page-frame.html     wxml 编译产物（视图层）
└── app-wxss.wxss       样式
```

```console
$ jq -r '.requestDomain[]' app-config.json
https://api.example.com
https://cdn.example.com
```

到这里通常就够了：域名拿到，接口从 `app-service.js` 里 grep，剩下的走常规 Web 测试。

## 第一屏三个坑（90% 的失败在这）

| 坑 | 后果 | 解法 |
| --- | --- | --- |
| 路径按教程写死 | 一条命令都跑不通 | 微信 4.x 换过目录，让 `KillWxapkg` 自己扫 |
| 只解 `__APP__.wxapkg` | 页面"不存在"、逻辑缺失 | 主包 + 所有分包 + 插件包，一起解 |
| 把 `app-service.js` 当源码读 | 结论全是错的 | 它是编译产物；路由靠 `app-config.json` 反查 |

## 30 秒分流

| 现场 | 走 |
| --- | --- |
| 本机有包 / 缓存可读 | **A 解包读源码**（80% 情况） |
| 包加密、解不开、只想看请求 | **B 开 devtools** |
| 要 sign / 加密参数 / 风控字段 | **C Hook 运行时** |
| wasm / 强混淆 / 只在内存解密 | **D dump + 动态跟踪** |
| iOS | 沙盒读 + 走 C/D，别指望直接解包 |

先问清三件事：**哪个平台、版本多少、有没有 root/越狱/PC 端登录**。包路径、加密强度、可读性各差一代。

## A · 解包读源码

1. **定位包**：让工具扫，别猜路径（[路径表](references/commands.md)只作兜底）。
2. **判加密形态**再解：`xxd -l 32 ./__APP__.wxapkg`。明文件头是 `beed`；`V1MMWX` 是 PC 加密变体。
3. **解包**：`unveilr`（最稳）或 `wux1an/wxapkg`（能重打包）。
4. **读产物**：先看 `app-config.json` 拿路由与域名，再带着具体问题去 `app-service.js` 里搜。
5. **要跑起来**：补 `project.config.json`（`appid` 可填测试号，`urlCheck: false`），导入开发者工具。

加密形态、探针脚本、20 行自写解包器：**[references/wxapkg-format.md](references/wxapkg-format.md)**

## B · 开 devtools

- Windows PC 微信：`x0xn/WeChatOpenDevTools`（管理员跑）→ 小程序窗口按 F12。
- 要稳定会话、看 storage 全量：`evi0s/WMPFDebugger`（Frida 挂 `WeChatAppEx`）。
- 开了之后**先抓 Network，再回头读代码**。先知道要解释什么，比通读几万行快十倍。

Console 里立刻能用的三条：

```js
Object.keys(__wxConfig.global)
__wxConfig.global.appConfig.pages      // 全部页面路由
__wxConfig.global.userInfo             // 当前用户态
```

## C · Hook 运行时

找 `sign` / `timestamp` / `nonce` / `encrypt` / `token`，顺序：搜名字 → 搜加密库特征（`CryptoJS`、`sm-crypto`、`JSEncrypt`）→ 看 header 组装处 → 反查 request 封装的调用链。

最快的一招不是 Frida，是**改解包产物插桩**，在开发者工具里看：

```js
const _req = wx.request;
wx.request = function (o) {
  console.log('[REQ]', o.method, o.url, JSON.stringify(o.data), JSON.stringify(o.header));
  return _req.apply(this, arguments);
};
```

Frida 骨架与 native dump：**[references/commands.md](references/commands.md)**

## D · 对抗保护

- 内存里才解密的包：hook `open`/`read`，在缓冲区出现 `be ed` 时落盘（骨架现成）。
- wasm / 字节码：`wasm2wat` + `wasm-decompile` 先读结构，再找谁传参。
- 强混淆：先做字符串解密（找解谜函数批量还原），别一行行读。

## 交付物（缺一条就等于没做完）

1. **包与哈希**：路径、`sha256`、微信版本、小程序 `appid` 与版本号
2. **产物目录** + 解包器与版本（复现靠它）
3. **接口清单**：`method path 域名 来源文件`
4. **鉴权与签名**：header 名、算法、密钥来源、时间戳规则 + 可重放 curl
5. **命令原文**，不是"用工具解一下"

## 参考

| 文件 | 什么时候读 |
| --- | --- |
| [references/repos.md](references/repos.md) | 选工具、找 fork（原库多被 DMCA 下架） |
| [references/wxapkg-format.md](references/wxapkg-format.md) | 解不开、要验解密、要自己写解包器 |
| [references/commands.md](references/commands.md) | 包路径、解包命令、devtools、Frida、接口提取 |
| [references/api-extraction.md](references/api-extraction.md) | 提域名/接口/sign/云函数，产出可重放请求 |
| [references/traps.md](references/traps.md) | 解不出来/白屏/Hook 不触发，按现象查 |
| [references/windows.md](references/windows.md) | Windows 上的等价命令与路径 |
| [examples/](examples/) | 一键跑通：造包 → 探针 → 解包 → 提接口 |

## 产物处理

- `out/` 里的 JS 常带硬编码密钥、token、用户数据：单独目录、不进 Git、报告里打码。
- 包 `sha256` + 工具版本 + 命令原文一起留档，否则结论不可复现。
- 解包产物是可执行 JS，别在主力机直接 `node` 跑来路不明的包。
