import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path

import pytest
from bricklayer import Color, Element, LegoBuild
from bricklayer.io import to_ldraw

SCRIPTS = Path(__file__).resolve().parents[4] / "skills/lego-build/scripts"


@pytest.fixture
def instructions(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "build_instructions", SCRIPTS / "build_instructions.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


def stepped_model():
    model = LegoBuild()
    model.add(Element("3001", Color.RED), (0, 0, 0))
    model.add_step()
    model.add(Element("3003", Color.BLUE), (0, 0, 1))
    model.add_step()
    return model


def test_requires_authored_steps_and_flat_parts(instructions):
    model = stepped_model()
    with pytest.raises(ValueError, match="step"):
        instructions.assembly_steps(to_ldraw(LegoBuild(model.placements)))
    parent = LegoBuild()
    parent.add(model, (0, 0, 0))
    with pytest.raises(ValueError, match="flat"):
        instructions.assembly_steps(to_ldraw(parent))


def test_steps_preserve_exact_model_and_inventory(instructions):
    model, steps = instructions.assembly_steps(to_ldraw(stepped_model()))
    assert [len(step) for step in steps] == [1, 1]
    assert tuple(p for step in steps for p in step) == model.placements
    assert Counter(p.content.ldraw_id for step in steps for p in step) == Counter(
        {"3001": 1, "3003": 1}
    )


def test_malformed_geometry_and_oversized_steps_rejected(instructions):
    with pytest.raises(ValueError):
        instructions.assembly_steps("1 4 0 0 0 1 0 0 0 1 0 0 0 1 nonexistent.dat")
    model = LegoBuild()
    for x in range(13):
        model.add(Element("3001", Color.RED), (x * 5, 0, 0))
    model.add_step()
    with pytest.raises(ValueError, match="12"):
        instructions.assembly_steps(to_ldraw(model))


def test_pdf_pages_and_manifest_match_authored_steps(instructions, tmp_path):
    from pypdf import PdfReader

    ldraw = to_ldraw(stepped_model())
    instructions.write_instructions(
        ldraw,
        tmp_path,
        {"title": "Tiny tower", "steps": [{"title": "Base"}, {"title": "Top"}]},
    )
    pages = PdfReader(tmp_path / "instructions.pdf").pages
    assert len(pages) == 3
    assert "Tiny tower" in pages[0].extract_text()
    assert "Base" in pages[1].extract_text()
    assert "3003" in pages[2].extract_text()
    manifest = json.loads((tmp_path / "instructions.json").read_text())
    assert [step["added_quantity"] for step in manifest["steps"]] == [1, 1]
    assert manifest["pieces"] == 2
    assert len(list((tmp_path / "steps").glob("*.png"))) == 4


def test_notes_must_match_steps_before_writing(instructions, tmp_path):
    with pytest.raises(ValueError, match="match"):
        instructions.write_instructions(
            to_ldraw(stepped_model()), tmp_path, {"steps": [{"title": "Only one"}]}
        )
    assert not (tmp_path / "instructions.pdf").exists()
