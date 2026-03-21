import threading
import time
import unittest
from types import SimpleNamespace
from unittest import mock

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.main import create_app


class _ScalarResult:
    def __init__(self, value: int) -> None:
        self._value = value

    def scalar(self) -> int:
        return self._value


class _FakeDbSession:
    async def execute(self, _query):  # noqa: ANN001
        return _ScalarResult(7)

    async def commit(self) -> None:
        return None

    def add(self, _obj) -> None:  # noqa: ANN001
        return None


class GenerateConcurrencyTests(unittest.TestCase):
    def test_long_generate_does_not_block_stats_endpoint(self) -> None:
        app = create_app()

        async def _fake_user():
            return SimpleNamespace(id=1)

        async def _fake_db():
            yield _FakeDbSession()

        app.dependency_overrides[get_current_user] = _fake_user
        app.dependency_overrides[get_db] = _fake_db

        parse_started = threading.Event()

        def _slow_extract(*args, **kwargs):  # noqa: ANN002,ANN003
            parse_started.set()
            time.sleep(0.6)
            return "csv", {"kind": "csv", "records": [{"dealName": "A"}], "text": "", "tables": []}

        def _slow_generate(self, **kwargs):  # noqa: ANN001
            time.sleep(0.6)
            return (
                'interface DealData { "dealName": string; }\n'
                "export default function (base64file: string): DealData[] {\n"
                "  return [{\"dealName\":\"ok\"} as DealData];\n"
                "}\n"
            )

        with (
            mock.patch("app.routers.generate.extract_extracted_input_from_bytes", side_effect=_slow_extract),
            mock.patch("app.services.llm_client.LLMClient.generate_ts_code", new=_slow_generate),
        ):
            gen_client = TestClient(app)
            stats_client = TestClient(app)
            response_holder: dict[str, object] = {}

            def _run_generate() -> None:
                response_holder["resp"] = gen_client.post(
                    "/generate",
                    files={"file": ("data.csv", b"a;b\n1;2\n", "text/csv")},
                    data={"schema": '{"dealName":"string"}'},
                )

            worker = threading.Thread(target=_run_generate)
            worker.start()
            self.assertTrue(parse_started.wait(timeout=1.0))

            start = time.perf_counter()
            stats_resp = stats_client.get("/stats/generations")
            elapsed_ms = int((time.perf_counter() - start) * 1000)

            worker.join(timeout=5.0)
            self.assertFalse(worker.is_alive())
            self.assertEqual(stats_resp.status_code, 200, stats_resp.text)
            self.assertLess(elapsed_ms, 500)

            gen_resp = response_holder.get("resp")
            self.assertIsNotNone(gen_resp)
            assert gen_resp is not None
            self.assertEqual(gen_resp.status_code, 200, gen_resp.text)


if __name__ == "__main__":
    unittest.main()
