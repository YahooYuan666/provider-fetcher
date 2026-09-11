# Provider Fetcher

填 Base URL 和 API Key，拉取当前密钥能用的模型 ID，再用 [models.dev](https://models.dev) 知识库补上上下文窗口、最大输出和输入类型。给没有「Fetch from Provider」的 Agent 填第三方供应商表单。

Windows / macOS / Linux。源码运行只需 Python 3.10+，无第三方运行时依赖。

## 它做什么

1. 向 `{base_url}/models` 发 `GET`（兼容 `/v1/models`、误填的 `/chat/completions`、子路径前缀）。
2. 只把供应商返回的模型 ID 当作现场名单。知识库不会凭空插入或删掉模型。
3. 用 models.dev 铰上上下文、最大输出、输入模态。中转常用后缀（`-high` / `-low` / `-fast` / `-preview` / `-thinking`）会回落到官方基座条目。
4. 获取成功后可手动收藏 **Base URL + API Key**。下次点「再查最新」会重新向供应商拉当前名单，而不是回放旧表。若这次组合尚未收藏，页面会弹出气泡建议收藏。

页面字段：模型 ID、上下文、最大输出、输入、来源。生图 / 生视频模型保留在表里。API 格式只提示「建议先尝试 Responses」。

## 源码运行

```bash
python -m provider_fetcher
```

启动后请在浏览器里查询。如果浏览器没有自动打开，访问 [http://127.0.0.1:8765](http://127.0.0.1:8765)。不要自动开浏览器：

```bash
python -m provider_fetcher --host 127.0.0.1 --port 8765 --no-browser
```

Windows 也可用 `run.bat`，macOS / Linux 可用 `run.sh`。

## Portable（Windows）

`dist/provider-fetcher-portable/` 里是免安装包：

1. 解压整个文件夹，不要只抽 exe。
2. 双击 `ProviderFetcher.exe`。控制台会提示在浏览器里查询；若浏览器未打开，访问 `http://127.0.0.1:8765/`。
3. 数据仍写在 `%APPDATA%\provider-fetcher`，与便携目录分开，升级不会冲掉收藏。

重新打包：

```bash
python -m pip install pyinstaller
python -m PyInstaller --noconfirm provider-fetcher.spec
```

产物在 `dist/provider-fetcher-portable/`。

## 本地数据

| 系统 | 目录 |
| --- | --- |
| Windows | `%APPDATA%\provider-fetcher` |
| macOS | `~/Library/Application Support/provider-fetcher` |
| Linux | `~/.local/share/provider-fetcher` |

其中是知识库缓存、凭据收藏、上次成功拉取的模型表。完整 API Key 只写在本机收藏文件里，页面只显示脱敏片段。

知识库未命中时，上下文和最大输出留空。供应商别名（`codex-auto-review`、`gpt-reserve`、`grok-composer-2.5-fast` 等）如果目录里没有对应基座，不会猜测。

## 测试

```bash
python -m unittest discover -s tests -v
```
