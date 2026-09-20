# Chat LLM (deepseek-chat) on the same 5,000 respondents

Model `deepseek-chat` · 5,000 cases

- base rate in this sample: **9.0%** (449 of 5,000 really had heart disease)
- majority-class baseline: 91.0%
- accuracy: **61.2%**
- precision 16.8% · recall 84.2% · F1 0.281 · lift 1.874x
- AUC (ranking, threshold-free): 0.7935
- confusion: TP 378 · FP 1868 · FN 71 · TN 2683

## Confidence band vs accuracy

| band | cases | accuracy | actual positive rate |
|---|---|---|---|
| 0.00-0.50 | 5000 | 61.2% | 9.0% |

## Auto-accept coverage vs error

| confidence >= | kept | coverage | error rate |
|---|---|---|---|
| 0.5 | 0 | 0.0% | n/a |
| 0.7 | 0 | 0.0% | n/a |
| 0.85 | 0 | 0.0% | n/a |
| 0.95 | 0 | 0.0% | n/a |

## Calibration: stated probability vs reality

| stated | cases | mean stated | actual positive rate |
|---|---|---|---|
| 0.00-0.10 | 2754 | 6.2% | 2.6% |
| 0.10-0.20 | 1856 | 16.8% | 13.8% |
| 0.20-0.30 | 6 | 22.7% | 16.7% |
| 0.30-0.45 | 384 | 33.2% | 31.5% |

## Stated reason (explainability check)

- a named factor: 4,395 of 5,000 (none_clear 12.1%)
- the named factor is actually present in the data: **98.3%**

| factor named | count |
|---|---|
| high_blood_pressure | 1554 |
| high_cholesterol | 709 |
| smoking_history | 612 |
| diabetes | 606 |
| none_clear | 605 |
| age | 315 |
| obesity | 293 |
| prior_stroke | 193 |
| physical_inactivity | 93 |
| poor_self_rated_health | 20 |

## Modifiable risk factor present

- accuracy 99.0% · precision 98.9% · recall 100.0% · lift 1.182x (base rate 83.6%)

## Flag for follow-up

| threshold | flagged | coverage | precision | recall | lift |
|---|---|---|---|---|---|
| 0.5 | 3697 | 73.9% | 11.6% | 95.8% | 1.295x |
| 0.7 | 3697 | 73.9% | 11.6% | 95.8% | 1.295x |
| 0.85 | 3697 | 73.9% | 11.6% | 95.8% | 1.295x |

## Cost and speed

- latency mean 0.9321s · p50 0.92s · p95 1.188s
- input tokens 3,950,968 · output tokens 146,608
- cost $0.6806 total · $0.1361 per 1,000 cases
