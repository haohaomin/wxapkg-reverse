# wxapkg 包结构与解密

## 一、明文包结构（大端）

```
off  size  field
0x00  1    magic1        0xBE
0x01  1    magic2        0xED
0x02  4    info1         （常见 0x00000000）
0x06  4    indexInfoLength
0x0A  4    bodyInfoLength
0x0E  1    lastMark      0xED
0x0F  4    fileCount
0x13  ...  index 区
```

index 区每条（大端）：

```
4  nameLen
n  name        （UTF-8，形如 ./app-service.js、./page-frame.html）
4  offset      （相对整个文件的绝对偏移）
4  size
```

各文件数据紧跟在 index 区之后，`offset + size` 应落在文件长度内。

### 内部两条不变量（用来验解密是否成功）

```
fileCount *  平均条目 ≈ (indexInfoLength - 4) / (nameLen+12)
19 + indexInfoLength + bodyInfoLength == 文件长度（±少量 padding）
```

对不上就是**没解密**或**头偏移算错**。

## 二、三种形态

| 形态 | 特征 | 处理 |
| --- | --- | --- |
| 明文 | `xxd -l 4` 得 `beed` | 直接解 |
| PC 加密 | 首 6 字节为 ASCII `V1MMWX` | 取 key 后 XOR 整个 body，再按明文解 |
| 变体/未知 | 头部既不是 `beed` 也不是 `V1MMWX` | 不要猜，走 dump（见 `commands.md`） |

iOS 侧一般不给可直接读的 `wxapkg`，且加密更硬，**别在解包器上死磕**，直接内存 dump 或 Hook。

## 三、探针脚本（先跑这个）

```python
# probe.py  —— 判定形态 + 验证解密是否成功
import sys, struct

def head(p):
    d = open(p, 'rb').read()
    print(f"{p}\n  size={len(d)}  head={d[:16].hex(' ')}")
    if d[:2] == b'\xbe\xed':
        info1, idx, body = struct.unpack('>III', d[2:14])
        cnt = struct.unpack('>I', d[15:19])[0]
        print(f"  PLAINTEXT  fileCount={cnt} idxLen={idx} bodyLen={body} expect={19+idx+body}")
        return
    if d[:6] == b'V1MMWX':
        print(f"  PC-ENCRYPTED key=0x{d[6]:02x}  (用下面的 decrypt 试)")
        return
    print("  UNKNOWN 形态，别硬解")

for p in sys.argv[1:]:
    head(p)
```

## 四、PC 加密解密

已知方案：首 6 字节被替换为 `V1MMWX`，第 7 字节（`data[6]`）作 XOR key，其后的 body 逐字节 XOR。

```python
def decrypt(data: bytes):
    if data[:6] != b'V1MMWX':
        return data
    key = data[6]
    buf = bytearray(data)
    # 关键：从 6 还是 7 开始 XOR，不同版本实现有差异
    for i in range(7, len(buf)):
        buf[i] ^= key
    buf[:6] = b'\xbe\xed\x00\x00\x00\x00'
    return bytes(buf)
```

**不要相信这一段的细节**，用不变量自检：解完拿 `probe.py` 的逻辑验 `fileCount`、`19+idx+body == len`。若失败，把起点在 `6..8` 之间枚举、key 在 `data[6]` 附近取，**以 `KillWxapkg`、`wux1an/wxapkg` 的实际实现为准**，别自己发明。

```bash
# 直接用成熟实现，最省事
KillWxapkg -in <dir> -out <out> -appid
```

## 五、自写解包器（20 行，够用）

```python
import struct, os, sys

def unpack(path, outdir):
    outdir = os.path.abspath(outdir)
    d = open(path, 'rb').read()
    assert d[:2] == b'\xbe\xed', "不是明文包，先解密"
    idx_len, body_len = struct.unpack('>II', d[6:14])
    cnt = struct.unpack('>I', d[15:19])[0]
    p, files = 0x13, []
    for _ in range(cnt):
        nl = struct.unpack('>I', d[p:p+4])[0]; p += 4
        name = d[p:p+nl].decode('utf-8', 'replace'); p += nl
        off, size = struct.unpack('>II', d[p:p+8]); p += 8
        files.append((name, off, size))
    for name, off, size in files:
        rel = name.lstrip('/')
        if rel.startswith('./'):
            rel = rel[2:]
        if not rel or '..' in rel.split('/'):
            print("path traversal, skip:", name); continue
        target = os.path.join(outdir, rel)
        os.makedirs(os.path.dirname(target) or outdir, exist_ok=True)
        open(target, 'wb').write(d[off:off+size])
        print(f"{name}\t{size}")
    print(f"共 {len(files)} 个文件")

if __name__ == '__main__':
    unpack(sys.argv[1], sys.argv[2])
```

坑：`name` 里含 `./`、可能含 `..`（**必须**做路径穿越校验）；分包文件本身也是一个 `wxapkg`（`__sub_package__.wxapkg` 之类），要递归解。

## 六、典型产物

```
app-config.json    页面路由、window/tabBar、networkTimeout、requestDomain、subPackages
app-service.js     全部业务逻辑（Webpack 风格合并）
app-wxss.js
page-frame.html    视图层模板（wxml 编译产物）
app-wxss.wxss
pages/**/*.js      异步分包/懒加载时才单独存在
```

`app-config.json` 的 `requestDomain` 直接就是后端域名白名单——**资产测绘的第一手数据**，比 grep 字符串准。

## 七、重打包

`wux1an/wxapkg` 支持 pack，但装回微信还要过目录命名（md5）、`appinfo` 校验，实操意义有限。

**要验证改动，正确做法**：把解包目录导入微信开发者工具，补 `project.config.json`（`appid` 用测试号），在模拟器里跑。真机验证走 Hook 注入，不要试图替换磁盘上的包。
