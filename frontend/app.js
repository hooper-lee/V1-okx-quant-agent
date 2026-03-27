const API_BASE = "";

let tradeRecords = [
  { side: "买入", strategy: "sma_crossover", createdAt: "2026-05-05 18:00:00" },
  { side: "买入", strategy: "mean_reversion", createdAt: "2026-05-05 18:00:00" },
];
let sourceMap = {};
let latestSnapshot = null;
let strategyMap = {};
let strategyModalMode = "create";
let latestReportText = "";
let latestDailySummaryEntries = [];
let activeReportTab = "report";
let promptTemplates = [];
let runtimeConfig = {};
let activeSourceName = "";
let sourceMetaMap = {};
let newsAutoRefreshTimer = null;
let newsNextRefreshAt = null;
const NEWS_AUTO_REFRESH_MS = 10 * 60 * 1000;
let currentView = "overview";
let latestAnalysisResult = null;
let latestAccountOverview = null;
let latestBacktestResult = null;
let latestBacktestSignature = "";
let latestBacktestAutoLabel = "";
let backtestRuns = [];
let strategyTemplates = [];
let automationStatus = null;
let authRequired = false;
let authTtlMinutes = 30;
const STRATEGY_CACHE_KEY = "okx-quant-agent:strategies";
const SELECTED_STRATEGY_KEY = "okx-quant-agent:selected-strategy";
const DEFAULT_STRATEGIES = [
  { name: "sma_crossover", type: "trend", risk_preference: "balanced", config: { symbol: "BTC-USDT-SWAP", timeframe: "1h", target_capital: 12000, target_horizon_days: 21 } },
  { name: "mean_reversion", type: "reversal", risk_preference: "balanced", config: { symbol: "ETH-USDT-SWAP", timeframe: "4h", target_capital: 8000, target_horizon_days: 45 } },
  { name: "news_sentiment", type: "hybrid", risk_preference: "balanced", config: { symbol: "SOL-USDT-SWAP", timeframe: "1d", target_capital: 15000, target_horizon_days: 90 } },
];

const NEWS_SOURCE_DESCRIPTIONS = {
  Cointelegraph: "偏行业快讯、市场热点和大事件跟踪",
  Decrypt: "偏项目解读、科技视角和产品动态",
  CryptoSlate: "偏市场综述、链上项目与数据观察",
  Cryptonews: "偏综合资讯、事件驱动和交易新闻",
};

const GUIDE_CONTENT = {
  daily: {
    title: "每日检查清单",
    targetView: "overview",
    actionLabel: "返回总览",
    sections: [
      {
        heading: "最短流程",
        list: [
          "账户 -> 刷新账户",
          "自检 -> 运行自检",
          "策略 -> 刷新分析",
        ],
      },
      {
        heading: "继续操作前的条件",
        text: "只有账户正常、自检正常、模式确认无误时，才建议继续回测或手动下单。",
      },
    ],
  },
  account: {
    title: "账户检查",
    targetView: "account",
    actionLabel: "打开账户页",
    sections: [
      {
        heading: "先做什么",
        text: "进入账户页后先点“刷新账户”。",
      },
      {
        heading: "重点确认",
        list: [
          "source 是否正常",
          "mode 是不是你预期的 paper 或 live",
          "total_equity 是否正常返回",
          "资产表里是否有真实数据",
        ],
      },
      {
        heading: "异常时",
        text: "如果这里异常，今天先不要交易，先去看配置里的 OKX 设置和自检页结果。",
      },
    ],
  },
  health: {
    title: "自检检查",
    targetView: "health",
    actionLabel: "打开自检页",
    sections: [
      {
        heading: "先做什么",
        text: "进入自检页后点“运行自检”。",
      },
      {
        heading: "重点看",
        list: [
          "OKX",
          "LLM",
          "看板快照",
        ],
      },
      {
        heading: "判断方式",
        list: [
          "正常：可以继续",
          "fallback：还能用，但要谨慎",
          "失败：先修问题，不要继续关键操作",
        ],
      },
    ],
  },
  strategies: {
    title: "策略检查",
    targetView: "strategies",
    actionLabel: "打开策略页",
    sections: [
      {
        heading: "先做什么",
        text: "进入策略页后点“刷新分析”。",
      },
      {
        heading: "重点确认",
        list: [
          "交易对正确",
          "周期正确",
          "信号是否正常",
          "风控结果是否正常",
        ],
      },
      {
        heading: "继续前",
        text: "只有当前策略分析结果合理时，再去回测或手动下单。",
      },
    ],
  },
  sop: {
    title: "自用 SOP",
    targetView: "overview",
    actionLabel: "返回总览",
    sections: [
      {
        heading: "推荐顺序",
        list: [
          "总览：先看当前策略、目标资金和账户实时",
          "账户：刷新账户，确认 source / mode / 资产数据",
          "自检：检查 OKX、LLM、看板快照",
          "策略：刷新分析，看信号和风控",
          "回测：确认收益率、最大回撤和交易次数",
        ],
      },
      {
        heading: "不要急着做的事",
        list: [
          "不要在模式没确认前直接下单",
          "不要在 OKX 异常时继续做交易动作",
          "不要一边大改配置一边直接实盘验证",
        ],
      },
      {
        heading: "你现在最适合的使用方式",
        text: "先把它当成看盘、看账户、看策略、跑回测的自用控制台；等连续稳定运行后，再考虑更自动化的玩法。",
      },
    ],
  },
};

function prettyJson(value) {
  return JSON.stringify(value, null, 2);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function compactText(value, maxLength = 160) {
  const normalized = String(value ?? "")
    .replace(/\s+/g, " ")
    .trim();
  if (!normalized) {
    return "--";
  }
  return normalized.length > maxLength ? `${normalized.slice(0, maxLength - 1)}…` : normalized;
}

function getStructuredAgentDecision(agent = {}, symbol = "") {
  const action = String(agent.action || agent.decision || "hold").toLowerCase();
  const confidence = Number(agent.confidence ?? 0.5);
  const reason = Array.isArray(agent.reason)
    ? agent.reason.filter(Boolean).map((item) => String(item))
    : agent.rationale
      ? [String(agent.rationale)]
      : [];
  return {
    market_view: agent.market_view || agent.structured?.market_view || "sideways neutral",
    confidence,
    action,
    symbol: agent.symbol || agent.structured?.symbol || symbol || "--",
    position_size: agent.position_size ?? agent.structured?.position_size ?? null,
    reason,
  };
}

function buildStructuredDecisionHtml(agent = {}, symbol = "") {
  const structured = getStructuredAgentDecision(agent, symbol);
  const reasonText = structured.reason.length ? structured.reason.join(" / ") : "--";
  const positionSizeText =
    structured.position_size != null && Number.isFinite(Number(structured.position_size))
      ? Number(structured.position_size).toFixed(6)
      : "--";
  return `
    <li>市场观点：${escapeHtml(structured.market_view)}</li>
    <li>建议动作：${escapeHtml(structured.action)}</li>
    <li>标的：${escapeHtml(structured.symbol)}</li>
    <li>建议仓位：${escapeHtml(positionSizeText)}</li>
    <li>决策原因：${escapeHtml(reasonText)}</li>
  `;
}

function buildStructuredDecisionCard(agent = {}, symbol = "") {
  const structured = getStructuredAgentDecision(agent, symbol);
  return `
    <article class="report-card">
      <h4>结构化决策</h4>
      <pre class="report-json">${escapeHtml(prettyJson(structured))}</pre>
    </article>
  `;
}

function buildStructuredSummaryCard(item = {}) {
  if (!item?.structured) {
    return "";
  }
  return `
    <article class="report-card">
      <h4>${escapeHtml(item.strategy_name || "--")} / ${escapeHtml(item.date || item.created_at || "--")} / 结构化总结</h4>
      <pre class="report-json">${escapeHtml(prettyJson(item.structured))}</pre>
    </article>
  `;
}

function loadCachedStrategies() {
  try {
    const payload = JSON.parse(window.localStorage.getItem(STRATEGY_CACHE_KEY) || "[]");
    return Array.isArray(payload) && payload.length ? payload : [...DEFAULT_STRATEGIES];
  } catch (_error) {
    return [...DEFAULT_STRATEGIES];
  }
}

function saveCachedStrategies(items) {
  try {
    window.localStorage.setItem(STRATEGY_CACHE_KEY, JSON.stringify(items || []));
  } catch (_error) {
    // ignore cache failures
  }
}

function loadSelectedStrategyName() {
  try {
    return window.localStorage.getItem(SELECTED_STRATEGY_KEY) || "";
  } catch (_error) {
    return "";
  }
}

function saveSelectedStrategyName(name) {
  try {
    if (name) {
      window.localStorage.setItem(SELECTED_STRATEGY_KEY, name);
    }
  } catch (_error) {
    // ignore cache failures
  }
}

function getConfiguredAutoTradeStrategyNames() {
  const configured = automationStatus?.config?.auto_trade_strategy_names;
  return Array.isArray(configured) ? configured.filter(Boolean) : [];
}

function getOperationalStrategyItems(items = []) {
  const allItems = Array.isArray(items) ? items.filter((item) => item?.name) : [];
  const configuredNames = getConfiguredAutoTradeStrategyNames();
  if (!configuredNames.length) {
    return allItems;
  }
  const filtered = allItems.filter((item) => configuredNames.includes(item.name));
  return filtered.length ? filtered : allItems;
}

function parseCsvList(value) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function setRuntimeStatus(message) {
  const modalStatus = document.getElementById("runtime-config-status");
  const pageStatus = document.getElementById("config-runtime-status");
  if (modalStatus) {
    modalStatus.textContent = message;
  }
  if (pageStatus) {
    pageStatus.textContent = message.replace("运行参数状态：", "配置页状态：");
  }
}

function setStrategyModalStatus(message) {
  const status = document.getElementById("strategy-modal-status");
  if (status) {
    status.textContent = message;
  }
}

function setDailyReportTab(tabName = "report") {
  activeReportTab = tabName === "summary" ? "summary" : "report";
  document.getElementById("daily-report-body")?.classList.toggle("hidden", activeReportTab !== "report");
  document.getElementById("daily-summary-body")?.classList.toggle("hidden", activeReportTab !== "summary");
  document.getElementById("daily-report-tab-report")?.classList.toggle("active", activeReportTab === "report");
  document.getElementById("daily-report-tab-summary")?.classList.toggle("active", activeReportTab === "summary");
}

function resetStrategyPresentation(strategyName = "") {
  const displayName = strategyName || document.getElementById("strategy-select")?.value || "--";
  saveSelectedStrategyName(displayName);
  document.getElementById("current-strategy-name").textContent = displayName;
  document.getElementById("strategy-details").innerHTML = "<li>正在切换策略并刷新分析...</li>";
  document.getElementById("strategy-details-page").innerHTML = "<li>正在切换策略并刷新分析...</li>";
  document.getElementById("mini-strategy").textContent = displayName;
  document.getElementById("mini-signal").textContent = "--";
  document.getElementById("mini-yield").textContent = "--";
  document.getElementById("daily-report-date").textContent = "正在刷新...";
  document.getElementById("daily-report-body").innerHTML = `
    <article class="report-card">
      <h4>每日日报</h4>
      <p>正在根据 ${escapeHtml(displayName)} 刷新日报内容...</p>
    </article>
  `;
  document.getElementById("daily-summary-body").innerHTML = `
    <article class="report-card">
      <h4>每日策略总结</h4>
      <p>正在加载 ${escapeHtml(displayName)} 的历史总结...</p>
    </article>
  `;
}

function bindClick(id, handler) {
  const element = document.getElementById(id);
  if (element) {
    element.addEventListener("click", handler);
  }
}

function bindChange(id, handler) {
  const element = document.getElementById(id);
  if (element) {
    element.addEventListener("change", handler);
  }
}

function switchView(viewName) {
  currentView = viewName;
  document.querySelectorAll(".page-view").forEach((section) => {
    section.classList.toggle("active", section.id === `view-${viewName}`);
  });
  document.querySelectorAll(".nav-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === viewName);
  });
}

function renderGuideModalContent(item) {
  const content = document.getElementById("guide-modal-content");
  content.innerHTML = (item.sections || [])
    .map((section) => {
      const textHtml = section.text ? `<p>${escapeHtml(section.text)}</p>` : "";
      const listHtml = section.list
        ? `<ul class="guide-modal-list">${section.list.map((entry) => `<li>${escapeHtml(entry)}</li>`).join("")}</ul>`
        : "";
      return `
        <section class="guide-modal-block">
          <h4>${escapeHtml(section.heading || "")}</h4>
          ${textHtml}
          ${listHtml}
        </section>
      `;
    })
    .join("");
}

function renderGuideHubChooser() {
  const content = document.getElementById("guide-modal-content");
  content.innerHTML = `
    <section class="guide-modal-block">
      <h4>操作指南</h4>
      <p>先挑一项看说明，再决定是否跳到对应页面继续操作。</p>
      <div class="guide-modal-menu">
        <button type="button" class="guide-modal-menu-btn" data-guide-key="daily">每日检查清单</button>
        <button type="button" class="guide-modal-menu-btn" data-guide-key="account">账户检查</button>
        <button type="button" class="guide-modal-menu-btn" data-guide-key="health">自检检查</button>
        <button type="button" class="guide-modal-menu-btn" data-guide-key="strategies">策略检查</button>
        <button type="button" class="guide-modal-menu-btn" data-guide-key="sop">自用 SOP</button>
      </div>
    </section>
  `;
}

function renderToolHubChooser() {
  const content = document.getElementById("guide-modal-content");
  content.innerHTML = `
    <section class="guide-modal-block">
      <h4>快捷工具</h4>
      <p>这里放不常驻但经常会用到的入口。</p>
      <div class="guide-modal-menu">
        <button type="button" class="guide-modal-menu-btn" data-tool-url="/docs">API 文档</button>
        <button type="button" class="guide-modal-menu-btn" data-tool-url="/api/v1/dashboard/snapshot">调试 JSON</button>
      </div>
    </section>
    <section class="guide-modal-block">
      <h4>操作指南</h4>
      <p>如果你想按步骤检查系统，直接从这里继续。</p>
      <div class="guide-modal-menu">
        <button type="button" class="guide-modal-menu-btn" data-tool-action="open-guide-chooser">打开清单</button>
      </div>
    </section>
  `;
}

function openToolHubModal() {
  document.getElementById("guide-modal-title").textContent = "工具";
  renderToolHubChooser();
  const actionButton = document.getElementById("guide-modal-open-view-btn");
  actionButton.textContent = "关闭";
  actionButton.dataset.targetView = "";
  actionButton.classList.add("hidden");
  document.getElementById("guide-modal-backdrop").classList.remove("hidden");
}

function openGuideModal(guideKey) {
  const item = GUIDE_CONTENT[guideKey];
  if (!item) {
    return;
  }
  document.getElementById("guide-modal-title").textContent = item.title;
  renderGuideModalContent(item);
  const actionButton = document.getElementById("guide-modal-open-view-btn");
  actionButton.textContent = item.actionLabel || "打开对应页面";
  actionButton.dataset.targetView = item.targetView || "overview";
  actionButton.classList.remove("hidden");
  document.getElementById("guide-modal-backdrop").classList.remove("hidden");
}

function closeGuideModal() {
  document.getElementById("guide-modal-backdrop").classList.add("hidden");
}

function formatDateTime(value) {
  if (!value) {
    return "未刷新";
  }
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }
  return date.toLocaleString("zh-CN", { hour12: false });
}

function getStatusLabel(status) {
  const mapping = {
    success: "抓取成功",
    live: "抓取成功",
    cache: "缓存命中",
    fallback: "回退占位",
    failed: "抓取失败",
    pending: "等待首次刷新",
    seeded: "内置内容",
  };
  return mapping[status] || status || "未知";
}

function getSelfCheckLabel(status) {
  const mapping = {
    normal: "正常",
    fallback: "fallback",
    failed: "失败",
  };
  return mapping[status] || status || "未知";
}

function renderNextRefreshTime() {
  document.getElementById("news-next-refresh").textContent = `下次刷新：${newsNextRefreshAt ? formatDateTime(newsNextRefreshAt) : "待启动"}`;
}

function scheduleNewsAutoRefresh() {
  if (newsAutoRefreshTimer) {
    clearInterval(newsAutoRefreshTimer);
  }
  newsNextRefreshAt = new Date(Date.now() + NEWS_AUTO_REFRESH_MS);
  renderNextRefreshTime();
  newsAutoRefreshTimer = window.setInterval(async () => {
    await refreshNewsSources(true);
    newsNextRefreshAt = new Date(Date.now() + NEWS_AUTO_REFRESH_MS);
    renderNextRefreshTime();
  }, NEWS_AUTO_REFRESH_MS);
}

function detectEmbeddingsPreset(modelName) {
  const normalized = (modelName || "").trim();
  if (!normalized) {
    return "text-embedding-3-small";
  }
  const presets = ["text-embedding-3-small", "text-embedding-3-large", "text-embedding-ada-002"];
  return presets.includes(normalized) ? normalized : "custom";
}

function applyRuntimeModeVisibility() {
  const mode = document.getElementById("runtime-provider-mode").value;
  const embeddingsEnabled = document.getElementById("runtime-embeddings-enabled").value === "true";
  const embeddingsPreset = document.getElementById("runtime-embeddings-preset").value;
  document.querySelectorAll(".runtime-compatible-only").forEach((element) => {
    element.style.display = mode === "compatible" ? "grid" : "none";
  });
  document.querySelectorAll(".runtime-embeddings-only").forEach((element) => {
    element.style.display = embeddingsEnabled ? "grid" : "none";
  });
  document.querySelectorAll(".runtime-embeddings-custom").forEach((element) => {
    element.style.display = embeddingsEnabled && embeddingsPreset === "custom" ? "grid" : "none";
  });
}

function applyConfigPageVisibility() {
  const mode = document.getElementById("config-provider-mode")?.value || "openai";
  const embeddingsEnabled = document.getElementById("config-embeddings-enabled")?.value === "true";
  const embeddingsPreset = document.getElementById("config-embeddings-preset")?.value || "text-embedding-3-small";
  const embeddingsUseShared = document.getElementById("config-embeddings-use-shared")?.value !== "false";
  document.querySelectorAll(".config-compatible-only").forEach((element) => {
    element.style.display = mode === "compatible" ? "grid" : "none";
  });
  document.querySelectorAll(".config-embeddings-only").forEach((element) => {
    element.style.display = embeddingsEnabled ? "grid" : "none";
  });
  document.querySelectorAll(".config-embeddings-dedicated-only").forEach((element) => {
    element.style.display = embeddingsEnabled && !embeddingsUseShared ? "grid" : "none";
  });
  document.querySelectorAll(".config-embeddings-custom-only").forEach((element) => {
    element.style.display = embeddingsEnabled && embeddingsPreset === "custom" ? "grid" : "none";
  });
}

async function request(path, options = {}) {
  const timeoutMs = options.timeoutMs ?? 15000;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      signal: controller.signal,
      ...options,
    });
  } catch (error) {
    window.clearTimeout(timer);
    if (error?.name === "AbortError") {
      throw new Error(`请求超时，已在 ${timeoutMs / 1000} 秒后中止`);
    }
    throw error;
  }
  window.clearTimeout(timer);
  let data = {};
  try {
    data = await response.json();
  } catch (error) {
    data = {};
  }
  if (!response.ok) {
    if (response.status === 401 && data?.detail === "AUTH_REQUIRED") {
      authRequired = true;
      showAuthOverlay(data?.scope === "config" ? "进入配置模块前，需要先输入访问密码。" : "需要输入访问密码后才能继续。");
      throw new Error("AUTH_REQUIRED");
    }
    throw new Error(JSON.stringify(data, null, 2) || `HTTP ${response.status}`);
  }
  return data;
}

function showAuthOverlay(message = "请输入访问密码。") {
  document.getElementById("auth-overlay")?.classList.remove("hidden");
  const status = document.getElementById("auth-status");
  if (status) {
    status.textContent = `${message} 当前会话有效期 ${authTtlMinutes} 分钟。`;
  }
}

function hideAuthOverlay() {
  document.getElementById("auth-overlay")?.classList.add("hidden");
}

async function checkAuthStatus() {
  const response = await fetch("/api/v1/auth/status");
  const data = await response.json();
  const item = data.item || {};
  authTtlMinutes = Number(item.ttl_minutes || 30);
  authRequired = Boolean(item.enabled) && !item.authenticated;
  if (authRequired) {
    showAuthOverlay("请输入访问密码后进入系统。");
    return false;
  }
  hideAuthOverlay();
  return true;
}

function renderOverviewCapitalPanel(strategyName = "") {
  const strategy = getSelectedStrategyRecord(strategyName);
  const config = strategy?.config || {};
  const targetCapital = Number(config.target_capital || 10000);
  const targetHorizonDays = Number(config.target_horizon_days || 30);
  const timeframe = config.timeframe || latestAnalysisResult?.timeframe || "1h";
  const symbol = config.symbol || latestAnalysisResult?.symbol || "BTC-USDT-SWAP";
  const totalEquity = Number(latestAccountOverview?.total_equity || 0);
  const capitalGap = totalEquity - targetCapital;
  const progress = targetCapital > 0 ? clamp(Math.round((totalEquity / targetCapital) * 100), 0, 100) : 0;
  const yieldRate = targetCapital > 0 ? (((totalEquity - targetCapital) / targetCapital) * 100).toFixed(2) : "0.00";
  const progressFill = document.getElementById("progress-fill");

  document.getElementById("mini-strategy").textContent = strategy?.name || "--";
  document.getElementById("mini-yield").textContent = `${yieldRate}%`;
  document.getElementById("hero-asset").textContent = `${totalEquity.toFixed(2)} / ${targetCapital.toFixed(2)} USDT`;
  document.getElementById("progress-current-capital").textContent = `${totalEquity.toFixed(2)} USDT`;
  document.getElementById("progress-target-capital").textContent = `${targetCapital.toFixed(2)} USDT`;
  document.getElementById("progress-capital-gap").textContent = `${capitalGap >= 0 ? "+" : ""}${capitalGap.toFixed(2)} USDT`;
  document.getElementById("progress-days-remaining").textContent = calculateRemainingDays(strategy);
  document.getElementById("total-asset").textContent = `${totalEquity.toFixed(2)} USDT`;
  document.getElementById("coin-asset").textContent = `${symbol} / ${strategy?.type || "custom"} / ${targetHorizonDays}天 / ${timeframe}`;
  document.getElementById("yield-rate").textContent = `${yieldRate}%`;

  if (progressFill) {
    progressFill.classList.remove("progress-fill-loading");
    progressFill.style.width = `${progress}%`;
    progressFill.textContent = `${progress}%`;
  }

  updateAssetTable(
    latestAccountOverview?.assets?.length
      ? latestAccountOverview.assets.map((item) => ({
          asset: item.asset,
          balance: Number(item.equity ?? item.balance ?? 0).toFixed(4),
          available: Number(item.available ?? 0).toFixed(4),
        }))
      : [],
  );
}

async function loginToApp() {
  const password = document.getElementById("auth-password-input").value.trim();
  if (!password) {
    showAuthOverlay("请输入访问密码。");
    return;
  }
  document.getElementById("auth-status").textContent = "正在验证密码...";
  const response = await fetch("/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    showAuthOverlay(data?.detail || "密码错误");
    return;
  }
  authRequired = false;
  authTtlMinutes = Number(data?.item?.ttl_minutes || authTtlMinutes || 30);
  hideAuthOverlay();
  document.getElementById("auth-password-input").value = "";
  await initializeSecuredApp();
}

async function pollTask(taskId, { timeoutMs = 120000, intervalMs = 1200 } = {}) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const response = await request(`/api/v1/tasks/${encodeURIComponent(taskId)}`, {
      timeoutMs: Math.min(intervalMs + 3000, 10000),
    });
    const item = response.item || {};
    if (item.status === "completed") {
      return item.result;
    }
    if (item.status === "failed") {
      throw new Error(item.error || "后台任务执行失败");
    }
    await new Promise((resolve) => window.setTimeout(resolve, intervalMs));
  }
  throw new Error(`后台任务超时，已等待 ${Math.round(timeoutMs / 1000)} 秒`);
}

function updateTradeList() {
  const tradeList = document.getElementById("trade-list");
  const tradeListPage = document.getElementById("trade-list-page");
  tradeList.innerHTML = "";
  tradeListPage.innerHTML = "";

  tradeRecords.forEach((item, index) => {
    const li = document.createElement("li");
    li.innerHTML = `
      <span>${index + 1}、${item.strategy}</span>
      <span>${item.side}</span>
      <span>创建时间：${item.createdAt || item.created_at}</span>
    `;
    tradeList.appendChild(li);
    tradeListPage.appendChild(li.cloneNode(true));
  });
}

function updateAssetTable(positions) {
  const body = document.getElementById("asset-table-body");
  body.innerHTML = "";

  positions.forEach((item) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${item.asset}</td>
      <td>${item.balance}</td>
      <td>${item.available}</td>
    `;
    body.appendChild(row);
  });
}

function getSelectedStrategyRecord(strategyName = "") {
  const preferredName = strategyName || document.getElementById("strategy-select")?.value || "";
  return strategyMap[preferredName] || latestSnapshot?.historical_strategies?.[0] || null;
}

function getSelectedStrategySymbol(strategyName = "") {
  const strategy = getSelectedStrategyRecord(strategyName);
  return strategy?.config?.symbol || latestAnalysisResult?.symbol || "BTC-USDT-SWAP";
}

function getSelectedStrategyConfig(strategyName = "") {
  return getSelectedStrategyRecord(strategyName)?.config || {};
}

async function loadStrategyTemplates() {
  try {
    const response = await request("/api/v1/strategies/templates");
    strategyTemplates = response.items || [];
    renderStrategyTemplateSummaries();
  } catch (error) {
    strategyTemplates = [];
    renderStrategyTemplateSummaries();
  }
}

function renderStrategyTemplateSummaries() {
  const container = document.getElementById("strategy-template-summary-grid");
  if (!container) {
    return;
  }
  if (!strategyTemplates.length) {
    container.innerHTML = `
      <article class="template-summary-card"><strong>保守</strong><p>模板暂未加载。</p></article>
      <article class="template-summary-card"><strong>平衡</strong><p>模板暂未加载。</p></article>
      <article class="template-summary-card"><strong>激进</strong><p>模板暂未加载。</p></article>
    `;
    return;
  }
  container.innerHTML = strategyTemplates
    .map((item) => {
      const config = item.config || {};
      return `
        <article class="template-summary-card">
          <strong>${item.label}</strong>
          <p>${item.description || ""}</p>
          <p>周期 ${config.timeframe || "--"} / 杠杆 ${config.leverage || "--"}x / 开仓 ${config.entry_allocation_pct || "--"}%</p>
          <p>仓位上限 ${config.max_position_pct || "--"}% / 回撤 ${config.max_drawdown_limit_pct || "--"}% / 风险 ${config.risk_limit_pct || "--"}%</p>
        </article>
      `;
    })
    .join("");
}

function applyStrategyTemplate(templateKey) {
  const item = strategyTemplates.find((template) => template.key === templateKey);
  if (!item) {
    setRuntimeStatus(`运行参数状态：未找到 ${templateKey} 模板`);
    return;
  }
  clearAiUpdatedFields();
  const config = item.config || {};
  document.getElementById("new-strategy-type").value = item.strategy_type || "custom";
  document.getElementById("new-strategy-risk-preference").value = item.risk_preference || "balanced";
  document.getElementById("new-strategy-timeframe").value = config.timeframe || "1h";
  document.getElementById("new-strategy-leverage").value = config.leverage || 1;
  document.getElementById("new-strategy-margin-mode").value = config.margin_mode || "cross";
  document.getElementById("new-strategy-fast-period").value = config.fast_period || 7;
  document.getElementById("new-strategy-slow-period").value = config.slow_period || 20;
  document.getElementById("new-strategy-rsi-period").value = config.rsi_period || 14;
  document.getElementById("new-strategy-take-profit").value = config.take_profit_pct || 8;
  document.getElementById("new-strategy-stop-loss").value = config.stop_loss_pct || 3;
  document.getElementById("new-strategy-risk-limit").value = config.risk_limit_pct || 2;
  document.getElementById("new-strategy-entry-allocation").value = config.entry_allocation_pct || 25;
  document.getElementById("new-strategy-max-position").value = config.max_position_pct || 50;
  document.getElementById("new-strategy-max-drawdown").value = config.max_drawdown_limit_pct || 12;
  if (!document.getElementById("new-strategy-description").value.trim()) {
    document.getElementById("new-strategy-description").value = item.description || "";
  }
  document.getElementById("new-strategy-execution-notes").value = item.execution_notes || "按策略信号与风控结果执行。";
  setRuntimeStatus(`运行参数状态：已套用${item.label}模板`);
}

function getSelectedStrategyTimeframe(strategyName = "") {
  const strategy = getSelectedStrategyRecord(strategyName);
  return strategy?.config?.timeframe || latestAnalysisResult?.timeframe || "1h";
}

function syncBacktestInputs(strategyName = "") {
  const strategy = getSelectedStrategyRecord(strategyName);
  if (!strategy) {
    return;
  }
  const config = strategy.config || {};
  const symbol = config.symbol || latestAnalysisResult?.symbol || "BTC-USDT-SWAP";
  document.getElementById("backtest-strategy").value = strategy.name;
  document.getElementById("backtest-symbol").value = symbol;
  document.getElementById("backtest-timeframe").value = config.timeframe || "1h";
  document.getElementById("backtest-capital").value = config.target_capital || 10000;
}

function toAssetTableRows(assets = []) {
  return assets.map((item) => ({
    asset: item.asset,
    balance: item.balance ?? item.equity ?? 0,
    available: item.available ?? 0,
  }));
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function calculateRemainingDays(strategy) {
  const targetDays = Number(strategy?.config?.target_horizon_days || 0);
  if (!targetDays) {
    return "--";
  }
  const createdAt = strategy?.created_at ? new Date(String(strategy.created_at).replace(" ", "T")) : null;
  if (!createdAt || Number.isNaN(createdAt.getTime())) {
    return `${targetDays} 天`;
  }
  const elapsedDays = Math.max(0, Math.floor((Date.now() - createdAt.getTime()) / (1000 * 60 * 60 * 24)));
  return `${Math.max(0, targetDays - elapsedDays)} 天`;
}

function buildStrategyDrivenMetrics(result, fallbackMetrics = {}) {
  const strategy = getSelectedStrategyRecord(result?.strategy_name);
  const config = strategy?.config || {};
  const targetCapital = Number(config.target_capital || latestAccountOverview?.available_equity || fallbackMetrics.total_asset || 10000);
  const targetHorizonDays = Number(config.target_horizon_days || 30);
  const timeframe = config.timeframe || result?.timeframe || "1h";
  const totalEquity = Number(latestAccountOverview?.total_equity ?? fallbackMetrics.total_asset ?? targetCapital);
  const availableEquity = Number(latestAccountOverview?.available_equity ?? targetCapital);
  const pnlBase = targetCapital > 0 ? ((totalEquity - targetCapital) / targetCapital) * 100 : 0;
  const confidenceProgress = Math.round((result?.agent?.confidence || 0.1) * 100);
  const capitalProgress = targetCapital > 0 ? (totalEquity / targetCapital) * 100 : 0;
  const blendedProgress = clamp(Math.round(capitalProgress * 0.7 + confidenceProgress * 0.3), 5, 100);
  const capitalGap = totalEquity - targetCapital;
  const positions = latestAccountOverview?.assets?.length
    ? toAssetTableRows(latestAccountOverview.assets)
    : fallbackMetrics.positions || [];
  return {
    strategy,
    targetCapital,
    targetHorizonDays,
    timeframe,
    totalEquity,
    availableEquity,
    capitalGap,
    yieldRate: pnlBase.toFixed(2),
    progress: blendedProgress,
    remainingDays: calculateRemainingDays(strategy),
    positions,
    coinAsset: `${result?.symbol || "BTC-USDT-SWAP"} / ${strategy?.type || "custom"} / ${targetHorizonDays}天`,
    trend: fallbackMetrics.trend || latestSnapshot?.account_metrics?.trend || [],
    candles: fallbackMetrics.candles || latestSnapshot?.account_metrics?.candles || [],
  };
}

function renderTaMetrics(indicators = {}) {
  const macd = indicators.macd || {};
  const boll = indicators.bollinger_bands || {};
  const rows = [
    { label: "SMA", value: `${Number(indicators.sma_fast || 0).toFixed(2)} / ${Number(indicators.sma_slow || 0).toFixed(2)}` },
    { label: "EMA", value: `${Number(indicators.ema_fast || 0).toFixed(2)} / ${Number(indicators.ema_slow || 0).toFixed(2)}` },
    { label: "RSI", value: Number(indicators.rsi || 0).toFixed(2) },
    { label: "MACD", value: `${Number(macd.line || 0).toFixed(2)} / ${Number(macd.signal || 0).toFixed(2)} / ${Number(macd.histogram || 0).toFixed(2)}` },
    { label: "BOLL", value: `${Number(boll.lower || 0).toFixed(2)} / ${Number(boll.middle || 0).toFixed(2)} / ${Number(boll.upper || 0).toFixed(2)}` },
    { label: "ATR / VOL-MA", value: `${Number(indicators.atr || 0).toFixed(2)} / ${Number(indicators.volume_ma || 0).toFixed(2)}` },
  ];
  const html = rows.map((row) => `<div><dt>${row.label}</dt><dd>${row.value}</dd></div>`).join("");
  document.getElementById("ta-metrics-overview").innerHTML = html;
  document.getElementById("ta-metrics-page").innerHTML = html;
}

function updateRuntimeModePill(source = "demo", mode = "paper", error = "") {
  const pill = document.getElementById("runtime-mode-pill");
  const normalizedSource = String(source || "demo").toLowerCase();
  const isLiveSource = normalizedSource === "okx-live" || normalizedSource === "okx-ccxt";
  const state = isLiveSource ? "live" : normalizedSource === "demo-fallback" ? "fallback" : "demo";
  pill.className = `runtime-pill runtime-pill-${state}`;
  pill.textContent = state === "live" ? `${normalizedSource} / ${mode}` : state === "fallback" ? "okx-fallback" : "demo";
  pill.title = error || source;
}

function renderStrategyDiagnostics(result = {}) {
  const score = result.signal?.score ?? "--";
  const agent = result.agent?.action || result.agent?.decision || "--";
  const risk = result.risk_preview?.approved ? "approved" : "blocked";
  document.getElementById("strategy-score-page").textContent = String(score);
  document.getElementById("strategy-agent-page").textContent = agent;
  document.getElementById("strategy-risk-page").textContent = risk;
  document.getElementById("strategy-diagnostics-output").value = prettyJson({
    signal: result.signal,
    agent_decision: getStructuredAgentDecision(result.agent, result.symbol),
    agent: result.agent,
    risk_preview: result.risk_preview,
    rl_hint: result.rl_hint,
  });
}

function renderBacktestCurve(points = []) {
  const svg = document.getElementById("backtest-curve-chart");
  if (!points.length) {
    svg.innerHTML = "";
    return;
  }
  const width = 520;
  const height = 160;
  const padding = 16;
  const values = points.map((point) => Number(point.equity || 0));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 1);
  const coords = points.map((point, index) => {
    const x = padding + (index * (width - padding * 2)) / Math.max(points.length - 1, 1);
    const y = height - padding - ((Number(point.equity || 0) - min) / range) * (height - padding * 2);
    return { x, y, label: String(point.index), value: Number(point.equity || 0) };
  });
  const polyline = coords.map((point) => `${point.x},${point.y}`).join(" ");
  svg.innerHTML = `
    <polyline points="${polyline}" fill="none" stroke="#58cbff" stroke-width="3"></polyline>
    ${coords.map((point) => `<circle cx="${point.x}" cy="${point.y}" r="2.5" fill="#4dffb1"></circle>`).join("")}
  `;
}

function renderBacktestTrades(trades = []) {
  const body = document.getElementById("backtest-trades-body");
  const recent = trades.slice(-6).reverse();
  body.innerHTML = recent.length
    ? recent
        .map(
          (item) => `
            <tr>
              <td>${item.side}</td>
              <td>${Number(item.price || 0).toFixed(2)}</td>
              <td>${Number(item.fee || 0).toFixed(4)}</td>
              <td>${item.pnl != null ? Number(item.pnl).toFixed(4) : "--"}</td>
            </tr>
          `,
        )
        .join("")
    : '<tr><td colspan="4">暂无成交记录</td></tr>';
}

function renderAccountOverview(data = {}) {
  latestAccountOverview = data;
  updateRuntimeModePill(data.source, data.mode, data.error || "");
  document.getElementById("account-source").textContent = data.source || "--";
  document.getElementById("account-total-equity").textContent = data.total_equity != null ? `${Number(data.total_equity).toFixed(2)} USDT` : "--";
  document.getElementById("account-available-equity").textContent = data.available_equity != null ? `${Number(data.available_equity).toFixed(2)} USDT` : "--";
  document.getElementById("account-mode").textContent = data.mode || "--";
  document.getElementById("account-upl").textContent = data.upl != null ? `${Number(data.upl).toFixed(2)}` : "--";
  document.getElementById("account-status-output").value = prettyJson(data);
  const capitalHint = document.getElementById("strategy-capital-hint");
  if (capitalHint) {
    capitalHint.textContent = `当前账户可用资金：${data.available_equity != null ? Number(data.available_equity).toFixed(2) : "--"} USDT${data.source ? ` / ${data.source}` : ""}`;
  }
  const body = document.getElementById("account-assets-body");
  const assets = data.assets || [];
  body.innerHTML = assets.length
    ? assets
        .map(
          (item) => `
            <tr>
              <td>${item.asset}</td>
              <td>${Number(item.equity || 0).toFixed(4)}</td>
              <td>${Number(item.available || 0).toFixed(4)}</td>
              <td>${Number(item.upl || 0).toFixed(4)}</td>
            </tr>
          `,
        )
        .join("")
    : '<tr><td colspan="4">暂无资产数据</td></tr>';
  renderOverviewCapitalPanel(document.getElementById("strategy-select")?.value || "");
  if (latestAnalysisResult) {
    updateStrategyView(latestAnalysisResult, latestSnapshot?.account_metrics || {});
  }
}

function renderPositions(data = {}) {
  const body = document.getElementById("positions-body");
  const items = data.items || [];
  body.innerHTML = items.length
    ? items
        .map(
          (item) => `
            <tr>
              <td>${item.symbol}</td>
              <td>${item.side}</td>
              <td>${Number(item.size || 0).toFixed(4)}</td>
              <td>${Number(item.entry_price || 0).toFixed(2)}</td>
              <td>${Number(item.mark_price || 0).toFixed(2)}</td>
              <td>${Number(item.upl || 0).toFixed(4)}</td>
            </tr>
          `,
        )
        .join("")
    : '<tr><td colspan="6">暂无持仓数据</td></tr>';
}

function renderOrders(data = {}) {
  const pendingBody = document.getElementById("pending-orders-body");
  const historyBody = document.getElementById("history-orders-body");
  const pending = data.pending || [];
  const history = data.history || [];
  pendingBody.innerHTML = pending.length
    ? pending
        .map(
          (item) => `
            <tr>
              <td>${item.order_id}</td>
              <td>${item.symbol}</td>
              <td>${item.side}</td>
              <td>${item.type}</td>
              <td>${Number(item.size || 0).toFixed(4)}</td>
              <td>${item.status}</td>
            </tr>
          `,
        )
        .join("")
    : '<tr><td colspan="6">暂无挂单</td></tr>';
  historyBody.innerHTML = history.length
    ? history
        .map(
          (item) => `
            <tr>
              <td>${item.order_id}</td>
              <td>${item.symbol}</td>
              <td>${item.side}</td>
              <td>${Number(item.avg_price || 0).toFixed(2)}</td>
              <td>${Number(item.filled_size || item.size || 0).toFixed(4)}</td>
              <td>${item.status}</td>
            </tr>
          `,
        )
        .join("")
    : '<tr><td colspan="6">暂无历史订单</td></tr>';
}

function renderTrendChart(points, candles = []) {
  const svg = document.getElementById("trend-chart");
  const width = 520;
  const height = 160;
  const padding = 16;
  const series = candles.length
    ? candles.map((item, index) => ({ label: String(index + 1), value: item.close }))
    : points;
  const values = series.map((point) => point.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 1);

  const coords = series.map((point, index) => {
    const x = padding + (index * (width - padding * 2)) / Math.max(series.length - 1, 1);
    const y = height - padding - ((point.value - min) / range) * (height - padding * 2);
    return { ...point, x, y };
  });

  const polyline = coords.map((point) => `${point.x},${point.y}`).join(" ");
  const circles = coords
    .map(
      (point) => `<circle cx="${point.x}" cy="${point.y}" r="3" fill="#5a9638"></circle>`,
    )
    .join("");
  const labels = coords
    .filter((_, index) => index % Math.max(Math.floor(coords.length / 5), 1) === 0 || index === coords.length - 1)
    .map(
      (point) =>
        `<text x="${point.x}" y="${height - 4}" text-anchor="middle" font-size="11" fill="#666d75">${point.label}</text>`,
    )
    .join("");

  svg.innerHTML = `
    <polyline points="${polyline}" fill="none" stroke="#456f2c" stroke-width="3"></polyline>
    ${circles}
    ${labels}
  `;
}

function renderTrendChartHeader(result, strategy) {
  const label = document.getElementById("trend-chart-label");
  const title = document.getElementById("trend-chart-title");
  if (!label || !title) {
    return;
  }
  label.textContent = `${result.symbol} / ${result.timeframe}`;
  title.textContent = `${strategy?.name || result.strategy_name} Trend Projection`;
}

function setProgressLoadingState() {
  const progressFill = document.getElementById("progress-fill");
  if (!progressFill) {
    return;
  }
  progressFill.classList.add("progress-fill-loading");
  progressFill.style.width = "0%";
  progressFill.textContent = "--";
}

function renderSourceCards(sourceName) {
  activeSourceName = sourceName;
  const meta = sourceMetaMap[sourceName] || {};
  const sourceDescription = NEWS_SOURCE_DESCRIPTIONS[sourceName] || "用于补充当前策略的外部资讯上下文。";
  const items = sourceMap[sourceName] || [{ title: "热点摘要", body: "等待外部信息源接入。", source: sourceName }];
  const container = document.getElementById("source-content");
  container.classList.add("switching");
  window.setTimeout(() => container.classList.remove("switching"), 180);
  document.getElementById("news-refresh-policy").textContent = "更新方式：每 10 分钟自动刷新，也可手动刷新";
  document.getElementById("news-last-refresh").textContent = `上次刷新：${formatDateTime(meta.last_refreshed_at)}`;
  document.getElementById("news-current-status").textContent = `当前状态：${getStatusLabel(meta.status)}${meta.last_error ? ` / ${meta.last_error}` : ""}`;
  document.getElementById("news-switch-status").textContent = `切换状态：已切换到 ${sourceName}`;
  const summaryModeLabel =
    meta.summary_mode === "llm"
      ? "LLM 摘要"
      : meta.summary_mode === "raw-fallback"
        ? "LLM 失败回退"
        : "原文清洗";
  document.getElementById("news-panel-subtitle").textContent = meta.item_count
    ? `当前源 ${sourceName}，共 ${meta.item_count} 条内容，${sourceDescription}，当前模式：${summaryModeLabel}`
    : `当前源 ${sourceName}，暂无可用内容，${sourceDescription}，当前模式：${summaryModeLabel}`;
  document.getElementById("news-refresh-policy-page").textContent = "更新方式：每 10 分钟自动刷新，也可手动刷新";
  document.getElementById("news-last-refresh-page").textContent = `上次刷新：${formatDateTime(meta.last_refreshed_at)}`;
  container.innerHTML = `
    ${items
      .map(
        (item, index) => `
          <article class="source-card">
            <div class="source-card-head">
              <div class="source-card-title-block">
                <h3>${item.title || `${sourceName} ${String(index + 1).padStart(2, "0")}`}</h3>
                <p class="source-card-subtitle">${sourceDescription}</p>
              </div>
              <div class="source-meta">
                <span class="source-meta-tag">${item.source || sourceName}</span>
                <span class="source-meta-tag">${formatDateTime(item.published_at || meta.last_refreshed_at || "")}</span>
                <span class="source-meta-tag">${summaryModeLabel}</span>
              </div>
            </div>
            <p>${item.body || item.summary || "暂无摘要内容。"}</p>
            ${item.link ? `<a class="source-link" href="${item.link}" target="_blank" rel="noreferrer">查看原文</a>` : ""}
          </article>
        `,
      )
      .join("")}
    <article class="source-card">
      <div class="source-card-head">
        <div class="source-card-title-block">
          <h3>策略关联</h3>
          <p class="source-card-subtitle">${sourceDescription}</p>
        </div>
        <div class="source-meta">
          <span class="source-meta-tag">${sourceName}</span>
          <span class="source-meta-tag">${getStatusLabel(meta.status)}</span>
          <span class="source-meta-tag">${summaryModeLabel}</span>
        </div>
      </div>
      <p>${sourceDescription}。该信息源可作为 RAG 上下文输入，辅助 Agent 在波动行情下重新评估信号强度和风险阈值。</p>
    </article>
  `;
}

function renderSourceChips(sourceNames) {
  const row = document.getElementById("source-row");
  const rowPage = document.getElementById("source-row-page");
  const html = sourceNames
    .map(
      (name, index) => {
        const meta = sourceMetaMap[name] || {};
        const badge = meta.status || meta.mode || "pending";
        const description = NEWS_SOURCE_DESCRIPTIONS[name] || "外部资讯源";
        return `
        <button class="source-chip ${name === activeSourceName || (!activeSourceName && index === 0) ? "active" : ""}" type="button" data-source="${name}">
          <span>${name}</span>
          <small class="source-chip-desc">${description}</small>
          <small class="source-chip-badge ${badge}">${getStatusLabel(badge)}</small>
        </button>
      `;
      },
    )
    .join("");
  row.innerHTML = html;
  rowPage.innerHTML = html;
}

async function loadNewsSourcesPanel() {
  try {
    const symbol = getSelectedStrategySymbol();
    const response = await request(`/api/v1/news/sources?symbol=${encodeURIComponent(symbol)}&use_llm=false`, { timeoutMs: 20000 });
    const items = response.items || [];
    sourceMap = Object.fromEntries(items.map((item) => [item.name, item.items]));
    sourceMetaMap = Object.fromEntries(items.map((item) => [item.name, item.meta || {}]));
    const sourceNames = items.map((item) => item.name);
    if (!sourceNames.length) {
      document.getElementById("news-current-status").textContent = "当前状态：没有可用新闻源";
      return;
    }
    activeSourceName = sourceNames.includes(activeSourceName) ? activeSourceName : sourceNames[0];
    renderSourceChips(sourceNames);
    renderSourceCards(activeSourceName);
  } catch (error) {
    document.getElementById("news-current-status").textContent = `当前状态：新闻源加载失败 / ${String(error)}`;
    document.getElementById("news-switch-status").textContent = "切换状态：新闻源兜底加载失败";
  }
}

async function summarizeActiveNewsSource() {
  if (!activeSourceName) {
    setRuntimeStatus("运行参数状态：请先选择一个新闻源，再执行 LLM 摘要。");
    return;
  }
  try {
    setRuntimeStatus(`运行参数状态：正在为 ${activeSourceName} 生成 LLM 摘要...`);
    const symbol = getSelectedStrategySymbol();
    const response = await request(
      `/api/v1/news/summarize?source_name=${encodeURIComponent(activeSourceName)}&symbol=${encodeURIComponent(symbol)}`,
      { method: "POST", timeoutMs: 60000 },
    );
    const item = response.item || {};
    sourceMap[activeSourceName] = item.items || [];
    sourceMetaMap[activeSourceName] = item.meta || {};
    renderSourceChips(Object.keys(sourceMap));
    renderSourceCards(activeSourceName);
    setRuntimeStatus(`运行参数状态：${activeSourceName} 的 LLM 摘要已生成`);
  } catch (error) {
    setRuntimeStatus(`运行参数状态：${activeSourceName || "当前新闻源"} LLM 摘要失败 ${String(error)}`);
  }
}

function renderDailyReport(report, fallbackResult, fallbackMetrics) {
  const dateText = report?.date || new Date().toLocaleDateString("zh-CN");
  document.getElementById("daily-report-date").textContent = dateText;
  const sections = report?.sections?.length
    ? report.sections
    : [
        {
          title: "市场摘要",
          body: `当前监控标的为 ${fallbackResult.symbol}，最新价格 ${fallbackResult.last_price}，短线信号为 ${fallbackResult.signal.signal}，走势周期 ${fallbackResult.timeframe}。`,
        },
        {
          title: "策略结论",
          body: `当前启用策略 ${fallbackResult.strategy_name}，Agent 决策为 ${fallbackResult.agent.decision}，置信度约 ${Math.max(10, Math.round(fallbackResult.agent.confidence * 100))}%。`,
        },
        {
          title: "风险提醒",
          body: `风险预检结果为 ${fallbackResult.risk_preview.reason}，当前收益率展示为 ${fallbackMetrics.yield_rate}%，需结合仓位波动继续控制风险暴露。`,
        },
        {
          title: "操作建议",
          body: "建议结合外部热点信息源与账户资产变化，确认趋势延续后再决定是否加仓；若波动放大则优先保守执行。",
        },
      ];

  latestReportText = sections
    .map((section, index) => `${index + 1}. ${section.title}\n${section.body}`)
    .join("\n\n");

  document.getElementById("daily-report-body").innerHTML = sections
    .map(
      (section) => `
        <article class="report-card">
          <h4>${section.title}</h4>
          <p>${section.body}</p>
        </article>
      `,
    )
    .join("");
}

function renderDailySummaryEntries(items = []) {
  latestDailySummaryEntries = Array.isArray(items) ? items : [];
  const body = document.getElementById("daily-summary-body");
  if (!body) {
    return;
  }
  const structuredDecisionCard = latestAnalysisResult?.agent ? buildStructuredDecisionCard(latestAnalysisResult.agent, latestAnalysisResult.symbol) : "";
  if (!latestDailySummaryEntries.length) {
    body.innerHTML = `
      ${structuredDecisionCard}
      <article class="report-card">
        <h4>每日策略总结</h4>
        <p>还没有可显示的每日总结。你可以去配置页点“立即生成每日总结”，或者等待定时任务运行后再回来查看。</p>
      </article>
    `;
    return;
  }
  body.innerHTML =
    structuredDecisionCard +
    latestDailySummaryEntries
      .map(
        (item) => `
        ${buildStructuredSummaryCard(item)}
        <article class="report-card">
          <h4>${escapeHtml(item.strategy_name || "--")} / ${escapeHtml(item.date || item.created_at || "--")}</h4>
          <p>${escapeHtml(item.content || "暂无内容").replace(/\n/g, "<br />")}</p>
        </article>
      `,
      )
      .join("");
}

async function loadDailySummaryHistory(strategyName = "") {
  try {
    const query = strategyName ? `?strategy_name=${encodeURIComponent(strategyName)}&limit=6` : "?limit=6";
    const response = await request(`/api/v1/automation/daily-summary/history${query}`);
    renderDailySummaryEntries(response.items || []);
  } catch (_error) {
    renderDailySummaryEntries([]);
  }
}

function exportDailyReport() {
  if (!latestReportText) {
    return;
  }

  const blob = new Blob([latestReportText], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  const date = new Date().toISOString().slice(0, 10);
  anchor.href = url;
  anchor.download = `daily-report-${date}.txt`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

function openStrategyModal(mode) {
  strategyModalMode = mode;
  document.getElementById("strategy-modal-title").textContent = mode === "create" ? "新增策略" : "编辑当前策略";
  document.getElementById("modal-submit-btn").textContent = mode === "create" ? "新增策略" : "以当前内容新增副本";
  document.getElementById("save-strategy-btn").style.display = mode === "edit" ? "inline-flex" : "none";
  document.getElementById("strategy-modal-backdrop").classList.remove("hidden");
}

function closeStrategyModal() {
  if (window.__strategyAiBusy) {
    setStrategyModalStatus("AI 建议仍在生成中，请等待完成或超时提示。");
    return;
  }
  document.getElementById("strategy-modal-backdrop").classList.add("hidden");
}

function openPromptModal() {
  document.getElementById("prompt-modal-backdrop").classList.remove("hidden");
}

function closePromptModal() {
  document.getElementById("prompt-modal-backdrop").classList.add("hidden");
}

async function loadPromptTemplates() {
  const response = await request("/api/v1/prompts");
  promptTemplates = response.items;
  const select = document.getElementById("prompt-template-select");
  const selectPage = document.getElementById("config-prompt-template-select");
  select.innerHTML = promptTemplates
    .map((item) => `<option value="${item.name}">${item.category || "模板"} / ${item.label || item.name}</option>`)
    .join("");
  if (selectPage) {
    selectPage.innerHTML = select.innerHTML;
  }
  if (promptTemplates.length) {
    await loadPromptTemplate(promptTemplates[0].name);
  }
}

async function loadRuntimeConfig() {
  const response = await request("/api/v1/runtime-config");
  runtimeConfig = response.item || {};
  document.getElementById("runtime-provider-mode").value = runtimeConfig.openai_base_url ? "compatible" : "openai";
  document.getElementById("config-provider-mode").value = runtimeConfig.openai_base_url ? "compatible" : "openai";
  document.getElementById("runtime-openai-api-key").value = runtimeConfig.openai_api_key || "";
  document.getElementById("config-openai-api-key").value = runtimeConfig.openai_api_key || "";
  document.getElementById("config-app-password").value = runtimeConfig.app_password || "";
  document.getElementById("config-app-session-ttl").value = runtimeConfig.app_session_ttl_minutes ?? 30;
  document.getElementById("runtime-openai-model").value = runtimeConfig.openai_model || "";
  document.getElementById("config-openai-model").value = runtimeConfig.openai_model || "";
  document.getElementById("runtime-llm-model").value = runtimeConfig.llm_model || "";
  document.getElementById("config-llm-model").value = runtimeConfig.llm_model || "";
  document.getElementById("runtime-llm-temperature").value = runtimeConfig.llm_temperature ?? 0.1;
  document.getElementById("config-llm-temperature").value = runtimeConfig.llm_temperature ?? 0.1;
  document.getElementById("runtime-openai-base-url").value = runtimeConfig.openai_base_url || "";
  document.getElementById("config-openai-base-url").value = runtimeConfig.openai_base_url || "";
  document.getElementById("config-embeddings-use-shared").value = String(runtimeConfig.embeddings_use_shared_credentials ?? true);
  document.getElementById("config-embeddings-api-key").value = runtimeConfig.embeddings_api_key || "";
  document.getElementById("config-embeddings-base-url").value = runtimeConfig.embeddings_base_url || "";
  document.getElementById("runtime-embeddings-model").value = runtimeConfig.embeddings_model || "";
  document.getElementById("config-embeddings-model").value = runtimeConfig.embeddings_model || "";
  const embeddingsPreset = detectEmbeddingsPreset(runtimeConfig.embeddings_model);
  document.getElementById("runtime-embeddings-preset").value = embeddingsPreset;
  document.getElementById("config-embeddings-preset").value = embeddingsPreset;
  document.getElementById("runtime-embeddings-enabled").value = String(runtimeConfig.embeddings_enabled ?? false);
  document.getElementById("config-embeddings-enabled").value = String(runtimeConfig.embeddings_enabled ?? false);
  document.getElementById("runtime-okx-api-key").value = runtimeConfig.okx_api_key || "";
  document.getElementById("config-okx-api-key").value = runtimeConfig.okx_api_key || "";
  document.getElementById("runtime-okx-api-secret").value = runtimeConfig.okx_api_secret || "";
  document.getElementById("config-okx-api-secret").value = runtimeConfig.okx_api_secret || "";
  document.getElementById("runtime-okx-passphrase").value = runtimeConfig.okx_passphrase || "";
  document.getElementById("config-okx-passphrase").value = runtimeConfig.okx_passphrase || "";
  document.getElementById("runtime-okx-rest-base").value = runtimeConfig.okx_rest_base || "https://www.okx.com";
  document.getElementById("config-okx-rest-base").value = runtimeConfig.okx_rest_base || "https://www.okx.com";
  document.getElementById("runtime-okx-use-paper").value = String(runtimeConfig.okx_use_paper ?? true);
  document.getElementById("config-okx-use-paper").value = String(runtimeConfig.okx_use_paper ?? true);
  document.getElementById("config-okx-adapter").value = runtimeConfig.okx_adapter || "native";
  document.getElementById("config-feishu-webhook-url").value = runtimeConfig.feishu_webhook_url || "";
  document.getElementById("config-feishu-push-daily-report").value = String(runtimeConfig.feishu_push_daily_report ?? true);
  document.getElementById("config-feishu-push-daily-summary").value = String(runtimeConfig.feishu_push_daily_summary ?? true);
  document.getElementById("config-llm-summary").textContent = runtimeConfig.llm_model || "未配置";
  document.getElementById("config-embeddings-access-summary").textContent = runtimeConfig.embeddings_enabled
    ? runtimeConfig.embeddings_use_shared_credentials !== false
      ? "复用当前模型接入"
      : runtimeConfig.embeddings_base_url || "单独 Key / 默认 URL"
    : "未启用";
  document.getElementById("config-embeddings-summary").textContent = runtimeConfig.embeddings_enabled
    ? runtimeConfig.embeddings_model || "已开启"
    : "关闭";
  document.getElementById("config-okx-summary").textContent = `${runtimeConfig.okx_use_paper ? "模拟盘" : "实盘"} / ${runtimeConfig.okx_adapter || "native"}`;
  document.getElementById("config-news-summary").textContent = Array.isArray(runtimeConfig.news_sources)
    ? `${runtimeConfig.news_sources.length} 个`
    : "默认";
  document.getElementById("config-feishu-summary").textContent = runtimeConfig.feishu_webhook_url
    ? `已配置 / 日报 ${runtimeConfig.feishu_push_daily_report === false ? "关" : "开"} / 总结 ${runtimeConfig.feishu_push_daily_summary === false ? "关" : "开"}`
    : "未配置";
  applyRuntimeModeVisibility();
  applyConfigPageVisibility();
  await loadAutomationStatus();
}

async function loadAutomationStatus() {
  const response = await request("/api/v1/automation/status");
  automationStatus = response.item || {};
  const config = automationStatus.config || {};
  document.getElementById("config-auto-trade-enabled").value = String(config.auto_trade_enabled ?? false);
  document.getElementById("config-auto-trade-interval").value = config.auto_trade_interval_minutes ?? 15;
  document.getElementById("config-auto-trade-strategies").value = (config.auto_trade_strategy_names || []).join(", ");
  document.getElementById("config-auto-trade-confidence").value = config.auto_trade_min_confidence ?? 0.55;
  document.getElementById("config-daily-summary-enabled").value = String(config.daily_summary_enabled ?? false);
  document.getElementById("config-daily-summary-hour").value = config.daily_summary_hour ?? 21;
  document.getElementById("config-daily-summary-strategies").value = (config.daily_summary_strategy_names || []).join(", ");
  document.getElementById("config-daily-summary-apply-ai-updates").value = String(config.daily_summary_apply_ai_updates ?? false);
  document.getElementById("config-automation-running").textContent = automationStatus.service_running ? "运行中" : "已停止";
  document.getElementById("config-auto-trade-summary").textContent = config.auto_trade_enabled
    ? `开启 / 上次 ${automationStatus.auto_trade?.last_run_at || "未执行"}`
    : "关闭";
  document.getElementById("config-daily-summary-summary").textContent = config.daily_summary_enabled
    ? `开启 / 上次 ${automationStatus.daily_summary?.last_run_at || "未执行"}`
    : "关闭";
  document.getElementById("automation-output").value = prettyJson(automationStatus);
}

async function saveAutomationConfig() {
  const runtimePayload = {
    app_password: runtimeConfig.app_password || "",
    app_session_ttl_minutes: Number(runtimeConfig.app_session_ttl_minutes ?? 30),
    openai_api_key: runtimeConfig.openai_api_key || "",
    openai_model: runtimeConfig.openai_model || "",
    llm_model: runtimeConfig.llm_model || "",
    llm_temperature: Number(runtimeConfig.llm_temperature ?? 0.1),
    openai_base_url: runtimeConfig.openai_base_url || "",
    embeddings_enabled: Boolean(runtimeConfig.embeddings_enabled),
    embeddings_use_shared_credentials: runtimeConfig.embeddings_use_shared_credentials !== false,
    embeddings_api_key: runtimeConfig.embeddings_api_key || "",
    embeddings_base_url: runtimeConfig.embeddings_base_url || "",
    embeddings_model: runtimeConfig.embeddings_model || "text-embedding-3-small",
    okx_api_key: runtimeConfig.okx_api_key || "",
    okx_api_secret: runtimeConfig.okx_api_secret || "",
    okx_passphrase: runtimeConfig.okx_passphrase || "",
    okx_rest_base: runtimeConfig.okx_rest_base || "https://www.okx.com",
    okx_use_paper: runtimeConfig.okx_use_paper !== false,
    okx_adapter: runtimeConfig.okx_adapter || "native",
    feishu_webhook_url: document.getElementById("config-feishu-webhook-url").value.trim(),
    feishu_push_daily_report: document.getElementById("config-feishu-push-daily-report").value === "true",
    feishu_push_daily_summary: document.getElementById("config-feishu-push-daily-summary").value === "true",
  };
  await request("/api/v1/runtime-config", {
    method: "PUT",
    body: JSON.stringify(runtimePayload),
  });
  runtimeConfig = { ...runtimeConfig, ...runtimePayload };
  const payload = {
    auto_trade_enabled: document.getElementById("config-auto-trade-enabled").value === "true",
    auto_trade_interval_minutes: Number(document.getElementById("config-auto-trade-interval").value || 15),
    auto_trade_strategy_names: parseCsvList(document.getElementById("config-auto-trade-strategies").value),
    auto_trade_min_confidence: Number(document.getElementById("config-auto-trade-confidence").value || 0.55),
    daily_summary_enabled: document.getElementById("config-daily-summary-enabled").value === "true",
    daily_summary_hour: Number(document.getElementById("config-daily-summary-hour").value || 21),
    daily_summary_strategy_names: parseCsvList(document.getElementById("config-daily-summary-strategies").value),
    daily_summary_apply_ai_updates: document.getElementById("config-daily-summary-apply-ai-updates").value === "true",
  };
  const response = await request("/api/v1/automation/config", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  document.getElementById("automation-output").value = prettyJson(response.item || {});
  await loadAutomationStatus();
  await syncOperationalStrategySelection();
  setRuntimeStatus("运行参数状态：自动交易 / 每日总结 / 飞书推送配置已保存");
}

async function testFeishuPush() {
  setRuntimeStatus("运行参数状态：正在发送飞书测试消息...");
  const runtimePayload = {
    app_password: runtimeConfig.app_password || "",
    app_session_ttl_minutes: Number(runtimeConfig.app_session_ttl_minutes ?? 30),
    openai_api_key: runtimeConfig.openai_api_key || "",
    openai_model: runtimeConfig.openai_model || "",
    llm_model: runtimeConfig.llm_model || "",
    llm_temperature: Number(runtimeConfig.llm_temperature ?? 0.1),
    openai_base_url: runtimeConfig.openai_base_url || "",
    embeddings_enabled: Boolean(runtimeConfig.embeddings_enabled),
    embeddings_use_shared_credentials: runtimeConfig.embeddings_use_shared_credentials !== false,
    embeddings_api_key: runtimeConfig.embeddings_api_key || "",
    embeddings_base_url: runtimeConfig.embeddings_base_url || "",
    embeddings_model: runtimeConfig.embeddings_model || "text-embedding-3-small",
    okx_api_key: runtimeConfig.okx_api_key || "",
    okx_api_secret: runtimeConfig.okx_api_secret || "",
    okx_passphrase: runtimeConfig.okx_passphrase || "",
    okx_rest_base: runtimeConfig.okx_rest_base || "https://www.okx.com",
    okx_use_paper: runtimeConfig.okx_use_paper !== false,
    okx_adapter: runtimeConfig.okx_adapter || "native",
    feishu_webhook_url: document.getElementById("config-feishu-webhook-url").value.trim(),
    feishu_push_daily_report: document.getElementById("config-feishu-push-daily-report").value === "true",
    feishu_push_daily_summary: document.getElementById("config-feishu-push-daily-summary").value === "true",
  };
  await request("/api/v1/runtime-config", {
    method: "PUT",
    body: JSON.stringify(runtimePayload),
  });
  runtimeConfig = { ...runtimeConfig, ...runtimePayload };
  const response = await request("/api/v1/runtime-config/test-feishu", { method: "POST", timeoutMs: 30000 });
  document.getElementById("automation-output").value = prettyJson(response);
  await loadRuntimeConfig();
  setRuntimeStatus(response.ok ? "运行参数状态：飞书测试消息已发送" : `运行参数状态：飞书测试失败 ${response.message || ""}`);
}

async function runAutoTradeNow() {
  setRuntimeStatus("运行参数状态：正在执行自动交易任务...");
  const response = await request("/api/v1/automation/auto-trade/run", {
    method: "POST",
    timeoutMs: 30000,
  });
  document.getElementById("automation-output").value = prettyJson(response.item || {});
  await loadAutomationStatus();
  setRuntimeStatus("运行参数状态：自动交易任务已执行");
}

async function runDailySummaryNow() {
  setRuntimeStatus("运行参数状态：正在生成每日自动总结...");
  const task = await request("/api/v1/automation/daily-summary/run-async?force=true", {
    method: "POST",
  });
  document.getElementById("automation-output").value = prettyJson({ status: "queued", task: task.item || {} });
  const result = await pollTask(task.item.id, { timeoutMs: 180000 });
  document.getElementById("automation-output").value = prettyJson(result.item || result);
  await loadAutomationStatus();
  await refreshStrategiesOnly(document.getElementById("strategy-select")?.value || "");
  await loadDailySummaryHistory(document.getElementById("strategy-select")?.value || "");
  await loadDashboardSnapshot(document.getElementById("strategy-select")?.value || "");
  setRuntimeStatus("运行参数状态：每日自动总结已执行");
}

async function loadNewsSourceConfig() {
  const response = await request("/api/v1/news/config");
  const enriched = (response.items || []).map((item) => ({
    ...item,
    description: NEWS_SOURCE_DESCRIPTIONS[item.name] || "",
    summary_mode: item.llm_summary ? "llm" : "raw",
  }));
  const pretty = prettyJson(enriched);
  const dataEditor = document.getElementById("data-news-source-editor");
  if (dataEditor) {
    dataEditor.value = pretty;
  }
  document.getElementById("data-source-output").value = pretty;
}

async function loadPromptTemplate(name) {
  const response = await request(`/api/v1/prompts/${encodeURIComponent(name)}`);
  const metaText = `模板说明：${response.item.category || "未分类"} / ${response.item.label || name}。${response.item.description || "暂无说明。"} `;
  document.getElementById("prompt-template-select").value = name;
  document.getElementById("config-prompt-template-select").value = name;
  document.getElementById("prompt-template-editor").value = response.item.content;
  document.getElementById("config-prompt-template-editor").value = response.item.content;
  document.getElementById("prompt-template-meta").textContent = metaText;
  document.getElementById("config-prompt-template-meta").textContent = metaText;
}

async function savePromptTemplate() {
  const name = document.getElementById("prompt-template-select").value;
  const content = document.getElementById("prompt-template-editor").value;
  await request(`/api/v1/prompts/${encodeURIComponent(name)}`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
  setRuntimeStatus(`运行参数状态：模板 ${name} 已保存`);
}

async function savePromptTemplateFromPage() {
  const name = document.getElementById("config-prompt-template-select").value;
  const content = document.getElementById("config-prompt-template-editor").value;
  await request(`/api/v1/prompts/${encodeURIComponent(name)}`, {
    method: "PUT",
    body: JSON.stringify({ content }),
  });
  document.getElementById("prompt-template-editor").value = content;
  setRuntimeStatus(`运行参数状态：模板 ${name} 已保存`);
}

async function previewPromptTemplate() {
  const name = document.getElementById("prompt-template-select").value;
  const symbol = getSelectedStrategySymbol();
  const strategyName = document.getElementById("strategy-select")?.value || "sma_crossover";
  const timeframe = getSelectedStrategyTimeframe(strategyName);
  setRuntimeStatus(`运行参数状态：正在预览模板 ${name}...`);
  document.getElementById("prompt-preview-output").value = "";
  try {
    const task = await request(`/api/v1/prompts/preview-async/${encodeURIComponent(name)}`, {
      method: "POST",
      body: JSON.stringify({ symbol, strategy_name: strategyName, timeframe }),
    });
    const response = await pollTask(task.item.id, { timeoutMs: 180000 });
    document.getElementById("prompt-preview-output").value = prettyJson(response.item || {});
    setRuntimeStatus(
      response.ok === false
        ? `运行参数状态：模板 ${name} 预览失败`
        : `运行参数状态：模板 ${name} 预览完成`,
    );
  } catch (error) {
    document.getElementById("prompt-preview-output").value = prettyJson({ message: String(error) });
    setRuntimeStatus(`运行参数状态：模板 ${name} 预览失败`);
  }
}

async function previewPromptTemplateFromPage() {
  const name = document.getElementById("config-prompt-template-select").value;
  const symbol = getSelectedStrategySymbol();
  const strategyName = document.getElementById("strategy-select")?.value || "sma_crossover";
  const timeframe = getSelectedStrategyTimeframe(strategyName);
  setRuntimeStatus(`运行参数状态：正在预览模板 ${name}...`);
  document.getElementById("config-prompt-preview-output").value = "";
  try {
    const task = await request(`/api/v1/prompts/preview-async/${encodeURIComponent(name)}`, {
      method: "POST",
      body: JSON.stringify({ symbol, strategy_name: strategyName, timeframe }),
    });
    const response = await pollTask(task.item.id, { timeoutMs: 180000 });
    const pretty = prettyJson(response.item || {});
    document.getElementById("config-prompt-preview-output").value = pretty;
    document.getElementById("prompt-preview-output").value = pretty;
    setRuntimeStatus(
      response.ok === false
        ? `运行参数状态：模板 ${name} 预览失败`
        : `运行参数状态：模板 ${name} 预览完成`,
    );
  } catch (error) {
    const pretty = prettyJson({ message: String(error) });
    document.getElementById("config-prompt-preview-output").value = pretty;
    document.getElementById("prompt-preview-output").value = pretty;
    setRuntimeStatus(`运行参数状态：模板 ${name} 预览失败`);
  }
}

async function saveNewsSourceConfig() {
  const raw = document.getElementById("data-news-source-editor").value.trim();
  let sources = [];
  try {
    sources = raw ? JSON.parse(raw) : [];
  } catch (error) {
    setRuntimeStatus(`运行参数状态：新闻源配置 JSON 解析失败：${error.message}`);
    document.getElementById("data-source-output").value = prettyJson({ message: error.message });
    return;
  }
  await request("/api/v1/news/config", {
    method: "PUT",
    body: JSON.stringify({ sources }),
  });
  document.getElementById("data-source-output").value = prettyJson({ ok: true, count: sources.length });
  setRuntimeStatus(`运行参数状态：新闻源配置已保存，共 ${sources.length} 个源`);
}

async function refreshNewsSources(silent = false) {
  if (!silent) {
    setRuntimeStatus("运行参数状态：正在刷新新闻源...");
  }
  try {
    const symbol = getSelectedStrategySymbol();
    const response = await request(`/api/v1/news/refresh?symbol=${encodeURIComponent(symbol)}&force=true`, { method: "POST", timeoutMs: 60000 });
    const summary = response.items.map((item) => `${item.name}:${getStatusLabel(item.status)}/${item.count}`).join(" | ");
    if (!silent) {
      setRuntimeStatus(`运行参数状态：新闻源已刷新 ${summary}`);
    }
    document.getElementById("data-source-output").value = prettyJson(response.items || []);
    newsNextRefreshAt = new Date(Date.now() + NEWS_AUTO_REFRESH_MS);
    renderNextRefreshTime();
    await loadDashboardSnapshot();
    await loadNewsSourceConfig();
  } catch (error) {
    if (!silent) {
      setRuntimeStatus(`运行参数状态：新闻源刷新失败 ${String(error)}`);
    }
    document.getElementById("data-source-output").value = prettyJson({ message: String(error) });
  }
}

async function runBacktest(event) {
  event?.preventDefault();
  try {
    latestBacktestResult = null;
    document.getElementById("backtest-result-output").value = prettyJson({ status: "running", message: "正在运行回测，请稍等..." });
    document.getElementById("backtest-human-summary").textContent = "正在根据当前参数重新计算回测结果，请等待完成。";
    const currentSignature = getCurrentBacktestSignature();
    const response = await request("/api/v1/backtest/run", {
      method: "POST",
      body: JSON.stringify({
        symbol: document.getElementById("backtest-symbol").value.trim(),
        timeframe: document.getElementById("backtest-timeframe").value.trim(),
        strategy_name: document.getElementById("backtest-strategy").value,
        initial_capital: Number(document.getElementById("backtest-capital").value),
        bars: Number(document.getElementById("backtest-bars").value),
      }),
      timeoutMs: 12000,
    });
    document.getElementById("backtest-return").textContent = `${response.total_return_pct ?? "--"}%`;
    document.getElementById("backtest-trades").textContent = String(response.trade_count ?? "--");
    document.getElementById("backtest-winrate").textContent = `${response.win_rate_pct ?? "--"}%`;
    document.getElementById("backtest-drawdown").textContent = `${response.max_drawdown_pct ?? "--"}%`;
    document.getElementById("backtest-sharpe").textContent = `${response.sharpe_ratio ?? "--"}`;
    document.getElementById("backtest-fees").textContent = `${response.fees_paid ?? "--"}`;
    renderBacktestCurve(response.equity_curve || []);
    renderBacktestTrades(response.trades || []);
    document.getElementById("backtest-result-output").value = prettyJson(response);
    document.getElementById("backtest-human-summary").textContent = buildBacktestHumanSummary(response);
    latestBacktestResult = response;
    latestBacktestSignature = currentSignature;
    const nextAutoLabel = `${response.symbol} / ${response.strategy_name} / ${new Date().toLocaleDateString("zh-CN")}`;
    const saveLabelInput = document.getElementById("backtest-save-label");
    const currentLabel = saveLabelInput.value.trim();
    if (!currentLabel || currentLabel === latestBacktestAutoLabel) {
      saveLabelInput.value = nextAutoLabel;
    }
    latestBacktestAutoLabel = nextAutoLabel;
    setRuntimeStatus("运行参数状态：回测已完成，可以查看结果解读后再决定是否保存。");
  } catch (error) {
    renderBacktestCurve([]);
    renderBacktestTrades([]);
    document.getElementById("backtest-result-output").value = prettyJson({ message: String(error) });
    document.getElementById("backtest-human-summary").textContent = "这次回测没有成功跑完，所以暂时还不能判断策略表现。建议先检查交易对、周期、K 线数量和当前策略是否配置正确。";
  }
}

function populateBacktestRunSelects() {
  const options = ['<option value="">请选择</option>']
    .concat(
      backtestRuns.map(
        (item) =>
          `<option value="${item.run_id}">${item.label} | ${item.strategy_name} | ${item.total_return_pct ?? "--"}%</option>`,
      ),
    )
    .join("");
  document.getElementById("backtest-compare-a").innerHTML = options;
  document.getElementById("backtest-compare-b").innerHTML = options;
}

function renderBacktestHistoryList() {
  const container = document.getElementById("backtest-history-list");
  if (!container) {
    return;
  }
  if (!backtestRuns.length) {
    container.innerHTML = '<p class="backtest-history-empty">还没有保存的回测记录。</p>';
    return;
  }
  container.innerHTML = backtestRuns
    .map(
      (item) => `
        <article class="backtest-history-item" data-run-id="${item.run_id}">
          <div class="backtest-history-item-head">
            <strong>${escapeHtml(item.label || item.run_id || "未命名回测")}</strong>
            <span>${escapeHtml(item.saved_at || "--")}</span>
          </div>
          <p>${escapeHtml(item.symbol || "--")} / ${escapeHtml(item.timeframe || "--")} / ${escapeHtml(item.strategy_name || "--")}</p>
          <p>收益 ${formatSignedPercent(item.total_return_pct)} / 回撤 ${formatPercentText(item.max_drawdown_pct)} / 胜率 ${formatPercentText(item.win_rate_pct)}</p>
          <div class="backtest-history-actions">
            <button type="button" data-role="set-a" data-run-id="${item.run_id}">设为 A</button>
            <button type="button" data-role="set-b" data-run-id="${item.run_id}">设为 B</button>
            <button type="button" data-role="delete" data-run-id="${item.run_id}">删除</button>
          </div>
        </article>
      `,
    )
    .join("");
}

async function loadBacktestRuns() {
  try {
    const response = await request("/api/v1/backtest/runs");
    backtestRuns = response.items || [];
    populateBacktestRunSelects();
    renderBacktestHistoryList();
    if (!backtestRuns.length) {
      document.getElementById("backtest-compare-output").value = "当前还没有保存的回测记录。";
      document.getElementById("backtest-compare-summary").textContent = "当前还没有可对比的历史回测。建议先保存两次不同参数或不同周期的回测结果，再回来对比。";
    }
  } catch (error) {
    document.getElementById("backtest-compare-output").value = prettyJson({ message: String(error) });
    document.getElementById("backtest-compare-summary").textContent = "历史回测加载失败，所以暂时还不能生成对比结论。";
  }
}

async function saveCurrentBacktest() {
  if (!latestBacktestResult) {
    document.getElementById("backtest-compare-output").value = prettyJson({ message: "请先运行一次回测，再保存结果。" });
    return;
  }
  if (getCurrentBacktestSignature() !== latestBacktestSignature) {
    document.getElementById("backtest-compare-output").value = prettyJson({
      message: "你已经修改了回测参数，但还没有重新运行回测。请先点“运行回测”，确认右侧结果刷新后再保存。",
    });
    setRuntimeStatus("运行参数状态：检测到参数已变更，请先重新运行回测，再保存这次结果。");
    return;
  }
  try {
    const response = await request("/api/v1/backtest/save", {
      method: "POST",
      body: JSON.stringify({
        label:
          document.getElementById("backtest-save-label").value.trim() ||
          `${latestBacktestResult.symbol} / ${latestBacktestResult.strategy_name}`,
        symbol: latestBacktestResult.symbol,
        timeframe: latestBacktestResult.timeframe,
        strategy_name: latestBacktestResult.strategy_name,
        initial_capital: Number(document.getElementById("backtest-capital").value || latestBacktestResult.initial_capital || 10000),
        result: latestBacktestResult,
      }),
    });
    document.getElementById("backtest-compare-output").value = prettyJson(response.item || {});
    await loadBacktestRuns();
    setRuntimeStatus(`运行参数状态：回测已保存 ${response.item?.run_id || ""}`);
  } catch (error) {
    document.getElementById("backtest-compare-output").value = prettyJson({ message: String(error) });
  }
}

async function compareBacktests() {
  const runA = document.getElementById("backtest-compare-a").value;
  const runB = document.getElementById("backtest-compare-b").value;
  if (!runA || !runB || runA === runB) {
    document.getElementById("backtest-compare-output").value = prettyJson({ message: "请选择两次不同的回测结果进行对比。" });
    document.getElementById("backtest-compare-summary").textContent = "要生成对比结论，需要先选择两次不同的已保存回测。";
    return;
  }
  try {
    const response = await request("/api/v1/backtest/compare", {
      method: "POST",
      body: JSON.stringify({ run_ids: [runA, runB] }),
    });
    document.getElementById("backtest-compare-output").value = prettyJson(response.item || {});
    document.getElementById("backtest-compare-summary").textContent = buildBacktestCompareSummary(response.item || {});
  } catch (error) {
    document.getElementById("backtest-compare-output").value = prettyJson({ message: String(error) });
    document.getElementById("backtest-compare-summary").textContent = "这次对比没有成功完成，所以暂时还不能判断哪次回测更适合继续跟踪。";
  }
}

async function deleteBacktestRun(runId) {
  if (!runId) {
    return;
  }
  const confirmed = window.confirm("确定删除这条历史回测记录吗？删除后就不能再参与对比了。");
  if (!confirmed) {
    return;
  }
  try {
    const response = await request(`/api/v1/backtest/runs/${encodeURIComponent(runId)}`, {
      method: "DELETE",
    });
    document.getElementById("backtest-compare-output").value = prettyJson({
      ok: true,
      message: "历史回测已删除",
      item: response.item || {},
    });
    if (document.getElementById("backtest-compare-a").value === runId) {
      document.getElementById("backtest-compare-a").value = "";
    }
    if (document.getElementById("backtest-compare-b").value === runId) {
      document.getElementById("backtest-compare-b").value = "";
    }
    await loadBacktestRuns();
    setRuntimeStatus("运行参数状态：历史回测已删除");
  } catch (error) {
    document.getElementById("backtest-compare-output").value = prettyJson({ message: String(error) });
  }
}

function buildBacktestHumanSummary(result = {}) {
  const totalReturn = Number(result.total_return_pct ?? 0);
  const maxDrawdown = Number(result.max_drawdown_pct ?? 0);
  const winRate = Number(result.win_rate_pct ?? 0);
  const tradeCount = Number(result.trade_count ?? 0);
  const sharpe = Number(result.sharpe_ratio ?? 0);

  let performanceText = "整体表现一般";
  if (totalReturn >= 10) {
    performanceText = "整体表现较强";
  } else if (totalReturn >= 3) {
    performanceText = "整体有一定正收益";
  } else if (totalReturn > -1) {
    performanceText = "整体接近盈亏平衡";
  } else {
    performanceText = "整体偏弱，暂时不适合直接照搬到实盘";
  }

  let riskText = "回撤压力可接受";
  if (maxDrawdown >= 15) {
    riskText = "回撤偏大，需要优先降风险";
  } else if (maxDrawdown >= 8) {
    riskText = "回撤不低，建议保守观察";
  } else if (maxDrawdown <= 3) {
    riskText = "回撤控制得比较好";
  }

  let consistencyText = "交易样本还不算多";
  if (tradeCount >= 20) {
    consistencyText = "交易样本相对充分";
  } else if (tradeCount >= 8) {
    consistencyText = "交易样本勉强够看";
  } else if (tradeCount <= 2) {
    consistencyText = "交易次数太少，结论参考价值有限";
  }

  let qualityText = "策略质量中性";
  if (sharpe >= 1) {
    qualityText = "收益质量不错";
  } else if (sharpe >= 0.3) {
    qualityText = "收益质量尚可";
  } else if (sharpe < 0) {
    qualityText = "收益质量偏弱，波动和回报不够匹配";
  }

  return `${performanceText}。本次回测收益 ${formatSignedPercent(totalReturn)}，最大回撤 ${formatPercentText(maxDrawdown)}，胜率 ${formatPercentText(winRate)}，共触发 ${tradeCount} 次交易；${riskText}，${consistencyText}，${qualityText}。如果你现在是先筛策略，这版可以继续观察；如果准备自动交易，建议再和别的参数组合做一轮对比。`;
}

function buildBacktestCompareSummary(item = {}) {
  const rows = Array.isArray(item.summary) ? item.summary : [];
  if (rows.length < 2) {
    return "当前对比结果还不够完整，至少需要两次已保存的回测才能得出结论。";
  }
  const normalized = rows.map((row) => ({
    label: row.label || row.run_id || "未命名回测",
    totalReturn: Number(row.total_return_pct ?? 0),
    maxDrawdown: Number(row.max_drawdown_pct ?? 0),
    sharpe: Number(row.sharpe_ratio ?? 0),
  }));
  const bestReturn = [...normalized].sort((a, b) => b.totalReturn - a.totalReturn)[0];
  const safest = [...normalized].sort((a, b) => a.maxDrawdown - b.maxDrawdown)[0];
  const bestSharpe = [...normalized].sort((a, b) => b.sharpe - a.sharpe)[0];

  if (bestReturn.label === safest.label && bestReturn.label === bestSharpe.label) {
    return `这两次里，${bestReturn.label} 最值得优先关注：它同时拿到了更高收益、更低回撤和更好的 Sharpe，整体更像一套可以继续深挖的方案。`;
  }

  return `收益更高的是 ${bestReturn.label}（${formatSignedPercent(bestReturn.totalReturn)}），风险更稳的是 ${safest.label}（最大回撤 ${formatPercentText(safest.maxDrawdown)}），收益质量更好的是 ${bestSharpe.label}（Sharpe ${formatRatioText(bestSharpe.sharpe)}）。如果你现在更重视稳健，优先看 ${safest.label}；如果更重视进攻性，再重点观察 ${bestReturn.label}。`;
}

function formatSignedPercent(value) {
  const number = Number(value ?? 0);
  return `${number >= 0 ? "+" : ""}${number.toFixed(2)}%`;
}

function formatPercentText(value) {
  return `${Number(value ?? 0).toFixed(2)}%`;
}

function formatRatioText(value) {
  return Number(value ?? 0).toFixed(3);
}

function getCurrentBacktestSignature() {
  return JSON.stringify({
    symbol: document.getElementById("backtest-symbol")?.value.trim() || "",
    timeframe: document.getElementById("backtest-timeframe")?.value.trim() || "",
    strategy_name: document.getElementById("backtest-strategy")?.value || "",
    initial_capital: Number(document.getElementById("backtest-capital")?.value || 0),
    bars: Number(document.getElementById("backtest-bars")?.value || 0),
  });
}

async function loadAccountOverview() {
  try {
    const response = await request("/api/v1/account/overview");
    renderAccountOverview(response);
  } catch (error) {
    document.getElementById("account-status-output").value = prettyJson({ message: String(error) });
  }
}

async function loadPositions() {
  try {
    const response = await request("/api/v1/account/positions");
    renderPositions(response);
  } catch (error) {
    document.getElementById("positions-body").innerHTML = `<tr><td colspan="6">${String(error)}</td></tr>`;
  }
}

async function loadOrders() {
  try {
    const response = await request("/api/v1/account/orders");
    renderOrders(response);
  } catch (error) {
    document.getElementById("pending-orders-body").innerHTML = `<tr><td colspan="6">${String(error)}</td></tr>`;
    document.getElementById("history-orders-body").innerHTML = `<tr><td colspan="6">${String(error)}</td></tr>`;
  }
}

function resetOkxDiagnosticsView(message = "正在执行 OKX 网络诊断...") {
  document.getElementById("okx-diagnostics-base").textContent = "--";
  document.getElementById("okx-diagnostics-mode").textContent = "--";
  document.getElementById("okx-diagnostics-public").textContent = "--";
  document.getElementById("okx-diagnostics-private").textContent = "--";
  document.getElementById("okx-diagnostics-output").value = message;
}

function updateOkxDiagnosticsView(item = {}) {
  const publicStatus = item.public?.ok === true ? "可达" : item.public?.ok === false ? "异常" : "--";
  const privateStatus = item.private?.ok === true ? "可达" : item.private?.ok === false ? "异常" : "--";
  document.getElementById("okx-diagnostics-base").textContent = item.rest_base || "--";
  document.getElementById("okx-diagnostics-mode").textContent = item.mode || "--";
  document.getElementById("okx-diagnostics-public").textContent = publicStatus;
  document.getElementById("okx-diagnostics-private").textContent = privateStatus;
  document.getElementById("okx-diagnostics-output").value = prettyJson(item);
}

async function runOkxDiagnostics() {
  resetOkxDiagnosticsView("正在执行 OKX 网络诊断...");
  try {
    const response = await request("/api/v1/runtime-config/okx-diagnostics", {
      method: "POST",
      timeoutMs: 15000,
    });
    updateOkxDiagnosticsView(response.item || {});
  } catch (error) {
    document.getElementById("okx-diagnostics-output").value = prettyJson({ message: String(error) });
  }
}

function renderSelfCheck(item = {}) {
  const checks = item.checks || [];
  const grid = document.getElementById("self-check-grid");
  const output = document.getElementById("self-check-output");
  const status = document.getElementById("self-check-status");
  const summary = document.getElementById("self-check-summary");
  const recommendations = document.getElementById("self-check-recommendations");
  const overall = item.overall || "failed";
  const descriptions = {
    llm: "检查模型账号、模型名和接口地址是否可调用。",
    news: "检查新闻源抓取、缓存和摘要链路是否可用。",
    dashboard: "检查总览页聚合数据是否能生成。",
    backtest: "检查当前策略回测是否能跑通并返回结果。",
    okx: "检查 OKX 公共行情与私有账户链路。",
    prompt_preview: "检查 Prompt 模板是否能生成预览结果。",
  };
  const adviceMap = {
    llm: "去配置页检查模型接入方式、API Key、模型名和 Base URL，再重新测试模型连接。",
    news: "先刷新新闻源，确认原文抓取成功后，再按需对当前源生成 LLM 摘要。",
    dashboard: "先确保当前策略存在，再刷新分析；若还失败，优先查看右侧 detail 里的快照错误。",
    backtest: "去回测页确认当前策略、交易对和初始资金是否合理，再重新运行一次。",
    okx: "先看 OKX 网络诊断结果；如果是 403/拒绝访问，优先处理网络、区域或代理问题。",
    prompt_preview: "去配置页检查 Prompt 模板和模型链路，确认预览任务是否能完成。",
  };
  const failedChecks = checks.filter((check) => check.status !== "normal");
  status.textContent = `系统状态：${getSelfCheckLabel(overall)} / ${item.strategy_name || "--"} / ${item.symbol || "--"} / ${item.timeframe || "--"}`;
  grid.innerHTML = checks
    .map(
      (check) => `
        <div class="mini-stat self-check-card self-check-card-${check.status}">
          <span>${escapeHtml(check.label)}</span>
          <strong>${getSelfCheckLabel(check.status)}</strong>
          <small class="self-check-description">${escapeHtml(descriptions[check.key] || "检查当前模块链路状态。")}</small>
          <small class="status-chip status-chip-${check.status}" title="${escapeHtml(check.message || "")}">${escapeHtml(compactText(check.message || "", 110))}</small>
          <small class="self-check-card-reason">${escapeHtml(adviceMap[check.key] || "先查看 detail 输出，再对照当前模块配置逐项排查。")}</small>
        </div>
      `,
    )
    .join("");
  if (summary) {
    summary.textContent = failedChecks.length
      ? `本次自检发现 ${failedChecks.length} 个需要关注的检查项。建议先处理 ${failedChecks[0].label}，再回头重跑自检确认。`
      : "本次自检各模块都处于正常状态，可以继续做策略验证、回测或部署联调。";
  }
  if (recommendations) {
    recommendations.innerHTML = failedChecks.length
      ? failedChecks
          .slice(0, 4)
          .map((check) => `<li><strong>${escapeHtml(check.label)}</strong>：${escapeHtml(adviceMap[check.key] || "查看 detail 输出继续排查。")} 当前结果：${escapeHtml(compactText(check.message || "无详细信息", 90))}。</li>`)
          .join("")
      : "<li>当前没有阻塞项，优先去策略、回测和自动化页面验证业务链路。</li>";
  }
  output.value = prettyJson(item);
}

async function runSystemSelfCheck() {
  const strategyName =
    document.getElementById("self-check-strategy-select")?.value ||
    document.getElementById("strategy-select")?.value ||
    "sma_crossover";
  document.getElementById("self-check-status").textContent = "系统状态：正在执行自检，将依次检查 LLM、新闻源、看板快照、回测、OKX 和 Prompt 预览...";
  document.getElementById("self-check-output").value = "正在执行自检...\n\n建议先等待左侧状态卡片更新，再查看这里的 detail 输出。";
  if (document.getElementById("self-check-summary")) {
    document.getElementById("self-check-summary").textContent = `正在以 ${strategyName} 为上下文执行自检，请稍候...`;
  }
  try {
    const task = await request(`/api/v1/system/self-check-async?strategy_name=${encodeURIComponent(strategyName)}`, {
      method: "POST",
      timeoutMs: 60000,
    });
    const response = await pollTask(task.item.id, { timeoutMs: 180000 });
    renderSelfCheck(response.item || {});
  } catch (error) {
    const message = String(error);
    const hint = message.includes("请求超时")
      ? "自检请求发起超时，后台任务可能仍在执行。建议稍等 10-20 秒后重试。"
      : message;
    document.getElementById("self-check-status").textContent = `系统状态：失败 / ${hint}`;
    document.getElementById("self-check-output").value = prettyJson({ message: hint });
    if (document.getElementById("self-check-summary")) {
      document.getElementById("self-check-summary").textContent = hint;
    }
  }
}

async function saveRuntimeConfig() {
  const providerMode = document.getElementById("runtime-provider-mode").value;
  const embeddingsEnabled = document.getElementById("runtime-embeddings-enabled").value === "true";
  const embeddingsPreset = document.getElementById("runtime-embeddings-preset").value;
  const embeddingsModel =
    embeddingsEnabled && embeddingsPreset !== "custom"
      ? embeddingsPreset
      : document.getElementById("runtime-embeddings-model").value.trim();
  const payload = {
    app_password: runtimeConfig.app_password || "",
    app_session_ttl_minutes: runtimeConfig.app_session_ttl_minutes ?? 30,
    openai_api_key: document.getElementById("runtime-openai-api-key").value.trim(),
    openai_model:
      embeddingsEnabled && embeddingsPreset !== "custom"
        ? embeddingsPreset
        : document.getElementById("runtime-openai-model").value.trim(),
    llm_model: document.getElementById("runtime-llm-model").value.trim(),
    llm_temperature: Number(document.getElementById("runtime-llm-temperature").value),
    openai_base_url: providerMode === "compatible" ? document.getElementById("runtime-openai-base-url").value.trim() : "",
    embeddings_enabled: document.getElementById("runtime-embeddings-enabled").value === "true",
    embeddings_use_shared_credentials: runtimeConfig.embeddings_use_shared_credentials ?? true,
    embeddings_api_key: runtimeConfig.embeddings_api_key || "",
    embeddings_base_url: runtimeConfig.embeddings_base_url || "",
    embeddings_model: embeddingsModel,
    okx_api_key: document.getElementById("runtime-okx-api-key").value.trim(),
    okx_api_secret: document.getElementById("runtime-okx-api-secret").value.trim(),
    okx_passphrase: document.getElementById("runtime-okx-passphrase").value.trim(),
    okx_rest_base: document.getElementById("runtime-okx-rest-base").value.trim(),
    okx_use_paper: document.getElementById("runtime-okx-use-paper").value === "true",
    okx_adapter: runtimeConfig.okx_adapter || "native",
  };
  await request("/api/v1/runtime-config", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  setRuntimeStatus("运行参数状态：已保存");
}

async function saveRuntimeConfigFromPage(section = "all") {
  const providerMode = document.getElementById("config-provider-mode").value;
  const embeddingsEnabled = document.getElementById("config-embeddings-enabled").value === "true";
  const embeddingsPreset = document.getElementById("config-embeddings-preset").value;
  const embeddingsModel =
    embeddingsEnabled && embeddingsPreset !== "custom"
      ? embeddingsPreset
      : document.getElementById("config-embeddings-model").value.trim();
  const payload = {
    app_password: document.getElementById("config-app-password").value.trim(),
    app_session_ttl_minutes: Number(document.getElementById("config-app-session-ttl").value || 30),
    openai_api_key: document.getElementById("config-openai-api-key").value.trim(),
    openai_model:
      embeddingsEnabled && embeddingsPreset !== "custom"
        ? embeddingsPreset
        : document.getElementById("config-openai-model").value.trim(),
    llm_model: document.getElementById("config-llm-model").value.trim(),
    llm_temperature: Number(document.getElementById("config-llm-temperature").value),
    openai_base_url: providerMode === "compatible" ? document.getElementById("config-openai-base-url").value.trim() : "",
    embeddings_enabled: embeddingsEnabled,
    embeddings_use_shared_credentials: document.getElementById("config-embeddings-use-shared").value !== "false",
    embeddings_api_key: document.getElementById("config-embeddings-api-key").value.trim(),
    embeddings_base_url: document.getElementById("config-embeddings-base-url").value.trim(),
    embeddings_model: embeddingsModel,
    okx_api_key: document.getElementById("config-okx-api-key").value.trim(),
    okx_api_secret: document.getElementById("config-okx-api-secret").value.trim(),
    okx_passphrase: document.getElementById("config-okx-passphrase").value.trim(),
    okx_rest_base: document.getElementById("config-okx-rest-base").value.trim(),
    okx_use_paper: document.getElementById("config-okx-use-paper").value === "true",
    okx_adapter: document.getElementById("config-okx-adapter").value,
  };
  await request("/api/v1/runtime-config", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  runtimeConfig = { ...runtimeConfig, ...payload };
  document.getElementById("config-app-password").value = payload.app_password;
  document.getElementById("config-app-session-ttl").value = payload.app_session_ttl_minutes;
  document.getElementById("runtime-openai-api-key").value = payload.openai_api_key;
  document.getElementById("runtime-openai-model").value = payload.openai_model;
  document.getElementById("runtime-llm-model").value = payload.llm_model;
  document.getElementById("runtime-llm-temperature").value = payload.llm_temperature;
  document.getElementById("runtime-openai-base-url").value = payload.openai_base_url;
  document.getElementById("config-embeddings-use-shared").value = String(payload.embeddings_use_shared_credentials);
  document.getElementById("config-embeddings-api-key").value = payload.embeddings_api_key;
  document.getElementById("config-embeddings-base-url").value = payload.embeddings_base_url;
  document.getElementById("runtime-embeddings-enabled").value = String(payload.embeddings_enabled);
  document.getElementById("runtime-embeddings-preset").value = detectEmbeddingsPreset(payload.embeddings_model);
  document.getElementById("runtime-embeddings-model").value = payload.embeddings_model;
  document.getElementById("runtime-okx-api-key").value = payload.okx_api_key;
  document.getElementById("runtime-okx-api-secret").value = payload.okx_api_secret;
  document.getElementById("runtime-okx-passphrase").value = payload.okx_passphrase;
  document.getElementById("runtime-okx-rest-base").value = payload.okx_rest_base;
  document.getElementById("runtime-okx-use-paper").value = String(payload.okx_use_paper);
  runtimeConfig.okx_adapter = payload.okx_adapter;
  setRuntimeStatus(section === "okx" ? "运行参数状态：OKX 配置已保存" : "运行参数状态：模型与 RAG 配置已保存");
  await loadRuntimeConfig();
}

async function testLlmConnection() {
  setRuntimeStatus("运行参数状态：正在测试模型连接...");
  try {
    const response = await request("/api/v1/runtime-config/test-llm", { method: "POST" });
    setRuntimeStatus(response.ok ? `模型连接成功：${response.message}` : `模型连接失败：${response.message}`);
  } catch (error) {
    setRuntimeStatus(`模型连接失败：${String(error)}`);
  }
}

async function testEmbeddingsConnection() {
  setRuntimeStatus("运行参数状态：正在测试 Embeddings / RAG 连接...");
  try {
    const response = await request("/api/v1/runtime-config/test-embeddings", { method: "POST" });
    setRuntimeStatus(response.ok ? `Embeddings 连接成功：${response.message}` : `Embeddings 连接失败：${response.message}`);
  } catch (error) {
    setRuntimeStatus(`Embeddings 连接失败：${String(error)}`);
  }
}

async function testOkxPublicConnection() {
  setRuntimeStatus("运行参数状态：正在测试 OKX 公共行情连接...");
  resetOkxDiagnosticsView("正在测试 OKX 公共行情连接...");
  try {
    const response = await request("/api/v1/runtime-config/test-okx-public", { method: "POST" });
    updateOkxDiagnosticsView({
      rest_base: runtimeConfig.okx_rest_base,
      mode: runtimeConfig.okx_use_paper ? "paper" : "live",
      public: response,
      private: { ok: null, message: "请单独点击“私有账户”或“执行诊断”检查。" },
    });
    setRuntimeStatus(response.ok ? `OKX 公共行情连接成功：${response.message}` : `OKX 公共行情连接失败：${response.message}`);
  } catch (error) {
    updateOkxDiagnosticsView({
      rest_base: runtimeConfig.okx_rest_base,
      mode: runtimeConfig.okx_use_paper ? "paper" : "live",
      public: { ok: false, message: String(error) },
      private: { ok: null, message: "请单独点击“私有账户”或“执行诊断”检查。" },
    });
    setRuntimeStatus(`OKX 公共行情连接失败：${String(error)}`);
  }
}

async function testOkxPrivateConnection() {
  setRuntimeStatus("运行参数状态：正在测试 OKX 私有账户连接...");
  resetOkxDiagnosticsView("正在测试 OKX 私有账户连接...");
  try {
    const response = await request("/api/v1/runtime-config/test-okx-private", { method: "POST" });
    updateOkxDiagnosticsView({
      rest_base: runtimeConfig.okx_rest_base,
      mode: runtimeConfig.okx_use_paper ? "paper" : "live",
      public: { ok: null, message: "请单独点击“公共行情”或“执行诊断”检查。" },
      private: response,
    });
    setRuntimeStatus(response.ok ? `OKX 私有账户连接成功：${response.message}` : `OKX 私有账户连接失败：${response.message}`);
  } catch (error) {
    updateOkxDiagnosticsView({
      rest_base: runtimeConfig.okx_rest_base,
      mode: runtimeConfig.okx_use_paper ? "paper" : "live",
      public: { ok: null, message: "请单独点击“公共行情”或“执行诊断”检查。" },
      private: { ok: false, message: String(error) },
    });
    setRuntimeStatus(`OKX 私有账户连接失败：${String(error)}`);
  }
}

function updateStrategyView(result, metrics) {
  latestAnalysisResult = result;
  const dynamicMetrics = buildStrategyDrivenMetrics(result, metrics);
  const macd = result.indicators.macd || {};
  const boll = result.indicators.bollinger_bands || {};
  const strategy = dynamicMetrics.strategy;
  renderTaMetrics(result.indicators);
  renderStrategyDiagnostics(result);
  renderTrendChartHeader(result, strategy);
  const runtimePillText = document.getElementById("runtime-mode-pill")?.textContent || "demo";
  document.getElementById("hero-execution-mode").textContent = `${runtimePillText} / ${result.symbol}`;
  document.getElementById("hero-execution-detail").textContent = `${result.strategy_name} / ${dynamicMetrics.timeframe} / ${strategy?.risk_preference || "balanced"}`;
  document.getElementById("current-strategy-name").textContent = result.strategy_name;
  document.getElementById("mini-strategy").textContent = `${result.strategy_name} / ${dynamicMetrics.timeframe}`;
  document.getElementById("mini-signal").textContent = result.signal.signal;
  document.getElementById("mini-yield").textContent = `${dynamicMetrics.yieldRate}%`;
  document.getElementById("hero-confidence").textContent = `${Math.max(10, Math.round(result.agent.confidence * 100))}%`;
  document.getElementById("hero-asset").textContent = `${dynamicMetrics.totalEquity.toFixed(2)} / ${dynamicMetrics.targetCapital.toFixed(2)} USDT`;
  document.getElementById("hero-risk").textContent = result.risk_preview.approved ? "Approved" : "Blocked";
  document.getElementById("strategy-details").innerHTML = `
    <li>交易对：${result.symbol}</li>
    <li>周期：${result.timeframe}</li>
    <li>策略类型：${strategy?.type || "--"} / 风险偏好：${strategy?.risk_preference || "--"}</li>
    <li>目标资金：${dynamicMetrics.targetCapital.toFixed(2)} USDT / 目标周期：${dynamicMetrics.targetHorizonDays} 天</li>
    <li>杠杆 / 保证金模式：${strategy?.config?.leverage || "--"}x / ${strategy?.config?.margin_mode || "--"}</li>
    <li>单次开仓 / 仓位上限：${strategy?.config?.entry_allocation_pct || "--"}% / ${strategy?.config?.max_position_pct || "--"}%</li>
    <li>风险阈值 / 最大回撤：${strategy?.config?.risk_limit_pct || "--"}% / ${strategy?.config?.max_drawdown_limit_pct || "--"}%</li>
    <li>最新价格：${result.last_price}</li>
    <li>信号：${result.signal.signal}</li>
    <li>原因：${result.signal.reason}</li>
    <li>执行说明：${strategy?.execution_notes || "按策略信号与风控结果执行。"}</li>
    <li>SMA：${result.indicators.sma_fast?.toFixed?.(2) ?? result.indicators.sma_fast} / ${result.indicators.sma_slow?.toFixed?.(2) ?? result.indicators.sma_slow}</li>
    <li>EMA：${result.indicators.ema_fast?.toFixed?.(2) ?? result.indicators.ema_fast} / ${result.indicators.ema_slow?.toFixed?.(2) ?? result.indicators.ema_slow}</li>
    <li>RSI：${result.indicators.rsi?.toFixed?.(2) ?? result.indicators.rsi}</li>
    <li>MACD：${macd.line?.toFixed?.(2) ?? macd.line} / ${macd.signal?.toFixed?.(2) ?? macd.signal} / ${macd.histogram?.toFixed?.(2) ?? macd.histogram}</li>
    <li>BOLL：${boll.lower?.toFixed?.(2) ?? boll.lower} / ${boll.middle?.toFixed?.(2) ?? boll.middle} / ${boll.upper?.toFixed?.(2) ?? boll.upper}</li>
    <li>ATR：${result.indicators.atr?.toFixed?.(2) ?? result.indicators.atr}</li>
    <li>Volume MA：${result.indicators.volume_ma?.toFixed?.(2) ?? result.indicators.volume_ma}</li>
    <li>Agent 决策：${result.agent.action || result.agent.decision}</li>
    ${buildStructuredDecisionHtml(result.agent, result.symbol)}
  `;

  const confidence = dynamicMetrics.progress;
  const progressFill = document.getElementById("progress-fill");
  progressFill.classList.remove("progress-fill-loading");
  progressFill.style.width = `${confidence}%`;
  progressFill.textContent = `${confidence}%`;
  document.getElementById("progress-current-capital").textContent = `${dynamicMetrics.totalEquity.toFixed(2)} USDT`;
  document.getElementById("progress-target-capital").textContent = `${dynamicMetrics.targetCapital.toFixed(2)} USDT`;
  document.getElementById("progress-capital-gap").textContent =
    `${dynamicMetrics.capitalGap >= 0 ? "+" : ""}${dynamicMetrics.capitalGap.toFixed(2)} USDT`;
  document.getElementById("progress-days-remaining").textContent = dynamicMetrics.remainingDays;

  document.getElementById("total-asset").textContent = `${dynamicMetrics.totalEquity.toFixed(2)} USDT`;
  document.getElementById("coin-asset").textContent = dynamicMetrics.coinAsset;
  document.getElementById("yield-rate").textContent = `${dynamicMetrics.yieldRate}%`;

  updateAssetTable(dynamicMetrics.positions);
  renderTrendChart(dynamicMetrics.trend, dynamicMetrics.candles);
  renderDailyReport(latestSnapshot?.daily_report, result, metrics);
}

function fillStrategyEditor(strategy) {
  if (!strategy) {
    return;
  }

  clearAiUpdatedFields();
  const config = strategy.config || {};
  document.getElementById("new-strategy-name").value = strategy.name || "";
  document.getElementById("new-strategy-type").value = strategy.type || "custom";
  document.getElementById("new-strategy-risk-preference").value = strategy.risk_preference || "balanced";
  document.getElementById("new-strategy-symbol").value = config.symbol || "BTC-USDT-SWAP";
  document.getElementById("new-strategy-timeframe").value = config.timeframe || "1h";
  document.getElementById("new-strategy-target-capital").value = config.target_capital || 10000;
  document.getElementById("new-strategy-target-horizon").value = config.target_horizon_days || 30;
  document.getElementById("new-strategy-leverage").value = config.leverage || 1;
  document.getElementById("new-strategy-margin-mode").value = config.margin_mode || "cross";
  document.getElementById("new-strategy-fast-period").value = config.fast_period || 7;
  document.getElementById("new-strategy-slow-period").value = config.slow_period || 20;
  document.getElementById("new-strategy-rsi-period").value = config.rsi_period || 14;
  document.getElementById("new-strategy-take-profit").value = config.take_profit_pct || 8;
  document.getElementById("new-strategy-stop-loss").value = config.stop_loss_pct || 3;
  document.getElementById("new-strategy-risk-limit").value = config.risk_limit_pct || 2;
  document.getElementById("new-strategy-entry-allocation").value = config.entry_allocation_pct || 25;
  document.getElementById("new-strategy-max-position").value = config.max_position_pct || 50;
  document.getElementById("new-strategy-max-drawdown").value = config.max_drawdown_limit_pct || 12;
  document.getElementById("new-strategy-description").value = strategy.description || "";
  document.getElementById("new-strategy-execution-notes").value = strategy.execution_notes || "按策略信号与风控结果执行。";
}

function truncateStrategyText(value, maxLength) {
  const normalized = String(value || "").trim();
  if (normalized.length <= maxLength) {
    return { value: normalized, truncated: false };
  }
  return { value: `${normalized.slice(0, maxLength - 1).trimEnd()}…`, truncated: true };
}

function buildStrategyPayload() {
  const descriptionField = document.getElementById("new-strategy-description");
  const executionNotesField = document.getElementById("new-strategy-execution-notes");
  const normalizedDescription = truncateStrategyText(descriptionField.value || "用户创建的自定义策略。", 200);
  const normalizedExecutionNotes = truncateStrategyText(executionNotesField.value || "按策略信号与风控结果执行。", 400);
  descriptionField.value = normalizedDescription.value || "用户创建的自定义策略。";
  executionNotesField.value = normalizedExecutionNotes.value || "按策略信号与风控结果执行。";
  if (normalizedDescription.truncated || normalizedExecutionNotes.truncated) {
    const parts = [];
    if (normalizedDescription.truncated) {
      parts.push("策略说明已自动截断到 200 字以内");
    }
    if (normalizedExecutionNotes.truncated) {
      parts.push("执行说明已自动截断到 400 字以内");
    }
    setStrategyModalStatus(parts.join("；"));
  }
  return {
    name: document.getElementById("new-strategy-name").value.trim(),
    strategy_type: document.getElementById("new-strategy-type").value.trim(),
    risk_preference: document.getElementById("new-strategy-risk-preference").value,
    symbol: document.getElementById("new-strategy-symbol").value.trim(),
    timeframe: document.getElementById("new-strategy-timeframe").value.trim(),
    target_capital: Number(document.getElementById("new-strategy-target-capital").value),
    target_horizon_days: Number(document.getElementById("new-strategy-target-horizon").value),
    leverage: Number(document.getElementById("new-strategy-leverage").value),
    margin_mode: document.getElementById("new-strategy-margin-mode").value,
    fast_period: Number(document.getElementById("new-strategy-fast-period").value),
    slow_period: Number(document.getElementById("new-strategy-slow-period").value),
    rsi_period: Number(document.getElementById("new-strategy-rsi-period").value),
    take_profit_pct: Number(document.getElementById("new-strategy-take-profit").value),
    stop_loss_pct: Number(document.getElementById("new-strategy-stop-loss").value),
    risk_limit_pct: Number(document.getElementById("new-strategy-risk-limit").value),
    entry_allocation_pct: Number(document.getElementById("new-strategy-entry-allocation").value),
    max_position_pct: Number(document.getElementById("new-strategy-max-position").value),
    max_drawdown_limit_pct: Number(document.getElementById("new-strategy-max-drawdown").value),
    description: descriptionField.value.trim() || "用户创建的自定义策略。",
    execution_notes: executionNotesField.value.trim() || "按策略信号与风控结果执行。",
  };
}

function buildStrategySuggestionPayload() {
  return {
    name: document.getElementById("new-strategy-name").value.trim() || "strategy_draft",
    strategy_type: document.getElementById("new-strategy-type").value.trim() || "custom",
    symbol: document.getElementById("new-strategy-symbol").value.trim() || "BTC-USDT-SWAP",
    risk_preference: document.getElementById("new-strategy-risk-preference").value || "balanced",
    target_capital: Number(document.getElementById("new-strategy-target-capital").value || 10000),
    target_horizon_days: Number(document.getElementById("new-strategy-target-horizon").value || 30),
    leverage: Number(document.getElementById("new-strategy-leverage").value || 1),
  };
}

const AI_SUGGESTION_FIELD_MAP = [
  ["new-strategy-type", (item, fallbackPayload) => item.strategy_type || fallbackPayload.strategy_type],
  ["new-strategy-risk-preference", (item, fallbackPayload) => item.risk_preference || fallbackPayload.risk_preference],
  ["new-strategy-symbol", (item, fallbackPayload) => item.symbol || fallbackPayload.symbol || "BTC-USDT-SWAP"],
  ["new-strategy-timeframe", (item) => item.timeframe || "1h"],
  ["new-strategy-target-capital", (item, fallbackPayload) => item.target_capital ?? fallbackPayload.target_capital],
  ["new-strategy-target-horizon", (item, fallbackPayload) => item.target_horizon_days ?? fallbackPayload.target_horizon_days],
  ["new-strategy-leverage", (item) => item.leverage || 1],
  ["new-strategy-margin-mode", (item) => item.margin_mode || "cross"],
  ["new-strategy-fast-period", (item) => item.fast_period || 7],
  ["new-strategy-slow-period", (item) => item.slow_period || 20],
  ["new-strategy-rsi-period", (item) => item.rsi_period || 14],
  ["new-strategy-take-profit", (item) => item.take_profit_pct || 8],
  ["new-strategy-stop-loss", (item) => item.stop_loss_pct || 3],
  ["new-strategy-risk-limit", (item) => item.risk_limit_pct || 2],
  ["new-strategy-entry-allocation", (item) => item.entry_allocation_pct || 25],
  ["new-strategy-max-position", (item) => item.max_position_pct || 50],
  ["new-strategy-max-drawdown", (item) => item.max_drawdown_limit_pct || 12],
  ["new-strategy-description", (item) => item.description || ""],
  ["new-strategy-execution-notes", (item) => item.execution_notes || "按策略信号与风控结果执行。"],
];

function clearAiUpdatedFields() {
  document.querySelectorAll(".ai-updated-field").forEach((element) => {
    element.classList.remove("ai-updated-field");
  });
  document.querySelectorAll(".ai-updated-group").forEach((group) => {
    group.classList.remove("ai-updated-group");
  });
  document.querySelectorAll(".ai-updated-badge").forEach((badge) => {
    badge.remove();
  });
  const summary = document.getElementById("strategy-ai-diff-summary");
  if (summary) {
    summary.textContent = "AI 改动字段：尚未生成建议";
  }
  const diffDetails = document.getElementById("strategy-ai-diff-details");
  if (diffDetails) {
    diffDetails.innerHTML = '<p class="strategy-ai-empty">生成建议后，这里会显示字段变更前后的对比。</p>';
  }
}

function normalizeStrategyFieldValue(value) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value).trim();
}

function markAiUpdatedField(fieldId, beforeValue, afterValue) {
  const field = document.getElementById(fieldId);
  if (!field) {
    return false;
  }
  const beforeNormalized = normalizeStrategyFieldValue(beforeValue);
  const afterNormalized = normalizeStrategyFieldValue(afterValue);
  if (beforeNormalized === afterNormalized) {
    return false;
  }
  field.classList.add("ai-updated-field");
  const group = field.closest(".field-group");
  if (group) {
    group.classList.add("ai-updated-group");
    const label = group.querySelector("label");
    if (label && !label.querySelector(".ai-updated-badge")) {
      const badge = document.createElement("span");
      badge.className = "ai-updated-badge";
      badge.textContent = "AI 已调整";
      label.appendChild(badge);
    }
  }
  return true;
}

function applySuggestedStrategy(item, fallbackPayload) {
  clearAiUpdatedFields();
  const beforeValues = Object.fromEntries(
    AI_SUGGESTION_FIELD_MAP.map(([fieldId]) => [fieldId, document.getElementById(fieldId)?.value ?? ""]),
  );

  AI_SUGGESTION_FIELD_MAP.forEach(([fieldId, resolver]) => {
    const field = document.getElementById(fieldId);
    if (!field) {
      return;
    }
    field.value = resolver(item, fallbackPayload);
  });

  const changedFields = AI_SUGGESTION_FIELD_MAP.filter(([fieldId]) =>
    markAiUpdatedField(fieldId, beforeValues[fieldId], document.getElementById(fieldId)?.value ?? ""),
  );
  const summary = document.getElementById("strategy-ai-diff-summary");
  const diffDetails = document.getElementById("strategy-ai-diff-details");
  if (summary) {
    if (changedFields.length) {
      const labels = changedFields
        .map(([fieldId]) => document.querySelector(`label[for="${fieldId}"]`)?.textContent?.trim() || fieldId)
        .slice(0, 6);
      const suffix = changedFields.length > 6 ? " 等" : "";
      summary.textContent = `AI 改动字段：${changedFields.length} 项，包含 ${labels.join("、")}${suffix}`;
    } else {
      summary.textContent = "AI 改动字段：本次建议没有改变现有参数";
    }
  }
  if (diffDetails) {
    if (!changedFields.length) {
      diffDetails.innerHTML = '<p class="strategy-ai-empty">这次建议没有改动现有字段。</p>';
      return;
    }
    diffDetails.innerHTML = changedFields
      .map(([fieldId]) => {
        const label = document.querySelector(`label[for="${fieldId}"]`)?.textContent?.trim() || fieldId;
        const beforeValue = normalizeStrategyFieldValue(beforeValues[fieldId]) || "未填写";
        const afterValue = normalizeStrategyFieldValue(document.getElementById(fieldId)?.value ?? "") || "未填写";
        return `
          <div class="strategy-ai-diff-item">
            <strong>${label}</strong>
            <div class="strategy-ai-diff-values">
              <span>修改前：<code>${beforeValue}</code></span>
              <span>修改后：<code>${afterValue}</code></span>
            </div>
          </div>
        `;
      })
      .join("");
  }
}

function setStrategyAiBusy(busy, message) {
  window.__strategyAiBusy = busy;
  const overlay = document.getElementById("strategy-ai-overlay");
  const copy = document.getElementById("strategy-ai-overlay-copy");
  const aiButton = document.getElementById("suggest-strategy-ai-btn");
  if (copy && message) {
    copy.textContent = message;
  }
  if (overlay) {
    overlay.classList.toggle("hidden", !busy);
  }
  if (aiButton) {
    aiButton.disabled = busy;
  }
}

async function suggestStrategyDraft() {
  const payload = buildStrategySuggestionPayload();
  try {
    setRuntimeStatus("运行参数状态：正在生成快速建议...");
    const response = await request("/api/v1/strategies/suggest", {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 12000,
    });
    const item = response.item || {};
    applySuggestedStrategy(item, payload);
    setRuntimeStatus("运行参数状态：快速建议已生成（heuristic）");
  } catch (error) {
    setRuntimeStatus(`运行参数状态：快速建议生成失败 ${String(error)}`);
  }
}

async function suggestStrategyDraftAi() {
  const payload = buildStrategySuggestionPayload();
  try {
    setStrategyAiBusy(true, "正在基于当前参数生成策略建议，这通常需要 30-60 秒。完成前请不要关闭弹窗或切换其他操作。");
    setStrategyModalStatus("AI 建议生成中，请稍候...");
    setRuntimeStatus("运行参数状态：正在生成 AI 建议，兼容模型可能需要 30-60 秒...");
    const response = await request("/api/v1/strategies/suggest-ai", {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 60000,
    });
    const item = response.item || {};
    applySuggestedStrategy(item, payload);
    setStrategyModalStatus("AI 建议已生成，已在下方展示本次变更前后的差异。");
    setRuntimeStatus(`运行参数状态：AI 建议已生成（${item.source || "llm"}）`);
  } catch (error) {
    const message = String(error);
    document.getElementById("new-strategy-execution-notes").value = `AI 建议生成失败：${message}`;
    setStrategyModalStatus(`AI 建议生成失败：${message}`);
    if (message.includes("请求超时")) {
      setRuntimeStatus("运行参数状态：AI 建议超时，模型响应较慢或兼容接口延迟较高，请稍后重试。");
    } else {
      setRuntimeStatus(`运行参数状态：AI 建议生成失败 ${message}`);
    }
  } finally {
    setStrategyAiBusy(false, "本次 AI 建议已结束。");
  }
}

async function suggestStrategyDraftLegacy() {
  const payload = {
    name: document.getElementById("new-strategy-name").value.trim() || "strategy_draft",
    strategy_type: document.getElementById("new-strategy-type").value.trim() || "custom",
    risk_preference: document.getElementById("new-strategy-risk-preference").value || "balanced",
    target_capital: Number(document.getElementById("new-strategy-target-capital").value || 10000),
    target_horizon_days: Number(document.getElementById("new-strategy-target-horizon").value || 30),
  };
  try {
    setRuntimeStatus("运行参数状态：正在生成策略建议...");
    const response = await request("/api/v1/strategies/suggest", {
      method: "POST",
      body: JSON.stringify(payload),
      timeoutMs: 15000,
    });
    const item = response.item || {};
    applySuggestedStrategy(item, payload);
    setRuntimeStatus(`运行参数状态：策略建议已生成（${item.source || "fallback"}）`);
  } catch (error) {
    setRuntimeStatus(`运行参数状态：策略建议生成失败 ${String(error)}`);
  }
}

function updateHistoryStrategies(items) {
  const list = document.querySelector(".history-list");
  const listPage = document.getElementById("history-list-page");
  list.innerHTML = "";
  listPage.innerHTML = "";
  items.forEach((item, index) => {
    const li = document.createElement("li");
    li.innerHTML = `<span>${index + 1}、${item.name}</span><span>创建时间：${item.created_at}</span>`;
    list.appendChild(li);
    listPage.appendChild(li.cloneNode(true));
  });
}

async function loadDashboardSnapshot(strategyName = "") {
  try {
    const query = strategyName ? `?strategy_name=${encodeURIComponent(strategyName)}` : "";
    const snapshot = await request(`/api/v1/dashboard/snapshot${query}`, { timeoutMs: 60000 });
    latestSnapshot = snapshot;
    strategyMap = Object.fromEntries(snapshot.historical_strategies.map((item) => [item.name, item]));
    saveCachedStrategies(snapshot.historical_strategies || []);
    tradeRecords = (snapshot.trade_records || []).map((item) => ({
      strategy: item.strategy,
      side: item.side,
      createdAt: item.created_at,
    }));
    updateTradeList();
    updateHistoryStrategies(snapshot.historical_strategies);
    document.getElementById("current-strategy-name").textContent = snapshot.current_strategy.name;
    document.getElementById("strategy-details-page").innerHTML = document.getElementById("strategy-details").innerHTML;
    syncStrategySelect(snapshot.historical_strategies);
    syncStrategySelectPage(snapshot.historical_strategies);
    document.getElementById("strategy-select").value = snapshot.current_strategy.name;
    document.getElementById("strategy-select-page").value = snapshot.current_strategy.name;
    saveSelectedStrategyName(snapshot.current_strategy.name);
    fillStrategyEditor(strategyMap[snapshot.current_strategy.name] || snapshot.historical_strategies[0]);
    syncBacktestInputs(snapshot.current_strategy.name);
    sourceMap = Object.fromEntries(snapshot.sources.map((item) => [item.name, item.items]));
    sourceMetaMap = Object.fromEntries(snapshot.sources.map((item) => [item.name, item.meta || {}]));
    const sourceNames = snapshot.sources.map((item) => item.name);
    activeSourceName = sourceNames.includes(activeSourceName) ? activeSourceName : sourceNames[0] || "";
    if (sourceNames.length) {
      renderSourceChips(sourceNames);
      if (activeSourceName) {
        renderSourceCards(activeSourceName);
      }
    } else {
      await loadNewsSourcesPanel();
    }
    document.getElementById("data-source-output").value = prettyJson(snapshot.sources);
    renderOverviewCapitalPanel(snapshot.current_strategy.name);
    updateStrategyView(snapshot.analysis, snapshot.account_metrics);
    await loadDailySummaryHistory(snapshot.current_strategy.name);
  } catch (error) {
    document.getElementById("strategy-details").innerHTML = `<li>分析失败：${error.message}</li>`;
    document.getElementById("strategy-details-page").innerHTML = `<li>分析失败：${error.message}</li>`;
    document.getElementById("news-current-status").textContent = `当前状态：首页快照失败 / ${error.message}`;
    document.getElementById("news-switch-status").textContent = "切换状态：已切换到新闻源独立加载模式";
    renderOverviewCapitalPanel(strategyName || document.getElementById("strategy-select")?.value || "");
    try {
      await refreshStrategiesOnly(strategyName || document.getElementById("strategy-select")?.value || "");
    } catch (_innerError) {
      // Keep the original dashboard error visible while preserving any list we already had.
    }
    await loadNewsSourcesPanel();
    await loadDailySummaryHistory(strategyName || "");
  }
}

function syncStrategySelect(items, preferredName = "") {
  const select = document.getElementById("strategy-select");
  const names = Array.from(new Set(getOperationalStrategyItems(items).map((item) => item.name).filter(Boolean)));
  const selectedName = preferredName || select.value || names[0] || "";
  select.innerHTML = names
    .map((name) => `<option value="${name}" ${name === selectedName ? "selected" : ""}>${name}</option>`)
    .join("");
  if (names.length) {
    select.value = names.includes(selectedName) ? selectedName : names[0];
    if (select.selectedIndex < 0) {
      select.selectedIndex = 0;
    }
  }
}

function syncStrategySelectPage(items, preferredName = "") {
  const select = document.getElementById("strategy-select-page");
  const selfCheckSelect = document.getElementById("self-check-strategy-select");
  const names = Array.from(new Set(getOperationalStrategyItems(items).map((item) => item.name).filter(Boolean)));
  const selectedName = preferredName || select.value || names[0] || "";
  const html = names
    .map((name) => `<option value="${name}" ${name === selectedName ? "selected" : ""}>${name}</option>`)
    .join("");
  select.innerHTML = html;
  document.getElementById("backtest-strategy").innerHTML = html;
  if (selfCheckSelect) {
    selfCheckSelect.innerHTML = html;
  }
  if (names.length) {
    select.value = names.includes(selectedName) ? selectedName : names[0];
    if (select.selectedIndex < 0) {
      select.selectedIndex = 0;
    }
    const backtestSelect = document.getElementById("backtest-strategy");
    backtestSelect.value = names.includes(selectedName) ? selectedName : names[0];
    if (backtestSelect.selectedIndex < 0) {
      backtestSelect.selectedIndex = 0;
    }
    if (selfCheckSelect) {
      selfCheckSelect.value = names.includes(selectedName) ? selectedName : names[0];
      if (selfCheckSelect.selectedIndex < 0) {
        selfCheckSelect.selectedIndex = 0;
      }
    }
  }
}

async function refreshStrategiesOnly(preferredName = "") {
  let items = [];
  try {
    const response = await request("/api/v1/strategies");
    items = response.items || [];
  } catch (_error) {
    items = [];
  }
  if (!items.length) {
    items = Object.keys(strategyMap).length ? Object.values(strategyMap) : loadCachedStrategies();
  }
  if (!items.length) {
    items = [...DEFAULT_STRATEGIES];
  }
  saveCachedStrategies(items);
  strategyMap = Object.fromEntries(items.map((item) => [item.name, item]));
  updateHistoryStrategies(items);
  const operationalItems = getOperationalStrategyItems(items);
  const selectedName = preferredName || operationalItems[0]?.name || items[0]?.name || "";
  syncStrategySelect(items, selectedName);
  syncStrategySelectPage(items, selectedName);
  if (selectedName) {
    document.getElementById("strategy-select").value = selectedName;
    document.getElementById("strategy-select-page").value = selectedName;
    saveSelectedStrategyName(selectedName);
    document.getElementById("current-strategy-name").textContent = selectedName;
    fillStrategyEditor(strategyMap[selectedName] || items[0]);
    syncBacktestInputs(selectedName);
  }
  return items;
}

async function syncOperationalStrategySelection() {
  const currentSelected =
    document.getElementById("strategy-select")?.value ||
    document.getElementById("strategy-select-page")?.value ||
    "";
  await refreshStrategiesOnly(currentSelected);
  const nextSelected =
    document.getElementById("strategy-select")?.value ||
    document.getElementById("strategy-select-page")?.value ||
    "";
  if (nextSelected) {
    await loadDashboardSnapshot(nextSelected);
  }
}

async function runStrategyAnalysis() {
  try {
    setRuntimeStatus("运行参数状态：正在刷新当前策略分析...");
    setProgressLoadingState();
    const strategyName = document.getElementById("strategy-select").value;
    document.getElementById("strategy-select-page").value = strategyName;
    resetStrategyPresentation(strategyName);
    await loadDashboardSnapshot(strategyName);
    setRuntimeStatus("运行参数状态：策略分析已刷新");
  } catch (error) {
    document.getElementById("strategy-details").innerHTML = `<li>分析失败：${error.message}</li>`;
    document.getElementById("strategy-details-page").innerHTML = `<li>分析失败：${error.message}</li>`;
    setRuntimeStatus(`运行参数状态：策略分析刷新失败 ${error.message}`);
  }
}

async function executeTrade() {
  try {
    const strategyName = document.getElementById("strategy-select").value || "sma_crossover";
    const strategy = getSelectedStrategyRecord(strategyName);
    const symbol = getSelectedStrategySymbol(strategyName);
    const side = latestAnalysisResult?.signal?.signal === "sell" ? "sell" : "buy";
    const riskLimitPct = Number(strategy?.config?.risk_limit_pct || 2);
    const availableEquity = Number(latestAccountOverview?.available_equity || strategy?.config?.target_capital || 10000);
    const leverage = Number(strategy?.config?.leverage || 1);
    const entryAllocationPct = Number(strategy?.config?.entry_allocation_pct || 25);
    const maxPositionPct = Number(strategy?.config?.max_position_pct || 50);
    const lastPrice = Number(latestAnalysisResult?.last_price || latestSnapshot?.analysis?.last_price || 85000);
    const riskBudget = availableEquity * (riskLimitPct / 100);
    const entryBudget = availableEquity * (entryAllocationPct / 100);
    const maxPositionBudget = availableEquity * (maxPositionPct / 100);
    const notional = Math.min(riskBudget, entryBudget, maxPositionBudget) * leverage;
    const size = Math.max(0.001, Number((notional / Math.max(lastPrice, 1)).toFixed(4)));
    setRuntimeStatus(`运行参数状态：正在按 ${strategyName} 策略发起模拟下单，方向 ${side}，数量 ${size}`);
    const result = await request("/api/v1/trade/execute", {
      method: "POST",
      body: JSON.stringify({
        symbol,
        side,
        size,
        strategy_name: strategyName,
      }),
    });

    tradeRecords.unshift({
      side: result.execution.side === "buy" ? "买入" : "卖出",
      strategy: strategyName,
      createdAt: new Date().toLocaleString("zh-CN", { hour12: false }),
    });
    tradeRecords.splice(6);
    updateTradeList();
    loadOrders();
    loadAccountOverview();
    loadPositions();
    setRuntimeStatus(`运行参数状态：模拟下单已提交，策略 ${strategyName}，方向 ${result.execution.side}，数量 ${result.execution.size}`);
  } catch (error) {
    tradeRecords.unshift({
      side: "失败",
      strategy: "risk_control",
      createdAt: error.message,
    });
    tradeRecords.splice(6);
    updateTradeList();
    setRuntimeStatus(`运行参数状态：模拟下单失败 ${error.message}`);
  }
}

async function createStrategy(event) {
  event.preventDefault();
  const payload = buildStrategyPayload();
  const selected = document.getElementById("strategy-select")?.value || "";

  if (!payload.name) {
    setStrategyModalStatus("请先填写策略名称。");
    return;
  }

  if (strategyModalMode === "edit" && payload.name === selected) {
    setStrategyModalStatus("当前是编辑模式；如果要新增副本，请先改一个新的策略名称。");
    return;
  }

  try {
    setStrategyModalStatus(`正在创建策略 ${payload.name}...`);
    const response = await request("/api/v1/strategies", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    const created = response.item || payload;
    const items = await refreshStrategiesOnly(created.name);
    if (!items.some((item) => item.name === created.name)) {
      throw new Error(`策略 ${created.name} 已提交，但未出现在策略列表里`);
    }
    document.getElementById("strategy-select").value = created.name;
    document.getElementById("strategy-select-page").value = created.name;
    const selfCheckSelect = document.getElementById("self-check-strategy-select");
    if (selfCheckSelect) {
      selfCheckSelect.value = created.name;
    }
    setStrategyModalStatus(`策略 ${created.name} 已创建成功，正在切换并刷新分析...`);
    document.getElementById("create-strategy-form").reset();
    document.getElementById("new-strategy-type").value = "custom";
    document.getElementById("new-strategy-risk-preference").value = "balanced";
    document.getElementById("new-strategy-symbol").value = getSelectedStrategySymbol() || "BTC-USDT-SWAP";
    document.getElementById("new-strategy-timeframe").value = "1h";
    document.getElementById("new-strategy-target-capital").value = "10000";
    document.getElementById("new-strategy-target-horizon").value = "30";
    document.getElementById("new-strategy-leverage").value = "1";
    document.getElementById("new-strategy-margin-mode").value = "cross";
    document.getElementById("new-strategy-fast-period").value = "7";
    document.getElementById("new-strategy-slow-period").value = "20";
    document.getElementById("new-strategy-rsi-period").value = "14";
    document.getElementById("new-strategy-take-profit").value = "8";
    document.getElementById("new-strategy-stop-loss").value = "3";
    document.getElementById("new-strategy-risk-limit").value = "2";
    document.getElementById("new-strategy-entry-allocation").value = "25";
    document.getElementById("new-strategy-max-position").value = "50";
    document.getElementById("new-strategy-max-drawdown").value = "12";
    setRuntimeStatus(`运行参数状态：策略 ${created.name} 已保存，正在刷新分析...`);
    setStrategyModalStatus(`策略 ${created.name} 已创建，正在后台刷新分析...`);
    closeStrategyModal();
    resetStrategyPresentation(created.name);
    loadDashboardSnapshot(created.name)
      .then(() => {
        setRuntimeStatus(`运行参数状态：策略 ${created.name} 已创建并刷新成功`);
      })
      .catch((error) => {
        setRuntimeStatus(`运行参数状态：策略已保存，但分析刷新失败 ${error.message}`);
      });
  } catch (error) {
    setStrategyModalStatus(`创建策略失败：${error.message}`);
    document.getElementById("strategy-details").innerHTML = `<li>创建策略失败：${error.message}</li>`;
  }
}

async function saveCurrentStrategy() {
  const selected = document.getElementById("strategy-select").value;
  const payload = buildStrategyPayload();

  try {
    setStrategyModalStatus(`正在保存策略 ${selected}...`);
    await request(`/api/v1/strategies/${encodeURIComponent(selected)}`, {
      method: "PUT",
      body: JSON.stringify({
        strategy_type: payload.strategy_type,
        risk_preference: payload.risk_preference,
        description: payload.description,
        execution_notes: payload.execution_notes,
        symbol: payload.symbol,
        timeframe: payload.timeframe,
        target_capital: payload.target_capital,
        target_horizon_days: payload.target_horizon_days,
        leverage: payload.leverage,
        margin_mode: payload.margin_mode,
        fast_period: payload.fast_period,
        slow_period: payload.slow_period,
        rsi_period: payload.rsi_period,
        take_profit_pct: payload.take_profit_pct,
        stop_loss_pct: payload.stop_loss_pct,
        risk_limit_pct: payload.risk_limit_pct,
        entry_allocation_pct: payload.entry_allocation_pct,
        max_position_pct: payload.max_position_pct,
        max_drawdown_limit_pct: payload.max_drawdown_limit_pct,
      }),
    });
    const items = await refreshStrategiesOnly(selected);
    if (!items.some((item) => item.name === selected)) {
      throw new Error(`策略 ${selected} 已提交，但刷新后未找到`);
    }
    setStrategyModalStatus(`策略 ${selected} 已保存，正在后台刷新分析...`);
    closeStrategyModal();
    setRuntimeStatus(`运行参数状态：策略 ${selected} 已保存，正在刷新分析...`);
    resetStrategyPresentation(selected);
    loadDashboardSnapshot(selected)
      .then(() => {
        document.getElementById("strategy-select").value = selected;
        setRuntimeStatus(`运行参数状态：策略 ${selected} 已保存并刷新成功`);
      })
      .catch((error) => {
        setRuntimeStatus(`运行参数状态：策略已保存，但分析刷新失败 ${error.message}`);
      });
  } catch (error) {
    setStrategyModalStatus(`保存策略失败：${error.message}`);
    document.getElementById("strategy-details").innerHTML = `<li>保存策略失败：${error.message}</li>`;
  }
}

bindClick("analyze-btn", runStrategyAnalysis);
bindClick("analyze-btn-page", runStrategyAnalysis);
bindClick("trade-btn", executeTrade);
bindClick("trade-btn-page", executeTrade);
bindClick("refresh-account-btn", loadAccountOverview);
bindClick("refresh-positions-btn", loadPositions);
bindClick("refresh-orders-btn", loadOrders);
bindChange("strategy-select", (event) => {
  saveSelectedStrategyName(event.target.value);
  runStrategyAnalysis();
});
bindChange("strategy-select-page", (event) => {
  document.getElementById("strategy-select").value = event.target.value;
  saveSelectedStrategyName(event.target.value);
  const selfCheckSelect = document.getElementById("self-check-strategy-select");
  if (selfCheckSelect) {
    selfCheckSelect.value = event.target.value;
  }
  runStrategyAnalysis();
});
bindChange("self-check-strategy-select", (event) => {
  const strategySelect = document.getElementById("strategy-select");
  const strategySelectPage = document.getElementById("strategy-select-page");
  if (strategySelect) {
    strategySelect.value = event.target.value;
  }
  if (strategySelectPage) {
    strategySelectPage.value = event.target.value;
  }
  saveSelectedStrategyName(event.target.value);
});
bindChange("backtest-strategy", (event) => {
  syncBacktestInputs(event.target.value);
});
document.getElementById("create-strategy-form").addEventListener("submit", createStrategy);
bindClick("save-strategy-btn", saveCurrentStrategy);
document.getElementById("backtest-form").addEventListener("submit", runBacktest);
bindClick("save-backtest-btn", saveCurrentBacktest);
bindClick("refresh-backtest-runs-btn", loadBacktestRuns);
bindClick("compare-backtests-btn", compareBacktests);
bindClick("export-report-btn", exportDailyReport);
bindClick("daily-report-tab-report", () => setDailyReportTab("report"));
bindClick("daily-report-tab-summary", () => setDailyReportTab("summary"));
bindClick("open-prompt-modal-btn", async () => {
  await loadRuntimeConfig();
  await loadNewsSourceConfig();
  await loadPromptTemplates();
  document.getElementById("prompt-preview-output").value = "";
  openPromptModal();
});
bindClick("open-prompt-modal-btn-page", () => document.getElementById("open-prompt-modal-btn").click());
bindClick("open-prompt-modal-btn-data", () => document.getElementById("open-prompt-modal-btn").click());
bindClick("close-prompt-modal-btn", closePromptModal);
bindClick("close-guide-modal-btn", closeGuideModal);
bindChange("prompt-template-select", async (event) => {
  await loadPromptTemplate(event.target.value);
});
bindClick("save-prompt-template-btn", savePromptTemplate);
bindClick("preview-prompt-template-btn", previewPromptTemplate);
bindClick("save-news-config-btn", saveNewsSourceConfig);
bindClick("refresh-news-btn", refreshNewsSources);
bindClick("save-runtime-config-btn", saveRuntimeConfig);
bindClick("test-llm-connection-btn", testLlmConnection);
bindClick("test-okx-public-connection-btn", testOkxPublicConnection);
bindClick("test-okx-private-connection-btn", testOkxPrivateConnection);
bindClick("run-okx-diagnostics-btn", runOkxDiagnostics);
bindChange("runtime-provider-mode", applyRuntimeModeVisibility);
bindChange("runtime-embeddings-enabled", applyRuntimeModeVisibility);
bindChange("runtime-embeddings-preset", () => {
  const preset = document.getElementById("runtime-embeddings-preset").value;
  if (preset !== "custom") {
    document.getElementById("runtime-embeddings-model").value = preset;
    document.getElementById("runtime-openai-model").value = preset;
  }
  applyRuntimeModeVisibility();
});
bindChange("config-provider-mode", applyConfigPageVisibility);
bindChange("config-embeddings-enabled", applyConfigPageVisibility);
bindChange("config-embeddings-use-shared", applyConfigPageVisibility);
bindChange("config-embeddings-preset", () => {
  const preset = document.getElementById("config-embeddings-preset").value;
  if (preset !== "custom") {
    document.getElementById("config-embeddings-model").value = preset;
    document.getElementById("config-openai-model").value = preset;
  }
  applyConfigPageVisibility();
});
bindChange("config-prompt-template-select", async (event) => {
  await loadPromptTemplate(event.target.value);
});
bindClick("save-runtime-config-page-btn", async () => {
  await saveRuntimeConfigFromPage("llm");
});
bindClick("save-okx-config-page-btn", async () => {
  await saveRuntimeConfigFromPage("okx");
});
bindClick("test-llm-connection-page-btn", async () => {
  await saveRuntimeConfigFromPage("llm");
  await testLlmConnection();
});
bindClick("test-embeddings-connection-page-btn", async () => {
  await saveRuntimeConfigFromPage("llm");
  await testEmbeddingsConnection();
});
bindClick("test-okx-public-page-btn", async () => {
  await saveRuntimeConfigFromPage("okx");
  await testOkxPublicConnection();
});
bindClick("test-okx-private-page-btn", async () => {
  await saveRuntimeConfigFromPage("okx");
  await testOkxPrivateConnection();
});
bindClick("save-prompt-template-page-btn", savePromptTemplateFromPage);
bindClick("preview-prompt-template-page-btn", previewPromptTemplateFromPage);
bindClick("save-news-config-data-btn", saveNewsSourceConfig);
bindClick("refresh-news-btn-data", refreshNewsSources);
bindClick("summarize-news-btn-data", summarizeActiveNewsSource);
bindClick("save-automation-config-btn", saveAutomationConfig);
bindClick("test-feishu-btn", testFeishuPush);
bindClick("run-auto-trade-now-btn", runAutoTradeNow);
bindClick("run-daily-summary-now-btn", runDailySummaryNow);
bindClick("run-self-check-btn", runSystemSelfCheck);
bindClick("open-create-modal-btn", () => {
  clearAiUpdatedFields();
  document.getElementById("create-strategy-form").reset();
  document.getElementById("new-strategy-type").value = "custom";
  document.getElementById("new-strategy-risk-preference").value = "balanced";
  document.getElementById("new-strategy-symbol").value = getSelectedStrategySymbol() || "BTC-USDT-SWAP";
  document.getElementById("new-strategy-timeframe").value = "1h";
  document.getElementById("new-strategy-target-capital").value = "10000";
  document.getElementById("new-strategy-target-horizon").value = "30";
  document.getElementById("new-strategy-leverage").value = "1";
  document.getElementById("new-strategy-margin-mode").value = "cross";
  document.getElementById("new-strategy-fast-period").value = "7";
  document.getElementById("new-strategy-slow-period").value = "20";
  document.getElementById("new-strategy-rsi-period").value = "14";
  document.getElementById("new-strategy-take-profit").value = "8";
  document.getElementById("new-strategy-stop-loss").value = "3";
  document.getElementById("new-strategy-risk-limit").value = "2";
  document.getElementById("new-strategy-entry-allocation").value = "25";
  document.getElementById("new-strategy-max-position").value = "50";
  document.getElementById("new-strategy-max-drawdown").value = "12";
  document.getElementById("new-strategy-description").value = "用户创建的自定义策略。";
  document.getElementById("new-strategy-execution-notes").value = "按策略信号与风控结果执行。";
  setStrategyModalStatus("填写策略参数后，点击“新增策略”即可保存；成功后会自动切换到新策略。");
  openStrategyModal("create");
});
bindClick("use-available-capital-btn", () => {
  const availableText = document.getElementById("account-available-equity")?.textContent || "";
  const parsed = Number(String(availableText).replace(/[^0-9.]/g, ""));
  if (parsed > 0) {
    document.getElementById("new-strategy-target-capital").value = parsed.toFixed(2);
    setRuntimeStatus(`运行参数状态：已带入当前账户可用资金 ${parsed.toFixed(2)} USDT`);
  } else {
    setRuntimeStatus("运行参数状态：当前没有可用账户资金可带入，请先刷新账户页。");
  }
});
bindClick("apply-template-conservative-btn", () => applyStrategyTemplate("conservative"));
bindClick("apply-template-balanced-btn", () => applyStrategyTemplate("balanced"));
bindClick("apply-template-aggressive-btn", () => applyStrategyTemplate("aggressive"));
bindClick("suggest-strategy-btn", suggestStrategyDraft);
bindClick("suggest-strategy-ai-btn", suggestStrategyDraftAi);
bindClick("open-create-modal-btn-page", () => document.getElementById("open-create-modal-btn").click());
bindClick("open-edit-modal-btn", () => {
  clearAiUpdatedFields();
  const selected = document.getElementById("strategy-select").value;
  fillStrategyEditor(strategyMap[selected]);
  setStrategyModalStatus("修改当前策略后，点击“保存当前策略”即可覆盖更新。");
  openStrategyModal("edit");
});
bindClick("open-edit-modal-btn-page", () => document.getElementById("open-edit-modal-btn").click());
bindClick("close-strategy-modal-btn", closeStrategyModal);
bindClick("open-tool-hub-btn", openToolHubModal);

document.getElementById("backtest-history-list")?.addEventListener("click", (event) => {
  const target = event.target instanceof HTMLElement ? event.target.closest("button[data-role]") : null;
  if (!target) {
    return;
  }
  const runId = target.getAttribute("data-run-id") || "";
  const role = target.getAttribute("data-role");
  if (role === "set-a") {
    document.getElementById("backtest-compare-a").value = runId;
    setRuntimeStatus("运行参数状态：已将历史回测设为对比项 A");
  } else if (role === "set-b") {
    document.getElementById("backtest-compare-b").value = runId;
    setRuntimeStatus("运行参数状态：已将历史回测设为对比项 B");
  } else if (role === "delete") {
    deleteBacktestRun(runId);
  }
});
document.getElementById("strategy-modal-backdrop").addEventListener("click", (event) => {
  if (event.target.id === "strategy-modal-backdrop") {
    closeStrategyModal();
  }
});
document.getElementById("guide-modal-backdrop").addEventListener("click", (event) => {
  if (event.target.id === "guide-modal-backdrop") {
    closeGuideModal();
  }
});
document.getElementById("prompt-modal-backdrop").addEventListener("click", (event) => {
  if (event.target.id === "prompt-modal-backdrop") {
    closePromptModal();
  }
});

document.getElementById("guide-modal-content").addEventListener("click", (event) => {
  const button = event.target.closest("[data-guide-key], [data-tool-url], [data-tool-action]");
  if (!button) {
    return;
  }
  if (button.dataset.toolUrl) {
    window.open(button.dataset.toolUrl, "_blank", "noopener,noreferrer");
    closeGuideModal();
    return;
  }
  if (button.dataset.toolAction === "open-guide-chooser") {
    document.getElementById("guide-modal-title").textContent = "操作指南";
    renderGuideHubChooser();
    return;
  }
  openGuideModal(button.dataset.guideKey);
});

bindClick("guide-modal-open-view-btn", () => {
  const viewName = document.getElementById("guide-modal-open-view-btn").dataset.targetView || "overview";
  closeGuideModal();
  switchView(viewName);
  document.querySelector(`.nav-tab[data-view="${viewName}"]`)?.click();
});

document.getElementById("source-row").addEventListener("click", (event) => {
  const button = event.target.closest(".source-chip");
  if (!button) {
    return;
  }
  button.classList.add("syncing");
  window.setTimeout(() => button.classList.remove("syncing"), 260);
  document.querySelectorAll(".source-chip").forEach((item) => item.classList.remove("active"));
  button.classList.add("active");
  renderSourceCards(button.dataset.source);
});
document.getElementById("source-row-page").addEventListener("click", (event) => {
  const button = event.target.closest(".source-chip");
  if (!button) {
    return;
  }
  button.classList.add("syncing");
  window.setTimeout(() => button.classList.remove("syncing"), 260);
  document.querySelectorAll(".source-chip").forEach((item) => item.classList.remove("active"));
  document.querySelectorAll(`#source-row [data-source="${button.dataset.source}"], #source-row-page [data-source="${button.dataset.source}"]`).forEach((item) => {
    item.classList.add("active");
  });
  renderSourceCards(button.dataset.source);
});
document.querySelectorAll(".nav-tab").forEach((button) => {
  button.addEventListener("click", () => {
    switchView(button.dataset.view);
    if (button.dataset.view === "config") {
      loadRuntimeConfig();
      loadPromptTemplates();
      loadNewsSourceConfig();
    }
    if (button.dataset.view === "data") {
      loadNewsSourceConfig();
    }
    if (button.dataset.view === "health") {
      runSystemSelfCheck();
    }
    if (button.dataset.view === "account") {
      loadAccountOverview();
      loadPositions();
    }
    if (button.dataset.view === "orders") {
      loadOrders();
    }
    if (button.dataset.view === "backtest") {
      syncBacktestInputs(document.getElementById("strategy-select").value);
      loadBacktestRuns();
    }
  });
});

updateTradeList();
setDailyReportTab("report");
async function initializeApp() {
  const authorized = await checkAuthStatus();
  if (!authorized) {
    return;
  }
  await initializeSecuredApp();
}

async function initializeSecuredApp() {
  const cachedStrategies = loadCachedStrategies();
  const preferredStrategyName = loadSelectedStrategyName();
  await loadRuntimeConfig();
  strategyMap = Object.fromEntries(cachedStrategies.map((item) => [item.name, item]));
  syncStrategySelect(cachedStrategies, preferredStrategyName || cachedStrategies[0]?.name || "sma_crossover");
  syncStrategySelectPage(cachedStrategies, preferredStrategyName || cachedStrategies[0]?.name || "sma_crossover");
  try {
    await refreshStrategiesOnly(preferredStrategyName);
  } catch (error) {
    setRuntimeStatus(`运行参数状态：策略列表初始化失败 ${error.message}`);
  }
  await Promise.allSettled([
    loadNewsSourceConfig(),
    loadPromptTemplates(),
    loadStrategyTemplates(),
    loadAccountOverview(),
    loadPositions(),
    loadOrders(),
    loadBacktestRuns(),
  ]);
  scheduleNewsAutoRefresh();
  await loadDashboardSnapshot(loadSelectedStrategyName() || document.getElementById("strategy-select")?.value || "");
}

bindClick("auth-login-btn", () => {
  loginToApp().catch((error) => showAuthOverlay(String(error)));
});
document.getElementById("auth-password-input").addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    loginToApp().catch((error) => showAuthOverlay(String(error)));
  }
});

initializeApp();
