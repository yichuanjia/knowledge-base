# PRD: AI 知识库助手系统

## Problem Statement

用户每天面对 GitHub Trending、Hacker News 等海量技术信息源中 AI/LLM/Agent 领域的内容，手动筛选、阅读、分析和归档耗时巨大。缺乏一套自动化的采集→分析→归档管道，无法高效追踪和沉淀 AI 领域技术动态。

## Solution

构建一套 **AI 驱动的个人知识库助手系统**，通过 OpenCode 多 Agent 协作，自动从外部技术信息源采集 AI 领域动态，经 AI 深度分析后生成结构化知识条目（摘要、评分、标签），最终归档为可检索的 JSON 知识库，支持多渠道分发（Telegram / 飞书）。

系统分为三个阶段的流水线：
1. **采集（Collector）** — 从 GitHub / Hacker News 拉取数据，AI 过滤 AI 领域内容
2. **分析（Analyzer）** — 深度分析，生成摘要、技术亮点、评分和标签
3. **整理（Organizer）** — 按 URL 去重，标签清洗，归档并更新索引

## User Stories

1. 作为技术从业者，我希望每天自动获取 GitHub Trending 上 AI 领域的热门仓库，以便不错过重要开源项目
2. 作为技术从业者，我希望每天自动获取 Hacker News 上 AI 相关的热门讨论，以便了解社区关注点
3. 作为用户，我希望采集系统能自动过滤掉非 AI/LLM/Agent 领域的内容，以减少噪音
4. 作为用户，我希望每条采集内容都附带中文摘要，以便快速理解项目核心
5. 作为用户，我希望能对每个项目有一个 1-10 分的相关度评分，以便优先关注高价值内容
6. 作为用户，我希望能看到每个项目的关键技术亮点（2-5 条），以便抓住要点
7. 作为用户，我希望每个项目都有标准化的英文标签，以便后续分类检索
8. 作为用户，我希望系统能自动按 URL 去重，同一条目不重复保存
9. 作为用户，我希望所有知识条目存储在统一目录 `knowledge/articles/` 下，便于管理
10. 作为用户，我希望能有一个 `index.json` 索引文件，快速浏览所有已归档条目
11. 作为用户，我希望采集失败时能自动重试（指数退避），不丢数据
12. 作为用户，我希望单个来源采集失败不阻塞其他来源，各自独立运行
13. 作为用户，我希望通过 `python -m pipeline.main` 一条命令运行完整采集流程
14. 作为用户，我希望能通过 `opencode run <agent>` 独立运行各个 Agent
15. 作为用户，我希望系统日志输出到 `logs/` 目录，便于排查问题
16. 作为用户，我希望敏感配置（API Token）通过环境变量读取，不硬编码
17. 作为用户，我希望能看到采集的趋势分析（共同主题、新概念），了解技术风向
18. 作为用户，我希望能扩展到更多信息源（如 arXiv、Reddit），以覆盖更多领域
19. 作为用户，我希望能通过 Telegram / 飞书推送每日精选，不需打开电脑查看
20. 作为开发者，我希望能用 LangGraph 编排 Agent 工作流，实现更复杂的处理逻辑

## Implementation Decisions

### 架构决策

- **三阶段 Agent 架构**：Collector → Analyzer → Organizer，每个 Agent 独立运行，通过 JSON 数据传递
- **Agent 运行模式**：Collector 使用 Python 直调用 API（性能优先），Analyzer / Organizer 利用 OpenCode subagent 模式（AI 推理优先）
- **双通道采集**：GitHub 通过 Search API（关键词搜索），Hacker News 通过 Firebase API（top stories + 批量详情）

### 模块划分

- `pipeline/` — Collector 的 Python 实现
  - `main.py` — 入口，初始化日志、调用采集并汇总结果
  - `collector.py` — 核心采集逻辑：AI 关键词过滤、GitHub Search、HN API、数据保存
  - `github_api.py` — GitHub 仓库信息查询工具
  - `hn_api.py` — Hacker News API 客户端（带并发详情获取）
- `.opencode/agents/` — OpenCode Agent 定义
  - `collector.md` — 采集 Agent（使用 WebFetch 从页面抓取，subagent 模式）
  - `analyzer.md` — 分析 Agent（读取 raw 数据，AI 分析生成结构化输出，subagent 模式）
  - `organizer.md` — 整理 Agent（去重、格式化、归档、更新索引，subagent 模式）
- `.opencode/skills/` — 可复用技能
  - `github-trending/SKILL.md` — GitHub Trending 采集技能
  - `tech-summary/SKILL.md` — 技术深度分析技能
- `knowledge/` — 数据存储
  - `raw/` — 原始采集数据（`{source}-{date}.json`）
  - `articles/` — 结构化知识条目（`{date}-{source}-{slug}.json`）+ `index.json`
- `workflows/` — LangGraph 工作流（预留）
- `openclaw/` — OpenClaw 部署配置（预留）

### 数据格式

**原始采集数据**（`knowledge/raw/{source}-{date}.json`）：
```json
{
  "source": "github-trending",
  "collected_at": "2026-03-01T10:00:00Z",
  "items": [
    {
      "title": "owner/repo",
      "url": "https://github.com/...",
      "description": "...",
      "stars": 1520,
      "language": "Python"
    }
  ]
}
```

**结构化知识条目**（`knowledge/articles/{id}.json`）—— 必填字段：id, title, source, source_url, collected_at, summary, tags, status

**id 生成规则**：`{collected_date}-{source}-{slug}`

**relevance_score 评分标准**（1-10）：
- 9-10：突破性进展，改变行业格局
- 7-8：对个人技术栈直接有帮助
- 5-6：值得了解，关注后续发展
- 1-4：一般动态，参考价值有限

**status 流转**：draft → reviewed → published

### API 与重试策略

- GitHub Search API：`https://api.github.com/search/repositories`，搜索近一周创建仓库，多查询词串行搜索并去重，无 token 时限速 10 req/min（间隔 3s）
- Hacker News API：`https://hacker-news.firebaseio.com/v0`，获取 top stories → 并发拉取详情（ThreadPoolExecutor，8 线程）
- 自动重试：3 次指数退避（1s / 2s / 4s），全失败后记录日志不阻塞
- 来源隔离：GitHub 和 HN 采集各自独立，一方失败不影响另一方

### AI 过滤策略

- 预定义 59 个 AI 领域关键词列表（英文 + 中文），涵盖 LLM、Agent、RAG、多模态、推理等
- 短关键词（≤3 字符）使用词边界正则匹配，防止子串误匹配
- 同时匹配标题和描述文本

### 标签规范

- 英文小写 + 连字符连接（如 `open-source`、`multi-agent`）
- Organizer 阶段统一清洗格式

## Testing Decisions

### 测试策略

- 测试应覆盖外部行为而非实现细节
- 优先测试：关键词过滤准确性、重试逻辑、JSON 格式正确性、去重逻辑

### 测试范围

- `pipeline/collector.py`：`is_ai_related()` 过滤函数（边界 case 测试）、重复 URL 去重、数据保存格式
- `pipeline/hn_api.py`：重试逻辑、并发获取
- Agent 输出格式：JSON schema 校验
- Organizer 去重：相同 URL 跨日期的正确处理

### 已知参考

- 项目已有 `raw_api_test.py` 用于 API 测试
- 无现有测试框架，建议添加 `pytest`

## Out of Scope

- Web UI / 管理后台
- 全文搜索（暂仅依赖 index.json）
- 社交媒体分发实现（Telegram / 飞书推送 —— 预留 openclaw/ 目录）
- 用户自定义信息源接入
- 多用户支持
- 数据的自动过期和清理
- 移动端访问
- LangGraph 工作流编排（workflows/ 目录已预留，尚未实现）
- 非 AI 领域内容的采集

## Further Notes

- 当前系统 Collector 已完整实现（Python 代码），Analyzer 和 Organizer 以 OpenCode Agent 定义文件形式存在，依赖 OpenCode subagent 运行时调用
- `skills-lock.json` 用于技能版本锁定
- `.env` 文件存放 GITHUB_TOKEN 等环境变量
- `opencode.json.txt` 是 OpenCode 配置文件（重命名自 opencode.json 以避免被执行）
- 系统设计为可在 OpenClaw 平台上部署，通过定时触发实现每日自动运行
- Agent 角色遵循最小权限原则：Collector/Analyzer 禁止 Write/Edit，仅 Organizer 有写入权限
