# Baselines

# Majority class (always predict 'no heart disease')

5,000 cases

- base rate in this sample: **9.0%** (449 of 5,000 really had heart disease)
- majority-class baseline: 91.0%
- accuracy: **91.0%**
- precision 0.0% · recall 0.0% · F1 0.000 · lift 0.0x
- AUC (ranking, threshold-free): 0.5
- confusion: TP 0 · FP 0 · FN 449 · TN 4551

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
| 0.00-0.10 | 5000 | 9.0% | 9.0% |


---

# Hand-written rule (flag 2 or more classic risk factors)

5,000 cases

- base rate in this sample: **9.0%** (449 of 5,000 really had heart disease)
- majority-class baseline: 91.0%
- accuracy: **47.1%**
- precision 13.3% · recall 88.4% · F1 0.231 · lift 1.478x
- AUC (ranking, threshold-free): 0.7283
- confusion: TP 397 · FP 2595 · FN 52 · TN 1956

## Confidence band vs accuracy

| band | cases | accuracy | actual positive rate |
|---|---|---|---|
| 0.50-0.70 | 5000 | 47.1% | 9.0% |

## Auto-accept coverage vs error

| confidence >= | kept | coverage | error rate |
|---|---|---|---|
| 0.5 | 5000 | 100.0% | 52.94% |
| 0.7 | 0 | 0.0% | n/a |
| 0.85 | 0 | 0.0% | n/a |
| 0.95 | 0 | 0.0% | n/a |

## Calibration: stated probability vs reality

| stated | cases | mean stated | actual positive rate |
|---|---|---|---|
| 0.00-0.10 | 819 | 0.0% | 2.0% |
| 0.10-0.20 | 1189 | 14.3% | 3.0% |
| 0.20-0.30 | 1215 | 28.6% | 7.4% |
| 0.30-0.45 | 940 | 42.9% | 13.9% |
| 0.45-0.60 | 546 | 57.1% | 18.7% |
| 0.60-0.80 | 229 | 71.4% | 23.1% |
| 0.80-1.00 | 62 | 85.9% | 33.9% |


---

# Logistic regression (trained on 248,680 labelled CDC respondents)

5,000 cases

- base rate in this sample: **9.0%** (449 of 5,000 really had heart disease)
- majority-class baseline: 91.0%
- accuracy: **79.1%**
- precision 26.0% · recall 71.7% · F1 0.382 · lift 2.894x
- AUC (ranking, threshold-free): 0.8417
- confusion: TP 322 · FP 917 · FN 127 · TN 3634

## Confidence band vs accuracy

| band | cases | accuracy | actual positive rate |
|---|---|---|---|
| 0.50-0.70 | 334 | 37.1% | 37.1% |
| 0.70-0.85 | 640 | 24.7% | 24.7% |
| 0.85-0.95 | 1319 | 76.4% | 9.6% |
| 0.95-1.01 | 2707 | 98.5% | 1.5% |

## Auto-accept coverage vs error

| confidence >= | kept | coverage | error rate |
|---|---|---|---|
| 0.5 | 5000 | 100.0% | 20.88% |
| 0.7 | 4666 | 93.3% | 17.87% |
| 0.85 | 4026 | 80.5% | 8.74% |
| 0.95 | 2707 | 54.1% | 1.51% |

## Calibration: stated probability vs reality

| stated | cases | mean stated | actual positive rate |
|---|---|---|---|
| 0.00-0.10 | 3537 | 3.1% | 2.9% |
| 0.10-0.20 | 787 | 14.3% | 14.9% |
| 0.20-0.30 | 317 | 24.3% | 27.1% |
| 0.30-0.45 | 216 | 36.2% | 33.8% |
| 0.45-0.60 | 94 | 51.1% | 38.3% |
| 0.60-0.80 | 43 | 68.6% | 67.4% |
| 0.80-1.00 | 6 | 82.8% | 66.7% |


---
