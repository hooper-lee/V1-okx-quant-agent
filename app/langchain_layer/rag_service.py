class RAGCoordinator:
    def __init__(self, news_service, experience_store) -> None:
        self.news_service = news_service
        self.experience_store = experience_store

    def retrieve_context(self, symbol: str) -> dict:
        return {
            "news": self.news_service.search(symbol),
            "experience": self.experience_store.search(f"{symbol} trend risk"),
        }
