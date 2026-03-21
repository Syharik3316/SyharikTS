import os
import unittest
import uuid
from types import SimpleNamespace
from unittest import mock

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.main import create_app
from app.models.user import GenerationHistory
from app.services.generation_cache import build_generator_fingerprint, build_input_fingerprint


class _FakeScalarRows:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _FakeSelectResult:
    def __init__(self, row):
        self._row = row

    def scalars(self):
        return _FakeScalarRows(self._row)


class _FakeDbSession:
    def __init__(self, cached_row=None):
        self.cached_row = cached_row
        self.added = []

    async def execute(self, _query):  # noqa: ANN001
        return _FakeSelectResult(self.cached_row)

    async def commit(self):
        return None

    def add(self, obj):
        self.added.append(obj)


class GenerateCacheTests(unittest.TestCase):
    def _auth_overrides(self, app, db_session: _FakeDbSession, user_id):  # noqa: ANN001
        async def _fake_user():
            return SimpleNamespace(id=user_id)

        async def _fake_db():
            yield db_session

        app.dependency_overrides[get_current_user] = _fake_user
        app.dependency_overrides[get_db] = _fake_db

    def test_cache_hit_reuses_code_for_other_user(self) -> None:
        app = create_app()
        current_user_id = uuid.uuid4()
        original_user_id = uuid.uuid4()
        cached = GenerationHistory(
            id=uuid.uuid4(),
            user_id=original_user_id,
            generated_ts_code='export default function (): DealData[] { return []; }',
            schema_text='{"dealName":"string"}',
            main_file_name="old.csv",
            input_fingerprint="x",
            generator_fingerprint="y",
        )
        db_session = _FakeDbSession(cached_row=cached)
        self._auth_overrides(app, db_session, current_user_id)

        with (
            mock.patch("app.routers.generate.extract_extracted_input_from_bytes", side_effect=AssertionError("parse should not run")),
            mock.patch("app.services.llm_client.LLMClient.generate_ts_code", side_effect=AssertionError("llm should not run")),
        ):
            with TestClient(app) as client:
                resp = client.post(
                    "/generate",
                    files={"file": ("data.csv", b"a;b\n1;2\n", "text/csv")},
                    data={"schema": '{"dealName":"string"}'},
                )

        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()["code"], cached.generated_ts_code)
        self.assertEqual(len(db_session.added), 1)
        persisted = db_session.added[0]
        self.assertTrue(persisted.cache_hit)
        self.assertEqual(persisted.cache_source_generation_id, cached.id)
        self.assertEqual(persisted.user_id, current_user_id)
        self.assertEqual(persisted.total_tokens, 0)

    def test_cache_miss_runs_llm_and_persists_fingerprints(self) -> None:
        app = create_app()
        user_id = uuid.uuid4()
        db_session = _FakeDbSession(cached_row=None)
        self._auth_overrides(app, db_session, user_id)

        with (
            mock.patch(
                "app.routers.generate.extract_extracted_input_from_bytes",
                return_value=("csv", {"kind": "csv", "records": [{"dealName": "A"}], "text": "", "tables": []}),
            ),
            mock.patch(
                "app.services.llm_client.LLMClient.generate_ts_code",
                return_value='interface DealData { "dealName": string; }\n'
                "export default function (base64file: string): DealData[] {\n"
                "  return [{\"dealName\":\"ok\"} as DealData];\n"
                "}\n",
            ) as llm_mock,
        ):
            with TestClient(app) as client:
                resp = client.post(
                    "/generate",
                    files={"file": ("data.csv", b"a;b\n1;2\n", "text/csv")},
                    data={"schema": '{"dealName":"string"}'},
                )

        self.assertEqual(resp.status_code, 200, resp.text)
        llm_mock.assert_called_once()
        self.assertEqual(len(db_session.added), 1)
        persisted = db_session.added[0]
        self.assertFalse(persisted.cache_hit)
        self.assertTrue(bool(persisted.input_fingerprint))
        self.assertTrue(bool(persisted.generator_fingerprint))

    def test_generator_fingerprint_changes_with_prompt_version(self) -> None:
        with mock.patch.dict(os.environ, {"PROMPT_VERSION": "v1"}, clear=False):
            fp_v1 = build_generator_fingerprint(provider="gigachat", model="GigaChat-2-Max")
        with mock.patch.dict(os.environ, {"PROMPT_VERSION": "v2"}, clear=False):
            fp_v2 = build_generator_fingerprint(provider="gigachat", model="GigaChat-2-Max")
        self.assertNotEqual(fp_v1, fp_v2)

    def test_input_fingerprint_changes_with_file_kind(self) -> None:
        file_bytes = b"same-content"
        schema_text = '{"a":"string"}'
        fp_csv = build_input_fingerprint(file_bytes=file_bytes, schema_text=schema_text, file_kind="csv")
        fp_pdf = build_input_fingerprint(file_bytes=file_bytes, schema_text=schema_text, file_kind="pdf")
        self.assertNotEqual(fp_csv, fp_pdf)


if __name__ == "__main__":
    unittest.main()
