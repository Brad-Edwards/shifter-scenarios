"""Keep the modular KeplerOps runtime small, complete, and image-bound."""

import ast
import re
import unittest
from pathlib import Path


RUNTIME_ROOT = (
    Path(__file__).resolve().parents[2]
    / "assets"
    / "services"
    / "keplerops-runtime"
)
MAX_PHYSICAL_LINES = 500


class RuntimePythonFileSizeTests(unittest.TestCase):
    def test_runtime_python_files_do_not_exceed_line_limit(self) -> None:
        oversized = {
            str(path.relative_to(RUNTIME_ROOT)): len(path.read_bytes().splitlines())
            for path in sorted(RUNTIME_ROOT.rglob("*.py"))
            if len(path.read_bytes().splitlines()) > MAX_PHYSICAL_LINES
        }

        self.assertFalse(
            oversized,
            f"Runtime Python files must not exceed {MAX_PHYSICAL_LINES} "
            f"physical lines: {oversized}",
        )

    def test_composition_root_registers_every_runtime_router(self) -> None:
        source = (RUNTIME_ROOT / "app.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_routers = {
            alias.asname
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
            if alias.name == "router" and alias.asname is not None
        }
        include_loop = next(
            node
            for node in tree.body
            if isinstance(node, ast.For)
            and isinstance(node.target, ast.Name)
            and node.target.id == "router"
        )
        self.assertIsInstance(include_loop.iter, ast.Tuple)
        included_routers = {
            item.id for item in include_loop.iter.elts if isinstance(item, ast.Name)
        }
        self.assertEqual(included_routers, imported_routers)

        package_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((RUNTIME_ROOT / "keplerops_runtime").rglob("*.py"))
        )
        route_count = len(
            re.findall(r"^@router\.(?:get|post|put|patch|delete)\(", package_source, re.M)
        )
        self.assertEqual(route_count, 142)

    def test_every_runtime_image_copies_the_modular_package(self) -> None:
        pack_root = Path(__file__).resolve().parents[2]
        dockerfiles = (
            RUNTIME_ROOT / "Dockerfile",
            pack_root / "assets/services/Dockerfile.gateway",
            pack_root / "assets/services/Dockerfile.policy",
            pack_root / "assets/services/Dockerfile.proof",
        )
        for dockerfile in dockerfiles:
            source = dockerfile.read_text(encoding="utf-8")
            with self.subTest(dockerfile=dockerfile.name):
                self.assertIn(
                    "COPY assets/services/keplerops-runtime/keplerops_runtime "
                    "./keplerops_runtime",
                    source,
                )
                self.assertIn("oracle_domain.py ./oracle_domain.py", source)
                self.assertIn("research_domain.py ./research_domain.py", source)
                self.assertIn("research_readback.py ./research_readback.py", source)
