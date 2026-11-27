# Authoritative S08-AMEND-002 milestone record

**Contract:** v1.2.
**Delivery baseline:** verified main `ca6325f276e49cc24168779b82ca0f705972e66e`.
**Historical delivery CI:** 24/24 PASS.
**Milestone closure:** conditional on all eight gates
in `docs/sprints/S08_AMEND_002.md`, section 4.

Once the final amendment delivery evidence verifies
every condition, record S08 as CLOSED — DEVELOPMENT MVP
MILESTONE ONLY. Until then closure is pending.

This is not full original-contract acceptance:
26/36 original AC verified scoped, six transferred
not passed, three partially verified, one open.
18/20 original SG verified scoped; two partial.

S09-OB01 through S09-OB04 are mandatory.
D06-05 and D06-06 remain OPEN.
Original AC36 full acceptance remains OPEN.

S09 NOT STARTED.
PRODUCTION REMAINS NOT APPROVED.

This header supersedes earlier milestone allocation and
administrative status statements only. Historical evidence,
acceptance matrices, security requirements and release
restrictions below remain preserved.

---

# S08 Final Closeout Record

**Status:** CLOSEOUT CANDIDATE — NOT CLOSED.
**Contract:** v1.1, S08-AMEND-001.
**Release scope:** Development MVP only.
**Production:** NOT APPROVED.

G07 Owner approval accepts scoped reconciliation and
docs-only delivery. It does not grant final sprint closure
or authorize any unverified requirement as passed.

## 1. Binding checkpoint

- Feature PR: #28, merged.
- Feature commit: `c434291fa8bd8fe3affb79444876034a20ceee85`.
- Feature CI: 45842267405, four jobs passed.
- Main HEAD: `b0aac9f32cd26e02e60b8cf6c67da865f0f35854`.
- Main tree: `f4d138671de9618429f947abc40236c93ce496df`.
- Main CI: 45843273499, four jobs passed.
- Exact merged scope: 58 files.
- Historical mandatory delivery CI: 16/24.
- Historical verified package test identities: 312.
- Six historical S06 regression cases repaired and passed.
  R02 pytest stdout retained; local JUnit export unavailable.
- Authlib: 56 PASS, 1 strict expected XFAIL, 0 XPASS.

## 2. Evidence register

All E01-E07 evidence hashes were checked against retained
files during preparation of this closeout candidate.

| ID | Evidence file | SHA256 |
| --- | --- | --- |
| E01 | S08_WP01_G02_B_MERGE_EVIDENCE.txt | `c78ab725633bfbf4d2cf619dc8bcefbb66fe0449572a30c49b6621826b5a8601` |
| E02 | S08_WP05_F2_R02_EVIDENCE.txt | `2e317b20571ed9cbb6ba62e3c1052e6a11c06c590b61adc7eb0c35702af549cd` |
| E03 | S08_WP05_FINAL_EVIDENCE.txt | `f03b65e58c30cb1fd2239a720cc8ba2412cc58f53588a1eca5199bf2c5b79e37` |
| E04 | S08_WP05_EVAL_R03_EVIDENCE.txt | `f4b30907dfbcf597882e8a3b5ae28765fac585fcd26b9537e7e683c2330bb92c` |
| E05 | S08_WP06_A_EVIDENCE.txt | `2d8080c51a437db0b142cc76c391790f98d509aed3e862e30ac82c54c45cf1da` |
| E06 | S08_WP06_B_R04_EVIDENCE.txt | `ed185f1dfb8286cdda90146318e30201c126c102cc894cea737e01033ec203a7` |
| E07 | S08_WP06_C_EVIDENCE.txt | `18997e8824992bf8d79f528d084546c9c0136fe9db3ddc9e90fadcd3bf00b250` |

E05 contains the integrated predecessor evidence
reconciliation and static feature review.

E06 and E07 bind the corrected feature commit and its
actual GitHub CI. These results supersede failed CI
attempts without erasing the historical failures.

Additional historical evidence identities recorded
in the predecessor chain:

- WP02-A-R01 provider request verification:
  `3a52fd607967c7cbf02312427d65e8da6096d6a81869f986691f1abe97322`.
- WP02-B runtime compatibility:
  `a62751e8a47726f41adeb9041f918569f5471a73f230bbfa2912e046426c2143`.
- WP02-C-R03 schema regression:
  `61b8ca3ef8f29e08b3e55f707abf2c75df68b7dcaa5d935c179fc28ecdc836e2`.
- WP03-C wire authority:
  `d7e2d5863d1e6056796647bb5b780847dacfeb1cb90211c84084978b7c85ce73`.
- WP04-A evidence/retrieval:
  `6a7b3f836d28b16aadcd1ec460b725f5270e2258aeb8d789d6dbc2055e4cfcf6`.
- WP04-B controlled workflow:
  `d335ec813a551463456334e6f044255bd20ee5a723a24d455135d19690ca8cdf`.
- WP05-E private scoped runtime:
  `79be6005b3bfe87f303992acf82775f63b38d177c1d7f9a9f2bb7ce91894b95c`.

These historical identities are traceability references,
not assertions that their test suites were rerun here.

## 3. Acceptance reconciliation

- VERIFIED_SCOPED: 26/36.
- TRANSFERRED_NOT_PASSED: 6/36.
- PARTIALLY_VERIFIED: 3/36.
- OPEN: 1/36.

Scoped verification means evidence supports the stated
Development MVP capability within its actual tested
boundary. It is not full original-contract acceptance.

| ID | Original v1.0 requirement | Disposition | Evidence | Rationale / limitation |
| --- | --- | --- | --- | --- |
| AC01 | Reconcile S07 checkpoint and all D06 obligations. | VERIFIED_SCOPED | E01/E05 | S07 checkpoint and D06 register reconciled; open obligations retained. |
| AC02 | Obtain Owner approval of S08 contract and architecture decisions. | VERIFIED_SCOPED | E01/E05 | Owner-approved contract and S08-AMEND-001. |
| AC03 | Complete documentation-only delivery and mandatory CI. | VERIFIED_SCOPED | E01 | Documentation PR and merged-main CI completed. |
| AC04 | Verify official provider API contract and runtime compatibility. | VERIFIED_SCOPED | E02/E05 | Approved Basic Tavily request and actual bounded interoperability. |
| AC05 | Verify actual account quota, billing and applicable data handling terms. | VERIFIED_SCOPED | E02/E05 | Historical Free-plan quota and billing attestation; applicable terms reviewed. |
| AC06 | Verify required runtime dependency availability. | VERIFIED_SCOPED | E05/E06/E07 | Locked runtime compatibility and successful dependency checks. |
| AC07 | Verify default-deny authorization and non-bypassable controlled test scope. | VERIFIED_SCOPED | E03/E05/E06 | Default-deny, scoped authority, ticket and replay checks within application trust boundary. |
| AC08 | Verify provider request/response schemas, destination policy and error handling. | VERIFIED_SCOPED | E03/E05/E06 | Strict schemas, fixed destination and bounded error handling. |
| AC09 | Complete separately authorized live-provider smoke test with sanitized evidence. | VERIFIED_SCOPED | E02 | Separately authorized actual Tavily smoke; one free credit. |
| AC10 | Reserve durable usage before dispatch. | VERIFIED_SCOPED | E02/E03 | Durable reservation and dispatch ordering verified. |
| AC11 | Validate and persist actual usage metadata accurately. | VERIFIED_SCOPED | E02 | Actual provider usage metadata validated and settled. |
| AC12 | Reconcile provider credits with application accounting. | VERIFIED_SCOPED | E02 | Reserved and observed credit equal one; dashboard delta one by Owner attestation. |
| AC13 | Fail closed on missing, malformed or inconsistent usage. | VERIFIED_SCOPED | E05/E06/E07 | Missing and malformed usage fail-closed regression evidence. |
| AC14 | Preserve accounting across retries, recovery and duplicate reconciliation. | VERIFIED_SCOPED | E05/E06/E07 | Recovery, accounting and duplicate reconciliation tests. |
| AC15 | Prevent automatic paid usage and unauthorized dispatch. | VERIFIED_SCOPED | E02/E03/E06 | Scoped free usage and no automatic external retries; not a future billing guarantee. |
| AC16 | Distinguish real and synthetic evidence in evidence contracts. | VERIFIED_SCOPED | E03/E05 | Real and synthetic origins remain distinct. |
| AC17 | Verify provenance, source identity and genuine retrieval timestamps. | VERIFIED_SCOPED | E03 | Actual independent HTTPS retrieval, identity and chronological provenance. |
| AC18 | Verify evidence integrity and deduplication. | VERIFIED_SCOPED | E03/E05/E06 | Evidence integrity and deduplication fixtures plus actual retrieval evidence. |
| AC19 | Preserve owner/task/attempt isolation and fencing. | VERIFIED_SCOPED | E05/E06/E07 | Owner/task/attempt isolation and fencing tests. |
| AC20 | Verify deletion barrier and stale-attempt rejection. | VERIFIED_SCOPED | E05/E06/E07 | Deletion and stale-attempt rejection tests. |
| AC21 | Reject unknown, deleted, fabricated and cross-task citations. | VERIFIED_SCOPED | E03/E05/E06 | Citation lineage and rejection tests; actual independent citation resolution. |
| AC22 | Integrate authorized real evidence into bounded workflow. | TRANSFERRED_NOT_PASSED | E02/E03/E05 | Independent search and retrieval verified; complete real workflow remains S09-OB01. |
| AC23 | Handle sparse, inaccessible and conflicting evidence safely. | TRANSFERRED_NOT_PASSED | E02/E04/E05 | Some safe insufficient-evidence behavior verified; full sparse/inaccessible/conflicting acceptance remains S09-OB01. |
| AC24 | Create versioned dataset of approximately 40 research questions. | VERIFIED_SCOPED | E04/E05 | Versioned 40-case frozen synthetic dataset. |
| AC25 | Maintain held-out subset and reproducible frozen provider fixtures. | VERIFIED_SCOPED | E04/E05 | Frozen 30 development/10 held-out membership and fixture reproducibility; not independently blinded. |
| AC26 | Compare manual analyst, single-model and AgentOps workflow baselines. | TRANSFERRED_NOT_PASSED | E03/E04/E05 | Comparable three-arm benchmark not executed; S09-OB02. |
| AC27 | Measure structural citation validity and citation coverage. | TRANSFERRED_NOT_PASSED | E03/E04/E05 | Individual citation checks are not report-level structural validity or coverage metrics; S09-OB02. |
| AC28 | Assess semantic groundedness with a human-review rubric. | TRANSFERRED_NOT_PASSED | E04/E05 | Human semantic groundedness not measured; S09-OB02. |
| AC29 | Measure completion, usefulness, latency and cost. | TRANSFERRED_NOT_PASSED | E04/E05 | Comparable report completion, usefulness, latency and cost not measured; S09-OB02. |
| AC30 | Verify prompt-injection resistance, credential protection and unauthorized tool execution rejection. | PARTIALLY_VERIFIED | E03/E05/E06 | Scoped injection, credential and tool-control evidence available; complete real-workflow security evaluation remains open. |
| AC31 | Complete integrated external security acceptance and reconcile S06 SG06, SG08 and SG10. | PARTIALLY_VERIFIED | E02/E03/E06/E07 | Successor controls and integrated CI verified in scope; S06 external SG06/08/10 final reconciliation remains incomplete. |
| AC32 | Verify applicable regression suites and historical security gates. | VERIFIED_SCOPED | E06/E07 | Mandatory regression CI and historical strict Authlib XFAIL preserved. |
| AC33 | Verify closure evidence for D06-01, D06-04, D06-05 and D06-06. | PARTIALLY_VERIFIED | E02/E03/E05 | D06-01/04 scoped evidence reconciled; D06-05/06 remain open. |
| AC34 | Complete feature review, dependency integrity, secret review and mandatory feature CI. | VERIFIED_SCOPED | E05/E06 | Exact feature review, unchanged locks, targeted credential review and feature CI; not comprehensive secret audit. |
| AC35 | Complete separately authorized feature merge and exact merged-main CI. | VERIFIED_SCOPED | E07 | Exact PR #28 merge and exact merged-main CI complete. |
| AC36 | Complete Owner acceptance, closeout PR, final CI and final evidence. | OPEN | E07/G07/G08 | Scoped acceptance reconciliation authorized; closeout delivery and final acceptance gates remain pending. |

## 4. Security reconciliation

- VERIFIED_SCOPED: 18/20.
- PARTIALLY_VERIFIED: 2/20.
- OPEN: 0/20.
- Transferred security gates: 0.

| ID | Original v1.0 requirement | Disposition | Evidence | Rationale / limitation |
| --- | --- | --- | --- | --- |
| S08-SG01 | Default-deny external execution. | VERIFIED_SCOPED | E05/E06 | Default-deny verified; no global enablement. |
| S08-SG02 | Application-owned provider authorization. | VERIFIED_SCOPED | E05/E06 | Application-owned scoped grants and one-use wire tickets; not a Python process sandbox. |
| S08-SG03 | Strict request, response and tool schema validation. | VERIFIED_SCOPED | E05/E06 | Strict request/response/tool validation regression evidence. |
| S08-SG04 | Public HTTP(S) destination policy. | VERIFIED_SCOPED | E03/E06 | Fixed approved HTTPS origins and public destination checks. |
| S08-SG05 | Reject private IP, loopback, link-local and metadata destinations. | VERIFIED_SCOPED | E05/E06 | Private, loopback, link-local and metadata rejection tests. |
| S08-SG06 | DNS validation, destination binding and rebinding protection. | VERIFIED_SCOPED | E03/E06 | Pinned DNS and peer binding verified in scoped successor implementation. |
| S08-SG07 | Redirect validation and downgrade rejection. | VERIFIED_SCOPED | E03/E06 | Controlled redirects denied; isolated redirect/downgrade regression preserved. |
| S08-SG08 | TLS trust, hostname verification and URL credential rejection. | VERIFIED_SCOPED | E03/E06 | TLS trust, hostname and credential rejection checks; actual bounded HTTPS success. |
| S08-SG09 | Bounded HTTP response, content type and decompression. | VERIFIED_SCOPED | E03/E06 | Bounded HTTP, strict chunk handling and unsupported compression rejection. |
| S08-SG10 | Durable budgets, deadlines, retry and recovery restrictions. | VERIFIED_SCOPED | E02/E03/E06 | Durable budgets, deadlines and no unauthorized retry; indeterminate reservations retained. |
| S08-SG11 | Prompt-injection resistance and policy isolation. | PARTIALLY_VERIFIED | E04/E05/E06 | Scoped policy isolation verified; full real-evidence prompt-injection evaluation remains open. |
| S08-SG12 | Owner/task/attempt isolation. | VERIFIED_SCOPED | E05/E06/E07 | Owner/task/attempt isolation and lifecycle fencing tests. |
| S08-SG13 | Real evidence integrity and provenance. | VERIFIED_SCOPED | E03/E06 | Actual independent real evidence, integrity and provenance. |
| S08-SG14 | Citation integrity and fabricated citation rejection. | VERIFIED_SCOPED | E03/E06 | Actual independent citation resolution and rejection fixtures. |
| S08-SG15 | Credential protection and sanitized logs/errors. | VERIFIED_SCOPED | E02/E03/E05/E06 | Scoped credential protection, sanitized errors and targeted secret-pattern review. |
| S08-SG16 | No unauthorized worker activation, lifecycle mutation or report publication. | VERIFIED_SCOPED | E03/E05/E07 | No unauthorized worker activation, lifecycle changes or publication in verified scope. |
| S08-SG17 | Actual usage integrity and idempotent reconciliation. | VERIFIED_SCOPED | E02/E06 | One-credit actual settlement plus accounting replay and idempotency tests. |
| S08-SG18 | Free-plan quota enforcement and no automatic paid usage. | VERIFIED_SCOPED | E02/E05 | Historical Free-plan attestation and bounded free usage; not future billing assurance. |
| S08-SG19 | Synthetic/real evidence separation and evaluation integrity. | VERIFIED_SCOPED | E03/E04/E05 | Origins and frozen fixture integrity preserved; unmeasured metrics remain null. |
| S08-SG20 | Preserve historical security gates, strict Authlib XFAIL, dependencies and release governance. | PARTIALLY_VERIFIED | E06/E07 | Strict Authlib XFAIL and locks preserved; historical external security closure and final release governance remain open. |

S06 SG06, SG08 and SG10 retain historical PARTIAL
classification until complete successor external security
acceptance. Scoped successor evidence is available;
no retrospective historical status rewrite is authorized.

S08-SG11 and S08-SG20 remain partially verified.
No security requirement is waived by S08-AMEND-001.

## 5. Actual provider and retrieval evidence

G04 search:
- One actual Tavily Basic request.
- Reserved credits: 1; observed credits: 1.
- Dashboard usage: 0 to 1, Owner attestation.
- Free-plan PAYG and auto-upgrade disabled at smoke time.
- Approved source not found; no retrieval in that workflow.
- No automatic retry.

G04-B and G04-C:
- Independent authorized retrieval attempts were indeterminate.
- No accepted real evidence from those attempts.
- G04-C classified bounded HTTP response failure.
- Prior consumed authorizations remain preserved.

G04-D:
- One separately authorized HTTPS retrieval of
  https://www.rfc-editor.org/rfc/rfc9110.txt.
- Actual successful durable retrieval and citation resolution.
- Real evidence ID:
  17b68a8d-4636-56fe-9133-551d16fa5896.
- Retrieved at: 2026-11-26T13:55:27.549869Z.
- Publication timestamp unknown.
- Zero new Tavily credits and zero model calls.
- Nonpublishable outcome.
- Disposable database cleaned after evidence export.

The actual search and successful retrieval were independent
authorized executions, not proof of complete live research
within the same task or attempt.

No future account quota or billing guarantee is inferred.

## 6. Evaluation evidence and limitations

- Frozen dataset: 40 cases, 30 development / 10 held out.
- Held-out membership was Owner-visible, not independently blinded.
- Synthetic acquisition verification: 66/66.
- Frozen graph execution: 40/40.
- Candidate-ready results: 40/40.
- External model calls: 0 in the evaluation.
- Three-arm comparative benchmark: NOT EXECUTED.
- Report quality metrics: NOT MEASURED.
- V1 failure report and V2 recovery report both preserved.

Candidate-ready is a component outcome, not proof of
semantic quality, factual grounding or usefulness.

Original evaluation thresholds remain unchanged:
structural validity 100%, citation coverage at least 95%,
human groundedness at least 95%, completion at least 90%,
usefulness at least 80% rated 4/5 or higher,
p95 latency at most 240 seconds, mean estimated variable
cost at most USD 0.50 per started task, zero accepted
fabricated citations, unauthorized tools or cross-user
disclosure, and at least 30% lower paired median analyst
preparation time.

No metric is inferred from component test success.

## 7. D06 obligation register

| Obligation | Disposition | Evidence / remaining requirement |
| --- | --- | --- |
| D06-01 | CLOSED_VERIFIED_SCOPED_DEVELOPMENT_MVP | E02/E05; Tavily only, historical actual account and bounded smoke |
| D06-02 | HISTORICAL_SCOPED_CLOSURE_PRESERVED | S07 isolated secure connector closure unchanged |
| D06-03 | HISTORICAL_SCOPED_CLOSURE_PRESERVED | S07 isolated budget/deadline closure unchanged |
| D06-04 | CLOSED_VERIFIED_SCOPED_DEVELOPMENT_MVP | E02/E06; actual one-credit accounting and fail-closed tests |
| D06-05 | OPEN | Complete real evidence workflow and factual grounding, S09-OB01/02 |
| D06-06 | OPEN | Complete integrated external security and historical gate reconciliation |

No production scope is granted by D06-01/04 scoped closure.

## 8. Mandatory successor obligations

S09-OB01:
Complete remaining AC22/23 real-workflow acceptance,
including actual bounded evidence integration and safe
sparse, inaccessible and conflicting evidence handling.

S09-OB02:
Complete AC26-29 comparable three-arm evaluation,
structural report citation metrics, human groundedness,
usefulness, completion, latency and cost.

Preserve frozen evidence membership, original rubrics,
thresholds, disagreement and comparison methodology.

D06-05 remains OPEN under these obligations.
D06-06 remains OPEN with AC30/31/33 and incomplete
security gates explicitly tracked, not silently transferred.

Previously recorded repository governance work remains
outstanding. No required-check configuration is inferred
from a successful CI run.

S09 has NOT STARTED.

## 9. Release restrictions and final gates

- No production authentication approval.
- No general live provider enablement.
- No paid/PAYG usage or external model inference approval.
- No shared database migration, worker activation, public
  report publication or deployment authorization.
- All consumed G04 authorizations remain consumed.
- Protected stash must remain unchanged.
- G07 allows docs-only delivery, not merge.
- G08 is a separate Owner-controlled gate.
- AC36 remains open pending closeout PR/main CI and
  completion of all applicable final acceptance gates.
- A successful docs-only merge does not by itself resolve
  AC30/31/33, D06-05/06 or partially verified security gates.
- No CLOSED declaration while applicable mandatory gates
  remain unsatisfied. Any further milestone change requires
  explicit Owner authority and original traceability.

PRODUCTION REMAINS NOT APPROVED.
