---
name: format-output
description: 当用户要求整理文章格式、去重、校验质量时触发
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - Bash
---

# 格式化输出技能

## 触发条件

用户提到以下意图时激活：
- "整理"、"格式化" 文章
- "去重"、"检查重复"
- "校验"、"质量检查"
- "归档"、"发布"

## 执行步骤

### 第 1 步：读取文章

从 `knowledge/articles/` 目录读取所有文章文件（`*.json`），加载为待处理列表。

### 第 2 步：字段完整性检查

逐条检查必填字段是否完整：

| 必填字段 | 校验规则 |
|----------|----------|
| `id` | 非空，格式 `{YYYY-MM-DD}-{source}-{slug}` |
| `title` | 非空，长度 >= 2 |
| `source` | 有效值限 `github-trending` / `hacker-news` |
| `source_url` | 非空，以 `https://` 开头 |
| `collected_at` | ISO 8601 格式 |
| `summary` | 非空，长度 >= 20 字 |
| `tags` | 非空数组，至少 1 个标签 |
| `status` | 有效值限 `draft` / `reviewed` / `published` |

对不完整条目：
- 可自动修复的（如缺少 id、标签大小写），自动补充
- 不可修复的（如缺失关键字段），标记为 `draft` 状态

### 第 3 步：运行校验脚本

```bash
python hooks/validate_json.py knowledge/articles/*.json
python hooks/check_quality.py knowledge/articles/*.json
```

### 第 4 步：按 source_url 去重

- 相同 `source_url` 仅保留 `collected_at` 最新的一条
- 重复条目移动至 `knowledge/articles/archive/` 目录

### 第 5 步：标签清洗

- 统一转为英文小写
- 空格/下划线转为连字符（`-`）
- 去除首尾空白
- 合并语义相近的标签（如 `ai-agent` 和 `agent` → `agent`）

### 第 6 步：更新状态

处理完成后，将 `status` 更新为 `published`。

### 第 7 步：输出整理报告

向用户汇报：
- 处理条目总数
- 修复字段数量
- 去重数量
- 不合格条目数量及原因
- 质量评分分布

## 质量标准

| 指标 | 标准 |
|------|------|
| 必填字段 | 100% 不为空 |
| ID 格式 | `{YYYY-MM-DD}-{source}-{slug}` |
| 评分范围 | 1-10 |
| 摘要长度 | >= 20 字 |
| 标签数量 | >= 1 |
| 质量评分 | >= B 级（60 分） |

## 质量评分等级

| 等级 | 分数 | 含义 |
|------|------|------|
| A | >= 80 | 优秀，内容丰富且规范 |
| B | 60-79 | 合格，满足基本要求 |
| C | 40-59 | 需改进，存在明显问题 |
| D | < 40 | 不合格，建议重写或丢弃 |

## 错误处理

- 格式校验失败的条目不阻塞其他条目的处理
- 修复失败记录错误日志，标注原因
- 不在日志中输出文章正文或敏感信息
