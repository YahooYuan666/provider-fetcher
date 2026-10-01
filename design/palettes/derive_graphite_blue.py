"""Derive L2 for the chosen graphite_blue palette using the skill's own implementation."""
import json
import sys
from pathlib import Path

SKILL_SCRIPTS = Path.home() / ".agents" / "skills" / "ui-color-system" / "scripts"
sys.path.insert(0, str(SKILL_SCRIPTS))
import validate_palettes as vp  # noqa: E402

tokens_doc = json.loads(Path(__file__).with_name("graphite-blue.tokens.json").read_text(encoding="utf-8"))
tokens = tokens_doc["tokens"]
missing = [name for name in vp.L1 if name not in tokens]
assert not missing, f"missing L1: {missing}"
full = vp.derive(tokens)

# 逐套门禁（与 validate_palettes.check 的单套逻辑一致）
failures = []
panel, bg, sidebar = (vp.luminance(tokens[k]) for k in ("panel", "bg", "sidebar"))
if not (panel > bg > sidebar):
    failures.append(f"elevation failed: panel={panel:.4f} bg={bg:.4f} sidebar={sidebar:.4f}")
if vp.luminance(tokens["log_bg"]) > bg:
    failures.append("log_bg above bg")
if not bg < 0.12:
    failures.append(f"dark bg luminance {bg:.4f} not < 0.12")
for fg in ("text", "muted"):
    for surface in ("bg", "panel", "sidebar", "log_bg", "selected_bg"):
        ratio = vp.contrast(full[fg], full[surface])
        if ratio < 4.5:
            failures.append(f"{fg} on {surface} = {ratio:.2f}:1")
for surface in ("primary", "primary_hover"):
    ratio = vp.contrast(tokens["primary_text"], tokens[surface])
    if ratio < 4.5:
        failures.append(f"primary_text on {surface} = {ratio:.2f}:1")
for role in ("success", "warning", "error", "info"):
    for surface in ("panel", f"{role}_soft"):
        ratio = vp.contrast(full[f"{role}_text"], full[surface])
        if ratio < 4.5:
            failures.append(f"{role}_text on {surface} = {ratio:.2f}:1")

out = {"key": tokens_doc["key"], "mode": tokens_doc["mode"], "name": tokens_doc["name"], "l1": tokens, "l2": {}}
for key, value in full.items():
    if key not in tokens:
        out["l2"][key] = value
Path(__file__).with_name("graphite-blue.full.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

print("graphite_blue gates:", "PASS" if not failures else "FAIL")
for failure in failures:
    print("-", failure)
print(json.dumps(out["l2"], indent=1))
