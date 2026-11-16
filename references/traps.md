# 失败模式与排查

按「现象 → 原因 → 动作」查。每条都是实际卡过的。

## 解不开 / 解出来是乱码

| 现象 | 原因 | 动作 |
| --- | --- | --- |
| `xxd` 头部不是 `beed`，是 `V1MMWX` | PC 加密包 | 先解密再解包（`wxapkg-format.md`） |
| 头部既非 `beed` 也非 `V1MMWX` | 新版本变体 / 自定义加密 | 放弃静态解，走 Frida dump |
| 解出来 `fileCount` 是天文数字 | 头偏移错、没解密就硬解 | 用不变量 `19+idx+body==len` 自检 |
| 文件名乱码 | 非 UTF-8 或 index 偏移错 | 试 `gbk`/`utf-8-replace`，并核对 `nameLen` |
| 解出 0 个文件 | 只解了分包或缺主包 | 主包 + 所有分包一起解 |
| 解包器报 `invalid magic` | 工具版本不认该变体 | 换 `unveilr` / `KillWxapkg` 最新 release |

## 页面缺失 / 白屏

| 现象 | 原因 | 动作 |
| --- | --- | --- |
| 只有几个页面 | 分包未解 | 解每个 `*.wxapkg`，含插件包 |
| 页面在但样式全丢 | `app-wxss.js` 未还原 | 检查 `app-wxss.wxss` 是否生成 |
| wxml 报 `template not found` | `wxappUnpacker` 还原不全 | 手工从 `page-frame.html` 提模板，或放弃还原、只读逻辑 |
| 组件空壳 | 自定义组件路径映射丢了 | 查 `app-config.json` 的 `usingComponents` |
| 导入后报 `appid` 无效 | 用了被占用的 appid | 换 `touristappid` 或自己的测试号 |
| 接口全 403/CORS | `urlCheck` 未关 | `project.config.json` 里 `"urlCheck": false` |

## devtools 打不开

| 现象 | 原因 | 动作 |
| --- | --- | --- |
| 按 F12 无反应 | 微信版本不匹配 patch 脚本 | 用对应版本的 `WeChatOpenDevTools`，或换 `WMPFDebugger` |
| 面板开了但 Console 空 | 注入时机早于小程序加载 | 先打开小程序，再 attach |
| 一开就闪退 | patch 踩到完整性校验 | 换 Python 版 / 降微信版本 |
| 端口连不上 | 只监听本地回环 | 本地浏览器开 `127.0.0.1:<port>`，别远程连 |

## Frida / Hook 不生效

| 现象 | 原因 | 动作 |
| --- | --- | --- |
| `frida-ps` 看不到进程 | `frida-server` 架构不符或没起 | 按 `uname -m` 换 arm64/x86_64，`su` 启动 |
| attach 成功但 hook 不触发 | 目标是子进程（`WeChatAppEx` / `:appbrand`） | hook 子进程，或 `-f` 时用 `spawn` + `child-gating` |
| hook `open` 拿不到路径 | 走的是 `openat`/`open64` | 把 `openat`、`open64`、`fopen` 一起 hook |
| dump 出来全是密文 | 解密在别的函数里 | hook 解密函数返回值，或搜索 `be ed` 内存特征 |
| JS 层 hook 无效 | 小程序跑在独立 V8 上下文，不与主 JS 共享全局 | 用 devtools 断点，或改解包产物再跑 |
| 一 hook 就崩 | 指令对齐 / 反调试 | 用 `Interceptor.attach` 而非 inline patch；先 `--no-pause` 观察 |

## 签名重放失败

| 现象 | 原因 | 动作 |
| --- | --- | --- |
| 参数一致仍 401 | 缺 header（`Referer`/`Origin`/自定义 `x-*`） | 从 devtools 复制**整份**请求头 |
| 时间戳过期 | 服务端校验窗口 | 用当前时间重算，别用抓到的旧值 |
| sign 每次不同 | 含随机 nonce | 把 nonce 一起带，或 hook 生成函数 |
| sign 算法找不到 | 在 wasm / native | `wasm2wat` 读结构，或 Hook native `EVP_Digest*` |
| 只在真机成功 | 设备指纹参与签名 | 补 `wx.getSystemInfo` 相关字段（型号、`deviceId` 等） |

## 资产提取误判

| 现象 | 原因 | 动作 |
| --- | --- | --- |
| `urls.txt` 里全是 CDN/埋点 | grep 太宽 | 先取 `app-config.json` 的 `requestDomain`，再按域名过滤 |
| 接口路径拼不出来 | 用了变量拼接 | 搜 `baseUrl + "/"`、模板字符串 `` `${host}/api` `` |
| 域名打不开 | 内网域名 / 仅 App 内可达 | 记录进报告，别判「资产不存在」 |
| 云开发接口 404 | 走了 `wx.cloud`，不是 HTTP | 抓 `callFunction` 的 `name`，走云开发侧 |

## 报告口径

- 区分 **「解包还原产物」** 与 **「原始源码」**，别写成"源码泄露"。
- 结论必须能复现：包 `sha256` + 工具版本 + 命令原文。
- 抓到的 token / openid / 密钥：报告里打码，原始文件单独存并标注敏感。
