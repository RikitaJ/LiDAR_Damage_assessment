# Git protocol: commit and push after every change

For every coding agent working in this repo (Cursor, Claude Code or any other) and for both of us. It adds to ground rules 7–9 in `docs/ASSESSMENT_BRIEF.md`; where they differ, the brief wins.

## When you start a session

1. Run `git status`. If there are uncommitted changes you didn't make, stop and ask your human before touching them.
2. Run `git pull --rebase`.
3. Read `docs/ASSESSMENT_BRIEF.md` and `docs/GAP_REPORT.md`.

## After every change that works

Commit and push straight away: one logical change, one commit, one push. Never save up a session's work for one big commit, because Part 5 of the spec reads the history.

1. Check exactly what changed: `git status`, `git diff`.
2. Stage files by name: `git add <path> ...`. Never use `git add -A` or `git add .`, because extracted captures (`depth/`, `confidence/`, `*.mp4`) are not gitignored.
3. Never commit raw captures, model weights, `.env` or run outputs (`out/`, `.cache/`). They are fetched by `scripts/fetch_*.py` (brief rule 7).
4. Before committing code, run `pytest -q` with `MPLBACKEND=Agg` set until the rendering backend is fixed. Don't push failing tests. If you must push unfinished work, start the message with `WIP:`.
5. Message: a short imperative summary of what changed (72 characters at most), then a line or two on why. Commit under your own git identity (brief rule 8). If your tool adds a co-author trailer, keep it.
6. Run `git pull --rebase`, then `git push`. If the push is rejected, pull again, re-run the tests and push. Never force-push, and never amend or rebase commits that are already pushed.

## Ownership and conflicts

- The Builder owns `pipeline/`. The Tester owns `eval/`, `data/`, `scripts/` and `docs/`. Schemas change only by agreement (brief rule 9).
- If a rebase conflicts in the other person's files, stop and ask your human. Never resolve a conflict by discarding their work.

## End of session

`git status` is clean and `git log origin/main..HEAD` prints nothing. Tell your human which commits you pushed.
