"""Create a portable review archive; exclude runtime state and credentials."""
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"dist/ChainScope_Task1_source.zip"
with zipfile.ZipFile(OUT,"w",zipfile.ZIP_DEFLATED) as z:
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file(): continue
        rel=p.relative_to(ROOT)
        if any(part in {".git","__pycache__",".pytest_cache",".venv","runtime",".sites-runtime"} for part in rel.parts): continue
        if p.suffix in {".zip",".bundle",".pyc"} or p.name==".env": continue
        z.write(p,Path("industry-chain-terminal")/rel)
print(f"Source archive: {OUT.stat().st_size} bytes")
