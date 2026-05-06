from __future__ import annotations

from abc import ABC, abstractmethod


class RAGProvider(ABC):
    """RAG检索接口"""

    @abstractmethod
    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """检索相关文档

        Args:
            query: 查询文本
            top_k: 返回top-k个结果

        Returns:
            检索结果列表，每个结果包含:
            - content: 文档内容
            - score: 相关性分数
            - metadata: 元数据
        """
        pass


class StubRAGProvider(RAGProvider):
    """Stub RAG Provider - 暂时返回空结果"""

    def retrieve(self, query: str, top_k: int = 5) -> list[dict]:
        """暂时返回空结果，等待后续实现"""
        return []
