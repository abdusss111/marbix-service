from pydantic import BaseModel


class AdminStatsResponse(BaseModel):
    total_users: int
    total_strategies: int
    successful_strategies: int
    failed_strategies: int
    processing_strategies: int