from __future__ import annotations

from queryweaver.models import Route

SQL_SIGNALS = {
    "average", "count", "database", "how many", "revenue", "sales", "sum", "table",
    "数据库", "多少", "平均", "统计", "销售额", "表", "总计",
}


def route_question(question: str) -> Route:
    """Transparent baseline router; later milestones compare it with a model router."""
    normalized = question.casefold()
    return Route.SQL if any(signal in normalized for signal in SQL_SIGNALS) else Route.DOCUMENTS
