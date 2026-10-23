# Decisions — what binds more than one plan

A plan freezes the owner's answers for its own work ([`WORKFLOW.md`](WORKFLOW.md) §4 step 5). An
answer that binds work **outside** its plan (a store, a library ban, a public contract, a
vocabulary, a deploy rule) is promoted to a record in [`decisions/`](decisions/README.md) and gets
one row here. This table is derived: the record is the truth, the plan that made it keeps the
reasoning, this file points. A planning session reads it in step 3 of `WORKFLOW.md` §4; a build
session reads the records its prompt names.

A record is never edited after it is accepted; a change is a new record that `supersedes` it. With
one owner, a record is `accepted` when its PR merges. With several maintainers it is `proposed`
until the approval in `WORKFLOW.md` §12 Q10, and a row that depends on it is ⏸ "Waits on D-nnn".
`python3 PLANNING/check_planning.py` checks this file against `decisions/` (rules D1–D4). On a merge
conflict, take `master`'s version; if another session took your number, renumber your
record and redo your row.

| ID | Status | Date | Decision | Record |
|---|---|---|---|---|
