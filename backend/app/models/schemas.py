from pydantic import BaseModel, Field


class GenerateResponse(BaseModel):
    code: str = Field(..., description="Generated TypeScript code.")


class ErrorResponse(BaseModel):
    detail: str


class InferSchemaResponse(BaseModel):
    schema: str = Field(..., description="Inferred JSON schema example as string.")


class TotalGenerationsStatsResponse(BaseModel):
    total_generations_all_time: int = Field(..., ge=0)


class ObservabilitySummaryResponse(BaseModel):
    langfuse_enabled: bool
    langfuse_host: str
    langfuse_env: str
    langfuse_release: str
    llm_provider: str
    database_configured: bool
    generation_cache_total_requests: int = Field(..., ge=0)
    generation_cache_hit_count: int = Field(..., ge=0)
    generation_cache_hit_ratio: float = Field(..., ge=0.0, le=1.0)
    generation_cache_saved_total_tokens_estimate: int = Field(..., ge=0)

