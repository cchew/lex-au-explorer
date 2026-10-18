import json
import logging

import pytest

from build.metadata import (
    UnsupportedCorpusStructure,
    check_structure_version,
    load_corpus_index,
)


def _index(tmp_path, **extra):
    (tmp_path / "xml").mkdir()
    path = tmp_path / "index.json"
    path.write_text(json.dumps({"acts": {}, **extra}))
    return path


@pytest.mark.parametrize("version", [1, 2])
def test_supported_versions_pass(version):
    check_structure_version({"structure_version": version})


def test_unknown_version_is_refused():
    with pytest.raises(UnsupportedCorpusStructure, match="structure_version 3"):
        check_structure_version({"structure_version": 3})


def test_missing_version_warns_but_proceeds(caplog):
    with caplog.at_level(logging.WARNING, logger="build.metadata"):
        check_structure_version({"acts": {}})
    assert any("no structure_version" in r.message for r in caplog.records)


def test_load_corpus_index_refuses_an_unknown_structure(tmp_path):
    path = _index(tmp_path, structure_version=99)
    with pytest.raises(UnsupportedCorpusStructure):
        load_corpus_index(path, xml_dir=tmp_path / "xml")


def test_load_corpus_index_accepts_the_current_structure(tmp_path):
    path = _index(tmp_path, structure_version=2)
    assert load_corpus_index(path, xml_dir=tmp_path / "xml") == {}
