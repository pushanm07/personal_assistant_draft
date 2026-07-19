import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src.actions.web import get_context
except ModuleNotFoundError:
    from actions.web import get_context

question = " ".join(sys.argv[1:]).strip()
if not question:
    if not sys.stdin.isatty():
        question = sys.stdin.read().strip()
    else:
        question = input("Ask me something: ").strip()

print("\nSearching...\n")

context = get_context(question)

print(context)
