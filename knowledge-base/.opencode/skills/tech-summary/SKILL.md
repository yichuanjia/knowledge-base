---
name: tech-summary
description: 当需要对采集的技术内容进行深度分析总结时使用此技能
allowed-tools:
  - Read
  - Grep
  - Glob
  - WebFetch
---

# 技术深度分析技能

## 使用场景

读取 `knowledge/raw/` 中最新的采集数据，对每个项目进行深度分析，生成摘要、技术亮点、评分和标签，输出结构化分析结果。

## 执行步骤

### 第 1 步：读取最新采集文件

从 `knowledge/raw/` 目录读取最新的原始采集 JSON 文件（如 `github-trending-YYYY-MM-DD.json`），获取待分析的 `items` 列表。

### 第 2 步：逐条深度分析

对每个项目进行深度分析，输出以下内容：

- **摘要**：中文，不超过 50 字。公式：**[项目名] + 做什么 + 为什么值得关注**
- **技术亮点**：2-3 个，用事实说话，避免空泛评价。例如「支持 50+ 平台」「基于 Rust 实现高性能推理」而非「很强大」
- **评分**：1-10 分，必须附带评分理由

**评分标准**：

| 分数 | 含义 | 标准 |
|------|------|------|
| 9-10 | 改变格局 | 突破性进展，可能改变行业格局 |
| 7-8 | 直接有帮助 | 对个人技术栈有直接帮助 |
| 5-6 | 值得了解 | 值得关注后续发展 |
| 1-4 | 可略过 | 一般动态，参考价值有限 |

**约束**：15 个项目中，9-10 分的项目不超过 2 个。

- **标签建议**：英文小写，连字符连接。常用标签包括 `agent`、`llm`、`rag`、`fine-tuning`、`open-source`、`tool-use`、`multimodal`、`vector-database`、`prompt-engineering`、`evaluation`、`safety`、`inference`、`training`、`deployment`、`framework`

### 第 3 步：趋势发现

对所有项目进行整体分析，提炼：

- **共同主题**：本期项目集中体现在哪些方向（如 Agent、多模态、推理加速等）
- **新概念**：是否有新术语、新范式或新玩法出现

### 第 4 步：输出分析结果 JSON

将分析结果写入 `knowledge/articles/{date}-analysis.json`，日期与输入文件对应。

## 注意事项

- 摘要不超过 50 字，比采集阶段更精炼
- 技术亮点必须用事实支撑，避免空泛表述
- 评分必须有具体理由，不能只给数字
- 9-10 分严格控制，15 个项目不超过 2 个
- 不编造不存在的技术特性
- 标签统一英文小写，连字符连接

## 输出格式

保存到 `knowledge/articles/{YYYY-MM-DD}-analysis.json`：

```json
{
  "skill": "tech-summary",
  "analyzed_at": "2026-03-01T12:00:00Z",
  "source_file": "github-trending-2026-03-01.json",
  "trends": {
    "common_themes": ["Agent 框架", "推理加速"],
    "new_concepts": ["MCP 协议", "Agent-to-Agent 通信"]
  },
  "items": [
    {
      "name": "owner/repo",
      "url": "https://github.com/owner/repo",
      "summary": "不超过50字的中文摘要",
      "tech_highlights": [
        "支持 50+ 平台集成",
        "基于 Rust 实现高性能推理引擎"
      ],
      "score": 8,
      "score_reason": "Agent 框架领域的重要基础设施，多平台集成能力强，对构建 Agent 应用有直接帮助",
      "tags": ["agent", "framework", "open-source"]
    }
  ]
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `skill` | string | 技能名称，固定值 `tech-summary` |
| `analyzed_at` | string | ISO 8601 格式的分析时间戳 |
| `source_file` | string | 输入文件名 |
| `trends.common_themes` | string[] | 本期项目的共同主题 |
| `trends.new_concepts` | string[] | 出现的新概念或新范式 |
| `items[].name` | string | 项目名称，`owner/repo` 格式 |
| `items[].url` | string | 项目 GitHub URL |
| `items[].summary` | string | 中文摘要（不超过 50 字） |
| `items[].tech_highlights` | string[] | 技术亮点（2-3 个，用事实说话） |
| `items[].score` | number | 评分（1-10） |
| `items[].score_reason` | string | 评分理由 |
| `items[].tags` | string[] | 标签（英文小写，连字符连接） |
