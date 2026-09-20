# Jev (jev-1.13.0) on CDC BRFSS 2015 heart disease

Model `jev-1.13.0` · 1,000 cases

- base rate in this sample: **9.2%** (92 of 1,000 really had heart disease)
- majority-class baseline: 90.8%
- accuracy: **42.0%**
- precision 13.0% · recall 93.5% · F1 0.229 · lift 1.416x
- AUC (ranking, threshold-free): 0.8059
- confusion: TP 86 · FP 574 · FN 6 · TN 334

## Confidence band vs accuracy

| band | cases | accuracy | actual positive rate |
|---|---|---|---|
| 0.70-0.85 | 39 | 51.3% | 51.3% |
| 0.85-0.95 | 961 | 41.6% | 7.5% |

## Auto-accept coverage vs error

| confidence >= | kept | coverage | error rate |
|---|---|---|---|
| 0.5 | 1000 | 100.0% | 58.00% |
| 0.7 | 1000 | 100.0% | 58.00% |
| 0.85 | 961 | 96.1% | 58.38% |
| 0.95 | 0 | 0.0% | n/a |

## Calibration: stated probability vs reality

| stated | cases | mean stated | actual positive rate |
|---|---|---|---|
| 0.00-0.10 | 48 | 8.7% | 0.0% |
| 0.10-0.20 | 952 | 12.5% | 9.7% |

## Choosing the cut-off in code (stated probability >= threshold)

| threshold | flagged | share of rows | precision | recall | F1 | lift |
|---|---|---|---|---|---|---|
| 0.05 | 1,000 | 100.0% | 9.2% | 100.0% | 0.169 | 1.0x |
| 0.10 | 952 | 95.2% | 9.7% | 100.0% | 0.176 | 1.05x |
| 0.15 | 84 | 8.4% | 40.5% | 37.0% | 0.386 | 4.4x |
| 0.20 | 0 | 0.0% | 0.0% | 0.0% | 0.000 | 0.0x |
| 0.25 | 0 | 0.0% | 0.0% | 0.0% | 0.000 | 0.0x |
| 0.30 | 0 | 0.0% | 0.0% | 0.0% | 0.000 | 0.0x |
| 0.40 | 0 | 0.0% | 0.0% | 0.0% | 0.000 | 0.0x |
| 0.50 | 0 | 0.0% | 0.0% | 0.0% | 0.000 | 0.0x |
| 0.60 | 0 | 0.0% | 0.0% | 0.0% | 0.000 | 0.0x |
| 0.70 | 0 | 0.0% | 0.0% | 0.0% | 0.000 | 0.0x |

## Stated reason (explainability check)

- a named factor: 856 of 1,000 (none_clear 14.4%)
- the named factor is actually present in the data: **100.0%**

| factor named | count |
|---|---|
| obesity | 254 |
| high_blood_pressure | 221 |
| none_clear | 144 |
| age | 107 |
| high_cholesterol | 98 |
| smoking_history | 84 |
| prior_stroke | 32 |
| diabetes | 26 |
| physical_inactivity | 18 |
| poor_self_rated_health | 16 |

## Modifiable risk factor present

- accuracy 83.0% · precision 83.0% · recall 100.0% · lift 1.0x (base rate 83.0%)

## Flag for follow-up

| threshold | flagged | coverage | precision | recall | lift |
|---|---|---|---|---|---|
| 0.5 | 776 | 77.6% | 11.2% | 94.6% | 1.219x |
| 0.7 | 623 | 62.3% | 13.3% | 90.2% | 1.448x |
| 0.85 | 260 | 26.0% | 20.4% | 57.6% | 2.216x |

## Cost and speed

- latency mean 0.3817s · p50 0.377s · p95 0.459s
- input tokens 971,333 · output tokens 176,125
- cost $0.0408 total · $0.0408 per 1,000 cases
