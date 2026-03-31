# V1 OKX Quant Agent

> An AI-native quantitative trading operating system for OKX.  
> Built to unify market data, strategy generation, risk control, execution, memory, and research workflows into one extensible agent framework.

一个面向 OKX 的 AI 原生量化交易系统原型。  
它不是单纯的“交易脚本”或“策略回测工具”，而是一个试图把 **行情、研究、决策、风控、执行、复盘** 串成统一闭环的 Agent 化交易操作系统。

---

## Overview

传统量化系统通常分散在多个孤立模块中：

- 行情获取是一个系统
- 策略研究是一个系统
- 下单执行是一个系统
- 资讯与新闻是一个系统
- 交易复盘和经验沉淀又是另一个系统

AI 的真正价值，不只是替代一个策略函数，而是把这些模块连接起来，形成一个具备：

- 感知市场
- 理解上下文
- 生成判断
- 执行动作
- 积累记忆
- 自我迭代

能力的智能交易中枢。

**V1 OKX Quant Agent** 的目标，就是成为这个中枢的第一版可运行基础设施。

---

## Product Positioning

### What it is

V1 OKX Quant Agent 是一个面向数字资产交易场景的 **AI Quant Agent Framework**，用于构建：

- 智能交易控制台
- 自动化策略执行系统
- AI 辅助研究与分析工作流
- 多 Agent 协同决策系统
- 可持续迭代的量化交易操作系统

### What it is not

它不是一个只靠单一模型预测涨跌的 Demo。  
它更像一个可演进的底层框架，核心价值在于：

- 统一交易工作流
- 模块化接入 LLM / 数据源 / 交易所
- 支持策略、知识、执行、记忆长期积累
- 为未来自动策略闭环打基础

---

## Vision

构建一个可扩展的 **AI-Native Trading OS**：

- 上层是策略、研究、监控、风控、复盘应用
- 中层是 Agent 决策与工作流编排
- 底层是交易所、模型、向量库、新闻源、数据库等基础设施

最终让系统可以从“辅助分析工具”，逐步演进成：

1. **AI 交易研究助手**
2. **半自动策略执行系统**
3. **目标驱动型交易 Agent**
4. **多 Agent 协同的量化操作系统**

---

## Why Now

加密交易市场天然具备：

- 高频变化
- 多维信息源
- 24/7 连续运行
- 强烈依赖研究与执行联动

这正是 AI Agent 最适合落地的场景之一。

过去的交易系统大多强调“策略逻辑”，而未来的竞争力会更多体现在：

- 是否能快速吸收多源信息
- 是否能将研究直接转化为执行
- 是否具备持续学习与复盘能力
- 是否能形成人机协作或 Agent 协作闭环

因此，交易不再只是策略问题，而是**智能工作流系统**问题。  
这也是 V1 OKX Quant Agent 想要解决的核心方向。

---

## Core Value Proposition

这个项目的差异化，不在于“也能下单”，而在于它把未来 AI 交易系统最关键的几层提前打通了：

- **Execution Layer**：真实交易所接入与订单执行
- **Reasoning Layer**：模型参与结构化交易判断
- **Knowledge Layer**：RAG 检索增强与经验沉淀
- **Memory Layer**：为长期策略记忆和复盘做准备
- **Workflow Layer**：可演进成多步骤、多 Agent 决策流
- **Console Layer**：可视化控制台，便于运营、研究和演示

这意味着它既能作为一个技术项目，也能作为一个有产品化潜力的基础平台。

---

## Current Capabilities

### Infrastructure
- FastAPI backend
- AI-style console frontend
- Modular service architecture
- OpenAI-compatible model integration
- Chroma vector database support

### Trading
- OKX market data integration
- Order execution adapter
- Paper trading / live trading switch
- Structured decision generation
- Heuristic fallback when model is unavailable

### AI Layer
- LangChain-style runtime abstraction
- RAG retrieval coordination
- Agent decision service
- Extensible memory / context pipeline

### Product Layer
- Dashboard snapshot
- Strategy management APIs
- Backtest trigger endpoints
- Trading action endpoints
- System overview endpoints

---

## Architecture Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                        User / Operator                      │
│      Dashboard / API / Strategy Config / Research Input    │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    Application / API Layer                 │
│     FastAPI · REST APIs · Strategy APIs · Dashboard APIs   │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                  Agent Orchestration Layer                 │
│   AgentDecisionService · Workflow Routing · Task Control   │
└─────────────────────────────────────────────────────────────┘
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
┌────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ Reasoning Layer│  │ Knowledge Layer  │  │ Execution Layer  │
│ LLM Runtime    │  │ RAGCoordinator   │  │ OKXExecutor      │
│ Prompting      │  │ Chroma Vector DB │  │ Order Routing    │
│ Structured AI  │  │ Research Context │  │ Paper / Live     │
└────────────────┘  └──────────────────┘  └──────────────────┘
          │                  │                  │
          └──────────────────┼──────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                     Market & Data Layer                    │
│   MarketDataService · Candles · Ticker · External Feeds    │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│              Future Expansion: Memory / News / Multi-Agent │
│   Trade Memory · Journal · News Analysis · Goal Engine     │
└─────────────────────────────────────────────────────────────┘
