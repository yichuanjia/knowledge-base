# AGENTS.md — AI 知识库助手项目规范

## 项目概述
个人 AI 知识库助手系统。自动从技术信息源（GitHub Trending、Hacker News）采集 AI/LLM/Agent 领域的技术动态，AI 分析后结构化存储为 JSON，支持多渠道分发（Telegram/飞书）。

## 技术栈
- 语言: Python 3.12
- AI 编排: OpenCode + 国产大模型（DeepSeek/Qwen/GLM/Kimi）
- 工作流: LangGraph
- 部署: OpenClaw
- 依赖管理: pip + requirements.txt

## 编码规范
- 遵循 PEP 8
- 变量/函数命名: snake_case，类名: PascalCase
- 所有函数必须有 docstring（Google 风格）
- 所有函数必须添加类型注解（Type Hints）
- 禁止裸 print()，使用 logging
- 禁止 import *
- 文件编码 UTF-8
- 使用 f-string 格式化字符串，不用 % 或 .format()
- 使用 pathlib 处理路径，不用 os.path
- 文件操作使用 with 上下文管理器
- 捕获具体异常，禁止裸 except:
- 不提交注释掉的代码
- 敏感配置通过环境变量读取，禁止硬编码
- 入口文件必须有 `if __name__ == "__main__"` 保护
- 日志使用 Python `logging` 模块，默认级别 INFO，格式 `%(asctime)s [%(levelname)s] %(name)s: %(message)s`，输出到 `logs/` 目录

## 项目结构
```
ai-knowledge-base/
├── AGENTS.md
├── opencode.json
├── .opencode/
│   ├── agents/
│   │   ├── collector.md
│   │   ├── analyzer.md
│   │   └── organizer.md
│   └── skills/
│       ├── github-trending/SKILL.md
│       └── tech-summary/SKILL.md
├── knowledge/
│   ├── raw/
│   └── articles/
├── logs/
├── pipeline/
├── workflows/
└── openclaw/
```

## 知识条目格式

### 原始采集数据（`knowledge/raw/`）

Collector Agent 从外部源拉取的原始数据，以 JSON 文件存储，命名格式 `{source}-{date}.json`：

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

### 结构化知识条目（`knowledge/articles/`）

Analyzer Agent 分析后产出的结构化数据，以 JSON 文件存储，命名格式 `{id}.json`：

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
  "status": "reviewed"
}
```

**必填字段**：id, title, source, source_url, collected_at, summary, tags, status

**id 生成规则**：`{collected_date}-{source}-{slug}`，例如 `2026-03-01-github-openclaw`

**relevance_score 评分标准**（1-10）：
- 9-10：突破性进展，改变行业格局
- 7-8：对个人技术栈直接有帮助
- 5-6：值得了解，关注后续发展
- 1-4：一般动态，参考价值有限

**source 有效值**：`github-trending` / `hacker-news`

**status 可选值及流转**：
- `draft` — 待处理（暂不使用）
- `reviewed` — Analyzer 分析完成后写入
- `published` — Organizer 去重归档后更新

## 处理流程

1. **采集**（Collector）→ 从 GitHub Trending / Hacker News 拉取数据，用 AI 判断是否属于 AI/LLM/Agent 领域，不相关的丢弃，其余写入 `knowledge/raw/`
2. **分析**（Analyzer）→ 读取 `knowledge/raw/`，生成摘要、技术亮点、评分和标签，写入 `knowledge/articles/`，status 设为 `reviewed`
3. **整理**（Organizer）→ 按 `source_url` 精确去重（同 URL 保留最新），清洗标签格式（统一小写、连字符连接），归档后 status 更新为 `published`

## 运行方式
- 运行: `python -m pipeline.main`
- 各 Agent 独立调用: `opencode run <collector|analyzer|organizer>`

## 错误处理
- API 请求失败：自动重试 3 次（指数退避 1s/2s/4s），全失败后标记 `"error": true`
- 采集失败不阻塞其他来源，各自独立运行

## Agent 角色概览

| 角色 | 文件 | 职责 |
|------|------|------|
| 采集 Agent | .opencode/agents/collector.md | 从外部源采集技术动态，AI 过滤领域 |
| 分析 Agent | .opencode/agents/analyzer.md | 深度分析，生成摘要/评分/标签 |
| 整理 Agent | .opencode/agents/organizer.md | 按 URL 去重，标签清洗，归档 |

## 红线（绝对禁止）
- 不编造不存在的项目或数据
- 不在日志中输出 API Key 或敏感信息
- 不执行 rm -rf 等危险命令
- 不修改 AGENTS.md 本身（除非明确要求）
