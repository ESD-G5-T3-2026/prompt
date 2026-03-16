from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def _trim_non_blank(value: str, field_name: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError(f'{field_name} must be non-blank')
    return trimmed


class PromptCreate(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    template: str = Field(min_length=1)
    modelName: str = Field(min_length=1)
    temperature: float = Field(ge=0.0, le=2.0)
    maxTokens: int = Field(gt=0)

    @field_validator('id')
    @classmethod
    def validate_id(cls, value: str) -> str:
        return _trim_non_blank(value, 'id')

    @field_validator('name')
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _trim_non_blank(value, 'name')

    @field_validator('template')
    @classmethod
    def validate_template(cls, value: str) -> str:
        return _trim_non_blank(value, 'template')

    @field_validator('modelName')
    @classmethod
    def validate_model_name(cls, value: str) -> str:
        return _trim_non_blank(value, 'modelName')


class PromptPatch(BaseModel):
    name: Optional[str] = None
    template: Optional[str] = None
    modelName: Optional[str] = None
    temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    maxTokens: Optional[int] = Field(default=None, gt=0)

    @field_validator('name', 'template', 'modelName')
    @classmethod
    def optional_trim_non_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        trimmed = value.strip()
        if not trimmed:
            raise ValueError('must be non-blank')
        return trimmed


class PromptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    template: str
    modelName: str
    temperature: float
    maxTokens: int
    createdAt: str
    updatedAt: str


SUPABASE_URL = os.getenv('SUPABASE_URL', '').strip()
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '').strip()
PROMPT_TABLE = os.getenv('PROMPT_TABLE', 'prompt_configs').strip() or 'prompt_configs'
REQUEST_TIMEOUT_MS = int(os.getenv('PROMPT_TIMEOUT_MS', '10000'))

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError('SUPABASE_URL and SUPABASE_KEY are required for prompt service.')

client = httpx.Client(
    base_url=SUPABASE_URL.rstrip('/'),
    timeout=REQUEST_TIMEOUT_MS / 1000.0,
    headers={
        'apikey': SUPABASE_KEY,
        'Authorization': f'Bearer {SUPABASE_KEY}',
        'Content-Type': 'application/json',
    },
)

app = FastAPI(title='prompt', version='1.0.0')


def _table_path() -> str:
    return f'/rest/v1/{PROMPT_TABLE}'


def _row_to_response(row: Dict[str, Any]) -> PromptResponse:
    return PromptResponse(
        id=str(row['id']),
        name=str(row.get('name') or ''),
        template=str(row.get('template') or ''),
        modelName=str(row.get('model_name') or ''),
        temperature=float(row.get('temperature') or 0.0),
        maxTokens=int(row.get('max_tokens') or 0),
        createdAt=str(row.get('created_at') or ''),
        updatedAt=str(row.get('updated_at') or ''),
    )


def _fetch_prompt_row(prompt_id: str) -> Dict[str, Any] | None:
    try:
        response = client.get(_table_path(), params={'select': '*', 'id': f'eq.{prompt_id}'})
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f'Failed to read prompt from Supabase: {exc}') from exc
    rows = response.json()
    if not isinstance(rows, list) or not rows:
        return None
    return rows[0]


@app.get('/health')
def health() -> dict:
    return {'status': 'ok', 'service': 'prompt'}


@app.post('/api/v1/prompts', response_model=PromptResponse, status_code=201)
def create_prompt(payload: PromptCreate) -> PromptResponse:
    now = utc_now()
    insert_row = {
        'id': payload.id,
        'name': payload.name,
        'template': payload.template,
        'model_name': payload.modelName,
        'temperature': payload.temperature,
        'max_tokens': payload.maxTokens,
        'created_at': now,
        'updated_at': now,
    }
    try:
        response = client.post(_table_path(), headers={'Prefer': 'return=representation'}, json=insert_row)
        if response.status_code == 409:
            raise HTTPException(status_code=409, detail=f"Prompt with id '{payload.id}' already exists")
        response.raise_for_status()
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f'Failed to create prompt in Supabase: {exc}') from exc

    rows = response.json()
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=502, detail='Supabase returned an invalid create response')
    return _row_to_response(rows[0])


@app.get('/api/v1/prompts', response_model=List[PromptResponse])
def list_prompts() -> List[PromptResponse]:
    try:
        response = client.get(_table_path(), params={'select': '*', 'order': 'updated_at.desc,id.asc'})
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f'Failed to list prompts from Supabase: {exc}') from exc
    rows = response.json()
    if not isinstance(rows, list):
        raise HTTPException(status_code=502, detail='Supabase returned an invalid list response')
    return [_row_to_response(row) for row in rows]


@app.get('/api/v1/prompts/{prompt_id}', response_model=PromptResponse)
def get_prompt(prompt_id: str) -> PromptResponse:
    prompt_id = _trim_non_blank(prompt_id, 'prompt_id')
    row = _fetch_prompt_row(prompt_id)
    if row is None:
        raise HTTPException(status_code=404, detail='Prompt not found')
    return _row_to_response(row)


@app.patch('/api/v1/prompts/{prompt_id}', response_model=PromptResponse)
def patch_prompt(prompt_id: str, payload: PromptPatch) -> PromptResponse:
    prompt_id = _trim_non_blank(prompt_id, 'prompt_id')
    if payload.model_dump(exclude_none=True) == {}:
        raise HTTPException(status_code=400, detail='At least one field must be supplied')

    current = _fetch_prompt_row(prompt_id)
    if current is None:
        raise HTTPException(status_code=404, detail='Prompt not found')

    patch_row = {
        'updated_at': utc_now(),
    }
    if payload.name is not None:
        patch_row['name'] = payload.name
    if payload.template is not None:
        patch_row['template'] = payload.template
    if payload.modelName is not None:
        patch_row['model_name'] = payload.modelName
    if payload.temperature is not None:
        patch_row['temperature'] = payload.temperature
    if payload.maxTokens is not None:
        patch_row['max_tokens'] = payload.maxTokens

    try:
        response = client.patch(
            _table_path(),
            params={'id': f'eq.{prompt_id}'},
            headers={'Prefer': 'return=representation'},
            json=patch_row,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f'Failed to patch prompt in Supabase: {exc}') from exc

    rows = response.json()
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=502, detail='Supabase returned an invalid patch response')
    return _row_to_response(rows[0])


@app.delete('/api/v1/prompts/{prompt_id}', status_code=204)
def delete_prompt(prompt_id: str) -> None:
    prompt_id = _trim_non_blank(prompt_id, 'prompt_id')
    try:
        response = client.delete(
            _table_path(),
            params={'id': f'eq.{prompt_id}'},
            headers={'Prefer': 'return=representation'},
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f'Failed to delete prompt from Supabase: {exc}') from exc

    rows = response.json()
    if not isinstance(rows, list):
        raise HTTPException(status_code=502, detail='Supabase returned an invalid delete response')
    if not rows:
        raise HTTPException(status_code=404, detail='Prompt not found')
