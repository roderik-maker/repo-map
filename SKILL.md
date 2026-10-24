---
name: repo-map
description: >
  Build an interactive size map of any git repo as one HTML page: a foldable GitHub-style
  file tree with lines and characters per folder and file, a treemap, language mix, a
  draggable history timeline showing how each folder and file grew, and a right-click menu
  to open files in an editor. Use whenever the user wants to see a repo's structure, file
  tree, size, lines of code per folder, where the complexity sits, which scripts or folders
  are biggest, when something got bloated, or a repo overview/dashboard, even if they never
  say "repo map".
argument-hint: "[folder with or containing a repo] [--ref REF] [--hide PATH ...]"
---

# Repo map

```bash
python3 ~/.claude/skills/repo-map/scripts/gen.py <folder> --out <scratchpad>/<name>-repo-map.html
```

Then publish with the Artifact tool exactly as the script's last line says (`publish: …`), and report from its output. Nothing else to decide.

- `<folder>` is the repo, or any folder up to `--depth` (3) levels above one. Untracked local files beside the repos are ignored; linked worktrees collapse into their main repo.
- Several repos found: the script lists them and exits 2. Ask the user which, or pick the one they named, and rerun.
- Auto-handled, so no checks needed: stale `origin/HEAD` (falls back to `HEAD`, prints a `NOTE`), lock/generated/vendored/minified/giant data files (hidden at first load; the script prints each with its reason). Wrong hide: rerun with `--hide PATH` or `--no-auto-hide`.
- Report: `shown` totals, markdown share, biggest folders and files, what started hidden and why, ref + sha, and the history span. Say so if a `NOTE` is printed. Uncommitted work is not counted.
- Reads git objects only, never the working tree, never writes to the repo, never fetches. If `origin/*` may be stale, say so.
- Without the Artifact tool: `open <file>`. Don't use `SendUserFile` or the desktop browser pane on a `file://` path: scripts are off there and the page stays empty.
- What leaves the machine: paths, counts, commit subjects (`--no-subjects` drops them) and the checkout path. Never file contents. The artifact is private until shared.

Flags: `--ref`, `--hide PATH` (repeatable, folders work), `--no-auto-hide`, `--snaps N` (timeline points, default 150, 1 = no history), `--no-subjects`, `--depth N`.

## Page features (for "can it…")

- Tree: folders fold open; lines and characters per row with bars (share of repo or of folder), segments = language mix. Sort by size, name or biggest change.
- Treemap: size by lines or characters. Click a block to find it in the tree; Alt/⌥-click hides it.
- Timeline: drag the chart or use ← → to scrub; everything redraws at that commit. Play animates. "Biggest jumps" links jump to the commits where the repo grew most. Hovering any row or block shows that item's own size-over-time sparkline.
- Compare: "Show change vs" Previous, First or a point picked with Shift-click on the chart. Rows show +/− change and new/deleted tags; "Biggest change" sorts by it.
- Right-click a file or folder: copy its path, or copy a shell command that opens it in VS Code, Finder or the default text editor. The path is the working copy at the checkout, not the commit shown. There are no direct "open in editor" links: the Claude desktop artifact viewer blocks editor URL schemes (navigating to `vscode://` blanks the page, a hidden iframe does nothing), so to open a file from the session use the `open_in_editor` / `reveal_path` tools.
- Filters: Markdown include / exclude / only; hide any file or folder with the eye button (chips restore them; hover a chip for why it was hidden); expand/collapse all.
- State (filters, open folders, hidden items, compare mode) persists per viewer in localStorage, keyed by repo name. The timeline always opens at the latest commit.
- History is path-based: a renamed or moved file shows as removed from the old folder and added to the new one. Snapshots are evenly spaced along the first-parent commit line.

## Customise

- Colours: the 7 biggest languages by lines get the validated categorical palette in rank order; Markdown always keeps a slot. The rest fold into grey "Other".
- Extension to language: `LANG` / `NAMES` in gen.py. Auto-hide rules: `GENERATED`, `GEN_SUFFIX`, `GEN_HEAD`, `VENDORED`, `DATA_EXT`.
