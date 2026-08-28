from __future__ import annotations

from pathlib import Path

import typer

from build.cli import DEFAULT_VERIFICATION_PATH
from build.verification import run_verification

app = typer.Typer()


@app.command()
def main(
    corpus_dir: Path = typer.Option(..., "--corpus-dir", help="Path to lex-au's corpus/ directory"),
    out: Path = typer.Option(
        DEFAULT_VERIFICATION_PATH, "--out", help="Where to write/merge verification.json"
    ),
    delay: float = typer.Option(
        1.5, "--delay", help="Seconds between calls to legislation.gov.au"
    ),
) -> None:
    """Refresh the source-fidelity data by checking each corpus Act against
    legislation.gov.au's current in-force compilation. Run this before a
    deploy when you want a fresh 'Verified' claim in the reader; the build
    itself never touches the network."""
    summary = run_verification(corpus_dir / "index.json", out, delay=delay)
    typer.echo(f"Verification written to {out}: {summary}")
