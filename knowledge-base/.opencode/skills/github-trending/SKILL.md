---
name: github-trending
description: 当需要采集 GitHub 热门开源项目时使用此技能。适用于知识库采集阶段。
allowed-tools:
  - Read
  - Grep
  - Glob
  - WebFetch
---

# GitHub 热门项目采集技能

## 使用场景

在知识库采集阶段，从 GitHub Trending 页面采集 AI 领域热门开源项目。

## 执行步骤

### 第 1 步：搜索热门仓库

使用 `WebFetch` 获取 GitHub Trending 页面：

```
https://github.com/trending?since=daily
```

可选参数：`since=daily|weekly|monthly`

### 第 2 步：提取仓库信息

从页面中提取以下字段：

- `name` — 仓库名（owner/repo 格式）
- `url` — 仓库链接
- `description` — 项目描述
- `stars` — Star 数
- `language` — 主要编程语言
- `topics` — 主题标签

### 第 3 步：过滤

**纳入**以下类型：

- AI / ML / LLM / Agent 相关项目
- AI 领域开发者工具
- 重要框架重大更新

**排除**以下类型：

- Awesome 列表类仓库
- 纯教程或文档项目
- 刷 Star 的营销项目
- 无 README 或内容质量低

### 第 4 步：去重

按 `name` 去重，每个仓库只保留一条。

### 第 5 步：撰写中文摘要

为每个通过过滤的项目撰写中文摘要，公式：

> **[项目名] + 做什么 + 为什么值得关注**

- 语言：中文
- 长度：30-80 字

### 第 6 步：排序取 Top 15

按 Star 数降序排列，取前 15 个项目。若不足 15 个则全部保留。

### 第 7 步：输出 JSON

将结果写入 `knowledge/raw/github-trending-{YYYY-MM-DD}.json`，日期为采集当天实际日期。

## 注意事项

- 摘要必须是中文
- 不编造不存在的仓库
- 请求失败时自动重试 3 次（指数退避 1s/2s/4s），全失败后记录错误

## 输出格式

保存到 `knowledge/raw/github-trending-YYYY-MM-DD.json`：

```json
{
  "source": "github-trending",
  "skill": "github-trending",
  "collected_at": "2026-03-01T10:00:00Z",
  "items": [
    {
      "name": "owner/repo",
      "url": "https://github.com/owner/repo",
      "summary": "中文摘要：项目名 + 做什么 + 为什么值得关注",
      "stars": 1520,
      "language": "Python",
      "topics": ["agent", "llm", "open-source"]
    }
  ]
}
```

**字段说明**：

| 字段 | 类型 | 说明 |
|------|------|------|
| `source` | string | 数据来源，固定值 `github-trending` |
| `skill` | string | 技能名称，固定值 `github-trending` |
| `collected_at` | string | ISO 8601 格式的采集时间戳 |
| `items[].name` | string | 项目名称，`owner/repo` 格式 |
| `items[].url` | string | 项目 GitHub URL |
| `items[].summary` | string | 中文摘要（30-80 字） |
| `items[].stars` | number | 总 Star 数 |
| `items[].language` | string | 主要编程语言 |
| `items[].topics` | string[] | 项目主题标签（英文小写，连字符连接） |
