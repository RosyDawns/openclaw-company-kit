# Issue Flow Example

1. Product creates issue with `owner:*` and `priority:*` labels.
2. Senior dev picks one issue (WIP=1), creates branch + commit + PR.
3. Reviewer comments and updates status.
4. QA runs validation and marks pass/fail evidence.
5. `issue-sync.sh` reconciles labels and may auto-close done issue.
6. Dashboard reads GitHub + cron state and updates role panels.
