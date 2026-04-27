# Quarterly Report

A short sample document used by the file-based examples. It exercises
most of the supported markdown features.

## Highlights

- Revenue grew **14.5%** year over year.
- *Three* new regions opened.
- Operating costs held steady — see [the breakdown](https://example.com).

## Key numbers

Table: Revenue by region (USD millions).

| Region | Q1 | Q2 | Q3 | Q4 |
|--------|---:|---:|---:|---:|
| EMEA   |  4 |  6 |  7 |  9 |
| APAC   |  3 |  4 |  5 |  6 |
| AMER   |  8 |  9 | 11 | 12 |

## Methodology

> Figures are unaudited and rounded to the nearest million.

```python
total = sum(region.revenue for region in regions)
```

1. Pull from the data warehouse.
2. Aggregate by region and quarter.
3. Render with `md-reports`.
