#!/usr/bin/env bash
# setup.sh — install the smol-sim-search skill for Claude Code.
#
# Fully offline: everything it installs (Python, packages, model) is vendored in
# this repo under vendor/ and checked against vendor/SHA256SUMS first. It never
# uses the network. Idempotent: re-running only verifies what is already there.
#
#   ./setup.sh                      install (copies the skill to ~/.claude/skills)
#   ./setup.sh --link               dev mode: symlink the skill to this repo
#   ./setup.sh --update             reinstall the runtime and skill files from vendor/
#   ./setup.sh --runtime-dir DIR    put the runtime (Python, packages, model) in DIR
#   ./setup.sh --uninstall [--yes]  remove the skill and its runtime
set -euo pipefail

MIN_MACOS_MAJOR=14   # the vendored onnxruntime and numpy wheels are macosx_14_0_arm64

# --- paths ------------------------------------------------------------------------
REPO_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="$REPO_DIR/skills/smol-sim-search"
SKILLS_HOME="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
SKILL_DEST="$SKILLS_HOME/smol-sim-search"
LINK_RUNTIME_DEFAULT="${XDG_DATA_HOME:-$HOME/.local/share}/smol-sim-search/runtime"
VENDOR="${SEM_SETUP_VENDOR_DIR:-$REPO_DIR/vendor}"

# --- args -------------------------------------------------------------------------
MODE="copy"
UPDATE=0
UNINSTALL=0
ASSUME_YES=0
RUNTIME_DIR=""
SELF_TEST=1
while [ $# -gt 0 ]; do
  case "$1" in
    --link) MODE="link"; shift ;;
    --update) UPDATE=1; shift ;;
    --uninstall) UNINSTALL=1; shift ;;
    --yes|-y) ASSUME_YES=1; shift ;;
    --runtime-dir) [ $# -ge 2 ] || { echo "--runtime-dir needs a path" >&2; exit 2; }; RUNTIME_DIR="$2"; shift 2 ;;
    --runtime-dir=*) RUNTIME_DIR="${1#*=}"; shift ;;
    --no-self-test) SELF_TEST=0; shift ;;
    -h|--help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1 (see --help)" >&2; exit 2 ;;
  esac
done

if [ -t 1 ]; then B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; N=$'\033[0m'; else B=; G=; Y=; R=; N=; fi
step() { printf '%s==>%s %s\n' "$B" "$N" "$*"; }
ok()   { printf '    %sok%s %s\n' "$G" "$N" "$*"; }
warn() { printf '    %swarning:%s %s\n' "$Y" "$N" "$*" >&2; }
die()  { printf '%serror:%s %s\n' "$R" "$N" "$*" >&2; exit 1; }

# Resolve where an existing install keeps its runtime (for --update / --uninstall).
existing_runtime() {
  local d
  for d in "$SKILL_DEST/runtime" \
           "$( [ -f "$SKILL_DEST/.runtime-path" ] && cat "$SKILL_DEST/.runtime-path" || true)" \
           "$LINK_RUNTIME_DEFAULT"; do
    if [ -n "$d" ] && [ -f "$d/install.json" ]; then echo "$d"; return 0; fi
  done
  return 1
}

# --- uninstall --------------------------------------------------------------------
if [ "$UNINSTALL" = 1 ]; then
  targets=()
  [ -e "$SKILL_DEST" ] || [ -L "$SKILL_DEST" ] && targets+=("$SKILL_DEST")
  rt="$(existing_runtime || true)"
  [ -n "$RUNTIME_DIR" ] && [ -d "$RUNTIME_DIR" ] && rt="$RUNTIME_DIR"
  if [ -n "$rt" ] && [[ "$rt" != "$SKILL_DEST"/* ]]; then targets+=("$rt"); fi
  [ -f "$SKILL_SRC/.runtime-path" ] && targets+=("$SKILL_SRC/.runtime-path")
  if [ ${#targets[@]} -eq 0 ]; then echo "Nothing to uninstall."; exit 0; fi
  echo "This will remove:"; printf '  %s\n' "${targets[@]}"
  echo "Your project indexes (./.sem folders) are left alone."
  if [ "$ASSUME_YES" != 1 ]; then
    read -r -p "Proceed? [y/N] " ans
    case "$ans" in y|Y|yes|YES) ;; *) echo "Aborted."; exit 1 ;; esac
  fi
  for t in "${targets[@]}"; do rm -rf "$t"; done
  rmdir "$(dirname "$LINK_RUNTIME_DEFAULT")" 2>/dev/null || true
  # also clean compiled bytecode that --link mode left in the repo
  find "$SKILL_SRC" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true
  echo "Uninstalled."
  exit 0
fi

# --- 1. preflight -----------------------------------------------------------------
step "Preflight"
OS="$(uname -s)"; ARCH="$(uname -m)"
if [ "$OS" = "Darwin" ] && [ "$ARCH" = "arm64" ]; then
  HOST_PLATFORM="macos-arm64"
  mac_major="$(sw_vers -productVersion | cut -d. -f1)"
  [ "$mac_major" -ge "$MIN_MACOS_MAJOR" ] || die "macOS $MIN_MACOS_MAJOR or later is required (found $(sw_vers -productVersion))."
elif [ "${SEM_SETUP_ALLOW_LINUX:-}" = 1 ] && [ "$OS" = "Linux" ] && [ "$ARCH" = "x86_64" ]; then
  HOST_PLATFORM="linux-x86_64"
  warn "Linux dev mode (SEM_SETUP_ALLOW_LINUX=1): unsupported for real use"
else
  die "smol-sim-search supports macOS on Apple Silicon only (found $OS $ARCH)."
fi
if command -v shasum >/dev/null 2>&1; then SHA256="shasum -a 256"
elif command -v sha256sum >/dev/null 2>&1; then SHA256="sha256sum"
else die "required tool 'shasum' not found"; fi
command -v tar >/dev/null 2>&1 || die "required tool 'tar' not found"
sha256_of() { $SHA256 "$1" | cut -d' ' -f1; }

# --- 2. verify vendor/ --------------------------------------------------------------
step "Verifying vendored files"
[ -f "$VENDOR/SHA256SUMS" ] || die "$VENDOR/SHA256SUMS is missing. Re-clone the repository (vendor/ holds the runtime)."
grep -q "\"platform\": \"$HOST_PLATFORM\"" "$VENDOR/PROVENANCE.json" \
  || die "vendor/ was built for another platform (see $VENDOR/PROVENANCE.json); this machine is $HOST_PLATFORM"
if ! check_out="$(cd "$VENDOR" && $SHA256 -c SHA256SUMS 2>&1)"; then
  echo "$check_out" | grep -v ': OK$' >&2
  die "vendored files failed checksum verification. Re-clone the repository."
fi
ok "$(grep -c . "$VENDOR/SHA256SUMS") files match SHA256SUMS"
VENDOR_STAMP="$(sha256_of "$VENDOR/SHA256SUMS")"

# --- 3. install locations ---------------------------------------------------------
if [ -z "$RUNTIME_DIR" ] && [ -e "$SKILL_DEST" ]; then RUNTIME_DIR="$(existing_runtime || true)"; fi
if [ -z "$RUNTIME_DIR" ]; then
  if [ "$MODE" = link ]; then RUNTIME_DIR="$LINK_RUNTIME_DEFAULT"; else RUNTIME_DIR="$SKILL_DEST/runtime"; fi
fi
case "$RUNTIME_DIR" in /*) ;; *) RUNTIME_DIR="$PWD/$RUNTIME_DIR" ;; esac
if [ "$MODE" = link ] && [[ "$RUNTIME_DIR" == "$SKILL_DEST"/* ]]; then
  die "an installed copy exists at $SKILL_DEST with its runtime inside it. Run ./setup.sh --uninstall first to switch to --link."
fi
if [ "$MODE" = link ] && [[ "$RUNTIME_DIR" == "$REPO_DIR"/* ]]; then
  die "--link keeps the runtime outside the repo; choose a --runtime-dir outside $REPO_DIR"
fi
if [ "$MODE" = copy ] && [ -L "$SKILL_DEST" ]; then
  echo "    replacing --link install with a copy"
fi
mkdir -p "$SKILLS_HOME" "$RUNTIME_DIR"
avail_kb="$(df -Pk "$RUNTIME_DIR" | awk 'NR==2 {print $4}')"
if [ -n "$avail_kb" ] && [ "$avail_kb" -lt $((1024 * 1024)) ]; then
  warn "less than 1 GB free at $RUNTIME_DIR ($((avail_kb / 1024)) MB); the runtime needs about 450 MB"
fi
ok "skill:   $SKILL_DEST ($MODE)"
ok "runtime: $RUNTIME_DIR"

PY="$RUNTIME_DIR/python/bin/python3"
STAMP_FILE="$RUNTIME_DIR/.vendor-stamp"

# --- 4. Python + packages ---------------------------------------------------------------
step "Python runtime and packages"
if [ "$UPDATE" != 1 ] && [ -x "$PY" ] && [ "$(cat "$STAMP_FILE" 2>/dev/null)" = "$VENDOR_STAMP" ]; then
  ok "up to date"
else
  rm -f "$STAMP_FILE"
  # leftovers from the earlier download-based installer
  rm -rf "$RUNTIME_DIR/venv" "$RUNTIME_DIR/bin" "$RUNTIME_DIR/.setup-cache"
  tmpd="$(mktemp -d "$RUNTIME_DIR/.python-new.XXXXXX")"
  py_tgz="$(ls "$VENDOR"/python/cpython-*.tar.gz | head -1)"
  tar -xzf "$py_tgz" -C "$tmpd"
  rm -rf "$RUNTIME_DIR/python"
  mv "$tmpd/python" "$RUNTIME_DIR/python"
  rm -rf "$tmpd"
  # offline install from the vendored wheels only: no index, no dependency resolution, no cache
  PIP_CONFIG_FILE=/dev/null "$PY" -I -m pip install --isolated --no-index --no-deps --no-cache-dir \
    --disable-pip-version-check --no-warn-script-location --root-user-action=ignore --quiet "$VENDOR"/wheels/*.whl
  # precompile: at runtime the runtime dir is read-only and bytecode writes are disabled
  "$PY" -I -m compileall -q -j 0 "$RUNTIME_DIR/python/lib" >/dev/null 2>&1 || true
  ok "Python $("$PY" -c 'import platform; print(platform.python_version())') + $(ls "$VENDOR"/wheels/*.whl | wc -l | tr -d ' ') wheels installed from vendor/"
fi

# --- 5. model -----------------------------------------------------------------------
step "Model"
model_src="$(ls -d "$VENDOR"/models/*/ | head -1)"; model_src="${model_src%/}"
MODEL_KEY="$(basename "$model_src")"
MODEL_DEST="$RUNTIME_DIR/models/$MODEL_KEY"
read_json() {  # read_json FILE KEY [KEY...] -> prints the nested value
  "$PY" -I -c 'import functools,json,sys; print(functools.reduce(lambda d, k: d[k], sys.argv[2:], json.load(open(sys.argv[1]))))' "$@"
}
REV="$(read_json "$model_src/model.json" revision)"
if [ "$UPDATE" != 1 ] && [ "$(cat "$MODEL_DEST/.sem-revision" 2>/dev/null)" = "$REV" ] \
   && [ "$(cat "$MODEL_DEST/.vendor-stamp" 2>/dev/null)" = "$VENDOR_STAMP" ]; then
  ok "$MODEL_KEY @ ${REV:0:10} up to date"
else
  stage="$RUNTIME_DIR/models/.$MODEL_KEY.new"
  rm -rf "$stage"; mkdir -p "$stage"
  for f in model.json tokenizer.json MODEL_CARD.md; do cp "$model_src/$f" "$stage/"; done
  # large files are split in the repo; join and check against Hugging Face's published SHA-256
  for part0 in "$model_src"/*.part00; do
    [ -e "$part0" ] || continue
    name="$(basename "$part0" .part00)"
    cat "$model_src/$name".part* > "$stage/$name"
    want="$(read_json "$model_src/model.json" files_sha256 "$name")"
    got="$(sha256_of "$stage/$name")"
    [ "$got" = "$want" ] || die "$name: joined file hash $got does not match upstream $want"
  done
  [ -f "$stage/model.onnx" ] || die "model.onnx missing from $model_src"
  echo "$REV" > "$stage/.sem-revision"
  echo "$VENDOR_STAMP" > "$stage/.vendor-stamp"
  rm -rf "$MODEL_DEST"
  mv "$stage" "$MODEL_DEST"
  ok "$MODEL_KEY @ ${REV:0:10} installed (model.onnx matches upstream SHA-256)"
fi
echo "$VENDOR_STAMP" > "$STAMP_FILE"

# --- 6. install skill files (copy: staged + atomic swap; link: symlink) -----------------
step "Skill files"
compile_pkg() { "$PY" -I -m compileall -q "$1/sem" >/dev/null; }
if [ "$MODE" = link ]; then
  compile_pkg "$SKILL_SRC"
  if [ "$RUNTIME_DIR" != "$LINK_RUNTIME_DEFAULT" ]; then
    echo "$RUNTIME_DIR" > "$SKILL_SRC/.runtime-path"
  else
    rm -f "$SKILL_SRC/.runtime-path"
  fi
  if [ -d "$SKILL_DEST" ] && [ ! -L "$SKILL_DEST" ]; then
    die "$SKILL_DEST is an installed copy; run ./setup.sh --uninstall first to switch to --link"
  fi
  ln -sfn "$SKILL_SRC" "$SKILL_DEST"
  ok "linked $SKILL_DEST -> $SKILL_SRC"
else
  # the stage lives next to (not inside) the skills dir so Claude Code never sees it as a skill
  STAGE="$(mktemp -d "$(dirname "$SKILLS_HOME")/.smol-sim-search-stage.XXXXXX")"
  chmod 0755 "$STAGE"
  cleanup_stage() { rm -rf "$STAGE"; }
  trap cleanup_stage EXIT
  for item in SKILL.md references bin sem models.json; do
    cp -R "$SKILL_SRC/$item" "$STAGE/"
  done
  find "$STAGE" -name __pycache__ -type d -prune -exec rm -rf {} +
  rm -f "$STAGE/.runtime-path"
  chmod 0755 "$STAGE/bin/sem"
  compile_pkg "$STAGE"
  if [ "$RUNTIME_DIR" != "$SKILL_DEST/runtime" ]; then echo "$RUNTIME_DIR" > "$STAGE/.runtime-path"; fi

  same=0
  if [ -d "$SKILL_DEST" ] && [ ! -L "$SKILL_DEST" ] && [ "$UPDATE" != 1 ]; then
    if diff -rq -x runtime -x __pycache__ "$STAGE" "$SKILL_DEST" >/dev/null 2>&1; then same=1; fi
  fi
  if [ "$same" = 1 ]; then
    ok "up to date"
  else
    # carry the runtime over when it lives inside the skill dir
    if [ -d "$SKILL_DEST/runtime" ] && [ ! -L "$SKILL_DEST" ]; then mv "$SKILL_DEST/runtime" "$STAGE/runtime"; fi
    OLD="$(dirname "$SKILLS_HOME")/.smol-sim-search-old.$$"
    if [ -L "$SKILL_DEST" ]; then rm -f "$SKILL_DEST";
    elif [ -e "$SKILL_DEST" ]; then mv "$SKILL_DEST" "$OLD"; fi
    mv "$STAGE" "$SKILL_DEST"
    rm -rf "$OLD"
    ok "installed to $SKILL_DEST"
  fi
  trap - EXIT
  rm -rf "$STAGE"
fi

# --- 7. install.json --------------------------------------------------------------
step "Recording install"
"$PY" -I - "$RUNTIME_DIR" "$SKILL_DEST" "$MODE" "$VENDOR_STAMP" <<'EOF'
import json, sys, time
from importlib import metadata
from pathlib import Path
rt, skill, mode, stamp = sys.argv[1:5]
rtp = Path(rt)
f = rtp / "install.json"
old = json.loads(f.read_text()) if f.exists() else {}
models = {}
for d in sorted((rtp / "models").iterdir()):
    m = d / ".sem-revision"
    if d.is_dir() and m.exists():
        models[d.name] = m.read_text().strip()
now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
info = {
    "installed": old.get("installed", now),
    "verified": now,
    "mode": mode,
    "skill_dir": skill,
    "runtime_dir": rt,
    "vendor_sha256sums": stamp,
    "python": sys.version.split()[0],
    "packages": {p: metadata.version(p) for p in ("onnxruntime", "tokenizers", "numpy", "pypdf")},
    "models": models,
}
tmp = f.with_suffix(".tmp")
tmp.write_text(json.dumps(info, indent=2) + "\n")
tmp.replace(f)
EOF
ok "$RUNTIME_DIR/install.json"

# --- 8. self-test -----------------------------------------------------------------
SEM="$SKILL_DEST/bin/sem"
if [ "$SELF_TEST" = 1 ]; then
  step "Self-test"
  T="$(mktemp -d)"
  trap 'rm -rf "$T"' EXIT
  cp -R "$REPO_DIR/tests/fixtures" "$T/fixtures"
  (
    cd "$T"
    "$SEM" doctor >"$T/doctor.txt" 2>&1 || { cat "$T/doctor.txt"; exit 1; }
    "$SEM" index fixtures --json >"$T/index.json" 2>"$T/index.err" || { cat "$T/index.err"; exit 1; }
    "$SEM" search "why are there two high tides every day" -k 3 --json >"$T/search.json" 2>/dev/null
    "$SEM" dupes --across-files-only --json >"$T/dupes.json" 2>/dev/null
    "$PY" -I - "$T" <<'EOF'
import json, sys
t = sys.argv[1]
idx = json.load(open(f"{t}/index.json"))
s = json.load(open(f"{t}/search.json"))
d = json.load(open(f"{t}/dupes.json"))
top = s["results"][0]["path"] if s["results"] else None
pairs = {tuple(sorted((p["a"]["path"], p["b"]["path"]))) for p in d["pairs"]}
errs = []
if idx["files_seen"] < 9:
    errs.append(f"indexed only {idx['files_seen']} fixture files")
if top != "fixtures/docs/tides.md":
    errs.append(f"search top hit was {top}, expected fixtures/docs/tides.md")
if ("fixtures/docs/tides.md", "fixtures/notes/moon-notes.md") not in pairs:
    errs.append("dupes did not find the planted near-duplicate pair")
if errs:
    print("\n".join("    FAIL " + e for e in errs)); sys.exit(1)
print(f"    indexed {idx['chunks_embedded']} chunks from {idx['files_seen']} files in {idx['seconds']}s; "
      "search and dupes returned the expected results")
EOF
  ) || die "self-test failed (see above)"
  ok "passed"
fi

# --- 9. next steps ----------------------------------------------------------------
cat <<EOF

${G}${B}smol-sim-search is installed.${N}

  Skill:    $SKILL_DEST
  Runtime:  $RUNTIME_DIR
  Command:  $SEM

Start a new Claude Code session in any project and ask for semantic search,
similar files, near-duplicates, clusters, etc. Claude finds the skill by itself.

Nothing was downloaded: everything came from vendor/ in this repository.
No sandbox settings changes are needed: sem only writes to ./.sem in the
project and never uses the network.

Optional: if you don't run with sandbox auto-allow, you can pre-approve the
command by adding this permission rule to ~/.claude/settings.json yourself:
    "Bash($SEM:*)"

Uninstall:    ./setup.sh --uninstall
EOF
