---
name: miniprogram-reverse
description: 小程序逆向全流程：定位并解密 wxapkg、还原前端源码、给 PC 微信开 devtools、Frida/内存 dump 拿加密包、从产物提取后端接口与签名算法。用于静态还原小程序、抓运行时请求、把小程序当后端入口做资产测绘，或复现/篡改小程序逻辑。
whenToUse: 目标是微信/支付宝/抖音/QQ 小程序而不是纯 Web 或原生 App；或已从小程序抓到接口域名但需要还原 sign/加密参数；或需要批量提取本机小程序包与接口资产
---

# 小程序逆向

一句话：**小程序 = 若干 wxapkg 包 + 一个 JS 运行时**。拿到包就拿到 80%；剩下 20%（签名、参数加密、风控）只在运行时里，只能 Hook。

## 30 秒分流

| 现场情况 | 走哪条 |
| --- | --- |
| 手上/本机有 `*.wxapkg` 或微信缓存目录可读 | **A：解包读源码**（默认，80%） |
| 包加密解不开、或只想看真实请求 | **B：开 devtools** |
| 需要 sign 算法、加密参数、风控字段怎么来的 | **C：Hook 运行时** |
| 有 wasm / 强混淆 / 自定义字节码 | **D：dump + 动态跟踪** |
| iOS 目标 | 沙盒读 + 走 C/D，不要指望直接解包 |

先把形态问清：**哪个平台、什么版本、有没有 root/越狱/PC 端登录**。不同平台的包路径、加密、可读性差一代。

## A：拿包 → 解密 → 解包 → 读源码

1. **定位包**（路径随版本变，别写死）。先让工具自己扫：
   ```bash
   # 本机微信缓存全扫（PC/Mac 最省事）
   KillWxapkg -in ~/Library/Containers/com.tencent.xinWeChat -out ./dump -appid
   ```
   手查路径见 [references/commands.md](references/commands.md)。
2. **判加密形态**再解，别盲目套脚本：
   ```bash
   xxd -l 32 ./dump/wx*/__APP__.wxapkg
   ```
   明文体是 `beed` 开头；`V1MMWX` 之类是 PC 加密变体。三种形态与判定见 [references/wxapkg-format.md](references/wxapkg-format.md)。
3. **解包**：`unveilr`（Rust，最稳）或 `wux1an/wxapkg`（Go，能重打包）。
   ```bash
   unveilr ./dump/wx1234.../__APP__.wxapkg -o ./out
   ```
4. **读产物**。解出来不是源码而是编译产物，先看这五样：
   `app-config.json`（页面路由 + 合法域名 + 分包）、`app-service.js`（全部逻辑）、`page-frame.html`（wxml 编译产物）、`app-wxss.js/wxss`、分包 `*.wxapkg`。
   `wxappUnpacker` 能把 `app-service.js` 拆回 `pages/*/*.js`，但 template、自定义组件、`<wxs>` 常还原不全——**能读就打住，别追求 100% 还原**。
5. **想跑起来**：解包目录补 `project.config.json`（`appid` 可填测试号），微信开发者工具「导入项目」。真机行为以 B/C 为准，模拟器不可信。

## B：开 devtools（看真实请求最快的手段）

- PC 微信：`x0xn/WeChatOpenDevTools`（或 `-Python` 版）patch 后 F12 面板恢复，Console/Network 直接看。
- 需要稳定会话、能看 storage 与 wx.request 全量：`evi0s/WMPFDebugger` 用 Frida 挂 `WeChatAppEx.exe`。
- 开发者工具本身可跑解包产物（`msojocs/wechat-devtools-linux` 亦可），适合改逻辑试签名。

devtools 一开，**先抓 Network，再去读代码**——先知道要解释什么，比通读几万行 `app-service.js` 快十倍。

## C：Hook 运行时（签名与加密参数）

目标字段定位顺序：`sign` / `timestamp` / `nonce` / `x-*` / `encrypt` / `token`。

1. 在 `app-service.js` 里搜特征：`sign(`, `md5`, `hmac`, `sha256`, `sm4`, `rsa`, `getSign`, `encrypt`, `wx.request`。
2. 找到调用点后，Hook 两层：
   - **JS 层**：`wx.request` 的 options、`Function.prototype.apply`、`String.prototype` 关键变换、`crypto` 桩函数。
   - **Native 层**：Frida 挂 `libmmv8.so` / `WeChatAppEx`，盯 `memcpy`、`EVP_*`、`BoringSSL`。
3. 见 [references/commands.md](references/commands.md) 里的 Frida 骨架，改函数名直接用。

拿到 sign 后**先在 devtools 里重放**验证，再写脚本——不重放就等于没拿到。

## D：包被保护

- 加密包 / 内存里才解密的：Frida 挂客户端，在 `open`/`write`/`mmap` 或解密函数返回处 dump 明文 `wxapkg`。
- wasm / 自定义字节码：`wasm2wat` + `wasm-decompile` 先读结构，再看谁传参进去。
- 强混淆（`_0x` 变量、字符串数组轮转）：先做字符串解密（找解密函数 + 批量还原），别一行行读。

## 交付物（不落这五样等于没做完）

1. **包与哈希**：路径、`sha256`、微信版本、小程序 `appid` 与版本号。
2. **产物目录**：解包路径 + 解包器与版本（复现靠它）。
3. **接口清单**：`method path 域名 来源文件`，落到 `urls.txt` / `endpoints.csv`。
4. **鉴权与签名**：header 名、算法、密钥来源、时间戳/随机数规则；给出可重放的 curl。
5. **可复现步骤**：命令原文，不是"用工具解一下"。

## 常见坑（每条都真踩过）

- **路径写死**：微信 4.x 换了目录，老脚本全失效 → 让 `KillWxapkg` 扫。
- **只解 `__APP__.wxapkg`**：主包 + 分包 + 插件包，漏了分包会以为"没这个页面"。
- **把 `app-service.js` 当源码读**：它是编译产物，路由靠 `__wxConfig`/`app-config.json` 反查。
- **忽略合法域名列表**：`app-config.json` 里的 `requestDomain` 就是后端资产清单，比 grep 字符串更准。
- **模拟器能跑 ≠ 真机能跑**：区别在风控、设备指纹、native 加密。
- **devtools 里改了代码就以为线上也这样**：devtools 关掉部分校验，注意 `wx.getSystemInfo` 分支。
- **图省事直接抄网上解包脚本**：多被 DMCA 下架，且不处理加密变体 → 见 [references/repos.md](references/repos.md) 的 fork 现状。
- **反编译产物当"泄露源码"报出去**：报告里要区分「还原产物」与「原始源码」，否则结论不可信。

## 参考

| 文件 | 内容 |
| --- | --- |
| [references/repos.md](references/repos.md) | 工具仓库清单、状态、fork 现状、GitHub 搜索语法 |
| [references/wxapkg-format.md](references/wxapkg-format.md) | 包结构、三种加密形态、探针脚本、自写解包器思路 |
| [references/commands.md](references/commands.md) | 各平台路径与命令、Frida 骨架、接口提取、重打包 |
| [references/traps.md](references/traps.md) | 失败模式逐条排查（解不出来/白屏/乱码/Hook 不生效） |
| [references/api-extraction.md](references/api-extraction.md) | 从产物提取接口、签名、云开发函数名，产出可重放请求 |
| [references/windows.md](references/windows.md) | Windows 上的等价命令、路径、devtools、编码与权限 |

## 产物处理

- `out/` 里的 JS 常带硬编码密钥、token、用户数据：单独目录、不进 Git、报告里打码。
- 包 `sha256` + 工具版本 + 命令原文一起留档，否则结论不可复现。
- 解包产物是可执行 JS，别在主力机直接 `node` 运行来路不明的包。
