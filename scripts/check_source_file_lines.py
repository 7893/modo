"""Fail when first-party source files exceed the repository line limit."""
from pathlib import Path

MAX_LINES = 400
ROOT = Path(__file__).resolve().parents[1]
SOURCE_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".jsonc",
    ".py",
    ".sh",
    ".sql",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}
IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    "venv",
}
GENERATED_FILES = {
    "edge-app/src/tailwind.generated.css",
    "edge-app/worker-configuration.d.ts",
    "edge-app/pnpm-lock.yaml",
}


def iter_source_files():
    """Yield repository-owned source files, excluding dependencies and generated output."""
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in SOURCE_SUFFIXES:
            continue
        relative = path.relative_to(ROOT)
        if any(part in IGNORED_DIRECTORIES for part in relative.parts):
            continue
        if relative.as_posix() in GENERATED_FILES:
            continue
        yield relative, path


def main() -> int:
    oversized = []
    for relative, path in iter_source_files():
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > MAX_LINES:
            oversized.append((relative, line_count))

    if not oversized:
        print(f"Source file policy passed: all first-party files are <= {MAX_LINES} lines.")
        return 0

    print(f"Source file policy failed: limit is {MAX_LINES} lines.")
    for relative, line_count in sorted(oversized):
        print(f"  {relative}: {line_count} lines")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
