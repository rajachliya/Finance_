# Sources and references

> **Warning:** These references were suggested by an AI (Claude) without access to search or a database. Authors, years, volumes, page numbers and editions may be wrong, and some may not exist. Check every one before citing it, and log any that turn out wrong in the AI usage log.

Every number in `data/` must trace to a row in the Data_Sources tab of the tracking workbook. The starter values in the CSVs are marked `STARTER VALUE suggested by AI` until replaced.

## Cost and quantity data

1. CPWD, Delhi Schedule of Rates (DSR) and Delhi Analysis of Rates (DAR), latest edition, Civil and E&M volumes. *Used for:* Activity costs (rates x quantities). *Where:* cpwd.gov.in.
2. CPWD, Plinth Area Rates, latest edition. *Used for:* Sanity check of whole-building cost per square metre. *Where:* cpwd.gov.in.
3. State PWD Schedule of Rates for your chosen city (for example Maharashtra PWD district SSR). *Used for:* Local cost check against DSR. *Where:* State PWD website.
## Durations

4. Bureau of Indian Standards, IS 7272 (Part 1): Recommendations for labour output constants for building work. *Used for:* Converting quantities into crew-days for three-point durations. *Where:* BIS website or institute library.
5. Bureau of Indian Standards, National Building Code of India 2016 (Part 4 fire and life safety; lifts). *Used for:* Scope of fire-fighting and lift activities. *Where:* BIS website or institute library.
6. Chitkara, K.K., Construction Project Management: Planning, Scheduling and Controlling, McGraw Hill Education (India). *Used for:* Activity logic and typical Indian building schedules. *Where:* Institute library.
7. Interviews with a site or planning engineer (record name, role, date). *Used for:* Three-point estimates, floor cycle time, realistic logic. *Where:* Your contacts; record in Data_Sources.
## Calibration

8. MoSPI, Infrastructure and Project Monitoring Division: project implementation status reports and monthly flash reports on central sector projects of Rs 150 crore and above (PAIMANA portal). *Used for:* Reference class of time and cost overruns; reasons for delay. *Where:* mospi.gov.in.
9. Comptroller and Auditor General of India, performance audit reports on construction and infrastructure. *Used for:* Case-level evidence of delays and overruns. *Where:* cag.gov.in.
10. Singh, R. (2010). Delays and cost overruns in infrastructure projects: extent, causes and remedies. Economic and Political Weekly, 45(21), 43-54. *Used for:* Indian overrun statistics and causes. *Where:* EPW archive or JSTOR.
11. Flyvbjerg, B., Holm, M.S. and Buhl, S. (2002). Underestimating costs in public works projects: error or lie? Journal of the American Planning Association, 68(3), 279-295. *Used for:* International overrun evidence. *Where:* Journal website.
12. Flyvbjerg, B. (2006). From Nobel Prize to project management: getting risks right. Project Management Journal, 37(3), 5-15. *Used for:* Reference class forecasting method. *Where:* Journal website.
## Risk register

13. Doloi, H., Sawhney, A., Iyer, K.C. and Rentala, S. (2012). Analysing factors affecting delays in Indian construction projects. International Journal of Project Management, 30(4), 479-489. *Used for:* Indian delay factors for risk events. *Where:* ScienceDirect.
14. Iyer, K.C. and Jha, K.N. (2005). Factors affecting cost performance: evidence from Indian construction projects. International Journal of Project Management, 23(4), 283-295. *Used for:* Indian cost overrun factors for risk events. *Where:* ScienceDirect.
15. India Meteorological Department, rainfall normals and monsoon onset and withdrawal dates for your city. *Used for:* Monsoon risk probability and working days lost. *Where:* mausam.imd.gov.in.
16. Office of the Economic Adviser, DPIIT, Wholesale Price Index series (steel, cement). *Used for:* Steel and cement price escalation risk. *Where:* eaindustry.nic.in.
## Method

17. Malcolm, D.G., Roseboom, J.H., Clark, C.E. and Fazar, W. (1959). Application of a technique for research and development program evaluation. Operations Research, 7(5), 646-669. *Used for:* Origin of PERT three-point estimates. *Where:* INFORMS / JSTOR.
18. Van Slyke, R.M. (1963). Monte Carlo methods and the PERT problem. Operations Research, 11(5), 839-860. *Used for:* Merge bias: why simulation beats single-path PERT. *Where:* INFORMS / JSTOR.
19. AACE International Recommended Practice 57R-09: Integrated cost and schedule risk analysis using Monte Carlo simulation of a CPM model. *Used for:* Professional standard for exactly this kind of tool. *Where:* aacei.org.
20. AACE International Recommended Practice 41R-08: Risk analysis and contingency determination using range estimating. *Used for:* Contingency setting from simulation. *Where:* aacei.org.
21. Hulett, D. (2009). Practical Schedule Risk Analysis. Gower. *Used for:* Schedule risk, criticality, risk drivers. *Where:* Library.
22. Vose, D. (2008). Risk Analysis: A Quantitative Guide, 3rd ed. Wiley. *Used for:* PERT-Beta, triangular, correlation in Monte Carlo. *Where:* Library.
23. Iman, R.L. and Conover, W.J. (1982). A distribution-free approach to inducing rank correlation among input variables. Communications in Statistics - Simulation and Computation, 11(3), 311-334. *Used for:* Alternative correlation method to the Gaussian copula. *Where:* Journal website.
24. Higham, N.J. (2002). Computing the nearest correlation matrix - a problem from finance. IMA Journal of Numerical Analysis, 22(3), 329-343. *Used for:* Fixing correlation matrices that are not positive semi-definite. *Where:* Journal website.
25. Williams, T.M. (1992). Criticality in stochastic networks. Journal of the Operational Research Society, 43(4), 353-357. *Used for:* Criticality and cruciality indices. *Where:* Journal website.
26. Project Management Institute (2009). Practice Standard for Project Risk Management. *Used for:* Risk register structure, probability-impact. *Where:* pmi.org or library.
## Finance

27. Reserve Bank of India, Database on Indian Economy: lending rates. *Used for:* Interest rate for construction debt. *Where:* dbie.rbi.org.in.
28. Real Estate (Regulation and Development) Act, 2016, and your state RERA portal (for example MahaRERA). *Used for:* Comparable project prices, timelines, escrow rules. *Where:* Government gazette; state RERA portal.
29. Damodaran, A., cost of capital and country risk premium datasets. *Used for:* Discount rate justification. *Where:* pages.stern.nyu.edu/~adamodar.
30. Property portals (for example 99acres, MagicBricks): asking prices for comparable projects. *Used for:* Sale price per sq ft (note: asking prices exceed transaction prices). *Where:* Websites.
## Course

31. CE725 Course Project brief, Annexure A (AI usage log) and Annexure B (charter). *Used for:* Log format and deliverables. *Where:* Course_Project.pdf.
