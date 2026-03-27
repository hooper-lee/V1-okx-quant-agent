class MemoryService:
    def __init__(self, experience_store) -> None:
        self.experience_store = experience_store

    def recall(self, symbol: str) -> list[dict]:
        return self.experience_store.search(symbol) or self.experience_store.search("trend risk")

    def write(self, topic: str, content: str) -> None:
        self.experience_store.add_memory(topic=topic, content=content)

    def list_by_topic_prefix(self, prefix: str, limit: int = 10) -> list[dict]:
        return self.experience_store.list_by_topic_prefix(prefix=prefix, limit=limit)
