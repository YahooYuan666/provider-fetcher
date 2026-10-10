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

## 测试

```bash
python -m unittest discover -s tests -v
```

## 许可

MIT
