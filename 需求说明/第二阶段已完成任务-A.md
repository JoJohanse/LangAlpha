# 第二阶段已完成任务-A（截至当前版本）

## 1. 文档说明
- 统计范围：第二阶段当前已完成改造，不包含未实现项。
- 统计口径：以代码已落地与 Docker 测试结果为准。
- 结论摘要：第二阶段已形成“资讯增强主链路 + 日报并回 Insight”的可用版本。

## 2. 已完成任务清单（按能力域）
### 2.1 资讯增强（Phase 2A）
- 已完成新闻标签落库与标签提取流程：`news_article_tags`，覆盖 `sector/topic/region/tags` 维度。
- 已完成资讯热榜能力：`hot-rank` 排序与列表输出。
- 已完成标签维度检索：按 `sector`、`topic` 查询资讯列表。
- 已完成单条资讯一键提问：`POST /api/v1/news/{article_id}/ask`，可将文章上下文注入对话入口。
- 已完成 Dashboard 资讯多视图链路：`Events / Raw News / 7x24` 并行展示与联动。

### 2.2 日报能力收敛（原 Phase 2B 调整）
- 已按需求取消独立 `briefs` 模块路线，改为 Insight 主链路承载日报能力。
- 已完成 `AIDailyBriefCard` 早/晚切换。
- 已完成早晚报时间口径落地：
  - 早报：`00:00:00 <= t < 12:00:00`（ET）
  - 晚报：`12:00:00 <= t < 24:00:00`（ET）
- 已完成 Insight 响应扩展：返回 `brief_session`（`morning/evening`）。
- 已完成简报生成时间窗约束：生成前按窗口拉取并二次过滤新闻，提示词仅使用窗口内新闻。

### 2.3 兼容性与回归
- 第一阶段事件链路保持兼容：`/api/v1/events*` 与 marker/deeplink 主流程无破坏性改动。
- MarketView 与 Dashboard 的事件跳转闭环保持可用。

## 3. 接口 / 模型 / 迁移变更摘要
### 3.1 新增并保留接口
- `GET /api/v1/news/hot-rank`
- `GET /api/v1/news/by-sector/{sector}`
- `GET /api/v1/news/by-topic/{topic}`
- `POST /api/v1/news/{article_id}/ask`

### 3.2 日报语义调整
- 日报不再作为独立 `/api/v1/briefs/*` 主路径对外承诺。
- 日报能力收敛至 `/api/v1/insights/*` 与 Dashboard 的 Insight 卡片交互。

### 3.3 数据库迁移结论
- `012`：新增 `news_article_tags`（历史上曾引入 `daily_briefs`）。
- `013`：明确删除 `daily_briefs`，与“日报并回 Insight”一致。

### 3.4 关键类型变更
- 新闻侧：新增/扩展 `NewsTag`、`NewsHotRankItem`、`NewsAskRequest`、`NewsAskResponse`。
- Insight 侧：响应扩展 `brief_session`（`morning/evening`）。

## 4. 测试与验收结果（Docker）
### 4.1 后端
以下测试在 Docker 环境通过：
- `tests/unit/server/app/test_news_phase2.py`
- `tests/unit/server/app/test_insights.py`
- `tests/unit/server/services/test_insight_service.py`

### 4.2 前端
以下 Dashboard 相关 vitest 用例在 Docker 环境通过：
- `useDashboardData` 相关用例
- `Dashboard.eventDeepLink` 相关用例

### 4.3 镜像构建
- 前端镜像构建通过：`docker build -f deploy/Dockerfile.web ...`
- 构建中存在 secrets 使用告警，但不阻断构建结果。

## 5. 偏差说明（相对最初第二阶段计划）
- 原计划中的“独立日报模块”已按需求调整为“Insight 基座上的早/晚报能力”。
- 该调整属于架构收敛，不属于功能回退。

## 6. 当前未进入范围
以下能力仍不在本阶段已完成范围内：
- 研报线
- TTS
- 地图能力
- 观点一致性
- 自定义看板

## 7. 事实核对清单
- 每条“已完成项”均可映射到代码实现或测试结果。
- 接口清单与当前实现一致（不再对外承诺独立 `/api/v1/briefs/*` 主路径）。
- 早/晚报时间定义与代码一致（ET 00:00/12:00 分界）。
- Docker 结论与最近执行日志一致。

## 8. 说明与后续
- 本文档为第二阶段阶段性里程碑记录。
- 本文档不替代“第二阶段未完成项/任务-B”规划文档。
