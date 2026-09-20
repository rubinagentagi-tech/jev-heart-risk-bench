# Jev (jev-1.13.0) on CDC BRFSS 2015 heart disease

Model `jev-1.13.0` · 1,000 cases

- base rate in this sample: **9.2%** (92 of 1,000 really had heart disease)
- majority-class baseline: 90.8%
- accuracy: **65.0%**
- precision 17.9% · recall 78.3% · F1 0.291 · lift 1.947x
- AUC (ranking, threshold-free): 0.7925
- confusion: TP 72 · FP 330 · FN 20 · TN 578

## Confidence band vs accuracy

| band | cases | accuracy | actual positive rate |
|---|---|---|---|
| 0.00-0.50 | 122 | 64.8% | 13.1% |
| 0.50-0.70 | 209 | 76.6% | 6.7% |
| 0.70-0.85 | 303 | 63.4% | 5.3% |
| 0.85-0.95 | 299 | 59.9% | 11.4% |
| 0.95-1.01 | 67 | 59.7% | 17.9% |

## Auto-accept coverage vs error

| confidence >= | kept | coverage | error rate |
|---|---|---|---|
| 0.5 | 878 | 87.8% | 34.97% |
| 0.7 | 669 | 66.9% | 38.57% |
| 0.85 | 366 | 36.6% | 40.16% |
| 0.95 | 67 | 6.7% | 40.30% |

## Calibration: stated probability vs reality

| stated | cases | mean stated | actual positive rate |
|---|---|---|---|
| 0.00-0.10 | 511 | 1.4% | 2.5% |
| 0.10-0.20 | 46 | 15.0% | 6.5% |
| 0.20-0.30 | 27 | 24.7% | 7.4% |
| 0.30-0.45 | 14 | 36.6% | 14.3% |
| 0.45-0.60 | 16 | 52.8% | 12.5% |
| 0.60-0.80 | 48 | 71.4% | 8.3% |
| 0.80-1.00 | 338 | 91.6% | 19.5% |

## Choosing the cut-off in code (stated probability >= threshold)

| threshold | flagged | share of rows | precision | recall | F1 | lift |
|---|---|---|---|---|---|---|
| 0.05 | 533 | 53.3% | 15.6% | 90.2% | 0.266 | 1.693x |
| 0.10 | 489 | 48.9% | 16.2% | 85.9% | 0.272 | 1.756x |
| 0.15 | 471 | 47.1% | 16.8% | 85.9% | 0.281 | 1.823x |
| 0.20 | 443 | 44.3% | 17.2% | 82.6% | 0.284 | 1.865x |
| 0.25 | 428 | 42.8% | 17.5% | 81.5% | 0.288 | 1.905x |
| 0.30 | 416 | 41.6% | 17.8% | 80.4% | 0.291 | 1.934x |
| 0.40 | 405 | 40.5% | 17.8% | 78.3% | 0.290 | 1.932x |
| 0.50 | 399 | 39.9% | 18.1% | 78.3% | 0.293 | 1.961x |
| 0.60 | 386 | 38.6% | 18.1% | 76.1% | 0.293 | 1.971x |
| 0.70 | 366 | 36.6% | 18.6% | 73.9% | 0.297 | 2.019x |

## Stated reason (explainability check)

- a named factor: 856 of 1,000 (none_clear 14.4%)
- the named factor is actually present in the data: **99.9%**

| factor named | count |
|---|---|
| obesity | 257 |
| high_blood_pressure | 216 |
| none_clear | 144 |
| age | 104 |
| high_cholesterol | 98 |
| smoking_history | 88 |
| prior_stroke | 32 |
| diabetes | 30 |
| physical_inactivity | 17 |
| poor_self_rated_health | 14 |

## Modifiable risk factor present

- accuracy 83.0% · precision 83.0% · recall 100.0% · lift 1.0x (base rate 83.0%)

## Flag for follow-up

| threshold | flagged | coverage | precision | recall | lift |
|---|---|---|---|---|---|
| 0.5 | 780 | 78.0% | 11.2% | 94.6% | 1.212x |
| 0.7 | 622 | 62.2% | 13.3% | 90.2% | 1.45x |
| 0.85 | 262 | 26.2% | 20.6% | 58.7% | 2.24x |

## Cost and speed

- latency mean 0.38s · p50 0.374s · p95 0.48s
- input tokens 1,224,333 · output tokens 202,165
- cost $0.0514 total · $0.0514 per 1,000 cases
