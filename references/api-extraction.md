# 从产物到可重放请求

解包只是开始。真正有价值的是：**这个后端有哪些接口、怎么鉴权、sign 怎么算**。

## 一、先取权威域名清单

`app-config.json` 的 `requestDomain` 是小程序唯一允许请求的域名集合，比 grep 字符串准得多。

```bash
find ./out -name app-config.json | while read f; do
  echo "== $f"; jq -r '.requestDomain[]? // empty' "$f"
done | sort -u
```

`subPackages` 里的每个 `root` 也要看——很多业务接口藏在分包页面里。

## 二、找请求封装

几乎没人直接写 `wx.request`，都包了一层。先定位封装，后面所有接口都从它进出。

```bash
# 找封装点
grep -rn "wx.request" ./out --include=*.js | head -20
grep -rnE "(function|const|var)\s+\w*[Rr]equest\w*\s*[=(]" ./out --include=*.js | head -20
```

典型形态：
```js
const http = ({url, method='GET', data, header}) => new Promise(...)
// 或
class Request { get(url, params) { ... } }
```

找到后，所有 `http.get('/api/xxx')` 就是对接口的调用点，配合上下文能还原参数。

## 三、批量提取（脚本）

```python
# extract.py  —— python3 extract.py ./out > report.json
import os, re, json, sys

ROOT = sys.argv[1]
URL_RE   = re.compile(r'https?://[A-Za-z0-9._~:/?#@!$&*+,;=%\-]+')
PATH_RE  = re.compile(r'["\'](/[a-zA-Z0-9_\-/]{3,80})["\']')
TPL_RE   = re.compile(r'`\$\{[^}]+\}(/[a-zA-Z0-9_\-/{}$.]{2,80})`')
CF_RE    = re.compile(r'callFunction\s*\(\s*\{[^}]*name\s*:\s*["\']([^"\']+)')
SIGN_RE  = re.compile(r'(sign|signature|getSign|calcSign|encrypt|sm2|sm4|aes|rsa|hmac|md5|sha256)', re.I)

urls, paths, cfs, signs, domains = set(), set(), set(), set(), set()
for dp, _, fs in os.walk(ROOT):
    for fn in fs:
        p = os.path.join(dp, fn)
        if fn == 'app-config.json':
            try:
                cfg = json.load(open(p, encoding='utf-8', errors='replace'))
                domains.update(x for x in cfg.get('requestDomain', []) if isinstance(x, str))
            except Exception: pass
        if not fn.endswith(('.js', '.json')): continue
        try: txt = open(p, encoding='utf-8', errors='replace').read()
        except Exception: continue
        urls.update(URL_RE.findall(txt))
        paths.update(PATH_RE.findall(txt))
        paths.update(TPL_RE.findall(txt))
        cfs.update(CF_RE.findall(txt))
        for m in SIGN_RE.finditer(txt):
            s = max(0, m.start()-40)
            signs.add(txt[s:m.end()+40].replace('\n', ' '))

print(json.dumps({
    'domains': sorted(domains),
    'urls': sorted(urls),
    'paths': sorted(paths),
    'cloud_functions': sorted(cfs),
    'sign_candidates': sorted(signs)[:200],
}, ensure_ascii=False, indent=2))
```

输出直接能进报告。`sign_candidates` 是带上下文的片段，比裸函数名好定位。

## 四、定位签名

按这个顺序，命中即停：

1. **搜名字**：`sign`、`signature`、`getSign`、`calcSign`、`x-sign`、`X-Signature`。
2. **搜加密库特征**：`CryptoJS`、`sm-crypto`、`JSEncrypt`、`forge`、`md5(`、`hmac`。
3. **看 header 组装处**：搜索把 `timestamp` / `nonce` / `sign` 放进 header 的那段，签名入口就在附近。
4. **反查调用链**：从 request 封装往上，谁给它塞了 `sign`。

典型签名构造：
```js
const sign = md5(`${method}${path}${JSON.stringify(data)}${ts}${nonce}${SECRET}`).toUpperCase()
header.sign = sign
```

`SECRET` 常硬编码在同文件或 `config.js`（搜 `secret`、`appKey`、`APP_KEY`、`salt`）。

**验证**：在 devtools Console 里用相同输入调一次，输出与线上 header 一致才算拿到。

## 五、参数加密

| 特征 | 算法 | 判定 |
| --- | --- | --- |
| 16/24/32 字节 key + 16 字节 IV | AES-CBC | `aes` + `CBC` + `Pkcs7` |
| 16 字节 block、国密库 | SM4 | `sm-crypto`、`sm4` |
| 长串 base64 + 公钥 | RSA | `JSEncrypt`、`setPublicKey` |
| 固定 32 位 hex | MD5（非加密，只防篡改） | `md5` |
| 请求体整体 `{"data":"<base64>"}` | 多为 AES + 自定义协议头 | 找解密函数反向确认 |

拿到算法与 key 后，**用 Python 复现一遍**（`pycryptodome` / `gmssl`），与线上结果对齐再写脚本。

## 六、云开发

```bash
grep -rhoE "callFunction\s*\(\s*\{[^}]*name\s*:\s*['\"][^'\"]+" ./out | grep -oE "['\"][^'\"]+$" | tr -d "'\"" | sort -u
```

云函数不在 HTTP 层，抓包看不到；要分析逻辑得拿到环境 `envId` 与密钥后调 `@cloudbase/cli` / `@cloudbase/manager-node`。

## 七、产出可重放请求

从 devtools 的 Network 面板复制 **整份** 请求（含所有 header）落成 curl：

```bash
curl -X POST 'https://api.example.com/v1/order/list' \
  -H 'content-type: application/json' \
  -H 'x-sign: <sign>' -H 'x-timestamp: <ts>' -H 'x-nonce: <nonce>' \
  -H 'authorization: Bearer <token>' \
  --data-raw '{"page":1,"size":20}'
```

再写一个最小重放器，把 sign 计算接进去：

```python
# replay.py —— 参数化重放，验证签名算法
import hashlib, time, uuid, json, requests

SECRET = "<从产物里拿到的>"
def sign(method, path, body, ts, nonce):
    raw = f"{method}{path}{json.dumps(body, separators=(',',':'))}{ts}{nonce}{SECRET}"
    return hashlib.md5(raw.encode()).hexdigest().upper()

def call(path, body, token):
    ts, nonce = str(int(time.time()*1000)), uuid.uuid4().hex[:16]
    h = {"content-type": "application/json", "x-timestamp": ts, "x-nonce": nonce,
         "x-sign": sign("POST", path, body, ts, nonce), "authorization": f"Bearer {token}"}
    r = requests.post("https://api.example.com" + path, json=body, headers=h, timeout=10)
    print(r.status_code, r.text[:300])
    return r
```

## 八、收进报告

`endpoints.csv` 五列够用：

```
method,path,domain,auth,sign,source_file
POST,/v1/order/list,api.example.com,Bearer,sign=md5(method+path+body+ts+nonce+SECRET),pages/order/list.js
```

`source_file` 必须填——否则别人无法复核这条接口是从哪来的。
