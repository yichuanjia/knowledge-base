# 技术摘要生成技能

## 功能

为技术项目或文章生成高质量的中文技术摘要。

## 摘要要求

1. **语言**：中文
2. **字数**：100-200 字
3. **内容要素**：
   - 项目/文章的核心功能或论点
   - 技术亮点或创新点
   - 适用场景或目标用户
   - 与 AI/LLM/Agent 领域的关联

## 标签生成规则

1. **语言**：英文小写
2. **分隔符**：连字符（`-`）
3. **常用标签**：
   - `large-language-model` — 大语言模型
   - `agent` — 智能体
   - `rag` — 检索增强生成
   - `fine-tuning` — 微调
   - `open-source` — 开源
   - `tool-use` — 工具调用
   - `multimodal` — 多模态
   - `vector-database` — 向量数据库
   - `prompt-engineering` — 提示工程
   - `evaluation` — 评估
   - `safety` — 安全
   - `inference` — 推理
   - `training` — 训练
   - `deployment` — 部署
   - `framework` — 框架

## 评分标准

根据以下维度评估 relevance_score（0-1）：

| 维度 | 权重 | 说明 |
|------|------|------|
| 与 AI/LLM 直接相关性 | 40% | 是否直接涉及大模型/机器学习 |
| 技术深度 | 25% | 是否有技术含量 |
| 新颖性 | 20% | 是否代表了新的技术方向 |
| 实用性 | 15% | 是否可直接应用 |

## 示例

### 输入
```
项目：openai-agents-sdk
描述：Production-grade agent framework for building and running agentic workflows
语言：Python
Stars：12,000
```

### 输出
```json
{
  "summary": "OpenAI 推出的生产级 Agent 框架，用于构建和运行智能体工作流。提供标准化的 Agent 定义、工具集成和多 Agent 协作能力，支持 Python 生态。适用于需要快速搭建自主 Agent 应用的开发者，大幅降低了从原型到生产环境的工程复杂度。",
  "tags": ["agent", "framework", "open-source", "tool-use"],
  "relevance_score": 0.95
}
```
