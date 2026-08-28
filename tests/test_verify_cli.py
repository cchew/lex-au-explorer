import json

from typer.testing import CliRunner

from build import verify_cli


def test_verify_cli_calls_run_verification_with_corpus_index_and_out(tmp_path, monkeypatch):
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    (corpus_dir / "index.json").write_text(json.dumps({"acts": {}, "updated_at": "2026-08-01"}))
    out = tmp_path / "verification.json"

    seen = {}

    def fake_run(corpus_index_path, out_path, **kwargs):
        seen["corpus_index_path"] = corpus_index_path
        seen["out_path"] = out_path
        seen["delay"] = kwargs.get("delay")
        return {"current": 0, "stale": 0, "repealed": 0, "inferred": 0, "unverified": 0}

    monkeypatch.setattr(verify_cli, "run_verification", fake_run)

    result = CliRunner().invoke(
        verify_cli.app,
        ["--corpus-dir", str(corpus_dir), "--out", str(out)],
    )

    assert result.exit_code == 0, result.output
    assert seen["corpus_index_path"] == corpus_dir / "index.json"
    assert seen["out_path"] == out


def test_verify_cli_help_lists_corpus_dir():
    result = CliRunner().invoke(verify_cli.app, ["--help"])
    assert result.exit_code == 0
    assert "corpus-dir" in result.output
