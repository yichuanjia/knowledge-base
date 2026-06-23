# AGENTS.md — AI 知识库助手项目规范

## 项目概述
个人 AI 知识库助手系统。自动从技术信息源（GitHub Trending、Hacker News）
采集内容，AI 分析后结构化存储，支持多渠道分发。

## 技术栈
- 语言: Python 3.12
- AI 编排: OpenCode + 国产大模型（DeepSeek/Qwen/GLM/Kimi）
- 工作流: LangGraph（第 3 周引入）
- 部署: OpenClaw（第 4 周引入）
- 依赖管理: pip + requirements.txt
- 版本控制: Git

## 编码规范
- 遵循 PEP 8 规范
- 变量命名: snake_case
- 类名: PascalCase
- 所有函数必须有 docstring（Google 风格）
- 禁止裸 print()，使用 logging 或写入文件
- 日志统一使用 Python `logging` 模块，格式：`%(asctime)s [%(levelname)s] %(name)s: %(message)s`
- 默认日志级别 INFO，调试时切换 DEBUG
- 日志输出到 `logs/` 目录，单文件按天轮转
- 禁止在日志中输出 API Key 或敏感信息
- 禁止 import *
- 文件编码统一 UTF-8

## 项目结构
ai-knowledge-base/
├── AGENTS.md                  — 项目规范（本文件）
├── opencode.json              — OpenCode 配置
├── .opencode/
│   ├── agents/                — Agent 角色定义文件
│   │   ├── collector.md
│   │   ├── analyzer.md
│   │   └── organizer.md
│   └── skills/                — 可复用技能包
│       ├── github-trending/SKILL.md
│       └── tech-summary/SKILL.md
├── knowledge/
│   ├── raw/                   — 原始采集数据（JSON）
│   └── articles/              — 结构化知识条目（JSON）
├── logs/                       — 运行日志
├── pipeline/                  — 自动化流水线（Week 2）
├── workflows/                 — LangGraph 工作流（Week 3）
├── tests/                     — 测试用例
└── openclaw/                  — OpenClaw 部署配置（Week 4）

## 内容规范
- 摘要语言: 中文
- 摘要长度: 不超过 100 字
- 技术术语保留英文原文（如 LangGraph、Agent、Token）
- 评分标准: 1-10 分，9-10 改变格局，7-8 直接有帮助，5-6 值得了解

## 知识条目格式

### 原始数据（`knowledge/raw/`）

Collector 写入的原始采集数据，JSON 文件命名格式 `{source}-{date}.json`：

```json
{
  "source": "github-trending",
  "collected_at": "2026-03-01T10:00:00Z",
  "items": [
    {
      "title": "openclaw",
      "url": "https://github.com/example/openclaw",
      "description": "An open-source AI Agent runtime",
      "stars": 1520,
      "language": "Python"
    }
  ]
}
```

采集失败时额外添加 `"error": true` 及 `"error_message"` 字段。

### 结构化条目（`knowledge/articles/`）

每条知识以 JSON 文件存储在 `knowledge/articles/` 目录下：

```json
{
  "id": "2026-03-01-github-openclaw",
  "title": "OpenClaw: 开源 AI Agent 运行时",
  "source": "github-trending",
  "source_url": "https://github.com/example/project",
  "collected_at": "2026-03-01T10:00:00Z",
  "summary": "一句话中文摘要（不超过 100 字）",
  "analysis": {
    "tech_highlights": ["多 Agent 路由", "50+ 平台支持"],
    "relevance_score": 9
  },
  "tags": ["agent", "runtime", "open-source"],
  "status": "draft"
}
```

**必填字段**：id, title, source, source_url, collected_at, summary, tags, status

**source 有效值**：
- `github-trending` — GitHub Trending 采集
- `hacker-news` — Hacker News 采集

**status 可选值及流转**：
- `draft` — 采集 Agent 写入，待分析
- `reviewed` — 分析 Agent 完成分析后更新
- `published` — 整理 Agent 归档后更新

**注意**：`analysis` 字段由 Analyzer Agent 在阶段 2 填入，Collector 写入 draft 时不包含该字段。

**标签命名规范**：
- 统一使用小写英文、连字符连接（如 `ai-agent`、`open-source`）
- 禁止中文标签
- 不使用空格或下划线
- 整理阶段按规范统一清洗

## 采集与处理流程

### 阶段 1: 采集（Collector Agent）
1. 从 GitHub Trending / Hacker News 拉取原始数据
2. **内容过滤**：用 AI 判断每条目是否属于 AI/LLM/Agent 领域，不相关的直接丢弃
3. 将原始数据写入 `knowledge/raw/` 目录（JSON）

### 阶段 2: 分析（Analyzer Agent）
1. 读取 `knowledge/raw/` 中 status 为 `draft` 的条目
2. 生成摘要、技术亮点、相关性评分等结构化信息
3. 写入 `knowledge/articles/`，status 更新为 `reviewed`

### 阶段 3: 整理（Organizer Agent）
1. 读取 `knowledge/articles/` 中 status 为 `reviewed` 的条目
2. **去重**：按 `source_url` 精确匹配去重，同一 URL 仅保留最新条目
3. **标签规范化**：统一标签格式（小写、连字符连接）
4. 归档后 status 更新为 `published`

### 错误处理
- API 请求失败时写入 `knowledge/raw/` 并标记 `"error": true`，记录错误信息
- 自动重试 3 次，间隔采用指数退避（1s / 2s / 4s）
- 采集失败不阻塞其他来源，各自独立运行

## Agent 角色概览

| 角色 | 文件 | 职责 |
|------|------|------|
| 采集 Agent | .opencode/agents/collector.md | 从外部源采集技术动态 |
| 分析 Agent | .opencode/agents/analyzer.md | 深度分析和价值评估 |
| 整理 Agent | .opencode/agents/organizer.md | 去重、格式化、归档 |

## 测试策略
- 框架: pytest
- 测试目录: `tests/`
- 运行命令: `pytest tests/`

## 运行方式
- 本地运行: `python -m pipeline.main`
- 各 Agent 可独立调用: `opencode run <agent-name>`

## 红线（绝对禁止）
- 不编造不存在的项目或数据
- 不在日志中输出 API Key 或敏感信息
- 不执行任何破坏性文件系统操作（如 rm -rf、格式化等）
- 不修改 AGENTS.md 本身（除非明确要求）
