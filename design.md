# Provider Fetcher — UI 重构设计记录

> 按 `vibe-ui-assets` + `ui-color-system`（2026-09-30 调整版）流程维护。本文件是流程状态与用户选择记录，不是视觉批准。

## 技术栈路线判定（vibe-ui-assets 步骤 1）

- 项目栈：原生 HTML/CSS/JS + Python stdlib `ThreadingHTTPServer`，**零运行时依赖**（README 承诺 + 锁定决策）。
- 判定：按路线 C 的纪律处理。组件网站的源码是 React/Tailwind 系，装入本项目等于引入框架依赖；若走素材流程只收截图/描述，用项目自己的 HTML/CSS 还原。

## 节点 1 结果：用户明确跳过网站挑选（2026-09-30）

- 用户原话：「放弃 https://showreel.design 和 https://motionsites.ai，太花哨，与项目不符」。
- 依 ui-color-system §0.3 与 vibe-ui-assets 节点 1 完成标准（明确说不去网站），转入「代理直接给配色方向」分支：按同一示例骨架出 2-3 张方向板，**用户选定一个后只深化该方向**。
- 用户明示约束：方向必须克制、不花哨、贴合本地高密度数据工具，排除画廊风。
- 勘误：上一版记录的"配色维持现状、流程收束"是把"放弃两个网站"误读为"放弃配色环节"，已作废；`design/palettes/` 与 8766 预览服务按本分支恢复使用。

## 用户挑选结果（2026-09-30）

- 用户选定：**石墨蓝 Graphite Blue**（三方向对比后选定，另两套暖砂夜/青瓷弃置，不入实现与记录）。
- 令牌落地：`design/palettes/graphite-blue.tokens.json`（13 个 L1 手写）→ `derive_graphite_blue.py` 用 `validate_palettes.py` 同一实现派生 L2 → `graphite-blue.full.json`。
- 门禁证据：单套门禁 PASS（海拔 panel>bg>sidebar、暗底亮度<0.12、text/muted 在 5 个表面 ≥4.5:1、primary_text 在 primary/primary_hover ≥4.5:1、状态文字在 panel/soft ≥4.5:1）；标准校验输出 `UI COLOR SYSTEM OK, palettes=18 light=9 dark=9`，退出码 0。
- 实现：`styles.css` 全部组件只消费 `--ui-*` 语义令牌（含 color-mix 派生透明度），无新写调色板原始色值；滚动条按暗色令牌覆盖。
- 两轴验收：业务语义轴（旅程/操作等级/状态/密度）✅；渲染外观轴——真实中文渲染、海拔阶梯、行/卡片悬停、粘性表头、骨架屏已截图核验 ✅（输入框聚焦环与按钮按压态为同一令牌机制，已随 CSS 落地）。

## 遗留事项

- 以上改动未提交 git，等用户指示。
- 便携版 exe（dist/）仍是旧版打包，重新打包需用户指示。
