"""Twenty-four crashes of 2025-26, labelled by what happened next.

WHY THIS FILE IS IN THE REPOSITORY. A screen that claims to tell a
dislocation from a value trap is making a falsifiable claim, and a
falsifiable claim needs a scoreboard that cannot be quietly edited
after the fact. These are the cases, the inputs, and the labels. If the
screen scores them badly, that is visible here.

READ THE CONTAMINATION WARNINGS BEFORE TRUSTING ANY NUMBER.

1. THE INPUTS WERE ENCODED BY SOMEONE WHO KNEW THE ANSWERS. I wrote
   these snapshots after reading the outcomes. Every judgement call
   about a margin trend or a moat count had a thumb available to press
   on the scale, and no amount of care fully removes that. The right
   reading of any result here is "this is the most optimistic version
   of the screen's performance", not "this is its performance".

2. THE PRICES ARE FROM SEARCH SUMMARIES, NOT FROM A DATA FEED. This
   environment's egress proxy blocks every finance domain, so not one
   figure was read off a chart or a filing. Prices are +/-2%; several
   pre-crash peaks could not be sourced at all and are marked
   ``confidence="low"``. Peak-to-trough drawdowns built on an unsourced
   peak are the weakest numbers in the file.

3. AS-OF DISCIPLINE, AND WHERE IT BREAKS. Fundamentals are the last
   figures REPORTED BEFORE the trough, so the screen is scored on what
   it could have known. The exception is called out per case in
   ``lookahead``: ACN's raised buyback authorisation landed the day
   after the low, so it is excluded from the snapshot and recorded
   separately.

4. THE SAMPLE IS SMALL AND THE PERIOD IS ONE REGIME. Twenty-four names
   from a single AI-disruption cycle. A good AUC here is evidence that
   the screen is not obviously broken. It is not evidence that it works.

A NOTE ON WHAT THE OUTCOMES ACTUALLY MEAN. Two of the recoveries - UNH
and HUM - re-rated because a regulator deferred the risk (the April
2026 CMS rate decision), not because the bear case was refuted. UNH's
DOJ criminal probe is still open. They are labelled recoveries because
that is what the prices did, but a screen that gets them "right" for
structural reasons is getting the right answer from the wrong premise.
``narrative_resolution`` records the distinction.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from ..fable_score import SecuritySnapshot


# ticker -> (label, fields). label True = recovered from the trough.
#
# Field keys map onto SecuritySnapshot. ``dd`` is the drawdown from the
# 52-week high at the trough; ``vp`` the valuation percentile against the
# name's own history at the trough.
CASES: List[Dict] = [

    # ================= RECOVERIES =================

    dict(ticker="ACN", label=True, trough="2026-06-22", tier="A",
         trough_px=118.15, current_px=189.55, ret_from_trough=0.604,
         confidence="high", narrative_resolution="falsified",
         evidence="Q3 FY26: revenue $18.72B (+6%) vs $18.78B cons - a 0.3% "
                  "miss; bookings -2% y/y and -13% q/q; Q4 guide below the "
                  "low end; ~$400M of Middle East revenue lost. Margins and "
                  "cash generation intact (FY26 FCF guided $10.8-11.5B).",
         lookahead="The $7.5B buyback authorisation was announced 23 Jun, "
                   "one day AFTER the 22 Jun low, so the snapshot carries "
                   "only the prior ~$4.5B run-rate.",
         f=dict(roic=0.25, wacc=0.085, fcf_to_net_income=1.15, margin_trend=0,
                revenue_cagr_3y=0.05, demonstrated_growth=0.06,
                gross_margin_stability=0.85, moat_evidence_count=3,
                net_debt_to_ebitda=0.2, interest_coverage=30.0,
                dd=0.61, vp=2.0,
                dividend_yield=0.053, buyback_yield=0.061, sbc_yield=0.023,
                annual_volatility=0.35)),

    dict(ticker="CRM", label=True, trough="2026-06-22", tier="A",
         trough_px=146.32, current_px=255.65, ret_from_trough=0.747,
         confidence="medium", narrative_resolution="falsified",
         evidence="Feb 2026 'SaaSpocalypse': ~$285B of software cap wiped in "
                  "a day; a leaked Fortune-50 memo planned a 60% cut to "
                  "Salesforce/ServiceNow licences. Operating margin still "
                  "expanding, FCF conversion well above net income.",
         lookahead="Agentforce $1.5B ARR was disclosed ahead of Dreamforce, "
                   "AFTER the trough. Not in the snapshot.",
         f=dict(roic=0.13, wacc=0.09, fcf_to_net_income=1.60, margin_trend=1,
                revenue_cagr_3y=0.10, demonstrated_growth=0.10,
                gross_margin_stability=0.90, moat_evidence_count=3,
                net_debt_to_ebitda=-0.3, interest_coverage=20.0,
                dd=0.46, vp=3.0,
                dividend_yield=0.011, buyback_yield=0.055, sbc_yield=0.023,
                annual_volatility=0.38)),

    dict(ticker="NOW", label=True, trough="2026-04-23", tier="A",
         trough_px=81.24, current_px=141.07, ret_from_trough=0.736,
         confidence="medium", narrative_resolution="falsified",
         evidence="Q1 2026 beat every metric - subscription revenue $3.671B "
                  "(+19% cc), cRPO +21% cc and 100bps above guide, 32% op "
                  "margin vs 31.5% guided, 44% FCF margin - and the stock "
                  "fell 17% the next day, its worst ever. KeyBanc downgrade "
                  "on 'structural AI concerns'. Post-split prices.",
         lookahead="The $1B AI ACV disclosure came at Q2 on 22 Jul, three "
                   "months AFTER the trough.",
         f=dict(roic=0.15, wacc=0.09, fcf_to_net_income=1.80, margin_trend=1,
                revenue_cagr_3y=0.22, demonstrated_growth=0.22,
                gross_margin_stability=0.92, moat_evidence_count=4,
                net_debt_to_ebitda=-0.5, interest_coverage=30.0,
                dd=0.60, vp=2.0,
                dividend_yield=0.0, buyback_yield=0.008, sbc_yield=0.035,
                annual_volatility=0.42)),

    dict(ticker="TEAM", label=True, trough="2026-04-10", tier="A",
         trough_px=56.01, current_px=190.28, ret_from_trough=2.397,
         confidence="low", narrative_resolution="falsified",
         evidence="Named in the Feb 2026 software cohort; traded below 13.5x "
                  "forward earnings. WEAKEST-SOURCED CASE IN THE FILE - no "
                  "quarter-level revenue or ARR figure could be sourced, so "
                  "the fundamentals below are inference from the business "
                  "model, not from reported numbers.",
         lookahead="",
         f=dict(roic=0.08, wacc=0.095, fcf_to_net_income=2.50, margin_trend=1,
                revenue_cagr_3y=0.22, demonstrated_growth=0.22,
                gross_margin_stability=0.90, moat_evidence_count=3,
                net_debt_to_ebitda=-0.4, interest_coverage=15.0,
                dd=0.83, vp=1.0,
                dividend_yield=0.0, buyback_yield=0.010, sbc_yield=0.060,
                annual_volatility=0.50)),

    dict(ticker="UNH", label=True, trough="2026-03-27", tier="A",
         trough_px=255.97, current_px=399.0, ret_from_trough=0.559,
         confidence="medium", narrative_resolution="deferred",
         evidence="DOJ criminal AND civil probes into Medicare Advantage "
                  "billing; -16% on the fraud-probe headline; 2025 "
                  "medical-loss-ratio blowout. The cost problem was real and "
                  "in the numbers at the trough.",
         lookahead="The 7 Apr 2026 CMS rate decision (+11% in a day) and the "
                   "Q2 EPS +56% print both came AFTER the trough. The DOJ "
                   "probe is STILL OPEN - this recovery is the bear case "
                   "postponed, not refuted.",
         f=dict(roic=0.12, wacc=0.08, fcf_to_net_income=1.20, margin_trend=-1,
                revenue_cagr_3y=0.10, demonstrated_growth=0.08,
                gross_margin_stability=0.60, moat_evidence_count=3,
                net_debt_to_ebitda=1.4, interest_coverage=10.0,
                dd=0.59, vp=3.0,
                dividend_yield=0.035, buyback_yield=0.030, sbc_yield=0.005,
                annual_volatility=0.35)),

    dict(ticker="ELV", label=True, trough="2026-01-15", tier="A",
         trough_px=273.86, current_px=382.77, ret_from_trough=0.398,
         confidence="low", narrative_resolution="deferred",
         evidence="Medical-cost inflation across government-sponsored plans; "
                  "-30% to -32% through 2025. CONFLICT: a second undated "
                  "source quotes ELV at $323.05, which would make the "
                  "recovery +18% rather than +40%. Unresolved.",
         lookahead="Q1 2026 (22 Apr) EPS $12.58 vs $10.74 cons and the FY26 "
                   "guidance raise both came AFTER the trough.",
         f=dict(roic=0.11, wacc=0.085, fcf_to_net_income=1.10, margin_trend=-1,
                revenue_cagr_3y=0.08, demonstrated_growth=0.06,
                gross_margin_stability=0.55, moat_evidence_count=2,
                net_debt_to_ebitda=1.8, interest_coverage=8.0,
                dd=0.52, vp=4.0,
                dividend_yield=0.025, buyback_yield=0.050, sbc_yield=0.004,
                annual_volatility=0.33)),

    dict(ticker="CEG", label=True, trough="2025-04-08", tier="A",
         trough_px=161.35, current_px=379.25, ret_from_trough=1.350,
         confidence="medium", narrative_resolution="falsified",
         evidence="27 Jan 2025 DeepSeek R1: CEG -21% (-$22.8B) on the thesis "
                  "that efficient models collapse AI power demand; then the "
                  "April 2025 tariff drawdown. The Calpine acquisition was "
                  "already announced (10 Jan 2025).",
         lookahead="",
         f=dict(roic=0.14, wacc=0.08, fcf_to_net_income=0.90, margin_trend=1,
                revenue_cagr_3y=0.05, demonstrated_growth=0.15,
                gross_margin_stability=0.45, moat_evidence_count=3,
                net_debt_to_ebitda=1.2, interest_coverage=9.0,
                dd=0.54, vp=25.0,
                dividend_yield=0.009, buyback_yield=0.020, sbc_yield=0.003,
                annual_volatility=0.50)),

    dict(ticker="AAPL", label=True, trough="2025-04-09", tier="A",
         trough_px=168.15, current_px=284.47, ret_from_trough=0.717,
         confidence="medium", narrative_resolution="falsified",
         evidence="-19% in three days after 'Liberation Day', worst stretch "
                  "since 2001; 145% China duties implied; overlaid with "
                  "'Apple missed the AI cycle'. Cleanest pure-narrative case "
                  "in the set - the feared number was never a real number.",
         lookahead="The 12 Apr 2025 smartphone tariff exemption came three "
                   "days AFTER the low. Realised tariff cost since April "
                   "2025 totalled $3.3B against the feared 145% regime.",
         f=dict(roic=0.55, wacc=0.085, fcf_to_net_income=1.10, margin_trend=1,
                revenue_cagr_3y=0.03, demonstrated_growth=0.08,
                gross_margin_stability=0.95, moat_evidence_count=4,
                net_debt_to_ebitda=0.3, interest_coverage=40.0,
                dd=0.35, vp=20.0,
                dividend_yield=0.006, buyback_yield=0.038, sbc_yield=0.005,
                annual_volatility=0.30)),

    dict(ticker="NVDA", label=True, trough="2025-04-07", tier="A",
         trough_px=86.24, current_px=156.71, ret_from_trough=0.817,
         confidence="medium", narrative_resolution="falsified",
         evidence="DeepSeek: -17% in a day, -$589B, the largest single-day "
                  "loss in market history; then tariffs; then China export "
                  "restrictions. Traded near 20x forward earnings at the low.",
         lookahead="The H20 export-ban financial impact could not be sourced.",
         f=dict(roic=0.75, wacc=0.09, fcf_to_net_income=1.00, margin_trend=1,
                revenue_cagr_3y=0.70, demonstrated_growth=0.60,
                gross_margin_stability=0.85, moat_evidence_count=4,
                net_debt_to_ebitda=-0.5, interest_coverage=50.0,
                dd=0.44, vp=15.0,
                dividend_yield=0.0004, buyback_yield=0.015, sbc_yield=0.007,
                annual_volatility=0.55)),

    dict(ticker="DAL", label=True, trough="2025-04-30", tier="A",
         trough_px=39.94, current_px=95.68, ret_from_trough=1.395,
         confidence="low", narrative_resolution="falsified",
         evidence="April 2025: DAL -38%, UAL -40%, AAL -45% YTD; Delta, "
                  "American and Southwest all cut 2025 outlooks; recession "
                  "pricing. The current 52-week range no longer contains the "
                  "April 2025 low, so two windows are being spliced.",
         lookahead="Guidance was REINSTATED at Q2 2025 (EPS $5.25-6.25) "
                   "after the trough.",
         f=dict(roic=0.10, wacc=0.09, fcf_to_net_income=0.80, margin_trend=-1,
                revenue_cagr_3y=0.06, demonstrated_growth=0.10,
                gross_margin_stability=0.35, moat_evidence_count=2,
                net_debt_to_ebitda=2.0, interest_coverage=6.0,
                dd=0.43, vp=10.0,
                dividend_yield=0.015, buyback_yield=0.0, sbc_yield=0.003,
                annual_volatility=0.45)),

    dict(ticker="MU", label=True, trough="2025-08-15", tier="B",
         trough_px=111.87, current_px=1016.59, ret_from_trough=6.500,
         confidence="low", narrative_resolution="falsified",
         evidence="Classic memory-glut/commoditisation bear case. THREE "
                  "MUTUALLY INCONSISTENT LOWS in the sources ($106.75 / "
                  "$111.87 / $124.21); the magnitude (+650-720%) is "
                  "consistent, the base is not.",
         lookahead="The decisive fact - 2027 DRAM/HBM capacity contractually "
                   "sold out across 16 multi-year agreements - was disclosed "
                   "long after the trough.",
         f=dict(roic=0.12, wacc=0.10, fcf_to_net_income=0.60, margin_trend=1,
                revenue_cagr_3y=0.15, demonstrated_growth=0.20,
                gross_margin_stability=0.30, moat_evidence_count=2,
                net_debt_to_ebitda=0.5, interest_coverage=12.0,
                dd=0.30, vp=20.0,
                dividend_yield=0.004, buyback_yield=0.005, sbc_yield=0.012,
                annual_volatility=0.50)),

    dict(ticker="HUM", label=True, trough="2026-03-20", tier="B",
         trough_px=206.87, current_px=274.96, ret_from_trough=0.329,
         confidence="low", narrative_resolution="deferred",
         evidence="Star-Ratings headwind cut 2026 adjusted EPS guidance to "
                  ">=$9 from $17.14 in FY2025 - a ~47% earnings cut that was "
                  "REAL and still in the numbers. Conflicting 52-week ranges "
                  "across sources; current price NOT FOUND.",
         lookahead="The 7 Apr 2026 CMS decision (+2.48% vs +0.09% proposed) "
                   "came after the trough.",
         f=dict(roic=0.08, wacc=0.085, fcf_to_net_income=0.90, margin_trend=-1,
                revenue_cagr_3y=0.10, demonstrated_growth=0.02,
                gross_margin_stability=0.50, moat_evidence_count=2,
                net_debt_to_ebitda=1.5, interest_coverage=8.0,
                dd=0.40, vp=5.0,
                dividend_yield=0.018, buyback_yield=0.010, sbc_yield=0.004,
                annual_volatility=0.38)),

    dict(ticker="CVS", label=True, trough="2025-04-10", tier="C",
         trough_px=69.51, current_px=94.49, ret_from_trough=0.359,
         confidence="low", narrative_resolution="falsified",
         evidence="Aetna medical-loss-ratio blowout, CEO ousted. Recovery of "
                  "+35.9% MISSES the +40% bar used for the other cases; "
                  "included because excluding near-misses biases the test.",
         lookahead="MBR improvement to 85% from 87% and the '$13B reprieve' "
                   "(Apr 2026) both came later.",
         f=dict(roic=0.07, wacc=0.08, fcf_to_net_income=1.20, margin_trend=-1,
                revenue_cagr_3y=0.09, demonstrated_growth=0.0,
                gross_margin_stability=0.35, moat_evidence_count=2,
                net_debt_to_ebitda=3.3, interest_coverage=6.0,
                dd=0.55, vp=3.0,
                dividend_yield=0.038, buyback_yield=0.0, sbc_yield=0.004,
                annual_volatility=0.33)),

    dict(ticker="INTC", label=True, trough="2025-09-01", tier="contrast",
         trough_px=18.0, current_px=68.0, ret_from_trough=2.780,
         confidence="low", narrative_resolution="falsified",
         evidence="FAILS THE QUALITY SCREEN AT THE TROUGH - a distressed "
                  "turnaround, not a quality company temporarily mispriced. "
                  "Included deliberately as a case the screen SHOULD reject "
                  "and still be right to reject, even though it went up "
                  "278%. Trough price and date could not be sourced; the "
                  "+278% is well sourced, the base is not.",
         lookahead="Q1/Q2 2026 beats, the 18A ramp, the reported Apple "
                   "foundry agreement - all later.",
         f=dict(roic=0.00, wacc=0.09, fcf_to_net_income=None, margin_trend=-1,
                revenue_cagr_3y=-0.08, demonstrated_growth=-0.05,
                gross_margin_stability=0.40, moat_evidence_count=2,
                net_debt_to_ebitda=3.2, interest_coverage=2.0,
                dd=0.70, vp=5.0,
                dividend_yield=0.0, buyback_yield=0.0, sbc_yield=0.020,
                annual_volatility=0.55)),

    # ================= TRAPS =================

    dict(ticker="CTSH", label=False, trough=None, tier="trap",
         trough_px=38.97, current_px=38.97, ret_from_trough=-0.44,
         confidence="high", narrative_resolution="unresolved",
         evidence="THE MOST INSTRUCTIVE CASE IN THE FILE: same sector, same "
                  "AI-deflation narrative, same catalyst day as ACN, "
                  "opposite outcome. CTSH BEAT adjusted EPS in each of its "
                  "last five quarters; Q1 2026 revenue $5.41B (+5.8%), adj. "
                  "EPS $1.40 vs $1.33. It is NOT fundamentally broken - it "
                  "printed a staircase of fresh 52-week lows ($58.86 -> "
                  "$58.83 -> $50.81 -> $45.39 -> $38.97) anyway. On the "
                  "fields this screen reads, CTSH and ACN are near-twins.",
         lookahead="",
         f=dict(roic=0.11, wacc=0.09, fcf_to_net_income=1.10, margin_trend=0,
                revenue_cagr_3y=0.04, demonstrated_growth=0.04,
                gross_margin_stability=0.75, moat_evidence_count=2,
                net_debt_to_ebitda=-0.5, interest_coverage=30.0,
                dd=0.55, vp=2.0,
                dividend_yield=0.028, buyback_yield=0.045, sbc_yield=0.012,
                annual_volatility=0.33)),

    dict(ticker="LULU", label=False, trough=None, tier="trap",
         trough_px=96.54, current_px=96.54, ret_from_trough=-0.61,
         confidence="high", narrative_resolution="confirmed",
         evidence="Broke its June 2026 low of $109.36 and KEPT GOING to "
                  "$96.54, an 8-year low, down 43-46% in 2026 after being "
                  "down 45% in 2025. FY26 revenue guidance CUT to "
                  "$11.0-11.15B from $11.35-11.5B; gross margin -410bps in "
                  "Q1 on tariffs and promotions; the China growth leg "
                  "cracked. The tell: guidance was cut AGAIN after the stock "
                  "was already down 45%.",
         lookahead="",
         f=dict(roic=0.25, wacc=0.09, fcf_to_net_income=0.90, margin_trend=-1,
                revenue_cagr_3y=0.06, demonstrated_growth=0.0,
                gross_margin_stability=0.70, moat_evidence_count=2,
                net_debt_to_ebitda=-0.3, interest_coverage=30.0,
                dd=0.55, vp=1.0,
                dividend_yield=0.0, buyback_yield=0.055, sbc_yield=0.006,
                annual_volatility=0.45)),

    dict(ticker="NKE", label=False, trough=None, tier="trap",
         trough_px=36.28, current_px=36.28, ret_from_trough=-0.40,
         confidence="high", narrative_resolution="confirmed",
         evidence="12-year low, worst stock in the Dow. FY2026 revenue "
                  "$46.4B, flat reported / -2% cc - back at FY2022 levels "
                  "while net income is ~49% lower and FCF ~51% lower. That "
                  "is an EARNINGS-POWER impairment, not multiple "
                  "compression. Back-to-school brand popularity 92.5% (2021) "
                  "-> 38.2% (2025) -> 45.8% (2026).",
         lookahead="",
         f=dict(roic=0.12, wacc=0.085, fcf_to_net_income=0.60, margin_trend=-1,
                revenue_cagr_3y=-0.02, demonstrated_growth=-0.05,
                gross_margin_stability=0.60, moat_evidence_count=3,
                net_debt_to_ebitda=0.6, interest_coverage=12.0,
                dd=0.50, vp=2.0,
                dividend_yield=0.045, buyback_yield=0.020, sbc_yield=0.008,
                annual_volatility=0.35)),

    dict(ticker="INTU", label=False, trough=None, tier="trap",
         trough_px=255.08, current_px=255.08, ret_from_trough=-0.54,
         confidence="high", narrative_resolution="confirmed",
         evidence="From >$813 to $255.08. TurboTax unit growth guided to "
                  "2-3%; the CEO admitted Intuit 'lost quality DIY customers "
                  "to low-cost providers' - the price umbrella is gone, "
                  "which is exactly the mechanism the bears described. The "
                  "answer to AI was a 17% workforce cut and a $300M "
                  "restructuring charge, not a new revenue line.",
         lookahead="",
         f=dict(roic=0.14, wacc=0.09, fcf_to_net_income=1.20, margin_trend=-1,
                revenue_cagr_3y=0.10, demonstrated_growth=0.08,
                gross_margin_stability=0.80, moat_evidence_count=3,
                net_debt_to_ebitda=0.8, interest_coverage=15.0,
                dd=0.55, vp=3.0,
                dividend_yield=0.018, buyback_yield=0.030, sbc_yield=0.045,
                annual_volatility=0.38)),

    dict(ticker="IT", label=False, trough=None, tier="trap",
         trough_px=130.0, current_px=130.0, ret_from_trough=-0.63,
         confidence="medium", narrative_resolution="confirmed",
         evidence="THE CLEANEST QUANTITATIVE TRAP SIGNATURE IN THE DATASET: "
                  "operating margin 16.6% -> 5.7% and FCF margin 38.1% -> "
                  "17.6%, both roughly halved, while FY26 revenue was guided "
                  "to just 2% FX-neutral growth. -64% over 52 weeks, -71% "
                  "from the all-time high. Compare ACN, whose margins and "
                  "cash generation held while only the multiple collapsed.",
         lookahead="",
         f=dict(roic=0.18, wacc=0.09, fcf_to_net_income=0.90, margin_trend=-1,
                revenue_cagr_3y=0.04, demonstrated_growth=0.02,
                gross_margin_stability=0.60, moat_evidence_count=3,
                net_debt_to_ebitda=1.2, interest_coverage=12.0,
                dd=0.64, vp=1.0,
                dividend_yield=0.0, buyback_yield=0.060, sbc_yield=0.012,
                annual_volatility=0.40)),

    dict(ticker="TTD", label=False, trough=None, tier="trap",
         trough_px=30.0, current_px=30.0, ret_from_trough=-0.62,
         confidence="medium", narrative_resolution="confirmed",
         evidence="Q2 revenue $715M, +3% y/y, against +19% in the same "
                  "quarter a year earlier - growth from 19% to 3% in four "
                  "quarters is a structural share-loss signature. -22% on 7 "
                  "Aug 2026 to its lowest since January 2019. Morningstar "
                  "models share falling from ~2% to ~1.2% by 2034. No AI "
                  "narrative needed: the competitor (Amazon's DSP) was real.",
         lookahead="",
         f=dict(roic=0.20, wacc=0.095, fcf_to_net_income=1.30, margin_trend=-1,
                revenue_cagr_3y=0.15, demonstrated_growth=0.03,
                gross_margin_stability=0.80, moat_evidence_count=2,
                net_debt_to_ebitda=-0.6, interest_coverage=40.0,
                dd=0.66, vp=3.0,
                dividend_yield=0.0, buyback_yield=0.040, sbc_yield=0.050,
                annual_volatility=0.55)),

    dict(ticker="CSGP", label=False, trough=None, tier="trap",
         trough_px=30.0, current_px=30.0, ret_from_trough=-0.57,
         confidence="medium", narrative_resolution="confirmed",
         evidence="CRITICAL FOR THE MODEL: CoStar grew revenue 18% and "
                  "closed an $800M acquisition WHILE FALLING 51%. Net new "
                  "bookings were $69M, ~26% BELOW the prior-year quarter. "
                  "Reported revenue growth is not a defence; bookings "
                  "direction is. Same metric that triggered Accenture - but "
                  "CoStar's kept deteriorating. CFO departed; removed from "
                  "the Nasdaq-100 (-7.4% on that alone).",
         lookahead="",
         f=dict(roic=0.04, wacc=0.085, fcf_to_net_income=0.70, margin_trend=-1,
                revenue_cagr_3y=0.12, demonstrated_growth=0.05,
                gross_margin_stability=0.75, moat_evidence_count=3,
                net_debt_to_ebitda=-0.8, interest_coverage=25.0,
                dd=0.60, vp=5.0,
                dividend_yield=0.0, buyback_yield=0.005, sbc_yield=0.020,
                annual_volatility=0.40)),

    dict(ticker="BSX", label=False, trough=None, tier="trap",
         trough_px=45.0, current_px=45.0, ret_from_trough=-0.44,
         confidence="medium", narrative_resolution="confirmed",
         evidence="Guidance cut, then cut AGAIN - organic growth to 6.5-8% "
                  "from 10-11% - on 'an unanticipated degree of competitive "
                  "share movement in the US EP market'. Urology grew 1% in "
                  "Q2 2026. Repeat guidance cuts despite quarterly beats is "
                  "the pattern. A cyberattack added operational disruption.",
         lookahead="",
         f=dict(roic=0.10, wacc=0.085, fcf_to_net_income=0.85, margin_trend=-1,
                revenue_cagr_3y=0.16, demonstrated_growth=0.07,
                gross_margin_stability=0.70, moat_evidence_count=3,
                net_debt_to_ebitda=1.6, interest_coverage=12.0,
                dd=0.55, vp=8.0,
                dividend_yield=0.0, buyback_yield=0.005, sbc_yield=0.008,
                annual_volatility=0.33)),

    dict(ticker="NVO", label=False, trough=None, tier="trap",
         trough_px=35.0, current_px=35.0, ret_from_trough=-0.42,
         confidence="high", narrative_resolution="confirmed",
         evidence="THE PUREST 'BEAR CASE WAS SIMPLY CORRECT' CASE: 23 Feb "
                  "2026, CagriSema FAILED to show non-inferiority vs Lilly's "
                  "tirzepatide in Phase 3 REDEFINE 4 - primary endpoint "
                  "missed, -16% that day. February 2026 guidance projected a "
                  "5-13% SALES DECLINE. No amount of valuation support "
                  "survives a failed primary endpoint.",
         lookahead="",
         f=dict(roic=0.35, wacc=0.085, fcf_to_net_income=0.90, margin_trend=-1,
                revenue_cagr_3y=0.18, demonstrated_growth=-0.05,
                gross_margin_stability=0.80, moat_evidence_count=3,
                net_debt_to_ebitda=0.4, interest_coverage=25.0,
                dd=0.56, vp=2.0,
                dividend_yield=0.040, buyback_yield=0.020, sbc_yield=0.003,
                annual_volatility=0.40)),

    dict(ticker="FI", label=False, trough=None, tier="trap",
         trough_px=59.09, current_px=59.09, ret_from_trough=-0.56,
         confidence="high", narrative_resolution="confirmed",
         evidence="-44% in a single day on 29 Oct 2025, its worst ever, then "
                  "kept making new lows for four MORE months. The -44% day "
                  "was not capitulation. Organic growth collapsed to 1% y/y; "
                  "FY revenue growth guidance cut from ~10% to 3.5-4% and "
                  "adj. EPS from $10.15-10.30 to $8.50-8.60. Peak-to-trough "
                  "-75%.",
         lookahead="",
         f=dict(roic=0.09, wacc=0.085, fcf_to_net_income=1.10, margin_trend=-1,
                revenue_cagr_3y=0.06, demonstrated_growth=0.01,
                gross_margin_stability=0.70, moat_evidence_count=3,
                net_debt_to_ebitda=2.9, interest_coverage=7.0,
                dd=0.72, vp=1.0,
                dividend_yield=0.0, buyback_yield=0.090, sbc_yield=0.010,
                annual_volatility=0.45)),

    dict(ticker="PODD", label=False, trough=None, tier="trap",
         trough_px=148.84, current_px=148.84, ret_from_trough=-0.40,
         confidence="low", narrative_resolution="confirmed",
         evidence="The recurring pattern: beat Q2 on both lines, then cut "
                  "full-year revenue growth guidance and guide Q3 below. "
                  "THINNEST SOURCING OF THE TRAPS - directionally solid, "
                  "details unverified.",
         lookahead="",
         f=dict(roic=0.12, wacc=0.09, fcf_to_net_income=0.60, margin_trend=0,
                revenue_cagr_3y=0.22, demonstrated_growth=0.18,
                gross_margin_stability=0.70, moat_evidence_count=3,
                net_debt_to_ebitda=1.0, interest_coverage=10.0,
                dd=0.48, vp=10.0,
                dividend_yield=0.0, buyback_yield=0.0, sbc_yield=0.012,
                annual_volatility=0.42)),
]


def _snapshot(case: Dict) -> SecuritySnapshot:
    f = dict(case["f"])
    return SecuritySnapshot(
        ticker=case["ticker"],
        roic=f["roic"], wacc=f["wacc"],
        fcf_to_net_income=f["fcf_to_net_income"],
        margin_trend=f["margin_trend"],
        revenue_cagr_3y=f["revenue_cagr_3y"],
        demonstrated_growth=f["demonstrated_growth"],
        gross_margin_stability=f["gross_margin_stability"],
        moat_evidence_count=f["moat_evidence_count"],
        net_debt_to_ebitda=f["net_debt_to_ebitda"],
        interest_coverage=f["interest_coverage"],
        pct_off_52w_high=f["dd"],
        valuation_percentile_vs_history=f["vp"],
        dividend_yield=f["dividend_yield"],
        buyback_yield=f["buyback_yield"],
        sbc_yield=f["sbc_yield"],
        annual_volatility=f["annual_volatility"],
        adequately_liquid=True, has_defined_exit=True,
    )


def load_cases(exclude_tiers: Tuple[str, ...] = ()) -> List[Tuple[Dict, SecuritySnapshot]]:
    """Cases paired with the snapshot the screen would have seen."""
    return [(c, _snapshot(c)) for c in CASES
            if c["tier"] not in exclude_tiers]


def labels(exclude_tiers: Tuple[str, ...] = ()) -> Dict[str, bool]:
    return {c["ticker"]: c["label"] for c, _ in load_cases(exclude_tiers)}


def realized_returns(exclude_tiers: Tuple[str, ...] = ()) -> Dict[str, float]:
    """Return from the screen's entry point to 17 Sep 2026.

    For recoveries this is measured from the trough; for traps from the
    point the drawdown would have put them on the screen. Both are
    rough - treat the SIGN as sound and the magnitude as +/-10 points.
    """
    return {c["ticker"]: c["ret_from_trough"] for c, _ in load_cases(exclude_tiers)}
