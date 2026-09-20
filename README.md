# JEV heart-risk bench

Can a **decision model** read a plain-English health survey and judge a person's heart-disease
risk? This repo scores [Jev](https://typesafe.ai) (TypeSafe's System One, `jev-1.13.0`) on
**5,000 real respondents** from the CDC's 2015 Behavioral Risk Factor Surveillance
System, against a logistic regression, a hand-written rule, a chat LLM and the base rate.

**Interactive demo, build a person and ask Jev:**
https://rubinagentagi-tech.github.io/jev-heart-risk-bench/

![the app](app-preview.png)

![Jev's risk band across 5,000 real respondents](beads-jev-band.png)

Every profile in that demo was genuinely scored by Jev: all 29,952 cells of a full
factorial over the answers the visitor can change, with what actually happened to the real
respondents in each cell shown beside it.

## Headline numbers

All arms scored on the identical 5,000 respondents by the same script
(`src/score.py`). Base rate **9.0%**.

| arm | trained on | accuracy | AUC | precision | recall | lift | cost | per answer |
|---|---|---|---|---|---|---|---|---|
| Always say no |,  | 91.0% | 0.500 |,  | 0% |,  | $0 |,  |
| Hand-written rule (2+ risk factors) |,  | 47.1% | 0.7283 | 13.3% | 88.4% | 1.478x | $0 |,  |
| Logistic regression | 248,680 labelled respondents | 79.1% | 0.8417 | 26.0% | 71.7% | 2.894x | $0 |,  |
| Chat LLM (`deepseek-chat`) | nothing, a written question | 61.2% | 0.7935 | 16.8% | 84.2% | 1.874x | $0.68 | 0.93s |
| **Jev (`jev-1.13.0`)** | **nothing, a written question** | **72.2%** | **0.7725** | **20.2%** | **70.8%** | **2.247x** | **$0.24** | **0.38s** |

Accuracy is a trap here. At a 9.0% base rate, saying "no" to everyone is
91.0% accurate and worthless. Read recall, precision, lift and AUC.

### What it got right

- **Typed output with a checkable reason.** Of the answers naming a factor,
  **99.9%** named a factor that was actually present in that
  person's survey answers. You can audit the reason mechanically instead of reading prose.
- **Cost and speed.** **2.8x cheaper** and
  **2.5x faster** than the chat LLM on the same rows, with
  nothing to parse.

### What it got wrong

- **It lost to a logistic regression** (0.8417 vs 0.7725 AUC) that had
  248,680 labelled examples. Jev had none. That is the honest trade.
- **It over-assigns risk.** It flags
  32% of respondents as elevated
  or high against a 9.0% base rate, and its stated probability is
  **3.05x too high on average**.
- **It fails the auto-accept gate.** At confidence ≥ 0.85 it keeps
  31% of rows with a 9.6%
  error rate, far above the 2% this bench demands before anything is taken without review.
- **Confidence is not accuracy.** Jev's accuracy climbs with its confidence
  (66% → 92%),
  but the actual positive rate inside those bands stays flat near the base rate. Its confidence
  orders the queue; it does not certify the answer.

## Read this before the head-to-head table (an earlier version of this repo got it wrong, twice)

The first version claimed Jev "beat the chat LLM". That compared each model at its *own*
threshold, which measures how many people each decided to flag, not skill. The second version
over-corrected and claimed the two were "tied on skill". Both are wrong, and the second error is
more interesting than the first.

Everything below is from `src/rigour_check.py` (2,000-resample bootstrap, 95% CIs) with the full
output in `results/rigour-review.md`.

### What survives scrutiny

**1. The chat LLM's ranking is genuinely better, but by a small margin.**
AUC 0.7935 vs 0.7725, difference **+0.0210, 95% CI [+0.0106, +0.0319]**. The CI excludes
zero, so this is real, not noise.

**2. At any practical operating point you cannot see that difference.** Matched-coverage precision
differences at 5%, 10%, 20% and 30% flagged are +2.8, -0.2, +0.3 and +0.2 points, and **every one
of those CIs spans zero**. AUC detects a consistent small shift across the whole ranking; precision
at a fixed cut with 449 positives is too coarse to resolve it.

**3. The decisive finding is calibration, and it is not flattering to Jev.**

| | Brier | reliability | resolution | Brier skill vs base rate |
|---|---|---|---|---|
| Jev | 0.1892 | 0.1147 | 0.0072 | **-1.315** |
| chat LLM | 0.0746 | 0.0012 | 0.0071 | **+0.087** |

The two have **essentially identical resolution** (0.0072 vs 0.0071): they make the same quality of
distinction. They differ entirely in reliability. Jev's stated probabilities are so far from the
truth that a negative skill score of -1.315 means you would do better ignoring them and just
quoting the base rate. A decision model handing you a number you cannot use is worse than one
that abstains.

**4. Jev is only miscalibrated where it is confident.** In the range where both models operate
(stated probability <= 0.42, which covers 67.7% of Jev's answers) Jev's mean stated is 0.028
against an actual 0.037, so it slightly *under*-states. All of its overconfidence is concentrated
in the "elevated" and "high" tail it assigns to a third of respondents.

**5. Neither model is "just reading age".** Age band alone scores AUC 0.7215, which is a strong
single predictor, but *within* narrow age bands, where age is nearly constant, both models still
score 0.70 to 0.80. That is real discrimination among people the same age. An earlier version of
this README claimed "almost all the signal is age"; pooling across age bands inflates the apparent
performance of any age-correlated score, and the within-band numbers refute the claim.

**6. A trained model extracts about 2.4x more non-age signal than Jev does.** Logistic regression
on age band alone: AUC 0.7215. On all 21 fields: 0.8417, so the 20 non-age fields are worth
**+0.1203** when a model can weight them jointly. Jev's zero-shot reading captures +0.0510 of that
(about 42%), the chat LLM +0.0720 (about 60%).

### What did not survive

- **"The two are tied on skill."** Wrong. The AUC gap is real (CI excludes zero). It is small
  enough to be invisible at any single cut, but it is not zero.
- **"Almost all the signal is age."** Wrong, see point 5.
- **"Jev over-states by 3.05x."** True as a global average, misleading as a description. It is
  driven by the third of rows Jev puts in its high tail; elsewhere it is well behaved.
- **"The v3 contract ranks best."** On 1,000 rows with 92 positives the v1/v2/v3 AUCs are 0.7864,
  0.7925 and 0.8059, and **every pairwise CI spans zero**. The contract comparison cannot be
  resolved at that sample size and should not have been stated as a result.

### Limitations a reviewer should hold against this work

- **Complete-case deletion.** Deriving the cohort dropped 42.5% of raw records. Refusals and
  don't-knows are not missing at random, so 253,680 complete responses have a base
  rate of 9.4%, which is a property of this sample, not of US adults.
- **No survey weights.** BRFSS is a weighted sample. Applying none means every rate here is
  unweighted and not a population estimate.
- **The label is prevalence, not risk.** `_MICHD` records whether someone has *ever been told*
  they had a heart attack or CHD. It depends on whether they saw a doctor. Calling this a
  "heart risk" benchmark is loose; it is a "has been told" benchmark.
- **No pre-registration.** Five arms and many metrics were explored, so some differences will look
  real by chance. Only the calibration result is large enough to be safe from that criticism.

So the honest summary: **the chat LLM ranks slightly better, Jev's probabilities are unusable
while the LLM's are usable, and both are mediocre next to a trained model.** Jev's real advantages
are operational, 2.8x cheaper and
2.5x faster with a checkable reason code.

## The decision contract matters as much as the model

Same model, same 1,000 respondents, three ways of asking:

| contract | asks for | accuracy | AUC | what happened |
|---|---|---|---|---|
| v1 | one of four described bands | 74.0% | 0.7864 | flags 30% of people against a 9% rate |
| v2 | bands rewritten around the measured base rate | 65.0% | 0.7925 | worse, it flags 40%. It follows the words, not the percentages |
| v3 | the probability itself, as a typed judgement | 42.0% | 0.8059 | highest AUC, but every answer lands between 8% and 19% |

v3's AUC is nominally the highest (0.8059 against 0.7864 for v1) **but every pairwise bootstrap CI
spans zero at this sample size**, so that ordering is not established. What *is* solid is the
shape: v3's number is a ranking score, not a probability. Every one of its answers landed between
0.08 and 0.19, so reading it as "a 15% chance" is meaningless. The cut-off therefore belongs in
your code, where it can be tuned and reported: at 0.15 it flags 8.4% of respondents at 40.5%
precision, a 4.4x lift over the base rate. The model judges, the cut-off is yours.

The one contract finding that is safe to state is about over-assignment, which is a rate, not an
AUC: v1 flags 30% of respondents against a 9% base rate and v2, rewritten to anchor the bands on
the measured base rate, flags **40%**. The model follows the words in the criteria, not the
percentages printed beside them.

## Two bugs worth reading about

1. **The codebook inverted two of the strongest risk factors.** `_RFHYPE5` and `_RFCHOL` in
   BRFSS are coded **1 = No, 2 = Yes**,  the opposite of the raw question variables. The first
   full run scored **AUC 0.4628**, below a coin flip, and Jev looked worthless. The bug was in
   the data pipeline, not the model. After the fix the same contract scored **0.7725**.
   `src/derive_cohort.py` now runs eight direction checks on the derived table and refuses to
   write the cohort if any factor has the wrong sign.
2. **Rewriting criteria to fix over-assignment did not work.** v2 anchored each band to the
   observed rate and made the over-assignment worse. The model treats the criterion text as a
   rule to apply, not as a calibration target to hit.

## Data

- **Survey:** Centers for Disease Control and Prevention, *Behavioral Risk Factor Surveillance
  System 2015*,  https://www.cdc.gov/brfss/annual_data/annual_2015.html
  A US federal government work, **public domain** under 17 U.S.C. § 105.
  Downloaded raw (`LLCP2015XPT.zip`), parsed, and derived to **253,680 complete
  responses**,  the same complete-case count the widely used Kaggle mirror of this table carries,
  which is a useful cross-check on the derivation.
- **Value mappings:** the official [BRFSS 2015 Codebook Report]
  (https://www.cdc.gov/brfss/annual_data/2015/pdf/codebook15_llcp.pdf), quoted in comments next
  to every mapping in `src/derive_cohort.py`.
- **Answer key:** the recorded `_MICHD` answer ("ever told you had a heart attack or coronary
  heart disease"). It is never sent to any model.
- **Model input:** 5,000
  plain-English survey answers per respondent,  age band, sex, BMI, general health, and the
  yes/no risk factors. No diagnosis, no arithmetic.

## Reproduce

```bash
bash download.sh                 # ~95 MB from cdc.gov, unzips to a 1.1 GB SAS transport file
pip install -r requirements.txt
python src/derive_cohort.py      # -> cohort.parquet (253,680 rows, 8 integrity checks)
python src/pack_builder.py --n 5000 --seed 20260920
python src/run_jev.py    --pack cases.jsonl --out results/jev --workers 10
python src/run_baselines.py
python src/run_llm_arm.py --pack cases.jsonl --out results/llm --workers 24
python src/make_grid.py && python src/run_jev_grid.py --pack grid-cases.jsonl --out results/grid
python src/make_app.py           # -> cardio-app.html
```

Cost of this whole bench: **$2.39** in API
calls (34,877,184 tokens for the app lattice alone, 0.24 for Jev and
$0.68 for the chat LLM on the 5,000-respondent benchmark).

## Credits

Created by **Rubin Varghese**. Built with **Jev** (TypeSafe System One, `jev-1.13.0`), with
`deepseek-chat` as the comparison arm and scikit-learn for the logistic regression.
Survey data: CDC BRFSS 2015, public domain. Value mappings: CDC BRFSS 2015 Codebook Report.

This is a demonstration on public survey data. It is not a medical device, not clinical advice,
and must not be used to make decisions about anyone's care.
