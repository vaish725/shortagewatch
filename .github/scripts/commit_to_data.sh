#!/usr/bin/env bash
# Commit staged-in-place changes under data-branch/ to the data branch, retrying if another job pushed first.
# Usage: commit_to_data.sh "<commit message>" <path> [<path>...]   (paths relative to data-branch/)
set -euo pipefail
msg="$1"; shift
cd data-branch
git config user.name "shortagewatch-bot"
git config user.email "shortagewatch-bot@users.noreply.github.com"
git add "$@"
# A same-day rerun with identical data produces no diff
git diff --cached --quiet && exit 0
git commit -q -m "$msg"
for attempt in 1 2 3 4 5; do
  git push -q origin data && exit 0
  git pull -q --rebase origin data
done
echo "push to data branch failed after retries" >&2
exit 1
