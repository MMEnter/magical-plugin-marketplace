#!/usr/bin/env bash
# Report what changed in the tracked documentation pages since the last committed run.
#
#   diff_snapshots.sh <baseline-dir> <current-dir>
#
# Both directories hold flat <slug>.md files. Neither needs to be a git repository and
# neither needs a remote: the baseline is whatever this run read out of the workspace repo
# through the GitHub connector, and the current set is whatever this run just fetched.
# That is the whole reason this script no longer knows anything about git — the history
# lives in the repo, and reading it is the skill's job, not this script's.
#
# Exit code is always 0. A diff is a result, not an error.

set -uo pipefail

BASE="${1:-}"
CUR="${2:-}"

if [ -z "$BASE" ] || [ -z "$CUR" ]; then
  echo "usage: diff_snapshots.sh <baseline-dir> <current-dir>" >&2
  exit 0
fi

if [ ! -d "$CUR" ]; then
  echo "ERROR: current directory '$CUR' does not exist. Nothing was fetched this run." >&2
  exit 0
fi

# A missing or empty baseline directory is the first-run case, not a failure.
base_count=0
if [ -d "$BASE" ]; then
  base_count=$(find "$BASE" -maxdepth 1 -name '*.md' -type f 2>/dev/null | wc -l)
fi

if [ "$base_count" -eq 0 ]; then
  echo "NO_BASELINE: the workspace holds no committed snapshots — this is the first run."
  echo "Skip the doc-diff section of the brief and say so explicitly. Do not fabricate a"
  echo "baseline and do not describe this run's pages as additions."
  echo
  echo "Pages fetched this run:"
  find "$CUR" -maxdepth 1 -name '*.md' -type f -printf '  %f\n' 2>/dev/null | sort
  exit 0
fi

echo "=============================================="
echo " DOCUMENTATION DIFF"
echo " baseline: $base_count committed page(s)"
echo " current:  this run, $(date -u +%Y-%m-%d)"
echo "=============================================="
echo

changed=0
unchanged=0
new=0
missing=0

# Pages present this run: changed, unchanged, or newly tracked.
while IFS= read -r f; do
  slug="$(basename "$f")"
  if [ -f "$BASE/$slug" ]; then
    if cmp -s "$BASE/$slug" "$f"; then
      unchanged=$((unchanged + 1))
      continue
    fi
    changed=$((changed + 1))
    added=$(diff "$BASE/$slug" "$f" | grep -c '^>' || true)
    removed=$(diff "$BASE/$slug" "$f" | grep -c '^<' || true)
    echo "### CHANGED: $slug  (+$added / -$removed lines)"
    echo '```diff'
    diff -u "$BASE/$slug" "$f" | tail -n +3
    echo '```'
    echo
  else
    new=$((new + 1))
    echo "### NEWLY TRACKED: $slug"
    echo "No prior copy in the workspace. This is a page added to the tracked set, not"
    echo "necessarily a documentation change. It becomes diffable from next run."
    echo
  fi
done < <(find "$CUR" -maxdepth 1 -name '*.md' -type f | sort)

# Pages in the baseline that this run did not produce. Almost always a failed fetch.
while IFS= read -r f; do
  slug="$(basename "$f")"
  if [ ! -f "$CUR/$slug" ]; then
    missing=$((missing + 1))
    echo "### NOT FETCHED THIS RUN: $slug"
    echo "Present in the baseline, absent now — the fetch failed, or the page was removed"
    echo "upstream. Verify which before reporting it as news, and do NOT include this slug"
    echo "in the commit: leaving the committed copy alone is what keeps next week's"
    echo "baseline honest."
    echo
  fi
done < <(find "$BASE" -maxdepth 1 -name '*.md' -type f | sort)

if [ "$changed" -eq 0 ] && [ "$new" -eq 0 ] && [ "$missing" -eq 0 ]; then
  echo "NO DOCUMENTATION CHANGES since the baseline."
  echo
fi

echo "----------------------------------------------"
echo "SUMMARY: $changed changed, $unchanged unchanged, $new newly tracked, $missing not fetched"
echo "----------------------------------------------"
