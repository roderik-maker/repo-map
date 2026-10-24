# repo-map

Turn any git repo into one interactive HTML page: a foldable file tree sized by lines and characters, a treemap, and a draggable timeline that shows how every folder and file grew over the repo's history.

A [Claude Code](https://claude.com/claude-code) skill, but the generator is a standalone Python script (stdlib only), so it works without Claude too.

## What you get

- **Tree:** folders fold open; every row shows lines and characters with bars (share of repo or of folder), split by language.
- **Treemap:** size by lines or characters. Click a block to find it in the tree.
- **Timeline:** drag the chart or press Play and the whole page redraws at that commit. "Biggest jumps" links go to the commits where the repo grew most. Hovering any row or block shows that item's own size-over-time sparkline.
- **Compare:** show change against the previous snapshot, the first, or a point you Shift-click. Rows get +/− deltas and new/deleted tags.
- **Filters:** Markdown include/exclude/only, hide any file or folder, sort by size, name or biggest change.
- **Right-click** a file or folder to copy its path, or a shell command that opens it in VS Code, Finder or your text editor.
- **Auto-hide:** lock files, generated files, vendored folders, minified bundles and giant data files start hidden (with the reason on hover) so they don't flatten every other bar.

## Install

Needs `python3` and `git`.

```bash
git clone https://github.com/<your-username>/repo-map ~/.claude/skills/repo-map
```

Keep the folder name `repo-map`: `SKILL.md` calls the script by that path.

## Use

In Claude Code, ask for it ("map this repo", "show me where the bloat is") or run `/repo-map`. Claude runs the script and publishes the page as an artifact.

Without Claude:

```bash
python3 scripts/gen.py <repo-or-folder> --out repo-map.html
open repo-map.html        # xdg-open on Linux
```

`<repo-or-folder>` is a repo, or a folder with repos up to 3 levels below it (untracked files beside them are ignored; linked worktrees collapse into the main repo). With several repos the script lists them and exits.

| Flag | Effect |
|---|---|
| `--ref REF` | Ref to map. Default `origin/HEAD`, or `HEAD` when that is >30 days behind. |
| `--hide PATH` | Hide a file or folder at first load (repeatable). |
| `--no-auto-hide` | Hide only lock files and `--hide` paths. |
| `--snaps N` | Timeline points, default 150. `1` = no history. |
| `--no-subjects` | Leave commit subjects out of the page. |
| `--depth N` | Levels below the folder searched for repos, default 3. |
| `--out FILE` | Output path. |

## How it reads your repo

- Git objects only (`log`, `ls-tree`, `cat-file`): never the working tree, never writes to the repo, never fetches.
- Uncommitted work is not counted. The report says which ref and commit the map shows.
- History is path-based: a renamed or moved file shows as removed from the old folder and added to the new one. Snapshots are evenly spaced along the first-parent commit line.

## Privacy

- The page embeds file paths, line and character counts, commit subjects (drop them with `--no-subjects`) and the checkout path on your machine. **No file contents.**
- That is still your repo's structure: check before sharing a page made from a private repo.
- The page loads IBM Plex from Google Fonts, so a viewer's browser makes a request to Google.

## Notes

- Inside the Claude desktop app an artifact cannot launch editors (the viewer blocks `vscode://` links), which is why the menu copies commands instead of opening files.
- Colours: the 7 biggest languages get a categorical palette; the rest fold into grey "Other". Extensions map to languages in `LANG` in `scripts/gen.py`.

## License

MIT, see [LICENSE](LICENSE).
