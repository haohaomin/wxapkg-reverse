# examples

一条命令验证整条链路。不需要微信、不需要装任何逆向工具，只要 `python3`。

```bash
./run.sh          # macOS / Linux
python run.py     # 或在 Windows 上逐个跑，见下
```

## 你会看到什么

```console
$ ./run.sh
▶ 1/4  造样例包（主包 + 分包）
  sample/__APP__.wxapkg      1031 B  (4 files)
  sample/sub_detail.wxapkg   265 B  (2 files)

▶ 2/4  探针：判加密形态 + 结构自检
sample/__APP__.wxapkg
  size=1031  head=be ed 00 00 00 00 00 00 00 71 00 00 03 83 ed 00
  PLAINTEXT  fileCount=4 idxLen=113 bodyLen=899  [OK]

▶ 3/4  解包（主包和分包都要解，实战里漏分包是头号错误）
  [__APP__]
  ./app-config.json                      293 B
  ./app-service.js                       480 B
  ./page-frame.html                       75 B
  ./app-wxss.wxss                         51 B
  -> 4/4 files  =>  examples/out/__APP__
  [sub_detail]
  ./pages/detail/detail.js               138 B
  ./pages/detail/detail.wxml              34 B
  -> 2/2 files  =>  examples/out/sub_detail

▶ 4/4  提取域名 / 接口 / 云函数 / 签名线索

requestDomain（接口白名单）  (2)
  https://api.example.com
  https://cdn.example.com

URL  (3)
  https://api.example.com
  https://api.example.com/v1/order/detail
  https://cdn.example.com

接口路径  (1)
  /v1/order/list

云函数  (1)
  getUserProfile

签名线索  (3)
  data: { page: page, ts: Date.now(), sign: getSign(page) },
  function getSign(ts) {
  return md5("GET" + ts + "SECRET_KEY_PLACEHOLDER");

✔ 全链路通过：造包 → 探针 → 解包 → 提取
```

四步走完，产物在 `out/`，可以直接打开看。

## 文件

| 文件 | 作用 |
| --- | --- |
| `make_sample.py` | 按 wxapkg 大端结构造合成包（主包 4 文件 + 分包 2 文件） |
| `probe.py` | 判加密形态，用 `19 + idxLen + bodyLen == 文件长度` 自检 |
| `unpack.py` | 解包，带路径穿越防护 |
| `extract.py` | 提 `requestDomain` / URL / 接口路径 / 云函数 / 签名线索 |
| `run.sh` | 把上面四个串起来 |

后三个与 `../references/wxapkg-format.md`、`../references/api-extraction.md` 里的代码是同一份逻辑，独立成文件是为了能直接跑。

## Windows

`run.sh` 是 bash 脚本。Windows 上逐条跑：

```powershell
python make_sample.py sample
python probe.py sample\__APP__.wxapkg
python unpack.py sample\__APP__.wxapkg out\__APP__
python extract.py out
```

## 这只是合成包

`make_sample.py` 造的是**结构合法**的 wxapkg，用来验证 `probe` / `unpack` / `extract` 三段代码正确。它也刻意放了接口调用、云函数、`sign` 片段，好让 `extract` 有东西可抓。

它**不是**微信的真实产物，也不代表真实加密形态。真实包请用 `KillWxapkg` / `unveilr`，三种形态的判定见 `../references/wxapkg-format.md`。

## 自己造一个更狠的

改 `make_sample.py` 里的 `APP_SERVICE`，塞进你想验证的写法（模板字符串拼 URL、`wx.cloud` 调用、混淆后的 sign），看 `extract.py` 能不能抓出来。抓不住就说明提取规则要补。
