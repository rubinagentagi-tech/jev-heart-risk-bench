# Jev (jev-1.13.0) on CDC BRFSS 2015 heart disease

Model `jev-1.13.0` · 1,000 cases

- base rate in this sample: **9.2%** (92 of 1,000 really had heart disease)
- majority-class baseline: 90.8%
- accuracy: **74.0%**
- precision 22.2% · recall 72.8% · F1 0.340 · lift 2.411x
- AUC (ranking, threshold-free): 0.7864
- confusion: TP 67 · FP 235 · FN 25 · TN 673

## Confidence band vs accuracy

| band | cases | accuracy | actual positive rate |
|---|---|---|---|
| 0.00-0.50 | 209 | 66.0% | 8.6% |
| 0.50-0.70 | 279 | 60.6% | 14.7% |
| 0.70-0.85 | 196 | 74.5% | 6.1% |
| 0.85-0.95 | 214 | 90.2% | 6.1% |
| 0.95-1.01 | 102 | 92.2% | 7.8% |

## Auto-accept coverage vs error

| confidence >= | kept | coverage | error rate |
|---|---|---|---|
| 0.5 | 791 | 79.1% | 23.89% |
| 0.7 | 512 | 51.2% | 15.43% |
| 0.85 | 316 | 31.6% | 9.18% |
| 0.95 | 102 | 10.2% | 7.84% |

## Calibration: stated probability vs reality

| stated | cases | mean stated | actual positive rate |
|---|---|---|---|
| 0.00-0.10 | 638 | 1.3% | 3.3% |
| 0.10-0.20 | 40 | 13.1% | 7.5% |
| 0.20-0.30 | 6 | 24.2% | 0.0% |
| 0.30-0.45 | 10 | 37.1% | 10.0% |
| 0.45-0.60 | 25 | 55.1% | 16.0% |
| 0.60-0.80 | 136 | 69.3% | 14.0% |
| 0.80-1.00 | 145 | 90.6% | 30.3% |

## Choosing the cut-off in code (stated probability >= threshold)

| threshold | flagged | share of rows | precision | recall | F1 | lift |
|---|---|---|---|---|---|---|
| 0.05 | 423 | 42.3% | 17.5% | 80.4% | 0.287 | 1.902x |
| 0.10 | 362 | 36.2% | 19.6% | 77.2% | 0.313 | 2.132x |
| 0.15 | 334 | 33.4% | 20.7% | 75.0% | 0.324 | 2.246x |
| 0.20 | 322 | 32.2% | 21.1% | 73.9% | 0.329 | 2.295x |
| 0.25 | 318 | 31.8% | 21.4% | 73.9% | 0.332 | 2.324x |
| 0.30 | 316 | 31.6% | 21.5% | 73.9% | 0.333 | 2.339x |
| 0.40 | 310 | 31.0% | 21.9% | 73.9% | 0.338 | 2.384x |
| 0.50 | 305 | 30.5% | 22.0% | 72.8% | 0.338 | 2.388x |
| 0.60 | 281 | 28.1% | 22.4% | 68.5% | 0.338 | 2.437x |
| 0.70 | 210 | 21.0% | 26.2% | 59.8% | 0.364 | 2.847x |

## Stated reason (explainability check)

- a named factor: 856 of 1,000 (none_clear 14.4%)
- the named factor is actually present in the data: **100.0%**

| factor named | count |
|---|---|
| obesity | 255 |
| high_blood_pressure | 218 |
| none_clear | 144 |
| age | 108 |
| high_cholesterol | 98 |
| smoking_history | 85 |
| prior_stroke | 31 |
| diabetes | 27 |
| poor_self_rated_health | 17 |
| physical_inactivity | 17 |

## Modifiable risk factor present

- accuracy 83.0% · precision 83.0% · recall 100.0% · lift 1.0x (base rate 83.0%)

## Flag for follow-up

| threshold | flagged | coverage | precision | recall | lift |
|---|---|---|---|---|---|
| 0.5 | 776 | 77.6% | 11.2% | 94.6% | 1.219x |
| 0.7 | 628 | 62.8% | 13.2% | 90.2% | 1.437x |
| 0.85 | 256 | 25.6% | 20.7% | 57.6% | 2.25x |

## Cost and speed

- latency mean 0.3877s · p50 0.375s · p95 0.509s
- input tokens 1,161,333 · output tokens 202,198
- cost $0.0488 total · $0.0488 per 1,000 cases
