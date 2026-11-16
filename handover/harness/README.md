# Old against new

`python SP/harness/oldnew.py --new <worktree> --cases <cases.py> --out <your scratch folder> [case ...]`

- Old side: `bash SP/main-read/bin/council`. New side: `bash <worktree>/bin/council` (Python through `python_command`).
- A cases file is plain Python: `from oldnew import git, write, run_open, run_dir, CONFIG, council, OLD`, one
  function per case taking the prototype repo (already `git init`, branch main), and `CASES = [fn, ...]`.
- A case builds files, commits, opens a run (`run_open(repo, "council-review")` opens it with the old plugin and
  returns its folder name) and returns its calls. A call is `("state", "phase=prepare")`, or `(args, env)`, or
  `(args, env, before)` where `before(repo)` changes each side's copy just before that call.
- The prototype is copied to old/ and new/ (code-root rewritten per copy); each call runs on both, in order.
- Compared after every call: exit code, stdout, stderr, and every file under `.council/` (lock files skipped).
  Normalised: each side's repo path, times (`YYYY-MM-DD HH:MM[:SS]`, UTC `…Z`, `YYYYmmddTHHMMSSZ`), run-folder
  stamps, epochs, pids, `.tmp<pid>`, lock ages.
- A call whose only difference is CR LF (old) against LF (new) on stdout/stderr counts as `crlf-only`, apart
  from `same` and `diff`.
- Output: `cases=N calls=N same=N crlf-only=N diff=N`; every diff, old and new side by side, in `<out>/diffs.txt`.
  Exit 1 when any call differs. `<out>/calls.txt` holds every call as the old side answered it (check your
  calls reach the path you meant). Run one case by naming it after the options.
- Everything (repos, session marks, TMPDIR, diffs) goes under `--out`: nothing is shared between runs, so give
  each run its own folder. Calls inside one run go one at a time.
- Example: `SP/harness/cases_spine_a.py` (state and run events).
