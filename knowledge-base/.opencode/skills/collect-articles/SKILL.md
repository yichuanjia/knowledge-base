---
name: collect-articles
description: 当用户要求采集AI文章、搜索技术内容、获取GitHub热门项目时触发
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - WebFetch
---

# 采集文章技能

## 触发条件

用户提到以下意图时激活：
- "采集"、"收集"、"搜索" AI 相关内容
- "获取 GitHub 热门项目"
- "抓取 RSS 订阅"

## 执行步骤

### 第 1 步：确认采集参数

与用户确认以下参数，未明确时使用默认值：

| 参数 | 可选值 | 默认值 |
|------|--------|--------|
| 渠道（source） | `github` / `rss` / `all` | `github` |
| 关键词（keywords） | 自定义字符串 | 无（不过滤） |
| 数量限制（limit） | 正整数 | `10` |

### 第 2 步：执行采集

根据渠道选择采集方式：

**渠道为 github**：
```bash
python pipeline/pipeline.py --sources github --limit 10
```

**渠道为 rss**：
- 使用 `WebFetch` 抓取配置的 RSS 源
- 提取文章标题、链接、摘要、发布时间

**渠道为 all**：依次执行 github 和 rss 采集。

### 第 3 步：检查采集结果

- 读取 `knowledge/raw/` 中最新的采集文件
- 核实采集数据量是否符合预期
- 检查是否有 `"error": true` 标记的条目

### 第 4 步：汇报结果

向用户汇报：
- 采集渠道和数量
- 是否有采集失败的源
- 关键内容概览（前 3-5 条标题/摘要）
- 输出文件路径

## 输出位置

- 原始数据：`knowledge/raw/{source}-{YYYY-MM-DD}.json`
- 采集日志：`logs/`

## 错误处理

- 单个渠道采集失败不阻塞其他渠道
- API 请求失败自动重试 3 次（指数退避 1s/2s/4s）
- 全部失败后标记 `"error": true` 并记录日志
- 不在日志中输出 API Key 或敏感信息
