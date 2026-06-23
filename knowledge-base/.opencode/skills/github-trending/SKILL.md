# GitHub Trending 采集技能

## 功能

从 GitHub Trending 页面采集每日热门开源项目数据。

## 采集方法

使用 `webfetch` 工具获取 GitHub Trending 页面内容：

- **URL 格式**：`https://github.com/trending?since=daily`
- **可选参数**：
  - `since=daily|weekly|monthly`：时间范围
  - `spoken_language_code=zh`：语言过滤

## 解析规则

从页面中提取每个项目的信息：

1. **项目名称**：`owner/repo` 格式
2. **描述**：项目简介
3. **语言**：主要编程语言
4. **Stars**：总星标数
5. **今日新增**：本日/本周新增星标数
6. **URL**：`https://github.com/{owner}/{repo}`

## 过滤标准

仅保留以下领域的项目：

- AI / LLM / 大语言模型
- Agent / 智能体
- Machine Learning / 深度学习
- NLP / 自然语言处理
- Computer Vision / 计算机视觉
- Data Science / 数据科学
- MLOps / AI Infrastructure

## 输出

输出 JSON 数组，每条记录包含：

```json
{
  "id": "github-{owner}-{repo}",
  "title": "{owner}/{repo}",
  "source": "github-trending",
  "url": "https://github.com/{owner}/{repo}",
  "collected_at": "ISO 8601 时间戳",
  "description": "项目描述",
  "language": "编程语言",
  "stars": 12345,
  "stars_today": 123
}
```

## 去重

基于 `id` 字段去重，确保不产生重复条目。
