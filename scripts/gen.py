#!/usr/bin/env python3
"""Render a git repo's tracked files, and how their size changed over history, as one HTML page.

Reads git objects only (rev-list, ls-tree, cat-file): never the working tree, never writes to the repo.
PATH is a repo, or a folder with repos at most --depth levels below it; untracked local files are ignored.
"""
import argparse, collections, html, json, os, pathlib, re, subprocess, sys, tempfile

LANG = {
    "py": "Python", "pyi": "Python", "ipynb": "Notebook", "ts": "TypeScript", "tsx": "TypeScript",
    "js": "JavaScript", "jsx": "JavaScript", "mjs": "JavaScript", "cjs": "JavaScript",
    "go": "Go", "rs": "Rust", "java": "Java", "kt": "Kotlin", "kts": "Kotlin", "scala": "Scala",
    "rb": "Ruby", "php": "PHP", "cs": "C#", "fs": "F#", "swift": "Swift", "m": "Objective-C",
    "c": "C", "h": "C", "cpp": "C++", "cc": "C++", "cxx": "C++", "hpp": "C++", "hh": "C++",
    "sh": "Shell", "bash": "Shell", "zsh": "Shell", "fish": "Shell", "ps1": "PowerShell", "psm1": "PowerShell",
    "nix": "Nix", "tf": "Terraform", "tfvars": "Terraform", "hcl": "HCL", "bicep": "Bicep",
    "yaml": "YAML", "yml": "YAML", "json": "JSON", "json5": "JSON", "jsonc": "JSON", "hujson": "JSON",
    "toml": "TOML", "ini": "INI", "xml": "XML", "csv": "CSV",
    "md": "Markdown", "mdx": "Markdown", "markdown": "Markdown", "rst": "reStructuredText", "txt": "Text",
    "html": "HTML", "htm": "HTML", "css": "CSS", "scss": "CSS", "sass": "CSS", "less": "CSS",
    "vue": "Vue", "svelte": "Svelte", "sql": "SQL", "lua": "Lua", "ex": "Elixir", "exs": "Elixir",
    "erl": "Erlang", "hs": "Haskell", "ml": "OCaml", "clj": "Clojure", "dart": "Dart", "r": "R",
    "jl": "Julia", "pl": "Perl", "proto": "Protobuf", "graphql": "GraphQL", "gql": "GraphQL",
}
NAMES = {"Makefile": "Make", "Justfile": "Make", "CMakeLists.txt": "CMake", "flake.lock": "JSON"}
# Start hidden: lock files and generated output dwarf hand-written code. The viewer can unhide them.
GENERATED = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "Cargo.lock", "poetry.lock", "Pipfile.lock",
             "uv.lock", "composer.lock", "Gemfile.lock", "go.sum", "flake.lock", "gotk-components.yaml"}
GEN_SUFFIX = (".min.js", ".min.css", ".map", ".snap")
GEN_HEAD = re.compile(r"@generated|do not edit|code generated|auto-?generated|automatically generated|this file is generated", re.I)
VENDORED = {"node_modules", "vendor", "third_party", "Pods", "__snapshots__"}
DATA_EXT = {"json", "csv", "tsv", "yaml", "yml", "xml", "ndjson", "jsonl"}
SKIP_DIRS = {"node_modules", "vendor", "Library", "__pycache__"}   # never searched for repos
SLOTS = 7           # validated categorical colours; further languages fold into grey "Other"
BLOB_BUDGET = 60000 # unique blobs read across all snapshots; more than this thins the snapshots

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("path", nargs="?", default=".", help="repo, or a folder with repos up to --depth levels below it")
ap.add_argument("--depth", type=int, default=3, help="levels below PATH searched for repos (default 3)")
ap.add_argument("--ref", help="git ref to read (default: origin/HEAD, or HEAD when that is >30 days behind)")
ap.add_argument("--out", help="output HTML (default: <tmpdir>/<repo>-repo-map.html)")
ap.add_argument("--hide", action="append", default=[], metavar="PATH",
                help="file or folder hidden at first load; repeatable")
ap.add_argument("--no-auto-hide", action="store_true", help="hide only lock files and --hide paths")
ap.add_argument("--snaps", type=int, default=150, help="max history snapshots on the timeline (1 = no history)")
ap.add_argument("--no-subjects", action="store_true", help="leave commit subjects out of the page")
a = ap.parse_args()

def run(repo, *args, data=None, check=True):
    return subprocess.run(["git", "-C", repo, *args], input=data, capture_output=True, check=check).stdout

def git(repo, *args, check=True):
    return run(repo, *args, check=check).decode(errors="replace").strip()

def repo_of(d):
    r = subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel", "--git-common-dir"], capture_output=True, text=True)
    if r.returncode:
        return None
    top, common = r.stdout.split("\n")[:2]
    return top, os.path.realpath(os.path.join(d, common))

def find_repos(root, depth):
    """{git-common-dir: checkout}. Linked worktrees of one repo collapse to its main checkout."""
    here = repo_of(root)
    if here:
        return {here[1]: here[0]}
    found, level = {}, [root]
    for _ in range(depth):
        nxt = []
        for d in level:
            try:
                names = sorted(os.listdir(d))
            except OSError:
                continue
            for name in names:
                p = os.path.join(d, name)
                if name.startswith(".") or name in SKIP_DIRS or not os.path.isdir(p):
                    continue
                if os.path.exists(os.path.join(p, ".git")):
                    r = repo_of(p)
                    if r and (r[1] not in found or os.path.isdir(os.path.join(r[0], ".git"))):
                        found[r[1]] = r[0]
                else:
                    nxt.append(p)
        level = nxt
    return found

root = os.path.abspath(os.path.expanduser(a.path))
found = find_repos(root, a.depth)
if not found:
    sys.exit(f"no git repo at {root} or up to {a.depth} levels below it")
if len(found) > 1:
    print(f"{len(found)} repos under {root}; rerun with one of:")
    print("\n".join("  " + top for top in sorted(found.values())))
    sys.exit(2)
repo = next(iter(found.values()))

def ok(ref):
    return subprocess.run(["git", "-C", repo, "rev-parse", "-q", "--verify", ref + "^{commit}"],
                          capture_output=True).returncode == 0

def stamp(ref):
    return int(git(repo, "log", "-1", "--format=%ct", ref))

ref, note = a.ref, ""
if not ref:
    ref = "HEAD"
    if ok("origin/HEAD"):
        gap = (stamp("HEAD") - stamp("origin/HEAD")) // 86400
        if gap > 30:
            note = f"origin/HEAD is {gap} days behind HEAD, so HEAD was mapped"
        else:
            ref = "origin/HEAD"
if not ok(ref):
    sys.exit(f"no commit at {ref} (empty repo, or a typo in --ref?)")
label = git(repo, "rev-parse", "--abbrev-ref", ref, check=False) or ref
url = git(repo, "config", "--get", "remote.origin.url", check=False)
name = url.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git") if url else pathlib.Path(repo).name

def lang(path, head):
    base = path.rsplit("/", 1)[-1]
    if base in NAMES:
        return NAMES[base]
    if base.startswith("Dockerfile") or base.endswith(".dockerfile"):
        return "Docker"
    ext = base.rsplit(".", 1)[-1].lower() if "." in base.lstrip(".") else ""
    if ext in LANG:
        return LANG[ext]
    return next((l for k, l in (("python", "Python"), ("node", "JavaScript"), ("sh", "Shell")) if k in head), "Other")

def tree(commit):
    out = {}
    for rec in run(repo, "ls-tree", "-r", "-z", commit).split(b"\0"):
        if rec:
            meta, path = rec.split(b"\t", 1)
            mode, kind, sha = meta.split()
            if kind == b"blob" and mode != b"120000":   # symlinks and submodules carry no lines
                out[path.decode(errors="replace")] = sha.decode()
    return out

def read_blobs(shas):
    """sha -> (lines, chars, shebang line, generated-header flag); None for binary or missing."""
    info = {}
    for i in range(0, len(shas), 2000):
        chunk = shas[i:i + 2000]
        raw = run(repo, "cat-file", "--batch", data="".join(s + "\n" for s in chunk).encode())
        pos = 0
        for sha in chunk:
            nl = raw.index(b"\n", pos)
            head = raw[pos:nl].split()
            if head[-1] == b"missing":
                info[sha], pos = None, nl + 1
                continue
            size = int(head[2])
            body, pos = raw[nl + 1:nl + 1 + size], nl + 2 + size
            try:
                text = body.decode()
            except UnicodeDecodeError:
                info[sha] = None
                continue
            lines = text.count("\n") + (0 if not text or text.endswith("\n") else 1)
            first = text.split("\n", 1)[0] if text.startswith("#!") else ""
            info[sha] = (lines, len(text), first, bool(GEN_HEAD.search(text[:512])))
    return info

# Snapshots: commits along the first-parent line, evenly spaced by position, last one = ref.
log = [l.split("\t", 3) for l in git(repo, "log", "--first-parent", "--reverse",
                                      "--format=%H%x09%h%x09%cI%x09%s", ref).split("\n") if l]
n, k = len(log), max(a.snaps, 1)
idx = list(range(n)) if n <= k else [n - 1] if k == 1 else sorted({round(i * (n - 1) / (k - 1)) for i in range(k)})
trees = {i: tree(log[i][0]) for i in idx}
uniq = lambda: {s for i in idx for s in trees[i].values()}
while len(uniq()) > BLOB_BUDGET and len(idx) > 2:
    idx = sorted(set(idx[::2]) | {idx[-1]})
info = read_blobs(sorted(uniq()))

# Per path, the (lines, chars) step changes: [snapshot, lines, chars]; lines -1 = file absent from there on.
last, steps, first_head = {}, collections.defaultdict(list), {}
for j, i in enumerate(idx):
    cur = {}
    for p, sha in trees[i].items():
        v = info[sha]
        if v:
            cur[p] = v
            first_head.setdefault(p, v[2])
            if last.get(p) != v[:2]:
                steps[p].append([j, v[0], v[1]])
                last[p] = v[:2]
    for p in [p for p, v in last.items() if v is not None and p not in cur]:
        steps[p].append([j, -1, 0])
        last[p] = None
now = {p: info[sha] for p, sha in trees[idx[-1]].items() if info[sha]}
binary = [p for p, sha in trees[idx[-1]].items() if not info[sha]]

# Colour slots go to the biggest languages now; Markdown always keeps one so its filter works.
kind = {p: lang(p, first_head[p]) for p in steps}
by_lines = collections.Counter()
for p, v in now.items():
    by_lines[kind[p]] += v[0]
ranked = [l for l, _ in by_lines.most_common() if l != "Other"]
keep = ranked[:SLOTS]
if "Markdown" in ranked[SLOTS:]:
    keep = ranked[:SLOTS - 1] + ["Markdown"]
types = keep + (["Other"] if any(l not in keep for l in kind.values()) else [])
slot = {p: types.index(l if l in keep else "Other") for p, l in kind.items()}

paths = set(steps)
dirs = {p.rsplit("/", 1)[0] for p in paths if "/" in p}
dirs |= {d.rsplit("/", i)[0] for d in list(dirs) for i in range(1, d.count("/") + 1)}
total = max(sum(v[0] for v in now.values()), 1)
why = {}
for p, (l, c, _, gen) in now.items():
    base, parts = p.rsplit("/", 1)[-1], p.split("/")
    ext = base.rsplit(".", 1)[-1].lower() if "." in base.lstrip(".") else ""
    vend = next((i for i, d in enumerate(parts[:-1]) if d in VENDORED), None)
    if base in GENERATED or p.endswith(GEN_SUFFIX):
        why[p] = "lock or generated file"
    elif a.no_auto_hide:
        continue
    elif vend is not None:
        why.setdefault("/".join(parts[:vend + 1]), "vendored or snapshot folder")
    elif gen:
        why[p] = "header says generated"
    elif c >= 20000 and c / max(l, 1) >= 400:
        why[p] = "minified or bundled"
    elif ext in DATA_EXT and l >= 2000 and l / total >= 0.10:
        why[p] = f"data file, {l / total:.0%} of all lines"
for h in a.hide:
    h = h.rstrip("/")
    if h in paths | dirs:
        why[h] = "hidden by request"
    else:
        print(f"warning: --hide {h} matches no tracked file or folder")
hide = [h for h in sorted(why) if not any(h.startswith(o + "/") for o in why)]
covered = lambda p: any(p == h or p.startswith(h + "/") for h in hide)

snaps = [[log[i][1], log[i][2], "" if a.no_subjects else log[i][3][:90]] for i in idx]
meta = {"repo": name, "ref": label, "sha": snaps[-1][0], "date": snaps[-1][1], "types": types,
        "hide": hide, "why": {h: why[h] for h in hide}, "root": repo, "snaps": snaps}
data = [[p, slot[p], steps[p]] for p in sorted(steps)]
blob = lambda o: json.dumps(o, separators=(",", ":")).replace("</", "<\\/")
tpl = (pathlib.Path(__file__).parent.parent / "assets" / "template.html").read_text()
out = pathlib.Path(a.out or pathlib.Path(tempfile.gettempdir()) / f"{name}-repo-map.html")
out.write_text(tpl.replace("__TITLE__", html.escape(f"{name} Repo Map"))
                  .replace("__META__", blob(meta)).replace("__DATA__", blob(data)))

shown = {p: v for p, v in now.items() if not covered(p)}
L, C = sum(v[0] for v in shown.values()), sum(v[1] for v in shown.values())
HL = sum(v[0] for p, v in now.items() if covered(p))
md = [v for p, v in shown.items() if "Markdown" in types and slot[p] == types.index("Markdown")]
by_dir, by_lang = collections.Counter(), collections.Counter()
for p, v in shown.items():
    by_dir[p.split("/")[0] + "/" if "/" in p else "(root files)"] += v[0]
    by_lang[types[slot[p]]] += v[0]
print(f"repo: {repo}" + (f"  (found below {root})" if repo != root and not repo_of(root) else ""))
print(f"{name} @ {label} {meta['sha']} ({meta['date'][:10]})" + (f"  NOTE: {note}" if note else ""))
print(f"shown: {len(shown)} files, {L:,} lines, {C:,} chars" + (f"  (hidden: {HL:,} lines)" if HL else ""))
print(f"markdown: {len(md)} files, {sum(v[0] for v in md):,} lines ({sum(v[0] for v in md) / max(L, 1):.0%})")
print("languages:", ", ".join(f"{t} {x:,}" for t, x in by_lang.most_common()))
print("biggest folders:", ", ".join(f"{d} {x:,}" for d, x in by_dir.most_common(5)))
print("biggest files:", ", ".join(f"{p} {v[0]:,}" for p, v in sorted(shown.items(), key=lambda t: -t[1][0])[:5]))
print("hidden at first load:", ", ".join(f"{h} ({why[h]})" for h in hide) or "none")
print(f"history: {len(idx)} snapshots of {n} commits, {snaps[0][1][:10]} to {snaps[-1][1][:10]}")
if binary:
    print(f"binary, not counted: {len(binary)} ({', '.join(binary[:5])}{' …' if len(binary) > 5 else ''})")
print(f"-> {out}")
print(f'publish: Artifact file_path={out} icon=tree description="{name} at {label} {meta["sha"]}: file tree, treemap and size history over {len(idx)} snapshots."')
