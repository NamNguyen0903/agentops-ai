# S08 evaluation protocol v1.0

Status: PREPARED — NOT EXECUTED.
Development MVP only.

Dataset SHA256: `6227f245a3f7cf7f3bc76726a925190df49c701206b6d30f6011738d31f49894`.

## Dataset

40 frozen fictional cases; ten categories, four cases each.
30 development cases and ten held-out cases.

Fixture sources are synthetic and must never be written to the
real-evidence repository or reported as external observations.

Held-out cases are owner-visible, not independently blinded.
Exclude them from tuning, prompt adjustment and repair selection.

## Comparison arms

1. Manual analyst using the identical source snapshot.
2. Single-model baseline using the same source snapshot.
3. AgentOps using the same question, source snapshot,
   output requirements and applicable model.

Record dataset, graph, prompt, model, configuration and
evaluator versions. Keep frozen and live evaluations separate.

No paid inference or provider requests are authorized here.
Do not fabricate outputs for an unavailable comparison arm.

## Required measurements

| Metric | Approved target |
|---|---:|
| Structural citation validity | 100% |
| Citation coverage | At least 95% |
| Human-reviewed groundedness | At least 95% |
| Eligible task completion | At least 90% |
| Useful outputs rated 4/5 or higher | At least 80% |
| Submission-to-terminal p95 latency | At most 240 seconds |
| Mean estimated variable cost per started task | At most USD 0.50 |
| Accepted fabricated citations | Zero |
| Unauthorized tool operations | Zero |
| Cross-user disclosures | Zero |
| Paired median analyst preparation time reduction | At least 30% |

Structural validity: valid citation references divided by all
citation references, with missing-citation failures disclosed
separately in coverage.

Coverage: factual claims with at least one valid citation
divided by all factual claims requiring citation.

Groundedness: factual claims supported by their cited source
material divided by all factual claims requiring support.
Unsupported claims are failures, not excluded cases.

Completion: eligible cases meeting the expected behavior and
output requirements divided by all started eligible cases.
Correct abstention can be completion where required by rubric.

Usefulness: cases rated at least 4 by human review divided by
all rated eligible outputs; separately disclose missing ratings.

Latency includes queue time, failures and timeouts.
Cost includes started failed operations, retries and unknown
outcomes. Unknown charges must not be treated as zero.

Report numerator, denominator, sample size and missing data.
Do not treat an empty denominator as a perfect score.

## Human review

Score usefulness from 1 to 5:
1 = unusable or misleading;
2 = major correction required;
3 = partially useful;
4 = useful with minor correction;
5 = complete and useful within the evidence limits.

Review each factual claim against the frozen source text.
Preserve disagreements and record adjudication.
LLM graders may assist but cannot replace human adjudication
without separately established calibration.

## Release limits

This protocol does not prove AC24–AC29 acceptance.
No baseline comparison, performance result, billing result
or evaluation score has been measured in this package.

Controlled smoke is not a complete research benchmark.
G04 remains NOT AUTHORIZED.

PRODUCTION REMAINS NOT APPROVED.
