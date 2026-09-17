"""The settings reference page must stay in step with the config schema.

``website/docs/configuration/settings-reference.md`` documents every key a user
can put in ``config/config.yaml``.  Docs drift silently, so this test makes the
drift a test failure instead: adding a key to :data:`gt.config_check.SPEC`
without adding a row to the page (or documenting a key the schema does not have)
breaks the suite.

Together with ``test_config_check.test_spec_covers_exactly_the_pydantic_model``
this chains the three places a config key lives —
``config_model.py`` → ``config_check.SPEC`` → the settings reference.
"""
import re
from pathlib import Path

import pytest

from groundtruther.gt import config_check
from groundtruther.gt.config_check import SECTIONS, SPEC

#: The page under test, relative to the repository root.
DOC_PATH = Path(__file__).resolve().parents[2] / (
    "website/docs/configuration/settings-reference.md")

#: A dotted config key written as inline code, e.g. ``HabCam.imagepath``.
#: Anchored on the opening backtick so ``gt/config_check.SPEC`` and friends do
#: not look like config keys.
_KEY_IN_DOC = re.compile(r"`([A-Z][A-Za-z]*)\.([A-Za-z_][A-Za-z0-9_]*)`")


@pytest.fixture(scope="module")
def doc_text():
    if not DOC_PATH.is_file():
        pytest.fail(f"settings reference page is missing: {DOC_PATH}")
    return DOC_PATH.read_text(encoding="utf-8")


def test_every_spec_key_is_documented(doc_text):
    """Every key the validator knows about has a row on the page."""
    missing = [item.key for item in SPEC if f"`{item.key}`" not in doc_text]
    assert not missing, (
        "these config keys are not documented in "
        f"{DOC_PATH.name}: {missing}")


def test_the_page_documents_no_unknown_key(doc_text):
    """The page does not describe a key the schema does not have."""
    spec_keys = {item.key for item in SPEC}
    documented = {
        f"{section}.{name}"
        for section, name in _KEY_IN_DOC.findall(doc_text)
        if section in SECTIONS
    }
    unknown = sorted(documented - spec_keys)
    assert not unknown, (
        f"{DOC_PATH.name} documents keys that are not in config_check.SPEC "
        f"(renamed or removed?): {unknown}")


def test_the_key_count_is_stated_correctly(doc_text):
    """The page's headline count matches the number of keys in the spec."""
    assert f"**{len(SPEC)} keys" in doc_text, (
        f"the page should say '**{len(SPEC)} keys in "
        f"{len(SECTIONS)} sections.**'")
    assert f"in {len(SECTIONS)} sections" in doc_text


def test_every_section_has_a_heading(doc_text):
    """Each config section gets its own heading on the page."""
    missing = [s for s in config_check.SECTIONS if f"## `{s}`" not in doc_text]
    assert not missing, f"sections without a heading in {DOC_PATH.name}: {missing}"
