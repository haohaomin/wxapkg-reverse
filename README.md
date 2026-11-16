# wxapkg-reverse

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![format](https://img.shields.io/badge/format-SKILL.md-2ea44f)](SKILL.md)
[![works with](https://img.shields.io/badge/works%20with-DSH%20%7C%20Claude%20Skill-6b4fbb)](https://github.com/deepseek-ai/deepseek-harness)

> **包在哪、为什么解不开、sign 怎么算** —— 小程序逆向 90% 的时间烧在这三件事上，而它们一个都不在工具文档里。

一个 agent skill（DSH / Claude Skill 格式）：把这段试错压成一张分流表 + 六份按需加载的参考。写给 AI agent 读，也给人读。

```
本机有包？ ──是──→ A  解包读源码     KillWxapkg → unveilr → app-config.json
   │
   └─加密解不开/只想看请求──→ B  开 devtools     F12 / WMPFDebugger

要 sign / 加密参数？ ─────→ C  Hook 运行时     Frida + 插桩 wx.request

wasm / 强混淆 / 只在内存解密 ─→ D  内存 dump      hook read，抓 be ed
```

## 三十秒验证（不需要微信，不需要装逆向工具）

```bash
git clone https://github.com/haohaomin/wxapkg-reverse.git
cd wxapkg-reverse/examples && ./run.sh
```

```console
▶ 2/4  探针：判加密形态 + 结构自检
  PLAINTEXT  fileCount=4 idxLen=113 bodyLen=899  [OK]

▶ 3/4  解包（主包和分包都要解，实战里漏分包是头号错误）
  ./app-config.json                      293 B
  ./app-service.js                       480 B

▶ 4/4  提取域名 / 接口 / 云函数 / 签名线索
requestDomain（接口白名单）  (2)
  https://api.example.com
接口路径  (1)
  /v1/order/list
签名线索  (3)
  return md5("GET" + ts + "SECRET_KEY_PLACEHOLDER");
```

造包 → 探针 → 解包 → 提取，四步全通。脚本不是示意代码：写这份东西时在合成包上端到端验过，顺手修掉了两个真 bug（`struct` 切片长度、路径穿越校验拿相对路径比绝对路径）。

## 它省掉的是什么

| 你会撞的墙 | 没有它 | 有它 |
| --- | --- | --- |
| 微信 4.x 换了包目录，网上教程全废 | 翻半小时帖子，猜五个路径 | 一行命令扫全盘 |
| 头部不是 `beed` 而是 `V1MMWX`，脚本直接抛异常 | 换三个工具，都炸 | 探针给形态 + 解密 + 不变量自检 |
| 解完发现某些页面「不存在」 | 以为自己解错了 | 提示你漏了分包 |
| 在几万行 `app-service.js` 里找 `sign` | grep 到眼花 | 四条定位路径，从 header 组装处反推 |
| 解不出来就卡死在那 | 反复试错，没有下一步 | `traps.md`：现象 → 原因 → 动作 |

## 四条路线

| 路线 | 场景 | 手段 |
| --- | --- | --- |
| **A** 解包读源码 | 本机有包 / 缓存可读（80% 情况） | `KillWxapkg` / `unveilr` / `wux1an/wxapkg` |
| **B** 开 devtools | 想看真实请求、包解不开 | `WeChatOpenDevTools` / `WMPFDebugger` |
| **C** Hook 运行时 | 要 `sign`、加密参数、风控字段 | Frida + 给 `wx.request` 插桩 |
| **D** 对抗保护 | wasm / 强混淆 / 只在内存解密 | 内存 dump + 动态跟踪 |

**先判形态再动手**，而不是从「安装 Python」开始 —— 这是这个 skill 和其他教程最大的区别。

## 安装

技能名取自 `SKILL.md` 的 `name: miniprogram-reverse`，**目录名不影响**识别。

### DSH

```bash
git clone https://github.com/haohaomin/wxapkg-reverse.git ~/.dsh/skills/miniprogram-reverse
```

`~/.dsh/skills` 是用户级技能根（rank 400）。`unrestricted` preset 由 `includeDefaultRoots: true` 覆盖它，`redteam` preset 由 `customSkillDirs` 里的 `dshHomePath('skills')` 覆盖 —— 两个都能扫到，**不用改配置**。

### Windows

```powershell
git clone https://github.com/haohaomin/wxapkg-reverse.git "$env:USERPROFILE\.dsh\skills\miniprogram-reverse"
```

用户目录名常与主机名不一致（主机 `renhao`、用户 `renha` 这种），先 `whoami` 确认。Windows 上的等价命令见 [references/windows.md](references/windows.md)。

### Claude Code / 其他客户端

整个目录放进客户端的 skills 路径，或只取 `SKILL.md` 作为 system prompt 附件，`references/` 按需读。

## 目录

```
SKILL.md                    入口：10 秒最快路径、三个坑、分流表、四条路线、交付物
references/
├── repos.md                工具清单、DMCA 下架现状、fork 怎么选、搜索语法
├── wxapkg-format.md        包结构、三种加密形态、探针、20 行自写解包器
├── commands.md             各端包路径、解包、devtools、Frida、接口提取
├── api-extraction.md       域名/接口/sign/云函数，产出可重放 curl
├── traps.md                解不出来 / 白屏 / Hook 不触发，按现象查
└── windows.md              Windows 等价命令、路径、编码、权限
examples/                   可跑的合成包 + 四个脚本 + 一键 run.sh
```

## 三个值得单独说的点

**解密别凭记忆。** 「`V1MMWX` 从 offset 6 还是 7 开始 XOR」不同版本实现有差异。文档给的是不变量自检：

```
19 + indexInfoLength + bodyInfoLength == 文件长度
```

对不上就是没解开，别往下硬解。

**解包 ≠ 源码。** `app-service.js` 是编译产物，路由要靠 `app-config.json` 反查；`wxappUnpacker` 对 template、自定义组件、`<wxs>` 还原不全。别把还原产物写成「源码泄露」。

**合法域名列表才是资产清单。** `app-config.json` 里的 `requestDomain` 比 grep 字符串准得多 —— 那是小程序唯一允许请求的域名集合。

## FAQ

**支持哪些平台？**
微信为主（PC / Android / iOS），支付宝、抖音、QQ 小程序的包结构与调试方式在 `repos.md` 里标注了差异。iOS 的包加密更硬，走 dump 而不是解包器。

**解包会被封号吗？**
解包纯本地，不碰服务器。真正的风险在**请求频率和行为** —— 拿到接口后按普通 Web 测试的节奏来。

**要 root / 越狱吗？**
Android 取包目录需要；用 Frida 内存 dump 也需要。PC 端不需要，devtools 路线完全用户态。

**能拿到原始源码吗？**
不能。拿到的是微信编译后的产物（合并的 JS / 编译后的 wxml），可读但不是开发者写的那份。

**为什么不用现成的 GUI？**
GUI 只做到解包为止。你要的 `sign`、加密参数、风控字段全在运行时，GUI 帮不上。这个 skill 的一半篇幅在运行时。

## English

Agent skill (DSH / Claude Skill format) for WeChat MiniProgram reverse engineering: locate and decrypt `.wxapkg`, unpack to readable sources, enable devtools, hook the runtime for request signing, and extract backend endpoints. Ships a runnable example (`examples/run.sh`) that builds a synthetic `.wxapkg` and drives the whole pipeline — probe, unpack, extract — with no dependencies beyond `python3`.

## License

MIT
