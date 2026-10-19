"""Print a private read-only native QA export; never write to the project."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from novel_drama_candidate.feedback_adapter import _json
from novel_drama_candidate.native_qa_bridge import export_native_qa


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--enable', action='store_true')
    args = parser.parse_args()
    if args.enable and args.manifest is None:
        parser.error('--enable requires an explicit private --manifest')
    manifest = _json(args.manifest.read_bytes()) if args.enable else None
    result = export_native_qa(manifest, enabled=args.enable)
    # Windows pipes may otherwise use the system code page and corrupt private
    # Unicode paths or native QA text when another process reads this JSON.
    output = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    sys.stdout.buffer.write(output.encode('utf-8'))
    return 0 if result['status'] in ('DISABLED', 'HUMAN_REVIEW') else 1


if __name__ == '__main__':
    raise SystemExit(main())
