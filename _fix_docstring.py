"""Fix the mangled docstring in llm.py."""
path = r"src\brain\llm.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Fix the broken docstring delimiters ("""""" -> """)
old_open = '""""""Shared'
new_open = '"""Shared'
old_close = '""""""'
new_close = '"""'

if old_open in content:
    content = content.replace(old_open, new_open, 1)
    print("Fixed opening delimiter")
else:
    print("Opening delimiter not found")

if old_close in content:
    content = content.replace(old_close, new_close, 1)
    print("Fixed closing delimiter")
else:
    print("Closing delimiter not found")

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Done")
