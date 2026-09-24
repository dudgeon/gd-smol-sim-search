#!/usr/bin/env bash
# setup.sh — install the semantic-search skill for Claude Code.
#
# Run this in your own terminal (it needs the network; nothing else does).
# It is idempotent: re-running only verifies what is already there.
#
#   ./setup.sh                      install (copies the skill, downloads the default model)
#   ./setup.sh --model qwen3-0.6b   also install another model (repeatable)
#   ./setup.sh --link               dev mode: symlink the skill to this repo
#   ./setup.sh --update             refresh packages and skill files, keep models
#   ./setup.sh --runtime-dir DIR    put the runtime (uv, Python, venv, models) in DIR
#   ./setup.sh --uninstall [--yes]  remove the skill and its runtime
set -euo pipefail

# --- pins -------------------------------------------------------------------------
UV_VERSION="0.12.18"
UV_SHA256_aarch64_apple_darwin="cf40e0c6a202190ccd9e0406dcfdd5b2d6668a9a5c779b17948963df32aafe5b"
# Linux is for development of this repo only (see CLAUDE.md); not a supported target.
UV_SHA256_x86_64_unknown_linux_gnu="89eadd7c76fc063887959510d5ba0ab1264dfd5f1143b925ddb73021a40acf16"
PYTHON_VERSION="3.12.14"
MIN_MACOS_MAJOR=14   # torch 2.14 wheels are macosx_14_0_arm64

# --- paths ------------------------------------------------------------------------
REPO_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="$REPO_DIR/skills/semantic-search"
SKILLS_HOME="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
SKILL_DEST="$SKILLS_HOME/semantic-search"
LINK_RUNTIME_DEFAULT="${XDG_DATA_HOME:-$HOME/.local/share}/semantic-search/runtime"
REGISTRY="$SKILL_SRC/models.json"
LOCKFILE="${SEM_SETUP_LOCKFILE:-$SKILL_SRC/requirements.lock}"

# --- args -------------------------------------------------------------------------
MODELS=()
MODE="copy"
UPDATE=0
UNINSTALL=0
ASSUME_YES=0
RUNTIME_DIR=""
SELF_TEST=1
while [ $# -gt 0 ]; do
  case "$1" in
    --model) [ $# -ge 2 ] || { echo "--model needs a key" >&2; exit 2; }; MODELS+=("$2"); shift 2 ;;
    --model=*) MODELS+=("${1#*=}"); shift ;;
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
  UV_TRIPLE="aarch64-apple-darwin"
  mac_major="$(sw_vers -productVersion | cut -d. -f1)"
  [ "$mac_major" -ge "$MIN_MACOS_MAJOR" ] || die "macOS $MIN_MACOS_MAJOR or later is required (found $(sw_vers -productVersion))."
elif [ "${SEM_SETUP_ALLOW_LINUX:-}" = 1 ] && [ "$OS" = "Linux" ] && [ "$ARCH" = "x86_64" ]; then
  UV_TRIPLE="x86_64-unknown-linux-gnu"
  warn "Linux dev mode (SEM_SETUP_ALLOW_LINUX=1): unsupported for real use"
else
  die "semantic-search supports macOS on Apple Silicon only (found $OS $ARCH)."
fi
for tool in curl shasum tar; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    if [ "$tool" = shasum ] && command -v sha256sum >/dev/null 2>&1 && [ "$OS" = Linux ]; then continue; fi
    die "required tool '$tool' not found"
  fi
done
sha256_of() { if command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | cut -d' ' -f1; else sha256sum "$1" | cut -d' ' -f1; fi; }

for k in ${MODELS[@]+"${MODELS[@]}"}; do
  grep -q "^    \"$k\": {" "$REGISTRY" && [ "$k" != hash-test ] \
    || die "unknown model '$k' (see skills/semantic-search/models.json)"
done
DEFAULT_MODEL="$(sed -n 's/^  "default": "\(.*\)",$/\1/p' "$REGISTRY")"
[ -n "$DEFAULT_MODEL" ] || die "could not read default model from $REGISTRY"
WANT_MODELS=("$DEFAULT_MODEL")
for k in ${MODELS[@]+"${MODELS[@]}"}; do
  [[ " ${WANT_MODELS[*]} " == *" $k "* ]] || WANT_MODELS+=("$k")
done

# --- 2. install locations ---------------------------------------------------------
if [ -z "$RUNTIME_DIR" ]; then
  if [ "$UPDATE" = 1 ] || [ -e "$SKILL_DEST" ]; then RUNTIME_DIR="$(existing_runtime || true)"; fi
fi
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
if [ -n "$avail_kb" ] && [ "$avail_kb" -lt $((3 * 1024 * 1024)) ]; then
  warn "less than 3 GB free at $RUNTIME_DIR ($((avail_kb / 1024)) MB); the runtime needs about 1.5 GB plus models"
fi
ok "skill:   $SKILL_DEST ($MODE)"
ok "runtime: $RUNTIME_DIR"

export UV_CACHE_DIR="${SEM_SETUP_UV_CACHE_DIR:-$RUNTIME_DIR/.setup-cache/uv}"
export UV_PYTHON_INSTALL_DIR="$RUNTIME_DIR/python"
export UV_PYTHON_PREFERENCE=only-managed
export UV_NO_CONFIG=1 UV_NO_PROGRESS=1 UV_PYTHON_DOWNLOADS=manual
unset UV_NATIVE_TLS 2>/dev/null || true

# --- 3. uv ------------------------------------------------------------------------
step "uv $UV_VERSION"
UV="$RUNTIME_DIR/bin/uv"
if [ -x "$UV" ] && [ "$("$UV" --version 2>/dev/null | awk '{print $2}')" = "$UV_VERSION" ]; then
  ok "present"
else
  var="UV_SHA256_${UV_TRIPLE//-/_}"
  want="${!var}"
  tmpd="$(mktemp -d)"
  url="https://github.com/astral-sh/uv/releases/download/$UV_VERSION/uv-$UV_TRIPLE.tar.gz"
  curl --fail --location --silent --show-error --retry 3 -o "$tmpd/uv.tgz" "$url"
  got="$(sha256_of "$tmpd/uv.tgz")"
  [ "$got" = "$want" ] || die "uv checksum mismatch: got $got, want $want"
  tar -xzf "$tmpd/uv.tgz" -C "$tmpd"
  mkdir -p "$RUNTIME_DIR/bin"
  install -m 0755 "$tmpd/uv-$UV_TRIPLE/uv" "$UV"
  rm -rf "$tmpd"
  ok "downloaded and verified (sha256 $want)"
fi

# --- 4. Python --------------------------------------------------------------------
step "Python $PYTHON_VERSION"
# --no-bin: don't put python shims in ~/.local/bin; nothing outside the runtime dir
UV_PYTHON_DOWNLOADS=automatic "$UV" python install --quiet --no-bin "$PYTHON_VERSION"
ok "managed by uv in $RUNTIME_DIR/python (download verified by uv)"

# --- 5. venv + packages -------------------------------------------------------------
step "Python packages"
VENV="$RUNTIME_DIR/venv"
PY="$VENV/bin/python"
if [ ! -x "$PY" ] || [ "$("$PY" -c 'import platform; print(platform.python_version())' 2>/dev/null)" != "$PYTHON_VERSION" ]; then
  rm -rf "$VENV"
  "$UV" venv --quiet --python "$PYTHON_VERSION" "$VENV"
fi
"$UV" pip sync --quiet --python "$PY" --require-hashes --compile-bytecode "$LOCKFILE"
ok "synced from $(basename "$LOCKFILE") (hashes required)"

# --- 6. models --------------------------------------------------------------------
step "Models: ${WANT_MODELS[*]}"
mkdir -p "$RUNTIME_DIR/models"
for key in "${WANT_MODELS[@]}"; do
  if [ -n "${SEM_SETUP_MODELS_FROM:-}" ]; then
    # offline/mirror install: copy a pre-downloaded model whose revision matches the pin
    src="$SEM_SETUP_MODELS_FROM/$key"
    want_rev="$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['models'][sys.argv[2]]['revision'])" "$REGISTRY" "$key")"
    [ "$(cat "$src/.sem-revision" 2>/dev/null)" = "$want_rev" ] || die "$src/.sem-revision does not match pinned revision $want_rev"
    if [ "$(cat "$RUNTIME_DIR/models/$key/.sem-revision" 2>/dev/null)" != "$want_rev" ]; then
      rm -rf "$RUNTIME_DIR/models/$key"; cp -R "$src" "$RUNTIME_DIR/models/$key"
    fi
    ok "$key copied from $SEM_SETUP_MODELS_FROM"
    continue
  fi
  HF_HOME="$RUNTIME_DIR/.setup-cache/hf" HF_HUB_DISABLE_TELEMETRY=1 \
    "$PY" "$REPO_DIR/tools/fetch_model.py" "$REGISTRY" "$key" "$RUNTIME_DIR/models" \
    || die "model download failed for $key"
done
rm -rf "$RUNTIME_DIR/.setup-cache/hf"

# --- 7/9. install skill files (copy: staged + atomic swap; link: symlink) -----------------
step "Skill files"
compile_pkg() { "$PY" -m compileall -q "$1/sem" >/dev/null; }
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
  STAGE="$(mktemp -d "$(dirname "$SKILLS_HOME")/.semantic-search-stage.XXXXXX")"
  chmod 0755 "$STAGE"
  cleanup_stage() { rm -rf "$STAGE"; }
  trap cleanup_stage EXIT
  for item in SKILL.md references bin sem models.json requirements.lock; do
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
    OLD="$(dirname "$SKILLS_HOME")/.semantic-search-old.$$"
    if [ -L "$SKILL_DEST" ]; then rm -f "$SKILL_DEST";
    elif [ -e "$SKILL_DEST" ]; then mv "$SKILL_DEST" "$OLD"; fi
    mv "$STAGE" "$SKILL_DEST"
    rm -rf "$OLD"
    ok "installed to $SKILL_DEST"
  fi
  trap - EXIT
  rm -rf "$STAGE"
fi
rm -rf "$RUNTIME_DIR/.setup-cache"

# --- 8. install.json --------------------------------------------------------------
step "Recording install"
"$PY" - "$RUNTIME_DIR" "$SKILL_DEST" "$MODE" "$UV_VERSION" "$REGISTRY" <<'EOF'
import json, sys, time
from importlib import metadata
from pathlib import Path
rt, skill, mode, uv, registry = sys.argv[1:6]
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
    "uv": uv,
    "python": sys.version.split()[0],
    "packages": {p: metadata.version(p) for p in ("torch", "sentence-transformers", "transformers", "numpy", "pypdf", "huggingface-hub")},
    "models": models,
    "default_model": json.loads(Path(registry).read_text())["default"],
}
tmp = f.with_suffix(".tmp")
tmp.write_text(json.dumps(info, indent=2) + "\n")
tmp.replace(f)
EOF
ok "$RUNTIME_DIR/install.json"

# --- 10. self-test ----------------------------------------------------------------
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
    "$PY" - "$T" <<'EOF'
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
print(f"    indexed {idx['chunks_embedded']} chunks from {idx['files_seen']} files on {idx['device']} "
      f"in {idx['seconds']}s; search and dupes returned the expected results")
EOF
  ) || die "self-test failed (see above)"
  ok "passed"
  grep -E '^  (device|models):' "$T/doctor.txt" | sed 's/^/  /' || true
fi

# --- 11. next steps ---------------------------------------------------------------
cat <<EOF

${G}${B}semantic-search is installed.${N}

  Skill:    $SKILL_DEST
  Runtime:  $RUNTIME_DIR
  Command:  $SEM

Start a new Claude Code session in any project and ask for semantic search,
similar files, near-duplicates, clusters, etc. Claude finds the skill by itself.

No sandbox settings changes are needed: sem only writes to ./.sem in the
project and never uses the network.

Optional: if you don't run with sandbox auto-allow, you can pre-approve the
command by adding this permission rule to ~/.claude/settings.json yourself:
    "Bash($SEM:*)"

Add a model:  ./setup.sh --model qwen3-0.6b
Uninstall:    ./setup.sh --uninstall
EOF
