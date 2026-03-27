from fastapi import APIRouter

from app.api.endpoints import account, auth, automation, backtest, dashboard, market, news, prompts, runtime_config, strategy, strategy_catalog, system, tasks, trade

router = APIRouter()
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(system.router, prefix="/system", tags=["system"])
router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
router.include_router(account.router, prefix="/account", tags=["account"])
router.include_router(news.router, prefix="/news", tags=["news"])
router.include_router(market.router, prefix="/market", tags=["market"])
router.include_router(strategy.router, prefix="/strategy", tags=["strategy"])
router.include_router(strategy_catalog.router, prefix="/strategies", tags=["strategies"])
router.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
router.include_router(runtime_config.router, prefix="/runtime-config", tags=["runtime-config"])
router.include_router(automation.router, prefix="/automation", tags=["automation"])
router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
router.include_router(backtest.router, prefix="/backtest", tags=["backtest"])
router.include_router(trade.router, prefix="/trade", tags=["trade"])
