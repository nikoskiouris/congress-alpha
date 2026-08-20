# Engineer roles

TPO writes the prompt. Engineers do not pick scope.

## Explorer (`Task` explore)

```
Repo: congress-alpha (event-time congressional factor model).
Ticket: CA-XXX — <title>
Find the files and functions to change. Note any trade_date / disclosure_date risk.
Do not edit. Return: paths, 5-line plan, test files to touch.
```

## Builder (`Task` generalPurpose)

```
You are an engineer. TPO owns scope. Ticket CA-XXX only.
Read the ticket file ops/tickets/CA-XXX-*.md.
Event clock is disclosure_date. Never fill/train as-of trade_date.
Done when: <paste checkboxes>
Forbidden: <paste>
Implement + tests. Do not open extra tickets. Do not add ML/AWS.
When done: list files changed and how to pytest.
```

## Tester (`Task` shell)

```
Working directory is the repo root.
python -m pytest
If fail, return the failing node ids and first error lines. Do not rewrite production code unless TPO said so.
```

## TPO review (you)

After builder: read the diff. Kill: live-track-record language, trade_date as-of, silent amount defaults, extra features. Then TPO auto-merges. Engineers do not wait for Director.

Do not launch Bugbot or security-review unless the Director asked or the ticket touches ingest of external HTML/PDF.
