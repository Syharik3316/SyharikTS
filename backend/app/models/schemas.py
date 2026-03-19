from pydantic import BaseModel, Field


class GenerateResponse(BaseModel):
    code: str = Field(..., description="Generated TypeScript code.")


class ErrorResponse(BaseModel):
    detail: str


class InferSchemaResponse(BaseModel):
    schema: str = Field(..., description="Inferred JSON schema example as string.")

