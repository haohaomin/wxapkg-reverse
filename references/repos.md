# 工具仓库清单与获取

小程序逆向的仓库是**消耗品**：被投诉下架、作者停更、路径随微信版本失效。所以先看状态，别照抄教程链接。

## 一、解包 / 解密

| 仓库 | 语言 | 定位 | 现状 |
| --- | --- | --- | --- |
| `Ackites/KillWxapkg` | Go | 自动扫描微信缓存 → 解密 → 解包，单文件 | 2024 起最活跃，优先 |
| `r3x5ur/unveilr` | Rust | 解包最稳，分包与边界情况处理最好 | 持续维护 |
| `wux1an/wxapkg` | Go | 库 + CLI，解密/解包/**重打包** | 维护中 |
| `xuedingmiaojun/wxappUnpacker` | Node | 把 `app-service.js` 拆回 `pages/*/*.js` | 主力 fork |
| `dmnsy/wxappUnpacker` | Node | 同上，修了不少 bug | fork |
| `qwerty472123/wxappUnpacker` | Node | **原始仓库，已 takedown** | 只作历史参考 |

`wxappUnpacker` 家族都是 Node 脚本，用法基本一致：

```bash
git clone --depth 1 https://github.com/xuedingmiaojun/wxappUnpacker
cd wxappUnpacker && npm i
node wuWxapkg.js /path/to/__APP__.wxapkg      # 解包
node wuWxapkg.js /path/to/sub.wxapkg          # 分包：需主包已解在同一父目录
```

## 二、调试 / devtools

| 仓库 | 平台 | 作用 |
| --- | --- | --- |
| `x0xn/WeChatOpenDevTools` | Windows PC 微信 | patch 进程，恢复小程序 F12 面板 |
| `x0xn/WeChatOpenDevTools-Python` | Win/Mac | 同上，Python 重写，免 Node 环境 |
| `evi0s/WMPFDebugger` | PC 微信 | Frida 注入 `WeChatAppEx`，稳定 devtools 会话 |
| `msojocs/wechat-devtools-linux` | Linux | 社区版开发者工具，跑解包产物 |
| `msojocs/wechat-devtools` | 多平台 | 同上，patch 说明 |

## 三、抓包 / 一体化 GUI

| 仓库 | 说明 |
| --- | --- |
| `Cr4n5/CrackMinApp` | Windows GUI：抓包 + 下载包 + 解包，一条龙 |
| `frida` dump 脚本（社区零散） | 内存 dump 已解密 `wxapkg`，绕过磁盘加密 |
| `@cloudbase/cli` | 云开发：云函数、数据库、存储导出 |

## 四、批量与资产测绘

`KillWxapkg` 与 `wux1an/wxapkg` 都能无 GUI 扫目录，所以批量流程是：

```bash
# 全盘扫缓存，一次拿所有小程序的 appid + 包
KillWxapkg -in <wechat-data-dir> -out ./dump -appid

# 逐个解
for f in ./dump/*/__APP__.wxapkg; do unveilr "$f" -o "./out/$(basename $(dirname $f))"; done

# 每个包的合法域名（= 后端资产清单）
for j in ./out/*/app-config.json; do
  jq -r '.requestDomain[]?, .subPackages[]?.root' "$j" 2>/dev/null | sed "s|^|$(dirname $j)\t|"
done
```

## 五、自己按需找

GitHub 搜索语法（比任何清单都新）：

```
wxapkg in:name
unveilr in:name
wxappUnpacker in:name
小程序 逆向 in:readme
miniprogram reverse in:readme
topic:wxapkg
topic:wechat-miniprogram
```

遇到 `Repository unavailable due to DMCA takedown` 属正常：去 **fork 网络**（`?tab=forks` 里按最近更新排序）或者 `git clone` 过的镜像找。

## 六、安装注意

- Go 系（KillWxapkg、wux1an）直接下 release 单文件，别现场 `go build`（交叉编译常因 CGO 失败）。
- Rust 系（unveilr）同理下 release。
- Node 系必须装依赖：`npm i` 失败多为 `canvas`/`node-gyp`，换 `--ignore-scripts` 后手补。
- 全部工具在**隔离目录**跑，产物当可疑输入（含 JS 与未知二进制），别在主力机双击可执行文件。

## 七、能力边界

这些工具只做「包 → 文件」。**sign 算法、风控、native 加密不在任何工具里**，必须走 Hook（见 `commands.md`）。别指望换个解包器就能拿到加密参数。
