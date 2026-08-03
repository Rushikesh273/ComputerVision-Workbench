# Material Giveaway — Financial Analytics

## 1. Overview

**Material giveaway** is the excess product given to customers beyond the
labeled/target weight, due to imprecision in filling/packaging processes.
It represents raw material that was paid for but not recovered in sale
price — a direct, recurring cost that scales with production volume.

This document defines the terms used to measure it, the formulas used to
calculate its financial impact, worked examples in INR (₹), and the
assumptions underlying the calculation.

## 2. Key Terms

| Term | Definition |
|---|---|
| **Target Weight** | The specified/labeled weight a unit should be filled to (the spec or recipe value). |
| **Actual Weight** | The measured weight of a given unit on the production line (e.g. from a checkweigher). |
| **Weight Drift** | The signed difference between actual and target weight. Positive = overfilled, negative = underfilled. |
| **Positive Drift** | Weight Drift > 0 — the unit is overfilled. This is the source of material giveaway. |
| **Negative Drift** | Weight Drift < 0 — the unit is underfilled. This is a compliance/quality risk, not a giveaway cost. |
| **Material Giveaway** | The portion of drift that represents wasted material cost — only positive drift counts. |

## 3. Formulas

```
Weight Drift        = Actual Weight − Target Weight

Material Giveaway    = max(0, Weight Drift)

Loss (₹)             = Material Giveaway (kg) × Cost per Kg (₹/kg)
```

The `max(0, ...)` term is deliberate: underfilled units are excluded from
the giveaway/loss calculation because they don't represent wasted
material — they represent a different problem (regulatory/compliance
risk from short-filling), which should be tracked as a separate metric,
not netted against overfill cost.

### Aggregate loss (batch/period level)

```
Total Loss (₹) = Σ [max(0, Actual Weight_i − Target Weight) × Cost per Kg]
                  for each unit i in the batch/period
```

Note: this sums giveaway **per unit first, then multiplies by cost** —
it does not average drift across the batch and multiply once. These are
mathematically different if the drift distribution is asymmetric (see
`Assumptions_Document.docx`).

## 4. Example Calculations

All examples use **Cost per Kg = ₹150/kg** and **Target Weight = 1.000 kg**
unless stated otherwise.

### Example 1 — Overfill (typical giveaway case)

| Field | Value |
|---|---|
| Target Weight | 1.000 kg |
| Actual Weight | 1.025 kg |
| Weight Drift | 1.025 − 1.000 = **+0.025 kg** |
| Material Giveaway | max(0, 0.025) = **0.025 kg** |
| Loss per unit | 0.025 × ₹150 = **₹3.75** |

### Example 2 — Underfill (compliance risk, zero giveaway cost)

| Field | Value |
|---|---|
| Target Weight | 1.000 kg |
| Actual Weight | 0.985 kg |
| Weight Drift | 0.985 − 1.000 = **−0.015 kg** |
| Material Giveaway | max(0, −0.015) = **0 kg** |
| Loss per unit | **₹0** (flag separately as underfill/compliance risk) |

### Example 3 — On-target (no drift)

| Field | Value |
|---|---|
| Target Weight | 1.000 kg |
| Actual Weight | 1.000 kg |
| Weight Drift | **0 kg** |
| Material Giveaway | **0 kg** |
| Loss per unit | **₹0** |

### Example 4 — Scaling to production volume

Using Example 1's per-unit loss of ₹3.75:

| Volume | Total Loss |
|---|---|
| 1,000 units/day | ₹3,750/day |
| 30,000 units/month | ₹1,12,500/month |
| 3,60,000 units/year | ₹13,50,000/year |

A giveaway that looks negligible per unit (25 grams) compounds into a
significant annual cost purely from production volume — this is the
core reason to track and formalize the metric rather than treat it as
noise.
