"""Insert the Spotify + email snippets into main.qml before the MINI MODE section."""
from pathlib import Path

root = Path(r"c:\Users\pushan.mukherjee\Downloads\aitest\alana")
qml_path = root / "src/app/ui/qml/main.qml"
a = (root / "_snippet_a.txt").read_text(encoding="utf-8").rstrip("\n")
b = (root / "_snippet_b.txt").read_text(encoding="utf-8").rstrip("\n")
c = (root / "_snippet_c.txt").read_text(encoding="utf-8").rstrip("\n")

text = qml_path.read_text(encoding="utf-8")
marker = "// MINI MODE"
idx = text.find(marker)
if idx == -1:
    raise SystemExit("marker not found")

insert = "\n\n    " + a + "\n\n    " + b + "\n\n    " + c + "\n\n    "
new_text = text[:idx] + insert + text[idx:]
qml_path.write_text(new_text, encoding="utf-8")
print("inserted spotify+email panels")