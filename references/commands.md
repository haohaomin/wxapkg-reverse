# 命令手册：取包 · 解包 · 调试 · Hook

## 一、包路径速查

微信版本换了目录，**优先让工具扫，路径只作兜底**。

| 平台 | 路径 |
| --- | --- |
| macOS 旧版 | `~/Library/Containers/com.tencent.xinWeChat/Data/.wxapplet/packages/wx*/` |
| macOS 微信 4.x | `~/Library/Containers/com.tencent.xinWeChat/Data/Documents/app_data/radium/Applet/packages/wx*/` |
| Windows | `%USERPROFILE%\Documents\WeChat Files\Applet\wx*\<ver>\__APP__.wxapkg` |
| Windows 4.x | `%USERPROFILE%\Documents\xwechat_files\Applet\wx*\` |
| Android（root） | `/data/data/com.tencent.mm/MicroMsg/<32位md5>/appbrand/pkg/*.wxapkg` |
| iOS | 沙盒 `Library/Weapp/`，一般走 dump |

```bash
# 全盘找，避免猜路径
find ~/Library/Containers/com.tencent.xinWeChat -name "*.wxapkg" 2>/dev/null | head -20
```

## 二、解包

```bash
# 1) KillWxapkg（扫 + 解，一步）
KillWxapkg -in ~/Library/Containers/com.tencent.xinWeChat -out ./dump -appid

# 2) unveilr（单包，最稳）
unveilr ./dump/wx1234abcd/__APP__.wxapkg -o ./out/1234abcd

# 3) wux1an/wxapkg（带重打包）
wxapkg unpack ./__APP__.wxapkg -o ./out

# 4) wxappUnpacker（把 app-service.js 拆回页面级 js）
node wuWxapkg.js ./__APP__.wxapkg
```

分包要单独解，且**主包已解在同一父目录**：

```bash
for f in ./dump/wx1234abcd/*.wxapkg; do [ "$(basename $f)" != "__APP__.wxapkg" ] && unveilr "$f" -o ./out/1234abcd; done
```

## 三、导入开发者工具跑起来

```bash
cd ./out/1234abcd
cat > project.config.json <<'EOF'
{ "appid": "touristappid", "projectname": "re", "libVersion": "latest",
  "setting": { "urlCheck": false, "es6": false, "minified": false } }
EOF
```

微信开发者工具 →「导入项目」→ 选该目录 → `appid` 填测试号（或原 appid 若你已登录）。`urlCheck: false` 关掉域名校验，本地接口才能连。

## 四、PC 微信开 devtools

```bash
# 方案 1：WeChatOpenDevTools（Windows，管理员权限跑）
git clone --depth 1 https://github.com/x0xn/WeChatOpenDevTools && cd WeChatOpenDevTools
# 按 README 选对应微信版本，运行后小程序窗口按 F12

# 方案 2：Python 版（Win/Mac）
python WeChatOpenDevTools.py

# 方案 3：WMPFDebugger（Frida 注入，会话稳定）
git clone --depth 1 https://github.com/evi0s/WMPFDebugger && cd WMPFDebugger
# 按其 README 先启动微信小程序，再运行，用 Chrome 打开给出的 devtools 端口
```

开了 devtools 之后：**先 Network 抓一轮真实请求，再回头读代码**。

打开后立刻做的三件事：

```js
// Console 里
Object.keys(__wxConfig.global)                       // 全局配置
__wxConfig.global.appConfig.pages                   // 全部页面路由
__wxConfig.global.userInfo                          // 当前用户态（可能有 openid）
```

## 五、抓包（devtools 之外的兜底）

```bash
# mitmproxy：装证书到设备/系统信任区，抓 HTTPS
mitmproxy -p 8080 --set confdir=~/.mitmproxy

# Android 上把小程序的域名挑出来做定向抓包
mitmdump -p 8080 -w flow.dump "~d api.example.com"
```

小程序一般**不做 pinning**，但会受「合法域名」限制：把 DNS 或 hosts 指向自己的代理即可（`urlCheck` 只影响开发者工具，不影响线上）。

## 六、Frida：dump 已解密的 wxapkg

磁盘上是加密的、只有运行时才解密时用。

```js
// dump_wxapkg.js —— frida -U -f com.tencent.mm -l dump_wxapkg.js
const pathByFd = {};
const openP = Module.findExportByName(null, 'open');
if (openP) Interceptor.attach(openP, {
  onEnter(a) { try { this.path = a[0].readCString(); } catch (e) {} },
  onLeave(r) { const fd = r.toInt32(); if (this.path && fd > 0) pathByFd[fd] = this.path; }
});

const readP = Module.findExportByName(null, 'read');
if (readP) Interceptor.attach(readP, {
  onEnter(a) { this.fd = a[0].toInt32(); this.buf = a[1]; this.cnt = a[2].toInt32(); },
  onLeave(r) {
    const n = r.toInt32();
    if (n <= 0 || !pathByFd[this.fd]) return;
    if (this.buf.readU8() === 0xbe && this.buf.add(1).readU8() === 0xed) {
      const name = `/tmp/dump_${Date.now()}.wxapkg`;
      const f = new File(name, 'wb'); f.write(this.buf.readByteArray(n)); f.flush(); f.close();
      console.log('[+] dumped', name, n, pathByFd[this.fd]);
    }
  }
});
```

真机要 root + `frida-server` 同架构：

```bash
adb push frida-server /data/local/tmp/ && adb shell "su -c '/data/local/tmp/frida-server &'"
frida-ps -U | grep tencent
```

## 七、Hook 业务请求（最快看到 sign）

**首选：改解包产物，在开发者工具里插桩。**

在 `app.js` 最前面（或 `app-service.js` 顶部）插入：

```js
(function () {
  const _req = wx.request;
  wx.request = function (o) {
    console.log('[REQ]', o.method || 'GET', o.url, JSON.stringify(o.data), JSON.stringify(o.header));
    const ok = o.success;
    o.success = function (r) { console.log('[RES]', o.url, JSON.stringify(r.data).slice(0, 500)); ok && ok(r); };
    return _req.apply(this, arguments);
  };
  const _cf = wx.cloud && wx.cloud.callFunction;
  if (_cf) wx.cloud.callFunction = function (o) {
    console.log('[CF]', o.name, JSON.stringify(o.data));
    return _cf.apply(this, arguments);
  };
})();
```

第二条路：定位 sign 函数后在 Console 直接调，输入自己构造，看输出是否与线上一致。**能重放才算拿到**。

## 八、接口与资产提取

```bash
# 全量 URL
grep -rhoE "https?://[A-Za-z0-9._~:/?#@!$&'*+,;=%-]+" ./out | sed 's/[",)]$//' | sort -u > urls.txt

# baseURL / 路径拼接
grep -rhoE "(baseUrl|BASE_URL|apiHost|host)\s*[:=]\s*['\"][^'\"]+" ./out | sort -u

# 合法域名（最准的资产清单）
for f in $(find ./out -name app-config.json); do jq -r '.requestDomain[]?' $f; done | sort -u

# 云开发函数名
grep -rhoE "callFunction\s*\(\s*\{[^}]*name\s*:\s*['\"][^'\"]+" ./out | grep -oE "['\"][^'\"]+$" | sort -u

# 接口路径（相对路径拼接最常见）
grep -rhoE "['\"](/[a-zA-Z0-9_/-]{3,60})['\"]" ./out | tr -d "'\"" | sort -u | head -100
```

输出直接进 `httpx` 做存活：

```bash
cat urls.txt | ~/.local/bin/pd-httpx -sc -title -tech-detect
```

## 九、收尾

- 产物目录打一份 `sha256` 与工具版本，报告里写清「还原产物 / 原始源码」的区别。
- `out/` 里的 JS 含密钥与用户数据，按敏感文件处理。
