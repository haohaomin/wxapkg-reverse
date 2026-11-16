# Windows 上的等价操作

`commands.md` 里的命令是 bash 语法，Windows 上照抄会失败。这里给等价写法。

## 0. 先确认自己的家目录（踩过的坑）

```powershell
whoami; hostname; $env:USERPROFILE
```

用户目录名和主机名**经常不一致**（比如主机 `renhao`、用户 `renha`）。别按主机名拼路径。

DSH 的 home 与技能根：

```
C:\Users\<你>\.dsh\                     DSH_HOME
C:\Users\<你>\.dsh\skills\              用户级技能根（本 skill 所在）
C:\Users\<你>\.dsh\redteam\skills\      redteam preset 的第二技能根
```

两个 preset 都覆盖 `$DSH_HOME\skills`：`unrestricted` 靠 `includeDefaultRoots: true`，`redteam` 靠 `customSkillDirs` 里的 `dshHomePath('skills')`。放进去即生效，不用改配置。

## 1. 微信包路径

```powershell
# 旧版微信
$env:USERPROFILE\Documents\WeChat Files\Applet\wx*\<ver>\__APP__.wxapkg
# 微信 4.x
$env:USERPROFILE\Documents\xwechat_files\Applet\wx*\
# 兜底：直接搜
Get-ChildItem $env:USERPROFILE -Recurse -Filter "*.wxapkg" -ErrorAction SilentlyContinue |
  Select-Object -First 20 FullName
```

## 2. 解包工具（都是 .exe，语法同原版）

```powershell
# KillWxapkg：扫 + 解
.\KillWxapkg.exe -in "$env:USERPROFILE\Documents\xwechat_files" -out .\dump -appid

# unveilr
.\unveilr.exe .\dump\wx1234abcd\__APP__.wxapkg -o .\out\1234abcd

# wxappUnpacker（Node）
node .\wuWxapkg.js .\dump\wx1234abcd\__APP__.wxapkg
```

下载 release 时挑 `windows_amd64`。杀软可能报 `KillWxapkg.exe`（Go 二进制 + 扫盘行为），加信任目录后跑。

## 3. 命令替换速查

| bash（mac/Linux） | Windows PowerShell |
| --- | --- |
| `grep -rhoE "pattern" dir` | `Get-ChildItem dir -Recurse -File \| Select-String -Pattern 'x'` |
| `grep -r ... --include=*.js` | `Get-ChildItem dir -Recurse -Filter *.js \| Select-String 'x'` |
| `find . -name "*.wxapkg"` | `Get-ChildItem . -Recurse -Filter *.wxapkg` |
| `sort -u` | `Sort-Object -Unique` |
| `xxd -l 32 f` | `Format-Hex -Path f -Count 32` |
| `cat > f <<EOF` | `@'...'@ \| Set-Content -Encoding utf8 f` |
| `curl -X POST ...` | `curl.exe -X POST ...`（Windows 自带 curl.exe，别用 `curl` 别名） |
| `sha256sum f` | `Get-FileHash f -Algorithm SHA256` |
| `jq -r '.requestDomain[]' f` | 装 `jq`（`winget install jqlang.jq`），或 `(Get-Content f -Raw \| ConvertFrom-Json).requestDomain` |

装了 ripgrep 就统一用 `rg`，两平台语法一致，最省心：

```powershell
winget install BurntSushi.ripgrep.MSVC
rg -o "https?://[^'\"\s]+" .\out -N | Sort-Object -Unique
```

## 4. 提取脚本

`api-extraction.md` 的 `extract.py` 跨平台，只改调用方式：

```powershell
python .\extract.py .\out > report.json
```

Python 从 python.org 装时勾 **Add to PATH**；用 Microsoft Store 版则命令是 `python`。脚本按 UTF-8 读文件，PowerShell 重定向可能写成 UTF-16，用 `Set-Content -Encoding utf8` 或直接 `python .\extract.py .\out | Out-File -Encoding utf8 report.json`。

## 5. devtools（Windows 支持最好）

```powershell
# WeChatOpenDevTools：以管理员权限运行
git clone --depth 1 https://github.com/x0xn/WeChatOpenDevTools
cd WeChatOpenDevTools
# 按 README 选微信版本，跑后在小程序窗口按 F12

# WMPFDebugger：Frida 注入
git clone --depth 1 https://github.com/evi0s/WMPFDebugger
cd WMPFDebugger
# 先开小程序，再运行，Chrome 打开它给的 devtools 端口
```

Frida 装上后 `frida-ps -N`（Windows 是 `-N`，不是 `-U`）：

```powershell
pip install frida-tools
frida-ps -N | Select-String -Pattern "WeChat"
```

`WeChatAppEx.exe` 是小程序宿主进程，hook 它而不是主 `WeChat.exe`。

## 6. 编码

PowerShell 默认代码页可能是 GBK（936），中文输出会乱码：

```powershell
chcp 65001
$OutputEncoding = [Console]::OutputEncoding = [Text.UTF8Encoding]::new()
```

读 UTF-8 文件一律显式指定，别依赖默认：

```powershell
Get-Content .\app-config.json -Raw -Encoding utf8 | ConvertFrom-Json
```

## 7. 权限

- `KillWxapkg` 扫全盘、`WeChatOpenDevTools` patch 进程都要**管理员 PowerShell**。
- 装工具时把目录加进 Defender 排除（`设置 → 病毒和威胁防护 → 排除项`），否则 exe 可能被删。
- 产物目录不要放在 OneDrive 同步盘里——扫描会触发同步风暴。

## 8. 常用一键流程（PowerShell）

```powershell
$wechat = "$env:USERPROFILE\Documents\xwechat_files"
.\KillWxapkg.exe -in $wechat -out .\dump -appid
Get-ChildItem .\dump -Filter "__APP__.wxapkg" -Recurse | ForEach-Object {
    unveilr.exe $_.FullName -o ".\out\$($_.Directory.Name)"
}
Get-ChildItem .\out -Recurse -Filter app-config.json | ForEach-Object {
    (Get-Content $_.FullName -Raw | ConvertFrom-Json).requestDomain
} | Sort-Object -Unique
```
