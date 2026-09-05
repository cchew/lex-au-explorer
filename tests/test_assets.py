from __future__ import annotations

from pathlib import Path

from build.assets import copy_figure_assets
from build.ir import Node
from build.stylemap import HtmlStyleMap


def test_present_file_is_copied_and_not_missing(tmp_path: Path) -> None:
    src_dir = tmp_path / "images"
    src_dir.mkdir()
    (src_dir / "act-fig-1.png").write_bytes(b"PNGDATA")
    out_dir = tmp_path / "out" / "images"

    missing = copy_figure_assets(
        src_dir, ["corpus/images/act-fig-1.png"], out_dir
    )

    assert missing == set()
    assert (out_dir / "act-fig-1.png").read_bytes() == b"PNGDATA"


def test_absent_file_is_reported_missing(tmp_path: Path) -> None:
    src_dir = tmp_path / "images"
    src_dir.mkdir()
    (src_dir / "have.png").write_bytes(b"x")
    out_dir = tmp_path / "out" / "images"

    missing = copy_figure_assets(
        src_dir, ["corpus/images/have.png", "corpus/images/gone.png"], out_dir
    )

    assert missing == {"gone.png"}
    assert (out_dir / "have.png").exists()
    assert not (out_dir / "gone.png").exists()


def test_missing_corpus_dir_returns_all_basenames_and_does_not_crash(
    tmp_path: Path,
) -> None:
    src_dir = tmp_path / "does-not-exist"
    out_dir = tmp_path / "out" / "images"

    missing = copy_figure_assets(
        src_dir,
        [
            "corpus/images/income-tax-assessment-act-1997-fig-2.png",
            "corpus/images/income-tax-assessment-act-1997-fig-3.png",
        ],
        out_dir,
    )

    assert missing == {
        "income-tax-assessment-act-1997-fig-2.png",
        "income-tax-assessment-act-1997-fig-3.png",
    }
    # No output directory is created when there is nothing to copy.
    assert not out_dir.exists()


def test_basename_is_taken_from_the_src_path(tmp_path: Path) -> None:
    src_dir = tmp_path / "images"
    src_dir.mkdir()
    (src_dir / "deep-fig.png").write_bytes(b"x")
    out_dir = tmp_path / "out"

    missing = copy_figure_assets(
        src_dir, ["some/nested/corpus/images/deep-fig.png"], out_dir
    )

    assert missing == set()
    assert (out_dir / "deep-fig.png").exists()


def test_dimensions_flow_through_when_asset_present(tmp_path: Path) -> None:
    """copy_figure_assets marks the asset present -> _figure emits the <img>
    with the width/height lifted from the source <img> element."""
    src_dir = tmp_path / "images"
    src_dir.mkdir()
    (src_dir / "act-fig-1.png").write_bytes(b"PNGDATA")
    out_dir = tmp_path / "out" / "images"

    missing = copy_figure_assets(
        src_dir, ["corpus/images/act-fig-1.png"], out_dir
    )
    assert missing == set()

    basename = "act-fig-1.png"
    node = Node("figure", {
        "src": "corpus/images/act-fig-1.png",
        "width": "320",
        "height": "200",
        "asset": basename not in missing,
    })
    html = HtmlStyleMap()._figure(node, [])
    assert html == (
        '<figure><img src="/data/images/act-fig-1.png" '
        'alt="" width="320" height="200"></figure>'
    )


def test_absent_asset_renders_placeholder_without_crash(tmp_path: Path) -> None:
    src_dir = tmp_path / "images"
    src_dir.mkdir()
    out_dir = tmp_path / "out" / "images"

    missing = copy_figure_assets(
        src_dir, ["corpus/images/gone.png"], out_dir
    )
    assert missing == {"gone.png"}

    node = Node("figure", {
        "src": "corpus/images/gone.png",
        "width": "320",
        "height": "200",
        "alt": "Diagram",
        "asset": "gone.png" not in missing,
    })
    html = HtmlStyleMap()._figure(node, [])
    assert html == '<figure class="akn-figure-missing">[figure: Diagram]</figure>'


def test_empty_and_blank_srcs_are_ignored(tmp_path: Path) -> None:
    src_dir = tmp_path / "images"
    src_dir.mkdir()
    out_dir = tmp_path / "out"

    missing = copy_figure_assets(src_dir, ["", "   "], out_dir)

    assert missing == set()
    assert not out_dir.exists()
