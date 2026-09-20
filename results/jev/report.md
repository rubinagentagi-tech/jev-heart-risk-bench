# Jev (jev-1.13.0) on CDC BRFSS 2015 heart disease

Model `jev-1.13.0` · 5,000 cases

- base rate in this sample: **9.0%** (449 of 5,000 really had heart disease)
- majority-class baseline: 91.0%
- accuracy: **72.2%**
- precision 20.2% · recall 70.8% · F1 0.314 · lift 2.247x
- AUC (ranking, threshold-free): 0.7725
- confusion: TP 318 · FP 1258 · FN 131 · TN 3293

## Confidence band vs accuracy

| band | cases | accuracy | actual positive rate |
|---|---|---|---|
| 0.00-0.50 | 1015 | 65.9% | 8.0% |
| 0.50-0.70 | 1409 | 55.9% | 13.2% |
| 0.70-0.85 | 1011 | 73.1% | 7.9% |
| 0.85-0.95 | 1110 | 89.8% | 5.9% |
| 0.95-1.01 | 455 | 91.9% | 8.1% |

## Auto-accept coverage vs error

| confidence >= | kept | coverage | error rate |
|---|---|---|---|
| 0.5 | 3985 | 79.7% | 26.17% |
| 0.7 | 2576 | 51.5% | 16.38% |
| 0.85 | 1565 | 31.3% | 9.58% |
| 0.95 | 455 | 9.1% | 8.13% |

## Calibration: stated probability vs reality

| stated | cases | mean stated | actual positive rate |
|---|---|---|---|
| 0.00-0.10 | 3092 | 1.3% | 3.3% |
| 0.10-0.20 | 190 | 13.1% | 6.3% |
| 0.20-0.30 | 55 | 24.3% | 12.7% |
| 0.30-0.45 | 53 | 36.2% | 9.4% |
| 0.45-0.60 | 168 | 54.0% | 13.1% |
| 0.60-0.80 | 604 | 69.9% | 15.2% |
| 0.80-1.00 | 838 | 90.4% | 24.9% |

## Stated reason (explainability check)

- a named factor: 4,320 of 5,000 (none_clear 13.6%)
- the named factor is actually present in the data: **99.9%**

| factor named | count |
|---|---|
| obesity | 1307 |
| high_blood_pressure | 1021 |
| none_clear | 680 |
| age | 564 |
| high_cholesterol | 463 |
| smoking_history | 413 |
| diabetes | 220 |
| prior_stroke | 185 |
| physical_inactivity | 87 |
| poor_self_rated_health | 60 |

## Modifiable risk factor present

- accuracy 83.6% · precision 83.6% · recall 100.0% · lift 1.0x (base rate 83.6%)

## Flag for follow-up

| threshold | flagged | coverage | precision | recall | lift |
|---|---|---|---|---|---|
| 0.5 | 3910 | 78.2% | 11.0% | 96.0% | 1.228x |
| 0.7 | 3140 | 62.8% | 12.9% | 90.2% | 1.436x |
| 0.85 | 1418 | 28.4% | 18.6% | 58.6% | 2.065x |

## Cost and speed

- latency mean 0.3777s · p50 0.372s · p95 0.473s
- input tokens 5,806,222 · output tokens 1,010,907
- cost $0.2439 total · $0.0488 per 1,000 cases
