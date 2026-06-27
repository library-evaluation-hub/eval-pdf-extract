"""Unit tests for runner: run_one() with mocked subprocess."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from orchestrator.models import AdapterEntry, FixtureEntry
from orchestrator.runner import run_one
from tests.conftest import make_page, make_result


def _make_adapter() -> AdapterEntry:
    return AdapterEntry(
        id="test-adapter@1.0.0",
        command="test-adapter",
        language="python",
        timeout_seconds=10,
    )


def _make_fixture() -> FixtureEntry:
    return FixtureEntry(
        id="01_plain_text__test",
        path="fixtures/01_plain_text__test/input.pdf",
        category="plain_text",
        expected_page_count=1,
        sha256="abc123",
    )


def _setup_corpus(tmp_path: Path) -> Path:
    """Create a minimal corpus dir with input.pdf."""
    corpus_dir = tmp_path / "corpus"
    fixture_dir = corpus_dir / "fixtures" / "01_plain_text__test"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "input.pdf").write_bytes(b"%PDF-1.4 fake")
    return corpus_dir


class _FakePopen:
    """Fake psutil.Popen that writes result.json to output_dir on poll.

    Modes:
    - normal: poll() returns None once, then writes result and returns returncode
    - timeout: poll() always returns None until kill() is called
    """

    def __init__(
        self,
        cmd: list[str],
        result_data: dict[str, Any] | None = None,
        returncode: int = 0,
        memory_rss: int = 10 * 1024 * 1024,
        never_exit: bool = False,
    ) -> None:
        self._cmd = cmd
        self._output_dir = Path(cmd[cmd.index("--output-dir") + 1])
        self._result_data = result_data
        self._returncode = returncode
        self._memory_rss = memory_rss
        self._written = False
        self._poll_count = 0
        self._never_exit = never_exit
        self._killed = False
        self.stdout = MagicMock()
        self.stderr = MagicMock()
        self.stdout.read = MagicMock(return_value="")
        self.stderr.read = MagicMock(return_value="")

    def _maybe_write_result(self) -> None:
        if not self._written and self._result_data is not None:
            self._output_dir.mkdir(parents=True, exist_ok=True)
            (self._output_dir / "result.json").write_text(
                json.dumps(self._result_data), encoding="utf-8",
            )
            self._written = True

    def poll(self) -> int | None:
        if self._never_exit:
            return None
        self._poll_count += 1
        if self._poll_count > 1:
            self._maybe_write_result()
            return self._returncode
        return None

    def wait(self, timeout: float | None = None) -> int:
        self._maybe_write_result()
        return self._returncode

    def kill(self) -> None:
        self._killed = True

    def memory_info(self) -> MagicMock:
        mi = MagicMock()
        mi.rss = self._memory_rss
        return mi

    @property
    def returncode(self) -> int:
        return self._returncode


class TestRunOneSuccess:
    def test_successful_run(self, tmp_path: Path, result_schema_path: Path) -> None:
        corpus_dir = _setup_corpus(tmp_path)
        results_dir = tmp_path / "results"

        adapter = _make_adapter()
        fixture = _make_fixture()
        result_data = make_result([make_page(1, text="hello")])

        def fake_popen(cmd: list[str], **kwargs: Any) -> _FakePopen:
            return _FakePopen(cmd, result_data=result_data, returncode=0)

        with patch("orchestrator.runner.psutil.Popen", side_effect=fake_popen):
            rr = run_one(adapter, fixture, corpus_dir, results_dir, result_schema_path)

        assert rr.exit_code == 0
        assert rr.has_result is True
        assert rr.adapter_id == "test-adapter@1.0.0"
        assert rr.fixture_id == "01_plain_text__test"
        assert rr.error_category == "none"
        assert rr.result_data is not None
        assert len(rr.result_data["pages"]) == 1

    def test_no_result_json(self, tmp_path: Path, result_schema_path: Path) -> None:
        corpus_dir = _setup_corpus(tmp_path)
        results_dir = tmp_path / "results"

        adapter = _make_adapter()
        fixture = _make_fixture()

        def fake_popen(cmd: list[str], **kwargs: Any) -> _FakePopen:
            return _FakePopen(cmd, result_data=None, returncode=0)

        with patch("orchestrator.runner.psutil.Popen", side_effect=fake_popen):
            rr = run_one(adapter, fixture, corpus_dir, results_dir, result_schema_path)

        assert rr.exit_code == 0
        assert rr.has_result is False
        assert rr.result_data is None


class TestRunOneTimeout:
    def test_timeout_exit_code_124(self, tmp_path: Path, result_schema_path: Path) -> None:
        corpus_dir = _setup_corpus(tmp_path)
        results_dir = tmp_path / "results"

        adapter = AdapterEntry(
            id="test-adapter@1.0.0",
            command="test-adapter",
            language="python",
            timeout_seconds=1,
        )
        fixture = _make_fixture()

        def fake_popen(cmd: list[str], **kwargs: Any) -> _FakePopen:
            return _FakePopen(cmd, result_data=None, returncode=0, never_exit=True)

        with patch("orchestrator.runner.psutil.Popen", side_effect=fake_popen):
            rr = run_one(adapter, fixture, corpus_dir, results_dir, result_schema_path)

        assert rr.exit_code == 124
        assert rr.error_category == "timeout"
        assert rr.has_result is False


class TestRunOneNonZeroExitWithResult:
    def test_parse_error_with_partial_result(self, tmp_path: Path, result_schema_path: Path) -> None:
        corpus_dir = _setup_corpus(tmp_path)
        results_dir = tmp_path / "results"

        adapter = _make_adapter()
        fixture = _make_fixture()
        result_data = make_result([make_page(1, text="partial")])

        def fake_popen(cmd: list[str], **kwargs: Any) -> _FakePopen:
            return _FakePopen(cmd, result_data=result_data, returncode=65)

        with patch("orchestrator.runner.psutil.Popen", side_effect=fake_popen):
            rr = run_one(adapter, fixture, corpus_dir, results_dir, result_schema_path)

        assert rr.exit_code == 65
        assert rr.error_category == "parse_error"
        assert rr.has_result is True
        assert rr.result_data is not None
        assert rr.result_valid is True


class TestRunOneCommandNotFound:
    def test_command_not_found(self, tmp_path: Path, result_schema_path: Path) -> None:
        corpus_dir = _setup_corpus(tmp_path)
        results_dir = tmp_path / "results"

        adapter = _make_adapter()
        fixture = _make_fixture()

        with patch("orchestrator.runner.psutil.Popen", side_effect=FileNotFoundError):
            rr = run_one(adapter, fixture, corpus_dir, results_dir, result_schema_path)

        assert rr.exit_code == 127
        assert rr.has_result is False
        assert "not found" in rr.stderr
        assert rr.error_category == "crash"
