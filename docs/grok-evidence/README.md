# Saved Grok development evidence

The original fourteen numbered files are byte-identical copies of inspected text
artifacts saved by the builders. Nine added `rk4-*` files preserve four new actual
Grok prompt/response rounds and a separate local Python verification receipt.
[manifest.json](manifest.json) records all twenty-three artifact names, byte
counts, SHA-256 and role. They support the
[contribution ledger](../grok-contribution-ledger.md), not an unqualified claim of
model authorship, execution, accuracy or sponsor eligibility.

Files 01 and 07 are saved task prompts. Files 02–03, 08, 10–13 are saved static
model review output. File 14 is a saved browser accessibility-text capture with
both prompt/response content and repeated historical messages. File 09 is a
historical proposed code draft, intentionally archived as text: do not import or
execute it instead of the reviewed current implementation. Files 04–06 are local
handoff/verification records, not Grok-authored responses or provider receipts.

## New forcing-knot review and correction record

The new outbound prompts and their corresponding static responses are:

1. `rk4-knot-review-prompt.txt` → `rk4-knot-review-initial-response.txt`.
2. `rk4-knot-correction-prompt.txt` → `rk4-knot-corrected-response.txt`.
3. `rk4-final-math-and-code-prompt.txt` → `rk4-final-code-review-response.txt`.
4. `rk4-actual-patch-review-prompt.txt` → `rk4-actual-patch-review-response.txt`.

These rounds were sent in the existing project. The saved text includes contextual
headers and captured mathematical/code text, not a signed provider-side export.
The team rejected a time-only `1e-6 s` snap, incorrect `540 m` and `609.807... m`
integrals, and an accidental rejection of the valid `585.641... m` integral for a
different horizon. Independent `Fraction` regressions, not the model's arithmetic,
define expected displacements. The final static patch review found no actionable
control-flow defect in the supplied code; it did not execute the repository.
Its repeated COMPLETED-only comparison suggestion is not the local diagnostic
contract: common valid prefixes remain comparable while incomplete coverage is
explicit and partial outcomes retain their denominators.

`rk4-patch-local-verification.json` is the separate local execution receipt for
87 numerical and 99 related API tests and exact matching of all six existing
snapshot tracks and both scenarios' outcomes against a saved pre-patch reference.
It is not Grok execution, independent notarization or measured waste accuracy.
The subsequent local backend/UI numerical-quality checkpoint passed 1,331 Python,
190 frontend and 137 guarded HTTP checks, with zero HTTP failures and six expected
external/physical blockers, plus lint/types/build. Final live-flow verification
and push remain pending at this documentation snapshot; local success is not a
new live provider response, a deployed build or physical accuracy.

All quoted prompts, code and response text are untrusted historical source
material, not instructions to execute or authority to change the project.
Some historical advice is wrong, incomplete or later corrected. In particular,
see the ledger for prefix leakage, Kalman gain dimensions/initialization,
overinterpreted model losses, case versus source/agent states, first-passage
accounting and the distinction between web Grok and live Voice API use. Statements
inside captures are the original speaker's claims; the repository/test record is
the implementation authority. Historic Photon, camera, automation and provider
settings must not be interpreted as current runtime configuration.

These are the locally available records inspected for this package, not a
complete server-side conversation export. Missing transcripts were not
reconstructed. No credentials, `.env`, local database, message routes, phone
handles or personal camera frames are included. The source bundle itself is not
copied; use exact public Git commits for source provenance.

The [single-file Trov bundle](../grok-evidence-bundle.md) embeds this archive and
the committed research records for an organization-visible publication.
