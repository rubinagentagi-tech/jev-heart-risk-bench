# What this benchmark actually shows, and what I got wrong twice

This is the reasoning behind the numbers, written after two rounds of self-review. The point of
publishing it is that the corrections are more instructive than the original result.

## The question I was trying to answer

Does a typed decision model (Jev / TypeSafe System One) do something a chat LLM cannot, on a task
with a real answer key? The task: 5,000 real CDC survey respondents, 21 plain-English answers
each, decide whether the person has ever been told they had a heart attack or coronary heart
disease.

## What I got wrong the first time

I compared Jev and the chat LLM at each model's **own threshold**. Jev flagged 31.5% of people,
the LLM 44.9%. Flag more, catch more, look less precise. That is arithmetic, not skill. The
resulting line, "Jev beat the chat LLM", was an artifact of where each model happened to put its
cut.

## What I got wrong the second time, which is worse

I over-corrected and said the two were "tied on skill" because matched-coverage precision
differences were tiny. Then I bootstrapped it (2,000 resamples) and found the AUC difference is
**real**: +0.0210, 95% CI [+0.0106, +0.0319], CI excludes zero. So the honest position is:

- The chat LLM **does** rank better, consistently, across the whole ordering.
- That advantage is **too small to detect at any single operating point** with 449 positives:
  matched-coverage precision differences at 5/10/20/30% are +2.8, -0.2, +0.3, +0.2 points and
  every one of those CIs spans zero.

Both statements are true. "Tied" was the wrong word for a real but sub-detectable effect.

I also wrote "almost all the signal is age" from the fact that age band alone scores AUC 0.7215.
That reasoning is broken. Pooling across age bands inflates the apparent performance of any
age-correlated score. The correct check is within-stratum AUC, and there both models score
**0.70 to 0.80 inside narrow age bands**, which is real discrimination among people the same age.
The claim is refuted by my own follow-up test.

## The finding that actually matters

I expected a decision model to hand me a trustworthy probability and an LLM to hedge. The
opposite happened, and the Murphy decomposition of the Brier score makes it unambiguous:

| | Brier | reliability | resolution | skill vs base rate |
|---|---|---|---|---|
| Jev | 0.1892 | 0.1147 | 0.0072 | **-1.315** |
| chat LLM | 0.0746 | 0.0012 | 0.0071 | **+0.087** |

**Resolution is identical (0.0072 vs 0.0071).** The two models make the same quality of
distinction, which is why their matched-coverage precision curves sit on top of each other. They
differ entirely in **reliability** (0.1147 vs 0.0012).

A Brier skill score of **-1.315** means Jev's probabilities are worse than ignoring the model and
quoting the base rate on every row. Whatever its number means, it is not a probability that the
person is sick. It is closer to a confidence in the label it chose.

And the miscalibration is localised. Restrict to the range where both models operate (stated
probability ≤ 0.42, covering 67.7% of Jev's answers) and Jev's mean stated is 0.028 against an
actual 0.037: it slightly *under*-states and is perfectly usable. All of the damage is in the
"elevated" and "high" tail, which it assigns to a third of respondents with confidences of
0.9-0.99 on a group that is 28.8% positive.

## Why Jev over-assigns

Its criteria describe *risk factors* ("several risk factors acting together", "high blood pressure
plus high cholesterol"). Most adults have several risk factors, so a literal reading of the
contract puts a third of the population in the top two bands. The base rate is stated in the
instructions but nothing couples it to the rule. Rewriting the criteria to anchor the bands on the
measured base rate (contract v2) made it **worse**: 40% flagged instead of 30%. The model follows
the prose, not the percentages.

## How much does either model really extract?

Trained logistic regression on age band alone: AUC 0.7215. On all 21 fields: 0.8417. So the 20
non-age fields are worth **+0.1203** when a model can weight them jointly.

- Jev's zero-shot reading captures **+0.0510** of that, about 42%.
- The chat LLM captures **+0.0720**, about 60%.

Neither is doing the job a trained model does, and the gap is the price of not having labels.

## My verdict

Nothing "wins" on accuracy, and I would not trust any of the three-way claims in the original
table. What I would stand behind:

1. **A decision model's probability is not automatically a calibration.** This is the load-bearing
   finding, and it is large enough (skill -1.315 vs +0.09) that no multiple-comparisons objection
   touches it.
2. **Zero-shot judgement recovers roughly half the signal a trained model gets.** Useful if you
   have no labels, not a substitute if you do.
3. **Jev's real advantages are operational:** 2.8x cheaper, 2.5x faster, output that is typed by
   construction rather than by request, and a reason code that is machine-checkable (99.9% of
   named factors were genuinely present).
4. **If you need a probability, test the calibration before you deploy it.** On this task the
   general-purpose chat model's numbers were the usable ones.

## Caveats I would raise against my own work

- Complete-case deletion removed 42.5% of raw records, and missingness is not random.
- No BRFSS survey weights, so no number here is a population estimate.
- The label is *ever been told*, which is prevalence and depends on healthcare access. It is not
  incident risk, and the repo title should not pretend otherwise.
- Five arms and many metrics with no pre-registration. Only finding 1 is comfortably clear of that.
