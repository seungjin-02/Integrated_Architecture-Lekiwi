"""Prepare an explicit native source COPY for optional facade instrumentation.

The pinned upstream tree is never patched in place. A hash
manifest records the supported boundary; the runner rechecks it before imports.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

UPSTREAM_COMMIT = "48f298c71dd54277e8086a58300703ffee1dbb8e"
EXPECTED = {
    "lekiwi_web_operator/http_server.py": "519df24eb2192c91f03c85c89e46467be70ac9b00785dd71338facfd6a73795b",
    "lekiwi_web_operator/robot.py": "888dbd8b5ea4d079f5296dea8e01606013a5ee1ffc071b482f729a3c02dd3ed0",
    "lekiwi_web_operator/robot_api.py": "0e7880c38c53dad73076a7cc631b2dbf1514b0ab17e78abd4877c1cccfe1c616",
    "lekiwi_web_operator/__main__.py": "068bd83f0f3f70afc11002fb4cc84680740f64f73abd0691d16a7bbacc314e9e",
}
MANIFEST = "xlerobot-hook-plan.json"


def verify_source(source):
    source = Path(source).resolve(strict=True)
    for name, expected in EXPECTED.items():
        target = source / name
        if (
            target.is_symlink()
            or not target.is_file()
            or not target.resolve().is_relative_to(source)
        ):
            raise ValueError("Unsupported native source layout")
        # Bound reads before hashing untrusted/mistaken file targets.
        if target.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("Unsupported native source size")
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise ValueError(
                "Native source fingerprint differs; review the integration first"
            )
    return source


def verify_prepared(source):
    source = verify_source(source)
    path = source / MANIFEST
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 16384:
        raise ValueError("Prepare an explicit native copy before running hooks")
    plan = json.loads(path.read_text(encoding="utf-8"))
    if (
        plan.get("schema_version") != 1
        or plan.get("fingerprints") != EXPECTED
        or plan.get("modified_native_files") != []
    ):
        raise ValueError("Invalid native hook plan")
    return source


def prepare_copy(source, output):
    source = verify_source(source)
    requested = Path(output).absolute()
    # Do not recurse into source, replace a live tree, or follow linked parents.
    for component in (requested, *requested.parents):
        if component.is_symlink() or getattr(component, "is_junction", lambda: False)():
            raise ValueError("Linked output paths are not supported")
    output = requested.resolve()
    if (
        output.exists()
        or output.is_relative_to(source)
        or source.is_relative_to(output)
    ):
        raise ValueError("Output must be a new directory outside the source tree")
    for target in source.rglob("*"):
        if ".git" in target.relative_to(source).parts:
            continue
        if target.is_symlink() or getattr(target, "is_junction", lambda: False)():
            raise ValueError("Linked native source content is not copied")
    shutil.copytree(
        source,
        output,
        ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", MANIFEST),
    )
    # No native source file is changed. Composition is the entire patch plan.
    plan = {
        "schema_version": 1,
        "inspected_upstream_commit": UPSTREAM_COMMIT,
        "fingerprints": EXPECTED,
        "modified_native_files": [],
        "integration": "xlerobot_web_operator/run_native_observed.py --native-source <this-copy>",
        "scope": "RobotApi outer method calls and existing add_listener events only",
    }
    (output / MANIFEST).write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    verify_prepared(output)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Inspected upstream source directory (read only)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="New explicit copy directory; never the original",
    )
    args = parser.parse_args(argv)
    try:
        output = prepare_copy(args.source, args.output)
    except (OSError, ValueError, json.JSONDecodeError):
        parser.exit(
            1,
            "Native copy preparation failed; check target and supported source fingerprint.\n",
        )
    print(f"Prepared optional hook copy: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
