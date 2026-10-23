# Memory inbox

The **fallback** for memory written by a session that cannot reach `epifanio/groundtruther-memory` (a cloud session
that did not attach it). When the memory repo is attached, write there instead (`CLAUDE.md` →
"Memory").

## Append-only convention

* Name a new note `YYYY-MM-DD_<topic>.md` and **never edit it afterwards**.
* A later note that replaces an earlier one says so in its front matter: `supersedes: <file>`.
* Front matter: `name`, `description` (one line: it becomes the index line), `type`
  (`project` / `feedback` / `reference` / `user`), optionally `date` and `supersedes`.
* No secrets, ever (tokens, keys, passwords, connection strings with a password).

## Importing (on a machine whose memory dir is linked to the memory repo)

```bash
scripts/import-memory-inbox.sh --commit --push   # install + index lines, git rm the imported files,
                                                 # commit the removal, sync the memory repo
scripts/import-memory-inbox.sh -n                # dry run
```

An import never overwrites a memory file: a same-named file with different content is installed as
`<name>.incoming-<date>.md` for a human to merge. Commit the removal on a branch and open a PR.
