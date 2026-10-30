# Case study headline results (27 Oct 2026)

10,000 iterations, seed 42. Rerun `python scripts/run_case_study.py` after any data change.

## Schedule
- Plan with most-likely durations: 700 days (23.3 months)
- PERT on one critical path: 733 days
- Simulated P50 / P80 / P90: 778 / 817 / 839 days (25.9 / 27.2 / 28.0 months)
- Chance of finishing by the plan date: 2.7%

## Cost and contingency
- Base estimate: Rs 3,778 lakh; flat 10% budget: Rs 4,156 lakh
- P50 / P80 / P90 cost: Rs 4,024 / 4,114 / 4,166 lakh
- Contingency needed: 6.5% (P50), 8.9% (P80), 10.3% (P90)
- Chance a flat 10% is not enough: 11.5%

## Finance
- Plan NPV: Rs 614 lakh; plan + flat 10%: Rs 274 lakh
- Simulated median NPV: Rs 304 lakh; NPV with 80% confidence: Rs 195 lakh
- Chance NPV < 0: 1.2%
- Project IRR: plan 19.7%, simulated median 15.5%
- Equity IRR: plan 20.6%, simulated median 16.1%
- Interest during construction: plan Rs 84 lakh, simulated median Rs 112 lakh

## Cost of delay
- 30 days late at A28: NPV falls by Rs 52 lakh
- 60 days late at A28: NPV falls by Rs 104 lakh
- 90 days late at A28: NPV falls by Rs 155 lakh
- 180 days late at A28: NPV falls by Rs 306 lakh
- From the simulation: each extra month goes with about Rs 60 lakh less NPV

## What drives delay
- A28 Occupancy certificate and handover: critical in 100% of runs, rank correlation 0.51
- A10 Masonry floors 6-10: critical in 100% of runs, rank correlation 0.42
- A17 Flooring and wall tiling: critical in 100% of runs, rank correlation 0.38
- Risk R02 (Delay in fire NOC / occupancy approvals) adds 20 days to P80
- Risk R04 (Labour shortage after festival season) adds 8 days to P80
- Risk R08 (Contractor cash-flow problems slow work) adds 8 days to P80

## Model ladder (P80 duration, days)
- 1. Plan: most-likely durations: 700
- 2. PERT means on one critical path: 733
- 3. Simulation, activities independent: 755
- 4. + correlated activities: 760
- 5. + risk register events: 817

## Checks
- Correlation sensitivity: P80 moves +8 days between all-0 and all-0.9 correlation
- Convergence: P80 = 817.3 days at 10,000 runs vs 817.9 at 50,000

## One-line result (for slides, website, resume)
P80 contingency of 8.9% versus a flat 10%; P80 finish 3.9 months later than plan; median NPV Rs 310 lakh below the plan's.
