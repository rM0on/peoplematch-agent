# V5 Requirement Review publication notes

This directory is part of a **local release candidate** until an explicitly approved Push succeeds. Do not describe the code or PDFs as remotely published based only on their presence in this worktree. The prior public milestone remains at `2e8a9e4dac1dd437b0b6ad140e1eae462b3f9883` until the remote branch is separately checked after publication.

- [Engineering case](engineering-case.md): Mission, frozen boundary, actual code/review, HTTP 200 vs client rejection, validation tiers.
- [Claims ledger](claims-ledger.md): source, historical, prior audit, current candidate and not-verified claims.
- [Independent review closure](independent-review-closure.md): two release-review findings, regression evidence and current verification boundary.
- [V5 reproduction levels](../../v5-reproduction-guide.md): source/tests, isolated synthetic demo, historical Fresh Run.
- [API contract](../../api-design.md#v5-requirement-review-get-read-only): typed GET and fail-closed behavior.
- [Public portfolio](../../portfolio/v5/PeopleMatch-AI-Native-Engineer-Public-Portfolio.pdf) and [Executive brief](../../portfolio/v5/PeopleMatch-AI-Native-Engineer-Public-Executive-Brief.pdf): public identity only. The real-name Application editions remain local and excluded from this commit.

The featured workbench screenshot at `docs/images/requirement-review-v5.png` is a saved desktop browser image from the 2026-10-18 independent **synthetic** PostgreSQL audit. Its source was an isolated tmpfs database and newly seeded fixture, not a production applicant or the historical Fresh Top-3 Run. The [evidence ZIP](../../portfolio/v5/PeopleMatch-AI-Native-Engineering-Evidence-Pack.zip) contains a separate reader index, whitelist manifest and scoped proof; it intentionally omits secrets, database contents, model weights and private Application PDFs.

Publication status is a GitHub state, not a PDF export state. If the candidate is not pushed, new V5 links in the README are local-tree links only. After an approved Push, verify the remote commit SHA, README image, PDFs, ZIP, source links and archive checksum. Do not reuse the older local/unpublished Public PDF binary as a new published edition.
