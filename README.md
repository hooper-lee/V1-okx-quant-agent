# OKX Quant Agent

一个基于 LangChain 分层架构构建的 OKX 量化交易控制台，当前版本已经补上了：

- FastAPI 后端
- AI 科技风前端控制台
- LangChain 风格的 Chains / RAG / Agent / Memory 层
- Chroma 向量库存储
- OpenAI 兼容 LLM / Embeddings 接入口
- OKX 市场行情 / 下单执行适配层

## 当前能力

- `LangChainRuntime`
  - 使用 `langchain-openai` 连接 OpenAI 或兼容 OpenAI 协议的模型服务
- `RAGCoordinator`
  - 通过 `langchain-chroma` + `chromadb` 接真实向量库
- `AgentDecisionService`
  - 用模型生成结构化交易决策，失败时自动降级到启发式逻辑
- `MarketDataService`
  - 优先读取 OKX 实时 K 线 / ticker，失败时退回 demo 数据
- `OKXExecutor`
  - 支持 OKX 签名请求与模拟盘 / 实盘切换

## 自用 SOP

如果你已经把系统部署在线上，想按页面一步一步操作，优先看这份说明：

- [自用版 SOP](./docs/SELF_USE_SOP.md)
- [每日检查清单](./docs/DAILY_CHECKLIST.md)

## 项目结构

```text
.
├── app
│   ├── api
│   ├── core
│   ├── data
│   ├── execution
│   ├── integrations
│   ├── langchain_layer
│   ├── quant
│   ├── schemas
│   └── main.py
├── frontend
└── requirements.txt
```

## 环境变量

建议先创建一个本地环境变量文件，至少配置这些值：

```bash
export OPENAI_API_KEY="your-openai-key"
export OPENAI_MODEL="gpt-4.1-mini"
export EMBEDDINGS_MODEL="text-embedding-3-small"

export OKX_API_KEY="your-okx-key"
export OKX_API_SECRET="your-okx-secret"
export OKX_PASSPHRASE="your-okx-passphrase"
export OKX_USE_PAPER="true"

export USE_LIVE_SERVICES="true"
```

如果你要接其他兼容 OpenAI 协议的模型服务，还可以配置：

```bash
export OPENAI_BASE_URL="https://your-compatible-llm-endpoint/v1"
export LLM_MODEL="your-model-name"
```

## 安装依赖

```bash
python3 -m pip install -r requirements.txt
```

## 启动项目

```bash
python3 -m uvicorn app.main:app --reload
```

启动后访问：

- 首页: `http://127.0.0.1:8000/`
- 文档: `http://127.0.0.1:8000/docs`

## 部署到 AWS EC2

推荐先用 `EC2 + python venv` 跑通，再考虑 `Docker / Nginx / HTTPS`。

### 1. 服务器准备

- Ubuntu 22.04 或 24.04
- 开放安全组端口：
  - `22` 用于 SSH
  - `8010` 用于先直接访问项目
  - 如果后面上 Nginx，再开放 `80/443`

### 2. 拉代码

```bash
git clone https://github.com/hooper-lee/okx-quant-agent.git
cd okx-quant-agent
```

### 3. 配环境变量

```bash
cp .env.example .env
```

按实际情况填写：

- `OPENAI_API_KEY`
- `LLM_MODEL`
- `OPENAI_BASE_URL`（如果是兼容接口）
- `OKX_API_KEY`
- `OKX_API_SECRET`
- `OKX_PASSPHRASE`
- `OKX_USE_PAPER`

### 4. 一键部署

```bash
chmod +x deploy.sh
./deploy.sh
```

### 5. 访问

- 首页：`http://<EC2公网IP>:8010/`
- 文档：`http://<EC2公网IP>:8010/docs`

### 6. 可选：systemd 常驻

```bash
sudo cp deploy/systemd/okx-quant-agent.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable okx-quant-agent
sudo systemctl start okx-quant-agent
sudo systemctl status okx-quant-agent
```

### 7. 可选：Nginx 反向代理

```bash
sudo apt-get install -y nginx
sudo cp deploy/nginx/okx-quant-agent.conf /etc/nginx/sites-available/okx-quant-agent
sudo ln -s /etc/nginx/sites-available/okx-quant-agent /etc/nginx/sites-enabled/okx-quant-agent
sudo nginx -t
sudo systemctl restart nginx
```

## 重要说明

- 没有配置 LangChain / OpenAI 依赖或 API Key 时，系统会自动退回到本地启发式逻辑
- 没有配置 OKX 私有密钥时，下单仍然会走模拟返回，不会误触实盘
- 向量库默认持久化到项目根目录下的 `.chroma/`

## 已提供的接口

- `GET /health`
- `GET /api/v1/system/overview`
- `GET /api/v1/dashboard/snapshot`
- `GET /api/v1/market/candles`
- `POST /api/v1/strategy/analyze`
- `POST /api/v1/backtest/run`
- `POST /api/v1/trade/execute`
- `GET /api/v1/strategies`
- `POST /api/v1/strategies`
- `PUT /api/v1/strategies/{name}`

## 下一步建议

- 把新闻源接成真实资讯 API
- 把向量库文档写入改成正式 ingestion 流程
- 用 LangGraph 把 Agent 拆成多步决策图
- 增加 OKX 账户余额、持仓、订单历史接口
