"""Figure image assets: copy referenced ``<figure><img>`` files into the build.

The lex-au corpus records figures as ``<img src="corpus/images/{slug}-fig-{n}.png">``
(repo-relative, always ``.png``, ``alt=""`` on all 1,819 of them -- parity spike
note, section B). The image files themselves are **not** shipped in the lex-au
repo: there is no ``corpus/images/`` directory in practice. A missing source
directory is therefore a normal outcome, not an error -- every basename is
returned as "missing" and the style map renders a labelled placeholder.
"""

from __future__ import annotations

import os.path
import shutil
from pathlib import Path
from typing import Iterable

__all__ = ["copy_figure_assets"]


def copy_figure_assets(
    corpus_images_dir: Path,
    srcs: Iterable[str],
    out_images_dir: Path,
) -> set[str]:
    """Copy each referenced figure image into ``out_images_dir``.

    ``srcs`` is the raw ``<img src>`` strings collected from every parsed
    ``figure`` node. Each is reduced to its basename and looked up in
    ``corpus_images_dir``. Present files are copied; absent files -- and the
    common case of ``corpus_images_dir`` itself not existing -- have their
    basename added to the returned "missing" set.

    Does not raise on a missing source directory. Logs a one-line count.
    """
    basenames = {
        base
        for s in srcs
        if s and s.strip()
        for base in (os.path.basename(s),)
        if base
    }
    missing: set[str] = set()
    if not basenames:
        return missing

    dir_exists = corpus_images_dir.is_dir()
    if dir_exists:
        out_images_dir.mkdir(parents=True, exist_ok=True)

    for name in sorted(basenames):
        source = corpus_images_dir / name
        if dir_exists and source.is_file():
            shutil.copy2(source, out_images_dir / name)
        else:
            missing.add(name)

    copied = len(basenames) - len(missing)
    suffix = "" if dir_exists else f" (source dir {corpus_images_dir} not present)"
    print(f"Figure assets: {copied} copied, {len(missing)} missing{suffix}")
    return missing
