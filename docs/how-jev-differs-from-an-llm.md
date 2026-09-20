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

## 2. The LLM's numbers are better calibrated; Jev's have more range

| | 5th pct | median | 95th pct | share above 0.5 | mean stated | truth |
|---|---|---|---|---|---|---|
| Jev | 0.0 | 0.02 | 0.94 | 31.5% | 0.274 | 0.090 |
| chat LLM | 0.02 | 0.09 | 0.32 | 0.0% | 0.122 | 0.090 |

Jev uses the whole range and the chat LLM stays inside a narrow one, never once saying a person
is more likely than not. That much is true, and it looks like a win until you check what the
numbers mean:

| model | says 30-50% | those are actually positive | says 90-100% | those are actually positive | over-stated by |
|---|---|---|---|---|---|
| Jev | 77 people | 9.1% | 466 people | 28.8% | **3.05x** |
| chat LLM | 384 people | 31.5% | 0 people | n/a | **1.36x** |

**The chat LLM's probabilities are the better calibrated of the two.** The common claim that a
decision model hands you a trustworthy number and an LLM does not is false on this task. Jev's
range is confidence about which label it picked, not a probability that the person is sick.

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

At a 9.0% base rate these numbers mostly measure where each model put its
threshold. Jev flags 32% of people and
the chat LLM flags 45%, so the LLM buys
recall 84.2% against 70.8% and pays for it in precision. Compared at
matched coverage the two are within 0.2 to 2 points at every level, and inside narrow age bands
they are identical to two decimals. **They are tied on skill.** The trained logistic regression
beats both, because it had 248,680 labelled examples and they had none.

One more caveat worth stating: age band alone scores AUC 0.7215. Both arms add about 0.05 of AUC
on top of that and stop. There is not much learnable signal in 21 survey answers, which is the
real explanation for why neither zero-shot model is impressive here.

## 5. The reason is auditable

Jev names one of ten fixed factors. Of the answers that named one,
**99.9%** named a factor that is genuinely present in
that person's answers, so the explanation can be checked by a script rather than read and believed.
The chat LLM named a present factor 98.3% of the time,
also good, but it is prose, and checking prose does not scale the way checking a token does.

## What this does not say

It does not say Jev is better than an LLM. It says they are different instruments, and on this
task they were **equally skilled**: matched-coverage precision differs by 0.2 to 2 points at every
level, and within narrow age bands their AUC is identical to two decimals. Jev is a judgement
endpoint: one call, one typed answer, a reason code, no conversation, and a price per decision low
enough to run over every row you have. An LLM is a generalist you steer with prompts, and here it
was the better calibrated of the two. Both lost to a trained logistic regression that had a
quarter of a million labels.
