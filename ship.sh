#!/usr/bin/env bash
#
# One command to test, commit and publish.
#
#   ./ship.sh "what changed"          test, commit everything, push
#   ./ship.sh "notes" --release 2.1.0 ...and cut a permanent v2.1.0 release
#   ./ship.sh --dry                   just run the tests, change nothing
#
# Pushing is deliberately a thing you run, not something that happens behind
# your back — so nothing leaves this machine until you type the command.

set -euo pipefail
cd "$(dirname "$0")"

BOLD=$'\033[1m'; DIM=$'\033[2m'; GREEN=$'\033[32m'; RED=$'\033[31m'
YELLOW=$'\033[33m'; RESET=$'\033[0m'

step() { printf "\n%s==>%s %s%s\n" "$BOLD" "$RESET" "$1" "$RESET"; }
ok()   { printf "%s  ok%s  %s\n" "$GREEN" "$RESET" "$1"; }
die()  { printf "\n%serror:%s %s\n\n" "$RED" "$RESET" "$1" >&2; exit 1; }

MESSAGE=""
VERSION=""
DRY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --release) VERSION="${2:-}"; shift 2 ;;
    --dry)     DRY=1; shift ;;
    -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)         MESSAGE="$1"; shift ;;
  esac
done

# ---------------------------------------------------------------- tests ----
step "Running the test suite"
if ! python3 -m pytest tests/ -q --no-header 2>&1 | tail -3; then
  die "tests failed — nothing was committed or pushed"
fi
ok "tests passed"

if [ "$DRY" = "1" ]; then
  printf "\n%sdry run — stopping here%s\n\n" "$DIM" "$RESET"
  exit 0
fi

# --------------------------------------------------------------- commit ----
if [ -z "$(git status --porcelain)" ]; then
  ok "no local changes to commit"
else
  [ -n "$MESSAGE" ] || die "give me a commit message:  ./ship.sh \"what changed\""
  step "Committing"
  git add -A
  git status --short | sed 's/^/    /'
  git commit -q -m "$MESSAGE"
  ok "committed"
fi

# ----------------------------------------------------------------- push ----
step "Pushing to GitHub"
BRANCH="$(git rev-parse --abbrev-ref HEAD)"
git push -u origin "$BRANCH"
ok "pushed to $BRANCH"

# -------------------------------------------------------------- release ----
if [ -n "$VERSION" ]; then
  TAG="v${VERSION#v}"
  step "Tagging $TAG"

  # keep the package version and the tag honest with each other
  if ! grep -q "__version__ = \"${VERSION#v}\"" kenansautoclicker/__init__.py; then
    printf "%s  note%s  bumping __version__ to %s\n" "$YELLOW" "$RESET" "${VERSION#v}"
    python3 - "$VERSION" <<'PY'
import re, sys
v = sys.argv[1].lstrip("v")
p = "kenansautoclicker/__init__.py"
s = open(p, encoding="utf-8").read()
s = re.sub(r'__version__ = "[^"]+"', f'__version__ = "{v}"', s)
open(p, "w", encoding="utf-8").write(s)
PY
    git add kenansautoclicker/__init__.py
    git commit -q -m "Bump version to ${VERSION#v}"
    git push -q origin "$BRANCH"
  fi

  git rev-parse "$TAG" >/dev/null 2>&1 && die "tag $TAG already exists"
  git tag -a "$TAG" -m "${MESSAGE:-Release $TAG}"
  git push origin "$TAG"
  ok "tagged and pushed $TAG"
fi

# --------------------------------------------------------------- report ----
REMOTE="$(git remote get-url origin | sed 's/\.git$//;s#git@github.com:#https://github.com/#')"
printf "\n%sDone.%s GitHub is now testing and building.\n\n" "$BOLD" "$RESET"
printf "  build     %s/actions\n" "$REMOTE"
printf "  downloads %s/releases\n" "$REMOTE"
if [ -n "$VERSION" ]; then
  printf "\n  Your %sv%s%s release appears once the build finishes (~3 min).\n" \
         "$BOLD" "${VERSION#v}" "$RESET"
else
  printf "\n  The %slatest%s pre-release refreshes automatically (~3 min).\n" \
         "$BOLD" "$RESET"
fi
printf "\n"
