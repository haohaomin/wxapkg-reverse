# wxapkg-reverse

微信小程序逆向的 **agent skill**：解 `wxapkg`、还原前端源码、开 devtools、Hook 取 `sign`、提取后端接口。

不是又一个解包器 —— 解包器已经够多了（见 [references/repos.md](references/repos.md)）。这里补的是**流程与判定**：包在哪个目录、加密属于哪种形态、解不出来时下一步做什么、`sign` 到底从哪来、哪些坑会让你白干两小时。写给 AI agent 读，也给人读。

兼容 [DSH](https://github.com/deepseek-ai/deepseek-harness) 与任何支持 `SKILL.md` + YAML frontmatter 的客户端（Claude Skill 格式）。

---

## 它解决什么

大部分人卡住的不是「没有工具」，而是这三件事：

1. **包找不到** —— 微信 4.x 换了目录，网上教程全是旧路径
2. **包解不开** —— 头部不是 `beed` 而是 `V1MMWX`，套脚本直接抛异常
3. **解开了但没用** —— 拿到几万行 `app-service.js`，不知道 `sign` 从哪儿算出来

这个 skill 的第一屏就是分流表，直接告诉 agent 该走哪条路，而不是从「安装 Python」开始。

## 四条路线

| 路线 | 场景 | 手段 |
| --- | --- | --- |
| **A** 解包读源码 | 本机有包 / 缓存可读（80% 情况） | `KillWxapkg` / `unveilr` / `wux1an/wxapkg` |
| **B** 开 devtools | 想看真实请求、包解不开 | `WeChatOpenDevTools` / `WMPFDebugger` |
| **C** Hook 运行时 | 要 `sign`、加密参数、风控字段 | Frida + JS 插桩 |
| **D** 对抗保护 | wasm / 强混淆 / 只在内存解密 | 内存 dump + 动态跟踪 |

## 安装

技能名是 `SKILL.md` 里的 `name: miniprogram-reverse`，**目录名不影响**识别。

### DSH

```bash
git clone https://github.com/haohaomin/wxapkg-reverse.git ~/.dsh/skills/miniprogram-reverse
```

`~/.dsh/skills` 是用户级技能根（rank 400）。`unrestricted` preset 由 `includeDefaultRoots: true` 覆盖，`redteam` preset 由 `customSkillDirs` 里的 `dshHomePath('skills')` 覆盖 —— **两个都能直接扫到，不用改配置**。

### Windows

```powershell
git clone https://github.com/haohaomin/wxapkg-reverse.git "$env:USERPROFILE\.dsh\skills\miniprogram-reverse"
```

注意用户目录名常与主机名不一致（比如主机 `renhao`、用户 `renha`），先 `whoami` 确认。

### Claude Code / 其他客户端

把整个目录放进客户端的 skills 路径，或只取 `SKILL.md` 作为 system prompt 附件；`references/` 按需读。

## 用法

装上之后直接说人话：

```
这个 wxapkg 解不开，帮我看看
逆向一下这个小程序，我要它的接口列表
小程序的 sign 是怎么算的
```

agent 会自己走分流表。也可以点名加载：

```
/skill miniprogram-reverse
```

## 目录

| 文件 | 内容 |
| --- | --- |
| `SKILL.md` | 入口：30 秒分流、四条路线、交付物清单、常见坑 |
| `references/repos.md` | 工具仓库清单、DMCA 下架现状、fork 选择、GitHub 搜索语法 |
| `references/wxapkg-format.md` | 包结构（大端字段表）、三种加密形态、探针脚本、20 行自写解包器 |
| `references/commands.md` | 各端包路径、解包命令、devtools、Frida dump、接口提取 |
| `references/api-extraction.md` | 域名/接口/`sign`/云函数提取，产出可重放 curl |
| `references/traps.md` | 现象 → 原因 → 动作 的排查表 |
| `references/windows.md` | Windows 等价命令、路径、编码、权限 |

## 里面的脚本是跑过的

`wxapkg-format.md` 的探针与解包器、`api-extraction.md` 的提取器，都在合成的 `wxapkg` 上端到端验证过：按格式造包 → 解包 → 提取域名与 URL。写这份东西时修掉了两个真 bug（`struct` 切片长度、路径穿越校验拿相对路径比绝对路径）。

所以它们不是"看起来能跑"的示例代码。

## 两个值得单独说的点

**解密不要凭记忆。** `V1MMWX` 那段「从 offset 6 还是 7 开始 XOR」不同版本实现有差异。文档给的是**不变量自检**：

```
19 + indexInfoLength + bodyInfoLength == 文件长度
```

对不上就是没解开，别往下硬解。

**解包 ≠ 拿到源码。** `app-service.js` 是编译产物，路由靠 `app-config.json` 反查；`wxappUnpacker` 对 template、自定义组件、`<wxs>` 还原不全。别把还原产物当原始源码写进报告。

## 边界

解包产物里的 token、密钥、用户数据按敏感文件处理：单独目录、不进 Git、报告里打码。`.gitignore` 已排除 `out/`、`dump/`、`*.wxapkg`。

## English

Agent skill (DSH / Claude Skill format) for WeChat MiniProgram reverse engineering: locate and decrypt `.wxapkg`, unpack to readable sources, enable devtools, hook runtime for request signing, and extract backend endpoints. Four-route decision table up front instead of a wall of setup steps. Scripts included were validated end-to-end against a synthetic `.wxapkg`.

## License

MIT
