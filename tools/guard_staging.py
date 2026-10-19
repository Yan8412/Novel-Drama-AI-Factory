"""Conservative offline guard for the *starter* repository staging tree.

Not a comprehensive secret scanner. Must be complemented by full manual diff and
GitHub-side secret scanning before any upload of actual project files.
Path and file identity checks detect observed swaps, but do not make a concurrently
hostile filesystem safe. Review and stage from a quiescent, isolated directory.
"""
import os
import re
import stat
import sys
import unicodedata
from pathlib import Path

ALLOWED = {
    Path('src/novel_drama_candidate/native_qa_bridge.py'),
    Path('tests/test_native_qa_bridge.py'),
    Path('tools/export_native_qa.py'),
    Path('docs/NATIVE_QA_BRIDGE.md'),
    Path('src/novel_drama_candidate/feedback_adapter.py'),
    Path('tests/test_feedback_adapter.py'),
    Path('tools/validate_feedback_adapter.py'),
    Path('docs/QA_FEEDBACK_ADAPTER.md'),
    Path('README.md'), Path('MANIFEST_SHA256.txt'), Path('pyproject.toml'), Path('.gitignore'), Path('.editorconfig'),
    Path('.github/workflows/offline-cross-platform.yml'),
    Path('src/novel_drama_candidate/__init__.py'),
    Path('src/novel_drama_candidate/mode_router.py'),
    Path('src/novel_drama_candidate/motion_contract.py'),
    Path('src/novel_drama_candidate/prompt_candidate.py'),
    Path('tests/test_router.py'), Path('tests/test_motion.py'),
    Path('tests/test_prompt_candidate.py'), Path('tests/test_guard_staging.py'),
    Path('tools/guard_staging.py'),
    Path('docs/GITHUB_MIGRATION_SECURITY.md'), Path('docs/ARCHITECTURE_ADR_MULTI_MODE.md'),
    Path('docs/S1_PROMPT_GAP_AUDIT.md'), Path('docs/EXTERNAL_SOURCE_PROVENANCE.md'),
    Path('docs/AB_EXPERIMENT_GATE.md'), Path('docs/ACCEPTANCE_MATRIX.md'),
    Path('docs/CODEX_DESKTOP_EXECUTION.md'),
    Path('.gitattributes'),
    Path('docs/SKILL_INTEGRATION.md'),
    Path('skills/novel-drama-prompt-optimizer-candidate/SKILL.md'),
    Path('skills/novel-drama-prompt-optimizer-candidate/references/offline-handoff.md'),
    Path('skills/novel-drama-cinematic-video-director-candidate/SKILL.md'),
    Path('skills/novel-drama-cinematic-video-director-candidate/references/temporal-visibility.md'),
    Path('skills/novel-drama-character-performance-director-candidate/SKILL.md'),
    Path('skills/novel-drama-asset-spatial-director-candidate/SKILL.md'),
    Path('skills/novel-drama-asset-spatial-director-candidate/references/spatial-evidence.md'),
    Path('src/novel_drama_candidate/integration.py'),
    Path('tests/test_integration.py'),
    Path('src/novel_drama_candidate/qa_feedback.py'),
    Path('tests/test_qa_feedback.py'),
    Path('docs/FEEDBACK_ADAPTER.md'),
    Path('docs/FEEDBACK_PROVENANCE.md'),
    Path('skills/novel-drama-prompt-optimizer-candidate/references/feedback-cleanup.md'),
    Path('skills/novel-drama-cinematic-video-director-candidate/references/load-and-frame-review.md'),
    Path('skills/novel-drama-character-performance-director-candidate/references/assistance-evidence.md'),
    Path('skills/novel-drama-asset-spatial-director-candidate/references/world-screen-ledger.md'),
}
DENIED_PARTS = {'90_runtime', '20_specs', '.dsh', 'secrets', 'credentials', 'private'}
REDACTIONS = [
    re.compile(r'(?i)(?:sk-[a-z0-9_-]{20,}|ghp_[a-z0-9]{30,}|github_pat_[a-z0-9_]{30,})'),
    re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(r'(?i)(?:api[_-]?key|access[_-]?token|authorization)[ \t]*[:=][ \t]*["\']?[a-z0-9_/-]{24,}'),
]


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_size,
            info.st_mtime_ns)


def _snapshot(info):
    # On Windows, lstat and fstat can report different ctime semantics. Compare
    # ctime only between observations made through the same source.
    return _identity(info) + (info.st_ctime_ns,)


def _checked_path(path, root):
    """Check links, ancestry and containment before opening or accepting data."""
    info = path.lstat()
    for current in (path, *path.parents):
        entry = info if current == path else current.lstat()
        if (stat.S_ISLNK(entry.st_mode) or
                getattr(entry, 'st_file_attributes', 0) &
                getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)):
            raise ValueError('LINK_OR_REPARSE_POINT')
        if current == root:
            break
    path.resolve(strict=True).relative_to(root)
    return info


def _read_checked(path, root, before):
    """Bound the read and compare the opened file with the inspected pathname."""
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        if _identity(opened) != _identity(before):
            raise ValueError('FILE_IDENTITY_CHANGED_BEFORE_READ')
        data = stream.read(512_001)
        if _snapshot(os.fstat(stream.fileno())) != _snapshot(opened):
            raise ValueError('FILE_IDENTITY_CHANGED_DURING_READ')
    if _snapshot(_checked_path(path, root)) != _snapshot(before):
        raise ValueError('FILE_IDENTITY_CHANGED_AFTER_READ')
    if len(data) > 512_000:
        raise ValueError('OVERSIZE_TEXT')
    return data.decode('utf-8')


def verify(root: Path):
    errors = []
    actual = set()
    allowed = {p.as_posix() for p in ALLOWED}
    seen = {}
    inspected_files = {}
    inspected_directories = {}
    directory_entries = {}
    root = Path(os.path.abspath(root))
    try:
        # Inspect the supplied root and its ancestors before resolving aliases.
        _checked_path(root, Path(root.anchor))
        root = root.resolve(strict=True)
        root_identity = _identity(root.lstat())[:3]
        if not root.is_dir():
            return ['STAGING_ROOT_NOT_DIRECTORY']
    except (OSError, ValueError, RuntimeError) as exc:
        return [f'STAGING_ROOT_INVALID {type(exc).__name__}']

    def walk_error(exc):
        errors.append(f'STAGING_WALK_ERROR {type(exc).__name__}')

    for directory, dirs, files in os.walk(root, topdown=True, followlinks=False,
                                          onerror=walk_error):
        current = Path(directory)
        try:
            inspected_directories[current] = _checked_path(current, root)
            directory_entries[current] = frozenset(dirs + files)
            if _identity(root.lstat())[:3] != root_identity:
                raise ValueError('STAGING_ROOT_CHANGED')
        except (OSError, ValueError, RuntimeError) as exc:
            dirs[:] = []
            errors.append(f'UNSAFE_DIRECTORY {current.relative_to(root)} {type(exc).__name__}')
            continue
        for name in sorted(dirs + files):
            p = current / name
            rel = p.relative_to(root)
            rel_text = rel.as_posix()
            normalized = unicodedata.normalize('NFC', rel_text)
            key = normalized.casefold()
            if key in seen:
                errors.append(f'PATH_CASE_OR_NFC_COLLISION {rel_text}')
            seen[key] = rel_text
            is_directory = name in dirs
            try:
                before = _checked_path(p, root)
                if normalized != rel_text:
                    raise ValueError('NON_NFC_PATH')
                if is_directory:
                    if name in {'.git', '__pycache__', '.pytest_cache'}:
                        dirs.remove(name)
                    continue
                actual.add(rel_text)
                if rel_text not in allowed:
                    errors.append(f'UNREVIEWED_PATH {rel_text}')
                    continue
                if any(x.casefold() in DENIED_PARTS for x in rel.parts):
                    raise ValueError('DENIED_PATH')
                if not stat.S_ISREG(before.st_mode):
                    raise ValueError('NOT_REGULAR_FILE')
                if before.st_size > 512_000:
                    raise ValueError('OVERSIZE_TEXT')
                data = _read_checked(p, root, before)
                inspected_files[p] = before
            except UnicodeError:
                errors.append(f'NOT_UTF8_TEXT {rel_text}')
                continue
            except (OSError, ValueError, RuntimeError) as exc:
                if is_directory and name in dirs:
                    dirs.remove(name)
                reason = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
                errors.append(f'UNSAFE_PATH {rel_text} {reason}')
                continue
            for rx in REDACTIONS:
                if rx.search(data):
                    errors.append(f'POSSIBLE_SECRET {rel_text} (manual review required)')
    # Recheck earlier files and visited directories after the complete scan.
    # This catches observed late replacements/additions, not every possible race.
    for path, before in {**inspected_directories, **inspected_files}.items():
        try:
            if _snapshot(_checked_path(path, root)) != _snapshot(before):
                raise ValueError('IDENTITY_OR_CONTENT_CHANGED_AFTER_SCAN')
            if path in directory_entries and frozenset(p.name for p in path.iterdir()) != directory_entries[path]:
                raise ValueError('DIRECTORY_ENTRIES_CHANGED_AFTER_SCAN')
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(f'STAGING_CHANGED_DURING_SCAN {path.relative_to(root)} {type(exc).__name__}')
    try:
        if _identity(_checked_path(root, root))[:3] != root_identity:
            raise ValueError('STAGING_ROOT_CHANGED')
    except (OSError, ValueError, RuntimeError) as exc:
        errors.append(f'STAGING_ROOT_CHANGED {type(exc).__name__}')
    missing = allowed - actual
    for rel in sorted(missing):
        errors.append(f'MISSING_EXPECTED_FILE {rel}')
    return errors


if __name__ == '__main__':
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    findings = verify(root)
    if findings:
        print('BLOCKED: explicit staging allowlist check failed')
        for item in findings:
            print(item)
        sys.exit(1)
    print(f'PASS: {len(ALLOWED)} exact starter files reviewed. NOT an actual-project security audit.')
