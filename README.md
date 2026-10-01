# Provider Fetcher

给 AI Agent 新手用的本地小工具。面对 ZCode 这类 Agent 时，第三方供应商往往要填 **Base URL、API Key、模型 ID、上下文窗口、最大输出、输入类型**。很多 Agent 没有「Fetch from Provider」，新手也不清楚模型窗口限制。这个工具用来快速查阅当前密钥能用的模型，并跟上供应商改名单。

填 Base URL 和 API Key，拉取现场模型 ID，再用 [models.dev](https://models.dev) 补上下文、最大输出和输入类型。Windows / macOS / Linux。源码运行只需 Python 3.10+。

<p align="left">
  <img src="provider_fetcher/web/logo.svg" width="64" height="64" alt="Provider Fetcher mark">
</p>

## 它解决什么

- 不会填第三方供应商表单时，先查出当前 Key 能调哪些模型 ID。
- 供应商随时增删或改名模型时，用收藏的凭据再查最新名单，而不是死记旧 ID。
- 知识库补上 Agent 表单里常要的上下文、最大输出、输入模态；对不上就留空，不猜。

## 它做什么

1. 向 `{base_url}/models` 发 `GET`（兼容 `/v1/models`、误填的 `/chat/completions`、子路径前缀）。
2. 只把供应商返回的模型 ID 当作现场名单。知识库不会凭空插入或删掉模型。
3. 用 models.dev 铰上上下文、最大输出、输入模态。中转常用后缀（`-high` / `-low` / `-fast` / `-preview` / `-thinking`）会回落到官方基座条目。
4. 获取成功后可命名并收藏 **Base URL + API Key**。下次点「再查最新」会重新向供应商拉当前名单。若这次组合尚未收藏，右下角会弹出气泡建议收藏。
5. 一键生成 [OpenCode](https://opencode.ai) 的供应商配置文件 `opencode.json`：模型 ID、上下文窗口、最大输出、推理与工具调用支持直接写入，下载即用。
6. 拉取 OpenCode Zen（`opencode.ai/zen/v1`，密钥可用 `public`）时自动铰链 Zen 官方目录镜像（models.dev 的 opencode 供应商），免费模型带徽章置顶。另有一个「规格参考分」列，见下。

### 关于「免费」

免费判定是**纯被动**的，与 OpenCode 桌面版结果一致，只用 models.dev 目录里的 opencode 供应商（Zen 官方目录）数据，不发任何探测请求：

1. **沿用桌面版的 `isFree` 规则**（源码 `packages/app/src/components/dialog-select-model.tsx`）：`provider === "opencode" && (!cost || cost.input === 0)`——没有 cost 数据也算免费，只看 input 不看 output。
2. **再排除 `status == "deprecated"`**：Zen 下架的模型仍留在目录和公开 `/models` 里，桌面版不会列出。当前 34 个标称免费模型里有 26 个已废弃，过滤后剩下的 8 个与桌面版完全相同。

免费模型置顶，并显示目录里的正式显示名（「Muse Spark 1.3 Free」对应 ID `muse-spark-1.3-contributor-free」）。

### 关于「规格参考分」

这一列**不是模型能力评分**。目前没有任何社区榜单或公开基准能覆盖这些中转/聚合模型，工具也不做实测评测——它只是把目录里已经写明的参数规格按固定权重折算成一个便于横向对照的数：

| 维度 | 满分 |
| --- | --- |
| 上下文窗口 | 40 |
| 最大输出 | 20 |
| 推理档位 | 15 |
| 工具调用 | 15 |
| 多模态输入 | 6 |
| 结构化输出 | 4 |

权重由本工具设定，**不是行业标准，也没有实测依据**。把鼠标悬停在分数上可以看到逐项明细（如 `上下文窗口 40/40 · 最大输出 16/20 · …`），每一分都可核对。纸面参数漂亮不代表实际表现好，选模型请以自己的实测为准。

### 外部能否直连（实测）

「免费」不等于「能在本工具外部调用」：Zen 的免费档限制为**只能在 OpenCode 客户端内部使用**，外部 API 直连会返回 403 `OpenCode's free tier can only be used from within`。这一点目录里查不到，只有发请求才知道——所以另设「实测外部调用」按钮，对每个免费模型发一次 1-token 请求，结果写入「实测外部调用」列：外部可调用 / 仅限 OpenCode 客户端 / 上游已下架 / 需要有效 API Key / 服务端错误。结果存在本机，重启后仍在。探测带 3 秒间隔、单次上限 40 个模型，避免触发限流。

页面字段：模型 ID、上下文窗口、最大输出、输入类型、推理等级、结构化输出、来源。推理等级列显示该模型的推理等级（如 `low → medium → high`）及推理参数提示；结构化输出列标记是否支持结构化输出。生图 / 生视频模型保留在表里。API 格式只提示「建议先尝试 Responses」。

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

产物在 `dist/provider-fetcher-portable/`。GitHub Release 提供已验证的 Windows zip，解压后整夹运行。API Key 只保存在本机用户目录，不会打进 zip 或 Git 仓库。

## 本地数据

| 系统 | 目录 |
| --- | --- |
| Windows | `%APPDATA%\provider-fetcher` |
| macOS | `~/Library/Application Support/provider-fetcher` |
| Linux | `~/.local/share/provider-fetcher` |

其中是知识库缓存、凭据收藏、上次成功拉取的模型表。完整 API Key 只写在本机收藏文件里，页面只显示脱敏片段。

每次启动会在后台自动刷新一遍知识库；更新失败（比如离线）就沿用本地缓存，也可以随时在页面里点「更新知识库」。

知识库未命中时，上下文和最大输出留空。供应商别名如果目录里没有对应基座，不会猜测。

## 生成 OpenCode 配置

模型列表上方点「生成 OpenCode 配置」，下载 `opencode.json`，放到 OpenCode 的全局配置路径。OpenCode 三端都读用户主目录下的 `.config/opencode/`（源码用 `xdg-basedir` 解析，无平台特判）：

| 环境 | 路径 |
| --- | --- |
| Windows | `%USERPROFILE%\.config\opencode\opencode.json` |
| WSL | `~/.config/opencode/opencode.json`（Windows 侧经 `\\wsl.localhost\<发行版>\home\<用户名>\...` 访问，`wsl -l` 查发行版名） |
| macOS | `~/.config/opencode/opencode.json` |

- 设了 `XDG_CONFIG_HOME` 或 `OPENCODE_CONFIG_DIR` 时路径随之改变；放进项目根目录的 `opencode.json` 会合并覆盖全局配置。
- API Key 默认明文写入导出文件（仅存本机，别提交别分享）；不想落盘就改用 `opencode auth login`，然后把 `options.apiKey` 删掉。
- 只导出对话模型；目录未命中的模型保持现场 ID 写入，但上下文或最大输出缺一个时不带 `limit` 字段（OpenCode schema 里两者必填）。
- 目录声明了推理强度档位的模型会写入 OpenCode `variants`（每个档位对应 `reasoningEffort`），在 OpenCode 里用 `供应商/模型#档位` 选择强度，例如 `my-relay/grok-4.7#xhigh`；不带 `#` 跑 API 默认档。

## 测试

```bash
python -m unittest discover -s tests -v
```

## 许可

MIT
