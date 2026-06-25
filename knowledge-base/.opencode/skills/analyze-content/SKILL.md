---
name: analyze-content
description: 当用户要求分析文章技术价值、生成摘要、进行评分时触发
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
---

# 分析内容技能

## 触发条件

用户提到以下意图时激活：
- "分析"、"评估" 文章或项目
- "生成摘要"、"打分"
- "对比" 多个技术方案
- "深度剖析"、"技术解读"

## 分析框架

对每篇文章从五个维度分析：

| 维度 | 权重 | 分析要点 |
|------|------|----------|
| 核心创新 | 25% | 解决了什么问题？提出了什么新方法？与现有方案有何本质不同？ |
| 技术深度 | 25% | 是浅层介绍还是深入实现？是否有架构图、代码示例、性能数据？ |
| 实用价值 | 20% | 读者能直接应用吗？是否有可复现的代码或工具？ |
| 时效性 | 15% | 内容是否最新？技术是否会很快过时？ |
| 生态影响 | 15% | 对 AI 工具链/框架生态有什么影响？是否填补了某个空白？ |

## 执行步骤

### 第 1 步：读取待分析内容

从 `knowledge/raw/` 目录读取最新的采集文件，获取待分析的项目/文章列表。

### 第 2 步：逐条五维分析

对每条内容按上述框架逐维度分析，形成分析意见。

### 第 3 步：综合评分

根据五维分析结果给出综合评分（1-10）：

| 分数 | 含义 | 标准 |
|------|------|------|
| 9-10 | 改变格局 | 突破性进展，可能改变行业格局 |
| 7-8 | 直接有帮助 | 对个人技术栈有直接帮助 |
| 5-6 | 值得了解 | 值得关注后续发展 |
| 1-4 | 参考有限 | 一般动态，参考价值有限 |

**约束**：每批内容中 9-10 分不超过 20%。

### 第 4 步：输出分析结果

将分析结果写入 `knowledge/articles/` 目录。

## 输出格式

保存到 `knowledge/articles/{YYYY-MM-DD}-analysis.json`：

```json
{
  "skill": "analyze-content",
  "analyzed_at": "2026-03-01T12:00:00Z",
  "source_file": "github-trending-2026-03-01.json",
  "items": [
    {
      "name": "owner/repo",
      "url": "https://github.com/owner/repo",
      "summary": "不超过 100 字的中文摘要",
      "score": 8,
      "score_reason": "评分理由，结合五维分析说明",
      "tags": ["relevant", "tags"],
      "audience": "advanced",
      "analysis": {
        "innovation": "核心创新点描述",
        "tech_depth": "技术深度评估",
        "practical_value": "实用价值说明",
        "timeliness": "时效性判断",
        "ecosystem_impact": "生态影响分析"
      }
    }
  ]
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `skill` | string | 技能名称，固定值 `analyze-content` |
| `analyzed_at` | string | ISO 8601 格式的分析时间戳 |
| `source_file` | string | 输入文件名 |
| `items[].name` | string | 项目/文章名称 |
| `items[].url` | string | 原始链接 |
| `items[].summary` | string | 中文摘要（不超过 100 字） |
| `items[].score` | number | 综合评分（1-10） |
| `items[].score_reason` | string | 评分理由 |
| `items[].tags` | string[] | 英文小写，连字符连接 |
| `items[].audience` | string | 目标读者：`beginner` / `intermediate` / `advanced` |
| `items[].analysis` | object | 五维分析详情 |

## 注意事项

- 摘要必须精炼，不超过 100 字
- 评分必须有具体理由，不能只给数字
- 9-10 分严格控制数量
- 不编造不存在的技术特性
- 标签统一英文小写，连字符连接
