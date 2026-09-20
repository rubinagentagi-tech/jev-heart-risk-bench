# How Jev differs from an LLM,  measured, not asserted

Both models were asked the same question about the same 5,000 people, with the same
answer key and the same scoring script. Nothing here is a claim about what a model "feels like";
every line is a number from `results/`.

## 1. The output is typed, not prose

Jev returns one of four band labels, a probability distribution over them, a confidence, and a
reason code from a fixed list of ten. There is no text to parse.

The chat LLM had to be told to return JSON, and given `response_format: json_object` and
`temperature: 0`. It complied (0 unusable answers out of
5,000), so the usual "LLMs can't produce structured output" argument is **not**
supported by this run. What is different is the contract: Jev cannot return anything else. With
the LLM, the structure is a request you hope is honoured; with Jev it is the only thing the
endpoint can emit.

## 2. The LLM's number is a probability; Jev's is not

This is the finding that survived every check. Brier score with its Murphy decomposition, on the
same 5,000 rows:

| | Brier | reliability | resolution | skill vs base rate |
|---|---|---|---|---|
| Jev | 0.1892 | 0.1147 | 0.0072 | **-1.315** |
| chat LLM | 0.0746 | 0.0012 | 0.0071 | **+0.087** |

Read the middle two columns. **Resolution is identical** (0.0072 vs 0.0071): the two models make
the same quality of distinction, which is exactly why their matched-coverage precision curves sit
on top of each other. They differ in **reliability** (0.1147 vs 0.0012).

A skill score of **-1.315** means Jev's probabilities are worse than ignoring the model and
quoting the base rate on every row. Its number is closer to a confidence in the label it picked
than a probability the person is sick. The chat LLM's number, by contrast, is usable as a
probability.

The damage is localised, which makes it more interesting rather than less. Restrict to the range
where both models operate (stated probability <= 0.42, covering 67.7% of Jev's answers) and Jev's
mean stated is 0.028 against an actual 0.037: it is fine. All of the overconfidence lives in the
"elevated" and "high" tail, where it attaches 0.9 to 0.99 confidence to a group that is 28.8%
positive.

| | 5th pct | median | 95th pct | share above 0.5 | mean stated | truth |
|---|---|---|---|---|---|---|
| Jev | 0.0 | 0.02 | 0.94 | 31.5% | 0.274 | 0.090 |
| chat LLM | 0.02 | 0.09 | 0.32 | 0.0% | 0.122 | 0.090 |

Note also that the ranges barely overlap: the chat LLM never exceeds 0.42, so there is no way to
compare the two above that point at all. Any claim about "which is better calibrated" has to say
*where*.

## 3. Cost and speed

| | total for 5,000 people | per answer | mean latency |
|---|---|---|---|
| Jev | $0.2439 | $0.0488 per 1,000 | 0.378s |
| chat LLM | $0.6806 | $0.1361 per 1,000 | 0.932s |

Jev is **2.8x cheaper** and
**2.5x faster** on this workload. Its pricing model
is unusual and worth stating plainly: input tokens only, output free. The expensive part is the
question sheet, which is re-sent with every call,  trim the wording, not the data.

## 4. Accuracy, and why the headline numbers mislead

| | accuracy | AUC | precision | lift |
|---|---|---|---|---|
| Jev | 72.2% | 0.7725 | 20.2% | 2.247x |
| chat LLM | 61.2% | 0.7935 | 16.8% | 1.874x |
| logistic regression (supervised) | 79.1% | 0.8417 | 26.0% | 2.894x |

At a 9.0% base rate most of this table measures where each model put its
threshold. Jev flags 32% of people,
the chat LLM 45%. Bootstrapped
properly, the chat LLM's **ranking** advantage is real (AUC difference +0.021, 95% CI
[+0.011, +0.032]) but it is **too small to see at any single cut**: matched-coverage precision
differences at 5/10/20/30% flagged are +2.8, -0.2, +0.3, +0.2 points, and every one of those CIs
spans zero.

So the fair statement is that the chat LLM ranks slightly better across the whole ordering, and
that a practitioner choosing a threshold would not notice. Both lose to the trained regression,
which had 248,680 labelled examples against their none.

The 20 non-age fields, when a model can weight them jointly, are worth **+0.1203 AUC** (age band
alone 0.7215, all 21 fields 0.8417). Jev's zero-shot reading captures about 42% of that and the
chat LLM about 60%. That ratio, not the three-way table, is the real measure of what zero-shot
judgement buys you.

## 5. The reason is auditable

Jev names one of ten fixed factors. Of the answers that named one,
**99.9%** named a factor that is genuinely present in
that person's answers, so the explanation can be checked by a script rather than read and believed.
The chat LLM named a present factor 98.3% of the time,
also good, but it is prose, and checking prose does not scale the way checking a token does.

## What this does not say

It does not say Jev is better than an LLM. On this task the chat LLM ranked slightly better (a real
but sub-detectable +0.021 AUC) and, more importantly, produced numbers that work as probabilities
while Jev's did not (Brier skill -1.315 vs +0.087). Jev's case is operational: one call, one typed
answer, a reason code that is machine-checkable, no prompt to drift, 2.8x cheaper and 2.5x faster.
Both lost to a trained logistic regression that had a quarter of a million labels.

The transferable lesson is not about either vendor. **A typed decision output is not the same thing
as a calibrated probability, and a decision model is not calibrated just because it returns a
number beside its label.** Test the calibration on your own task before you build a threshold on it.
