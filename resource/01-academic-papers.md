# Academic Research on Market Making — Curated Knowledge Base

Purpose: inform the design of a crypto market-making (MM) bot running on OKX / Binance / Bybit (spot and perpetual futures) via their APIs.

Conventions used in this file
- `s` = mid-price, `q` = signed inventory (base units, + long / − short), `γ` = risk aversion, `σ` = mid-price volatility (price units per √time), `T−t` = time to horizon, `δ^b`, `δ^a` = distance of bid / ask quote from the reference price, `λ(δ) = A e^{−kδ}` = fill intensity of a quote at distance `δ` (`A` = base arrival rate, `k` = decay of fill probability with distance; `κ` in Hummingbot notation).
- Local PDFs live in `papers/` (relative to this file). Everything downloaded was verified to be a real PDF (`file`, size > 200 KB). Paywalled papers are linked only.
- Each formula was checked against the extracted text of the downloaded PDF or the arXiv abstract unless flagged "(from memory / not re-verified)".
- Relevance rating: 5 = must implement / directly shapes the quoting engine; 1 = background only.

Table of contents
1. Classical foundations: Ho–Stoll, Glosten–Milgrom, Kyle
2. Avellaneda & Stoikov (2008)
3. Guéant, Lehalle, Fernandez-Tapia (2012/2013)
4. Guéant (2017) "Optimal market making" and the Guéant book
5. Cartea, Jaimungal & Penalva book; Cartea–Jaimungal papers (adverse selection, short-term alpha, order-book signals)
6. Fodra & Labadie (2012); Fodra & Pham (2013/2015)
7. Stoikov — the micro-price (2017/2018)
8. Order flow imbalance and queue-based prediction: Cont–Kukanov–Stoikov; Cont & de Larrard; Lipton–Pesavento–Sotiropoulos
9. Multi-asset MM and MM with hedging: Bergault–Guéant et al.; Barzykin–Bergault–Guéant
10. Reinforcement learning for MM: Spooner; Ganesh (JPM); Gašperov–Kostanjčar; Sadighian (crypto); Selser et al.; 2023–2026 RL/DL papers
11. Crypto-specific MM / microstructure papers (2020–2026), incl. perps, funding, Hummingbot's AS adaptation
12. Latency, stale quotes and sniping: Budish–Cramton–Shim; Aquilina–Budish–O'Neill; Gao & Wang; Cartea–Jaimungal–Sánchez-Betancourt
13. Synthesis: what the literature says a good MM strategy must do
14. Recommended reading order
15. Index of downloaded PDFs

---

## 1. Classical foundations (brief)

### 1.1 Ho & Stoll (1981) — "Optimal dealer pricing under transactions and return uncertainty"
- Authors / year: Thomas Ho, Hans R. Stoll, 1981. Journal of Financial Economics 9(1), 47–73.
- Link: https://doi.org/10.1016/0304-405X(81)90020-9 (paywalled; not downloaded).
- Key ideas
  - First dynamic-programming model of a monopolistic, risk-averse dealer who sets bid and ask to maximise expected utility of terminal wealth over a finite horizon, facing (i) return uncertainty on inventory and (ii) transaction (fill) uncertainty. Avellaneda–Stoikov explicitly describe their model as "closely related to a paper by Ho and Stoll (1981)" (see AS text, https://math.nyu.edu/~avellane/HighFrequencyTrading.pdf, Introduction).
  - The dealer's quotes are shifted relative to the "true" price as a function of inventory: long inventory → lower bid and ask; the inventory effect on quotes was later found empirically significant (Ho & Macris 1984, cited in AS).
  - Ho & Stoll (1980, competing dealers) tie bid/ask to the dealers' reservation (indifference) prices — the concept AS re-uses.
- Formulas / parameters: no closed form commonly reused today; the structure (spread grows with risk aversion × return variance × horizon; quote placement skews with inventory) is what AS formalises in closed form. (Qualitative summary from memory; not re-verified against the paywalled text.)
- How to apply: conceptual origin of "inventory skew". Nothing to implement directly.
- Relevance: 2

### 1.2 Glosten & Milgrom (1985) — "Bid, ask and transaction prices in a specialist market with heterogeneously informed traders"
- Authors / year: Lawrence Glosten, Paul Milgrom, 1985. JFE 14(1), 71–100.
- Link: https://doi.org/10.1016/0304-405X(85)90044-3 (paywalled). Abstract mirrored at https://business.columbia.edu/faculty/research/bid-ask-and-transaction-prices-specialist-market-heterogeneously-informed-traders
- Key ideas (from the published abstract)
  - Adverse selection alone creates a positive bid–ask spread even for a risk-neutral, zero-profit specialist: every trade against the dealer is with probability π an informed trader.
  - Transaction prices convey information; the serial correlation of price changes depends on the share of the spread due to adverse selection.
  - Observed returns ≈ realizable returns + what the uninformed lose to insiders.
- Formulas / parameters
  - Bid = E[V | next order is a sell], Ask = E[V | next order is a buy]; each fill updates the dealer's belief about V (Bayesian). Spread ∝ probability of informed trading × information asymmetry. (Standard textbook form; not re-verified against the paywalled text.)
- How to apply to a crypto MM bot
  - Justifies treating every fill as a (weak) signal: after a fill on the bid, shift the fair-value estimate down. In practice this is implemented via micro-price / OFI adjustments and post-fill "cooldowns".
  - Spread must cover expected adverse-selection loss (probability of "toxic" counterparty × expected move after the fill), not only inventory risk.
- Relevance: 3

### 1.3 Kyle (1985) — "Continuous auctions and insider trading"
- Authors / year: Albert S. Kyle, 1985. Econometrica 53(6), 1315–1335.
- Link: https://doi.org/10.2307/1913210 (paywalled).
- Key ideas
  - A single insider trades strategically against noise traders; the market maker sets price as a linear function of net order flow. Price impact ("Kyle's lambda") is the equilibrium price of adverse selection.
  - Insider trades gradually; information is impounded linearly over time in the continuous version.
- Formulas / parameters
  - Single period: P = p0 + λ(x + u), with λ = (1/2)·√(Σ0/σu²), where Σ0 = prior variance of the asset value and σu² = variance of noise-trader order flow. (Standard result from memory; not re-verified against the paywalled text.)
- How to apply
  - Net signed flow moves the fair price: use realised λ (regress mid changes on signed volume / OFI as in Cont–Kukanov–Stoikov, Section 8) as the price-impact coefficient in fair-value updates and in the adverse-selection buffer.
  - The "noise-to-informed" ratio is the fundamental profitability condition — echoed rigorously by Gao & Wang (Section 12.3).
- Relevance: 3

---

## 2. Avellaneda & Stoikov (2008) — "High-frequency trading in a limit order book"
- Authors / year: Marco Avellaneda, Sasha Stoikov, 2008. Quantitative Finance 8(3), 217–224.
- Links: DOI https://doi.org/10.1080/14697680701381228 ; open PDF https://math.nyu.edu/~avellane/HighFrequencyTrading.pdf ; earlier preprint https://people.orie.cornell.edu/sfs33/LimitOrderBook.pdf
- Local PDF: `papers/avellaneda-stoikov-2008-hft-limit-order-book.pdf`
- Key ideas
  - The dealer is one player in a limit order book; the "true" price is the market mid, modelled as arithmetic Brownian motion dS = σ dW (no drift, no autocorrelation — the agent "has no opinion on the drift").
  - Two sources of risk: inventory risk (diffusive mid) and execution/transaction risk (Poisson arrival of market orders hitting the quotes).
  - Two-step solution: (1) compute a personal indifference/reservation price given inventory; (2) calibrate bid/ask distances to the book's fill intensity λ(δ).
  - Fill intensity is derived from econophysics: power-law market-order sizes f(x) ∝ x^(−1−α) and log price impact Δp ∝ K ln(Q) give λ(δ) = A e^{−kδ} with A = Λ/α and k = αK (Λ = total market-order rate).
  - Simulation (s=100, T=1, σ=2, dt=0.005, γ=0.1, k=1.5, A=140): "inventory" strategy vs "symmetric" strategy with the same average spread (1.49): profit 65.0 (std 6.6) vs 68.4 (std 12.7); final-inventory std 2.9 vs 8.4. The inventory-aware strategy sacrifices a little mean P&L for roughly half the variance. For γ=0.01 both strategies are nearly identical; for γ=1 the inventory strategy has very low variance but much lower profit (31.4 vs 44.0).
  - The bid–ask spread is independent of inventory (because of exponential intensities); only its centre (the reservation price) moves with inventory.
- Formulas / parameters (verified in the PDF text)
  - Value function with CARA utility: u(s,x,q,t) = max E[−exp(−γ(X_T + q_T S_T))].
  - "Frozen inventory" reservation price: r(s,q,t) = s − q·γ·σ²·(T−t).
  - Reservation bid / ask (eqs. 6–7, verified): r^a(s,q,t) = s + (1 − 2q)·γσ²(T−t)/2 ; r^b(s,q,t) = s + (−1 − 2q)·γσ²(T−t)/2 ; their average is r (eq. 8).
  - Optimal total spread (first-order expansion in q, exponential intensities): δ^a + δ^b = γσ²(T−t) + (2/γ)·ln(1 + γ/k).
  - Quotes: bid = r − δ^b, ask = r + δ^a, symmetric around r (so δ^a = δ^b = half the spread above).
  - GLFT (Section 3) later report AS's expansion as: δ^b ≃ (1/γ) ln(1+γ/k) + ((1+2q)/2)·γσ²(T−t), δ^a ≃ (1/γ) ln(1+γ/k) + ((1−2q)/2)·γσ²(T−t).
  - Infinite-horizon (stationary) variant with a discount rate ω: reservation price becomes independent of t; AS interpret the parameter as an upper bound on the inventory the agent may take.
- How to apply to a crypto MM bot
  - This is the minimal viable quoting engine: `r = mid − q·γ·σ²·τ`, `half_spread = γσ²τ/2 + (1/γ)·ln(1+γ/k)`, bid/ask = r ∓ half_spread, then round to tick and clamp to [min_spread, max_spread].
  - Parameters to estimate live: σ (e.g., EWMA of 1s–10s mid returns, in price units), A and k (fit ln λ(δ) = ln A − kδ from the empirical fill rate of quotes at distance δ, or from the rate at which trades execute ≥ δ away from the mid — Hummingbot's `trading_intensity` indicator does exactly this, Section 11.6). γ is a policy knob.
  - Caveats: (i) finite horizon T — quotes collapse to the symmetric strategy as t→T; for an always-on bot use the stationary/asymptotic version (GLFT, Section 3) or a rolling T (Hummingbot). (ii) Poisson fills independent of the book state — no queue position, no adverse selection; in crypto the fill rate depends strongly on imbalance/momentum. (iii) Zero drift — a bot that ignores short-term alpha is adversely selected (Cartea–Jaimungal–Ricci, Section 5). (iv) Continuous prices; on a tick grid the formulas become a heuristic. (v) Unit inventory per fill — with variable sizes use the Guéant (2017) Δ-generalisation.
- Relevance: 5

---

## 3. Guéant, Lehalle, Fernandez-Tapia (2012/2013) — "Dealing with the inventory risk: a solution to the market making problem"
- Authors / year: Olivier Guéant, Charles-Albert Lehalle, Joaquin Fernandez-Tapia. arXiv 2011 (v5 2012); Mathematics and Financial Economics 7(4), 477–507 (2013).
- Links: https://arxiv.org/abs/1105.3115 ; DOI https://doi.org/10.1007/s11579-012-0087-0
- Local PDF: `papers/gueant-lehalle-fernandez-tapia-2012-dealing-with-inventory-risk.pdf`
- Key ideas
  - Same model as AS (Brownian mid with volatility σ, intensities A e^{−kδ}, CARA utility, finite horizon) but adds hard inventory limits q ∈ {−Q,…,Q}.
  - Change of variables turns the HJB equations into a linear system of ODEs — no PDE solver needed — plus a verification theorem (the admissibility of the AS quotes was "an open problem").
  - Optimal quotes are almost independent of t far from T; this motivates the asymptotic (T→∞) quotes, characterised via the smallest eigenvalue of a tridiagonal matrix, and a Gaussian closed-form approximation of the eigenvector.
  - Shows the AS q-expansion is inaccurate away from T; the asymptotic formulas should be used instead for an always-on MM.
  - Extensions in the paper: drift in the mid-price (μ), market impact / adverse selection term, comparative statics, backtests ("adaptations of our results are in use at Cheuvreux").
- Formulas / parameters (verified in the PDF text)
  - With α = (k/2)·γσ² and η = A(1+γ/k)^(−(1+k/γ)), the asymptotic optimal quotes are
    - δ^b_∞(q) = (1/γ) ln(1+γ/k) + (1/k) ln( f0_q / f0_{q+1} ),
    - δ^a_∞(q) = (1/γ) ln(1+γ/k) + (1/k) ln( f0_q / f0_{q−1} ),
    - where f0 ∈ R^{2Q+1} is the eigenvector of the smallest eigenvalue of the ODE matrix M.
  - Closed-form (Gaussian) approximation, the "GLFT formulas":
    - δ^b*(q) ≈ (1/γ) ln(1+γ/k) + ((2q+1)/2) · √( σ²γ/(2kA) · (1+γ/k)^(1+k/γ) )
    - δ^a*(q) ≈ (1/γ) ln(1+γ/k) − ((2q−1)/2) · √( σ²γ/(2kA) · (1+γ/k)^(1+k/γ) )
    - total spread ψ*(q) ≈ (2/γ) ln(1+γ/k) + √( σ²γ/(2kA) · (1+γ/k)^(1+k/γ) )  (independent of q)
  - Interpretation: the skew per unit of inventory is c = √(σ²γ/(2kA)·(1+γ/k)^(1+k/γ)); bid distance grows and ask distance shrinks linearly in q.
  - Example calibration in the paper: σ = 0.3 tick·s^(−1/2), A = 0.9 s^(−1), k = 0.3 tick^(−1), γ = 0.01 tick^(−1), T = 600 s, Q = 30.
- How to apply to a crypto MM bot
  - Use the GLFT closed form instead of raw AS for an always-on bot: it has no T, gives a linear inventory skew with a principled slope, and a constant spread. Implementation: `half_spread_base = (1/γ) ln(1+γ/k)`, `skew = c · q` (with the c above), `bid = mid − half_spread_base − c(q + 1/2)`, `ask = mid + half_spread_base − c(q − 1/2)`.
  - Enforce the hard inventory bound Q: stop quoting the side that would breach it (the model's boundary condition). In perps this maps to a max notional / max leverage.
  - Note the parameter sensitivity: c ∝ √(σ²/A) — the skew should scale with volatility and inversely with liquidity (fill rate). Recalibrate A, k, σ continuously.
  - Caveats: same Poisson/no-adverse-selection assumptions as AS; the Gaussian approximation degrades when Q is small or γ/k is large (see their Figure 4); Moret & Lillo (2026, Section 10.10) show GLFT yields negative P&L under persistent one-sided (metaorder) flow.
- Relevance: 5

---

## 4. Guéant (2017) — "Optimal market making" and the Guéant book

### 4.1 Guéant (2017) "Optimal market making"
- Author / year: Olivier Guéant, arXiv 2016 (v5 2017); Applied Mathematical Finance 24(2), 112–154 (2017).
- Links: https://arxiv.org/abs/1605.01862
- Local PDF: `papers/gueant-2017-optimal-market-making.pdf`
- Key ideas
  - A general framework that "generalizes (and reconciles)" the post-AS models: general intensity functions Λ^b(δ), Λ^a(δ) (not just exponential), trade size Δ, two objectives — Model A: CARA utility (ξ = γ); Model B: risk-neutral expected P&L minus a quadratic running inventory penalty (ξ = 0, penalty (γ/2)σ²q² dt) — and a terminal inventory penalty ℓ(|q|).
  - Proves existence/uniqueness of the value function via a system of ODEs (Theorem 3.1) and verification theorems (3.2, 3.3); optimal quotes are given in closed loop.
  - New closed-form approximations (Section 4) that generalise GLFT to any intensity with H''_ξ(0) > 0, and a multi-asset extension (Section 5) with closed-form quotes.
  - Practical application to two credit indices; the asymptotic regime is reached quickly ("after less than 1 hour" in their example).
- Formulas / parameters (verified in the PDF text, eqs. 4.3–4.6)
  - Define the Hamiltonian H_ξ(p) = sup_δ Λ(δ)(1 − e^{−ξΔ(δ−p)})/(ξΔ) (ξ>0) or Λ(δ)(δ−p) (ξ=0), and δ̃*_ξ(p) = Λ^{−1}( ξ H_ξ(p) − H'_ξ(p) ).
  - General approximation: δ^b*(q) ≈ δ̃*_ξ( ((2q+Δ)/2) · √( γσ² / (2 H''_ξ(0)) ) ), δ^a*(q) ≈ δ̃*_ξ( −((2q−Δ)/2) · √( γσ² / (2 H''_ξ(0)) ) ).
  - Exponential intensity Λ(δ) = A e^{−kδ}:
    - ξ > 0: δ^b*(q) ≈ (1/(ξΔ)) ln(1 + ξΔ/k) + ((2q+Δ)/2) · √( γσ²/(2AΔk) · (1+ξΔ/k)^(k/(ξΔ)+1) )
    - ξ = 0: δ^b*(q) ≈ 1/k + ((2q+Δ)/2) · √( γσ² e / (2AΔk) )
    - (ask symmetric with −(2q−Δ)/2). With Δ = 1 and ξ = γ this is exactly GLFT.
  - Model B's "1/k + skew" form is the most-used practitioner formula: base half-spread = 1/k, skew slope = √(γσ²e/(2AΔk)).
- How to apply to a crypto MM bot
  - Use Model B (risk-neutral + running quadratic inventory penalty): it is easier to reason about (γ is a "price of variance", not a utility curvature) and its formula avoids the (1+γ/k) powers. Quote: `bid = mid − 1/k − s·(q + Δ/2)`, `ask = mid + 1/k − s·(q − Δ/2)`, with s = √(γσ²e/(2AΔk)).
  - Δ (typical fill size / order size) enters the skew: larger orders → larger skew per fill. Set Δ = your order size in base units.
  - The general-Λ machinery allows using an empirically fitted (e.g., logistic or power-law) fill curve instead of exponential: compute H''_ξ(0) numerically.
  - Caveats: heuristic approximations validated numerically in the paper; still no adverse selection / signal; assumes fills of fixed size Δ.
- Relevance: 5

### 4.2 Guéant (2016) — "The Financial Mathematics of Market Liquidity: From Optimal Execution to Market Making" (book)
- Chapman & Hall/CRC, 2016. DOI https://doi.org/10.1201/b21350 ; ISBN 9781498725484. Google Books: https://www.google.com/books/edition/The_Financial_Mathematics_of_Market_Liqu/uL_1CwAAQBAJ (paywalled; not downloaded).
- Key ideas: unified Almgren–Chriss-style execution framework, then quote-driven market making (AS/GLFT and generalisations), closed forms and multi-asset extensions; the "skew = slope, width = convexity of the inventory value function" identity (per the summary at https://github.com/microprediction/inventory/blob/main/literature/map_control.md).
- How to apply: reference text for deriving quotes from a value function θ(t,q): bid distance = δ̃*( (θ(q) − θ(q+Δ))/Δ ), ask distance = δ̃*( (θ(q) − θ(q−Δ))/Δ ). Any inventory value table (even RL-learned) can be turned into quotes this way.
- Relevance: 4

---

## 5. Cartea, Jaimungal & Penalva; Cartea–Jaimungal papers on adverse selection, order flow and short-term alpha

### 5.1 Cartea, Jaimungal, Penalva (2015) — "Algorithmic and High-Frequency Trading" (book)
- Cambridge University Press, August 2015, ISBN 9781107091146. Publisher page: https://www.cambridge.org/ae/universitypress/subjects/mathematics/mathematical-finance/algorithmic-and-high-frequency-trading ; front matter / TOC (open): https://assets.cambridge.org/97811070/91146/frontmatter/9781107091146_frontmatter.pdf (book itself paywalled; not downloaded).
- Structure (from the published TOC): Part I microstructure and empirical facts; Part II stochastic-control tools; Part III chapters 6–8 optimal execution (with limit and market orders), 9 targeting volume, 10 Market Making, 11 Pairs Trading, 12 Order Imbalance.
- Key ideas of the MM chapter (from memory of the book; not re-verified against the text): market making as stochastic control with (i) a running inventory penalty φ q² and terminal penalty α q_T², (ii) adverse selection via a mid-price jump correlated with the side of the incoming market order, (iii) short-term alpha α_t (mean-reverting drift), (iv) order-flow imbalance as a Markov-modulated signal, (v) model uncertainty / ambiguity aversion. The risk-neutral-with-running-penalty case gives quotes of the form δ^± ≈ 1/k + (inventory-linear skew ∝ φσ²), the same structure as Guéant's Model B (Section 4.1).
- How to apply: the standard toolbox; especially the "MM with adverse selection" chapter that adds a state-dependent buffer to quotes when a fill is likely to be followed by an adverse mid move.
- Relevance: 4

### 5.2 Cartea & Jaimungal (2013/2015) — "Risk metrics and fine tuning of high-frequency trading strategies"
- Mathematical Finance 25(3), 576–611. DOI https://doi.org/10.1111/mafi.12023 ; SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2010417 (SSRN download requires a session; not downloaded).
- Key ideas (from the abstract)
  - Mid-price driven by information flow plus stochastic jumps caused by market orders that impact prices and create short-term momentum.
  - Risk-neutral HF trader constrained by capital and inventory; the optimal strategy "incorporates a buffer to cover adverse selection costs and manages inventories to maximize the expected gains from market momentum".
  - Proposes risk metrics (inventory-based, proxying capital risk) to fine-tune the trade-off between expected profit and risk.
- How to apply: (a) add an adverse-selection buffer to the half-spread on the side more likely to be hit before an adverse jump; (b) report inventory-based risk metrics (time-weighted |q|, max |q|, inventory variance) alongside P&L in backtests.
- Relevance: 4

### 5.3 Cartea, Jaimungal & Ricci (2014) — "Buy low, sell high: a high frequency trading perspective"
- SIAM Journal on Financial Mathematics 5(1), 415–444. DOI https://doi.org/10.1137/130911196 ; open working-paper PDF (Oxford-Man): https://oxford-man.ox.ac.uk/wp-content/uploads/2020/05/Algorithmic-Trading-Stochastic-Control-and-Mutually-Exciting-Processes.pdf
- Local PDF: `papers/cartea-jaimungal-ricci-2014-buy-low-sell-high-short-term-alpha.pdf`
- Key ideas (verified in the PDF text)
  - Market buy/sell orders arrive as a multi-factor mutually-exciting (Hawkes) process: "influential" orders raise activity, cause one-/two-sided clustering of trades and temporarily change the shape of the LOB.
  - Market orders also move the short-term drift of the mid ("short-term-alpha" α_t, mean-reverting).
  - Central result: "HF traders who do not include predictors of short-term-alpha in their strategies are driven out of the market because they are adversely selected by better informed traders and because they are not able to profit from directional strategies". This holds even when the alpha parameters are mis-specified; MMs omitting alpha "face negative, or at best close to zero, mean PnLs" in their simulations (mean impact ε = 0.04).
  - When one side of the book is more likely to be adversely selected (MOs becoming one-sided), quotes on that side are posted deeper.
- Formulas / parameters: closed-form approximations of the optimal quotes via first-order Taylor expansion (per GLFT's description of the paper); the drift enters the quotes as a shift of both bid and ask in the direction of α_t, and the intensity state (Hawkes activity) modulates spread width.
- How to apply to a crypto MM bot
  - Build an explicit short-term alpha estimator (e.g., EWMA of signed trade flow / OFI / micro-price minus mid) and shift the reservation price by it: r = mid + α̂·h − γσ²q·τ (h = expected holding horizon).
  - Use trade-arrival clustering (Hawkes intensity or simply recent trade rate) as a regime variable: widen when activity spikes one-sidedly.
  - Caveat: parameters of Hawkes models are unstable in crypto; treat as regime detectors, not as precise predictors.
- Relevance: 5

### 5.4 Cartea, Donnelly & Jaimungal (2018) — "Enhancing trading strategies with order book signals"
- Applied Mathematical Finance 25(1), 1–35 (2018). DOI https://doi.org/10.1080/1350486X.2018.1434009 ; SSRN https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2668277 (DOIs confirmed via Crossref; not downloaded). Listed at https://sebastian.statistics.utoronto.ca/research-papers/
- Key ideas (from the abstract/summary on Jaimungal's page): volume imbalance at the top of the Nasdaq book predicts the direction of the next market order and of price changes; embedding a Markov-modulated imbalance state in the MM control problem improves profitability and reduces adverse selection.
- How to apply: the imbalance I = (Q^b − Q^a)/(Q^b + Q^a) as a discrete regime (e.g., 3–5 buckets) that (i) shifts the reservation price and (ii) changes the fill intensities per side. This is the single cheapest signal for a crypto bot (L1/L2 books are free via WebSocket on all three exchanges).
- Relevance: 4

---

## 6. Fodra & Labadie (2012); Fodra & Pham (2013, 2015)

### 6.1 Fodra & Labadie (2012) — "High-frequency market-making with inventory constraints and directional bets"
- Authors / year: Pietro Fodra, Mauricio Labadie, 2012. https://arxiv.org/abs/1206.4810
- Local PDF: `papers/fodra-labadie-2012-hf-market-making-inventory-constraints-directional-bets.pdf`
- Key ideas (from the abstract and text)
  - Extends AS and GLFT to a general class of mid-price processes (non-martingale: drift, mean reversion) under exponential or linear P&L utility.
  - Adds an inventory-risk-aversion parameter that penalises non-zero terminal inventory; it gives direct control on inventory risk and indirect control on the P&L distribution (variance, skewness, kurtosis, VaR).
  - The MM makes directional bets by placing asymmetric quotes: if prices are expected to rise, favour being hit on the bid.
  - Numerical result (mean-reverting mid): the MM can choose to raise average P&L by >15% with much larger inventory/P&L risk, or give up ~5% of benchmark P&L to gain inventory control and more than double the Sharpe ratio.
- Formulas / parameters: reservation ("indifference") price becomes mid + drift term − inventory term; the terminal-inventory penalty appears as an extra skew that grows as t→T (exact expressions depend on the mid model; see paper Sections 3–4).
- How to apply: a principled way to combine a directional forecast (funding-rate skew, momentum, cross-exchange lead) with inventory control; the key design lesson is the explicit separate knob for "how much inventory am I willing to carry to express a view". For a crypto bot, keep this knob small (the paper itself shows the >15% P&L route carries "huge risk").
- Relevance: 3

### 6.2 Fodra & Pham (2013) "Semi Markov model for market microstructure"; (2015) "High frequency trading and asymptotics for small risk aversion in a Markov renewal model"
- Links: https://arxiv.org/abs/1305.0105 ; https://arxiv.org/abs/1310.1756
- Local PDFs: `papers/fodra-pham-2013-semi-markov-model-market-microstructure.pdf`, `papers/fodra-pham-2015-hft-asymptotics-markov-renewal.pdf`
- Key ideas (from the abstracts)
  - Tick-by-tick price as a Markov renewal process: jump times form a point process; marks (±1 tick) follow a Markov chain, reproducing the strong short-term mean reversion of returns (microstructure noise / bid–ask bounce) and volatility clustering; closed-form mean signature plot; diffusive at large scale.
  - MM problem in that model reproduces two forms of adverse selection: "big" market orders that move the price against the MM, and "weak" adverse selection where small orders reduce the probability of a profitable execution.
  - Zero risk aversion: explicit optimal controls and a linear PDE for the value function; small risk aversion: perturbation expansion gives approximate controls from two simple PDEs.
- How to apply: crypto mids on a 1-tick grid (e.g., BTC-USDT perps with 0.1 tick) behave like this: strong negative autocorrelation of tick moves → after an uptick, the next move is more likely down. A bot can exploit that by not chasing the last tick (avoid re-quoting into the bounce) and by conditioning fill/adverse-move probabilities on the last tick direction.
- Relevance: 3

---

## 7. Stoikov (2017/2018) — "The micro-price: a high frequency estimator of future prices"
- Author / year: Sasha Stoikov. SSRN 2017; Quantitative Finance 18(12), 1959–1966 (2018).
- Links: SSRN https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2970694 ; DOI https://doi.org/10.1080/14697688.2018.1489139 ; code https://github.com/sstoikov/microprice ; talk https://www.youtube.com/watch?v=0ZHypIAxYNo (PDF not downloaded — SSRN requires a browser session; the arXiv HTML of a follow-up, https://arxiv.org/html/2411.13594v1, restates the construction).
- Key ideas (from the abstract)
  - The micro-price is defined as the limit of a sequence of expected future mid-prices, conditional on the order-book state (imbalance I and spread S); conditions for the limit to exist are given.
  - It is a martingale by construction and can be regarded as the "fair" price given the book.
  - It is expressed as an adjustment to the mid that depends on spread and imbalance; empirically a better short-term predictor than the mid-price or the volume-weighted mid.
- Formulas / parameters
  - P_micro(t) = lim_{n→∞} E[M_{τ_n} | I_t, S_t] = M_t + Σ_{k≥1} g_k(I_t, S_t), where τ_n is the n-th mid-price change and g_k are computed from an empirical Markov chain on discretised (I, S) states: the one-step adjustment is G¹ = (I − Q)^(−1) R¹ (Q = transition matrix among non-price-changing states, R¹ = expected mid change matrix), and higher-order terms are obtained by iterating the "after a price change" transition matrix (from the paper's construction as restated in the Stanford MS&E 448 report https://web.stanford.edu/class/msande448/2021/Final_reports/gr1.pdf; not re-verified against the SSRN PDF).
  - The naive weighted mid, (P^a Q^b + P^b Q^a)/(Q^a + Q^b), is a special case of "mid + adjustment linear in imbalance" without the martingale guarantee.
- How to apply to a crypto MM bot
  - Replace `mid` by `micro_price` as the reference price in the AS/GLFT formulas. Estimation: bucket imbalance into ~10 bins and spread into 1–3 tick states, estimate transition/mid-change matrices from a rolling window of L1 updates (Binance/OKX/Bybit bookTicker streams give exactly (P^b,Q^b,P^a,Q^a)), compute G¹ and 1–2 further terms.
  - Caveats: L1 sizes on crypto venues are heavily spoofed/flickering; use time-weighted or min-over-window sizes and consider L2 depth (top-3 levels) imbalance. The adjustment is typically a fraction of the spread (Lipton et al. find average next-move ≤ 1/3 spread even for very imbalanced books).
- Relevance: 5

---

## 8. Order flow imbalance and queue-based price prediction

### 8.1 Cont, Kukanov & Stoikov (2014) — "The price impact of order book events"
- Authors / year: Rama Cont, Arseniy Kukanov, Sasha Stoikov. arXiv 2010; Journal of Financial Econometrics 12(1), 47–88 (2014).
- Links: https://arxiv.org/abs/1011.6402 ; DOI https://doi.org/10.1093/jjfinec/nbt003
- Local PDF: `papers/cont-kukanov-stoikov-2014-price-impact-order-book-events.pdf`
- Key ideas (verified in text)
  - Over short intervals, mid-price changes are mainly driven by order flow imbalance (OFI) at the best quotes — the net of limit orders added, cancelled and market orders — not by trade volume alone.
  - Linear relation ΔP = β·OFI with average R² ≈ 65% across 50 NYSE stocks; the slope β (price impact coefficient) is inversely proportional to market depth; results are robust across time scales and stocks.
  - The linear OFI model plus a scaling argument implies the empirical "square-root" relation between price change and volume; trade-volume-based impact is noisier and less robust.
  - Near the open, depth is ~2× lower than average → price impact is higher (intraday seasonality of β).
- Formulas / parameters (verified)
  - Event contribution: e_n = 1{P^b_n ≥ P^b_{n−1}} q^b_n − 1{P^b_n ≤ P^b_{n−1}} q^b_{n−1} − 1{P^a_n ≤ P^a_{n−1}} q^a_n + 1{P^a_n ≥ P^a_{n−1}} q^a_{n−1}.
  - OFI_k = Σ_{n∈(t_{k−1},t_k]} e_n; equivalently OFI = L^b − C^b − M^s − L^s + C^s + M^b (limit buys − cancelled buys − market sells − limit sells + cancelled sells + market buys).
  - ΔP_k = β_k · OFI_k + ε_k ; stylised model ΔP ≈ OFI/(2D) (D = depth per level); empirically β_i ≈ c / AD_i^λ with λ ≈ 1, AD = average top-of-book depth.
- How to apply to a crypto MM bot
  - Compute OFI from the bookTicker/L1 stream (all three exchanges push best bid/ask with sizes at 10–100 ms). Rolling regression of Δmid on OFI gives β (your live "Kyle lambda") and its R².
  - Use β·OFI (recent window) as a short-horizon drift estimate to shift the reservation price; use β itself (∝ 1/depth) as a liquidity gauge: when depth thins, price impact rises → widen.
  - Caveat: crypto L1 depth is frequently dominated by a handful of MM bots' flickering quotes; aggregate OFI over 100–500 ms and over the top few levels to reduce noise.
- Relevance: 5

### 8.2 Cont & de Larrard (2013) — "Price dynamics in a Markovian limit order market"
- Authors / year: Rama Cont, Adrien de Larrard. SIAM J. Financial Mathematics 4(1), 1–25 (2013).
- Links: https://arxiv.org/abs/1104.4596 ; DOI https://doi.org/10.1137/110856605
- Local PDF: `papers/cont-delarrard-2013-price-dynamics-markovian-lob.pdf`
- Key ideas (from the abstract)
  - Reduced-form model of the top of the book as two queues (bid, ask) with Poisson arrivals of limit orders, market orders and cancellations.
  - Analytical expressions for: distribution of durations between price changes, distribution/autocorrelation of price changes, and — most useful — the probability that the next mid move is up, conditional on the current queue sizes (q^b, q^a).
  - Diffusion limit expresses long-run volatility in terms of order arrival/cancellation rates.
- Formulas / parameters: for symmetric Poisson queues, P(next move up | q^b, q^a) is a function of the two queue sizes (it reduces to a race between the two queues depleting; the paper gives it via an explicit formula involving arctan of the ratio for the Brownian approximation — not re-verified here, see paper Section 3).
- How to apply: a model-based alternative to the empirical micro-price: estimate arrival/cancel rates per side and compute P(up) from the queue sizes; also gives a fill-probability model for a quote joining the back of a queue (queue depletion before an adverse move).
- Relevance: 3

### 8.3 Lipton, Pesavento & Sotiropoulos (2013) — "Trade arrival dynamics and quote imbalance in a limit order book"
- Authors / year: Alexander Lipton, Umberto Pesavento, Michael G. Sotiropoulos, 2013. https://arxiv.org/abs/1312.0514
- Local PDF: `papers/lipton-pesavento-sotiropoulos-2013-trade-arrival-quote-imbalance.pdf`
- Key ideas (verified in text)
  - Imbalance I = (q^b − q^a)/(q^b + q^a) at the top of the book strongly predicts (a) the direction of the next mid move and (b) the arrival of the next buy/sell trade.
  - The expected mid move until the next tick is "well approximated by a linear function of the imbalance" and is "typically well below the bid–ask spread" — up to about a third of the spread for highly imbalanced books.
  - Adverse selection is visible in the data: conditional on the same imbalance, the expected mid move measured until the next *sell* trade (which would fill a resting bid) is shifted *upward* relative to the move until the next *buy* trade — i.e., by the time your bid is hit the price has, on average, moved in your favour less than the unconditional forecast suggests; the authors attribute this to the information advantage of aggressive traders.
  - A joint stochastic model of queue sizes and trades is proposed and calibrated; semi-analytic probabilities of market events are given.
- Formulas / parameters: E[Δmid | I] ≈ a·I (linear), with |a| ≤ spread/3 at the extremes; probabilities of "favourable move / unfavourable move / trade" as functions of I are computed from the model and compared to data.
- How to apply: (i) imbalance as a linear reservation-price adjustment (bounded by ~spread/3); (ii) condition fill and adverse-move probabilities on the side of the quote — a resting bid in a bid-heavy book is *less* likely to be filled and, when filled, is more likely to be filled just before a down move.
- Relevance: 4

---

## 9. Multi-asset market making and market making with hedging

### 9.1 Bergault, Evangelista, Guéant & Vieira (2022) — "Closed-form approximations in multi-asset market making"
- Authors / year: Philippe Bergault, David Evangelista, Olivier Guéant, Douglas Vieira. arXiv 2018 (v5 2022); Applied Mathematical Finance.
- Links: https://arxiv.org/abs/1810.04383
- Local PDF: `papers/bergault-evangelista-gueant-vieira-2022-closed-form-multi-asset-mm.pdf`
- Key ideas (from abstract and text)
  - For d correlated assets (covariance Σ), the value function of the multi-asset AS/GLFT problem is approximated by a quadratic form in the inventory vector; the leading asymptotic term is −(1/2)·√γ · qᵀΓq (Γ built from Σ and per-asset liquidity matrices D±).
  - Greedy quotes derived from this proxy are closed-form and interpretable: δ^{i,b} = δ̃*_ξ( 2 qᵀA(t)e_i + z_i e_iᵀA(t)e_i + e_iᵀB(t) ), with A(t), B(t) solving Riccati-type ODEs (asymptotically constant).
  - Uses: heuristic evaluation function, initial value for RL/value iteration, or directly as a quoting rule.
- Formulas / parameters: the skew on asset i depends on the *portfolio* risk (Σq)_i, not on q_i alone: being long BTC-perp makes the bot skew its ETH-perp quotes too (positive correlation).
- How to apply to a crypto MM bot
  - If quoting several perps (BTC, ETH, SOL…) or the same asset on several venues, compute a portfolio inventory vector and skew every instrument by γ·(Σ q)_i·(time/liquidity scaling) instead of per-instrument q_i. Crypto majors are 0.6–0.9 correlated intraday, so per-instrument risk control badly understates aggregate risk.
  - Caveat: Σ must be estimated at the quoting horizon (seconds–minutes) and re-estimated often.
- Relevance: 4

### 9.2 Bergault & Guéant (2022) — "Size matters for OTC market makers: general results and dimensionality reduction techniques"
- Links: https://arxiv.org/abs/1907.01225 (Mathematical Finance 2021).
- Local PDF: `papers/bergault-gueant-2022-size-matters-otc-market-makers.pdf`
- Key ideas (from abstract): multi-asset MM with (i) a factor model to beat the curse of dimensionality and (ii) size-dependent quotes — the MM answers different prices for different request sizes.
- How to apply: rationale for size-dependent pricing / layered quotes (tighter for small clips, wider for size) — i.e., quote ladders on the book rather than a single level.
- Relevance: 3

### 9.3 Barzykin, Bergault & Guéant (2022) — "Algorithmic market making in dealer markets with hedging and market impact"
- Links: https://arxiv.org/abs/2106.06974 (Mathematical Finance 2023). Companion: "Market making by an FX dealer: tiers, pricing ladders and hedging rates for optimal risk control", https://arxiv.org/abs/2112.02269 (not downloaded).
- Local PDF: `papers/barzykin-bergault-gueant-2022-algorithmic-mm-dealer-markets-hedging-market-impact.pdf`
- Key ideas (from abstracts)
  - The MM can both skew quotes (internalise) and trade in an external market to hedge (externalise) at a cost with market impact; the model yields an inventory band: inside it, pure internalisation (skew quotes and wait); outside it, hedge actively. "The larger the franchise, the wider is the inventory range suitable for pure internalization."
  - Answers "to hedge, or not to hedge?" as an optimal-control problem.
- How to apply to a crypto MM bot
  - Directly maps to perps: skew quotes within |q| ≤ q_int; beyond it, hedge with a taker order on the same venue or on another venue (e.g., long on Bybit perp → sell on Binance perp/spot) paying taker fee + impact. Set the band from (taker cost) vs (expected loss from carrying inventory: γσ²q²·τ).
  - Caveat: hedging across venues creates basis/funding risk and margin fragmentation; see Zeng & Liu (Section 11.2) for a perp-specific treatment.
- Relevance: 4

---

## 10. Reinforcement learning for market making

### 10.1 Spooner, Fearnley, Savani & Koukorinis (2018) — "Market making via reinforcement learning"
- AAMAS 2018. https://arxiv.org/abs/1804.04216
- Local PDF: `papers/spooner-2018-market-making-via-rl.pdf`
- Key ideas (verified in text)
  - High-fidelity LOB simulator replaying historical data; TD learning (Q-learning, SARSA, R-learning and variants) with a linear combination of tile codings (LCTC) as the value approximator.
  - The natural reward (mark-to-market P&L) leads to unstable learning and speculative behaviour; they introduce *dampened* rewards that penalise the inventory (speculation) component of P&L.
  - State = agent-state (inventory, active quoting distances normalised by spread) + market-state features (spread, mid-move, volatility, imbalance, etc.); actions = discrete pairs of quoting distances plus a "clear inventory" market order.
  - Outperforms simple fixed-spread benchmarks and an online-learning approach.
- Formulas / parameters (verified)
  - Incremental P&L: Ψ(t_i) = ψ^a(t_i) + ψ^b(t_i) + Inv(t_i)·Δm(t_i)  (spread captured + inventory mark-to-market).
  - Rewards: PnL r = Ψ ; symmetrically dampened r = Ψ − η·Inv·Δm ; asymmetrically dampened r = Ψ − max[0, η·Inv·Δm] (removes speculative *gains* but keeps losses → strongly encourages spread capture over trend-following).
- How to apply: even if you do not use RL, the asymmetrically dampened P&L is an excellent *objective for tuning* any MM (grid-search γ, k multipliers, etc.); and the state features list is a good checklist for what your quoting engine should observe.
- Relevance: 4

### 10.2 Ganesh, Vadori, Xu, Zheng, Reddy & Veloso (JP Morgan AI Research, 2019) — "Reinforcement learning for market making in a multi-agent dealer market"
- NeurIPS 2019 workshop. https://arxiv.org/abs/1911.05892
- Local PDF: `papers/ganesh-2019-rl-market-making-multiagent-dealer.pdf`
- Key ideas (verified in abstract/text)
  - Multi-agent dealer-market simulator (OTC-style: investors send RFQs, dealers price them); RL market maker trained against competitors with random/adaptive/persistent pricing policies, several reward formulations and market drifts.
  - The RL agent learns its competitors' pricing, learns to *skew* (asymmetric buy/sell prices) to manage inventory, and holds positive (negative) inventory when drift is positive (negative).
  - Hedging is modelled as price-taking at a cost; risk-averse reward variants (P&L minus inventory-PnL variance style terms) are proposed.
- How to apply: reinforcing that skewing is the primary inventory tool and hedging the secondary one; the reward-shaping menu (inventory P&L penalty, hedge cost) is reusable.
- Relevance: 3

### 10.3 Gašperov & Kostanjčar (2021) — "Market making with signals through deep reinforcement learning"; (2022) — "Deep RL for market making under a Hawkes-process-based LOB model"
- Links: IEEE Access 9, 61611–61622 (2021), DOI https://doi.org/10.1109/ACCESS.2021.3074782 (open access on IEEE Xplore; the direct PDF download was blocked from the shell, not saved). IEEE Control Systems Letters 6, 2485–2490 (2022), https://arxiv.org/abs/2207.09951
- Local PDF: `papers/gasperov-kostanjcar-2022-deep-rl-mm-hawkes-lob.pdf` (2022 paper only).
- Key ideas (from abstracts)
  - 2021: model-free deep RL MM whose state includes outputs of standalone *signal-generating units* (supervised predictors); continuous tick-based quoting actions; adversarial RL + neuroevolution for robustness. Historical-data results: 20–30% higher terminal wealth than benchmarks at ~60% of their inventory risk.
  - 2022: DRL controller trained on a weakly consistent multivariate Hawkes LOB simulator (Monte-Carlo backtesting); beats several MM benchmarks on risk-reward metrics even with significant transaction costs.
- How to apply: architecture pattern — separate signal models (micro-price/OFI/alpha) feeding a controller (analytic or learned); train/validate on a simulator whose order flow is *clustered* (Hawkes), since Poisson simulators under-estimate adverse selection.
- Relevance: 3

### 10.4 Sadighian (2019) — "Deep reinforcement learning in cryptocurrency market making"; (2020) — "Extending deep RL frameworks in cryptocurrency market making"
- Links: https://arxiv.org/abs/1911.08647 ; https://arxiv.org/abs/2004.06985
- Local PDFs: `papers/sadighian-2019-deep-rl-crypto-market-making.pdf`, `papers/sadighian-2020-extending-deep-rl-crypto-market-making.pdf`
- Key ideas (verified in abstracts/text)
  - 2019: DRLMM framework; observation space built from LOB snapshots and order-flow arrival statistics (OFI, trade-flow imbalance TFI); A2C and PPO agents with an MLP; two rewards compared: *positional P&L* (change in unrealised value + realised) and *trade completion* (a clipped goal-based reward in [−1,1] paid only when a round-trip completes). Notes that crypto venues have no designated MMs and rely on maker-taker fee schedules (rebates).
  - 2020: *event-based* environment — a step is triggered when price moves by more than a threshold rather than on a clock; trained on 8 days and tested on 30 days of BitMEX LOB data; event-based framing improved profit and stability vs time-based for both agents across seven reward functions.
- How to apply: (i) event-driven decision loop (re-quote on price/imbalance change thresholds, not on a timer) — this also reduces API rate-limit usage; (ii) include OFI/TFI in the state; (iii) if training RL, prefer rewards that pay for completed round-trips.
- Relevance: 4

### 10.5 Selser, Kreiner & Maurette (2021) — "Optimal market making by reinforcement learning"
- https://arxiv.org/abs/2104.04036 — Local PDF: `papers/selser-kreiner-maurette-2021-optimal-mm-by-rl.pdf`
- Key ideas: in the AS environment, a DQN agent with a reward equivalent (as an order relation over policies) to the CARA utility *recovers the AS optimal agent*. Useful as a sanity test for any RL MM pipeline.
- Relevance: 2

### 10.6 2023–2026 RL / deep-learning MM papers (abstract-level review)
- He, Zheng & Yang (2023) — "Integrating tick-level data and periodical signal for high-frequency market making", https://arxiv.org/abs/2306.17179 — Local PDF: `papers/he-zheng-yang-2023-tick-data-periodical-signal-hf-mm-crypto.pdf`. DRL that fuses tick-level LOB data with periodic (bar-level) prediction signals; simulation and real crypto-market experiments show better profit and risk than baselines. Design lesson: keep a slow "alpha" signal and a fast microstructure state as separate inputs. Relevance 3.
- Guo, Lin & Huang (2023) — "Market making with deep RL from limit order books", https://arxiv.org/abs/2305.15821 — CNN + attention LOB encoder, continuous action space, hybrid reward; latency and interpretability experiments (not downloaded). Relevance 2.
- Zheng & Ding (2024) — "Reinforcement learning in high-frequency market making", https://arxiv.org/abs/2407.21025 — theory: error vs complexity trade-off in the sampling interval Δ; two-player Nash Q-learning converges to the continuous-time game equilibrium as Δ→0 (not downloaded). Lesson: decision frequency is a tunable with a real trade-off, not "as fast as possible". Relevance 2.
- Jiang et al. (2025) — "Resolving latency and inventory risk in market making with RL" (RELAVER), https://arxiv.org/abs/2505.12465 — Local PDF: `papers/jiang-2025-resolving-latency-inventory-risk-mm-rl.pdf`. Simulator with random order latency (30–80/100 ms) and *scheduled* (non-instant) cancellations with price-time priority; shows that ignoring latency causes unintended cancels/fills and inventory drift; proposes an RL method robust to it. Highly relevant to REST/WS API bots where cancel/replace round-trips are 20–200 ms. Relevance 4.
- Zimmer & do Valle Costa (2025/26) — "RL-based market making as a stochastic control on non-stationary LOB dynamics", https://arxiv.org/abs/2509.12456 — PPO agent on a simulator with clustered arrivals, non-stationary spreads/drifts; compared against the closed-form optimum (not downloaded). Relevance 2.
- Jafree, Jain & Firoozye (2025) — "When AI trading agents compete: adverse selection of meta-orders by RL-based market making", https://arxiv.org/abs/2510.27334 — RL MM in a Hawkes LOB learns to exploit the drift induced by a medium-frequency trader's meta-order (not downloaded). Lesson: detecting metaorder flow is a profit source for the MM, and *being* the slow party is the loss source. Relevance 3.
- Cheridito & Weiss (2026) — "Multi-level market making with RL", https://arxiv.org/abs/2608.18195 — multi-level order allocation via logistic-normal distributions and deep-set encoder; tested against noise, tactical (imbalance-following) and strategic (EWMA imbalance) traders (not downloaded). Relevance 2.
- Moret & Lillo (2026) — "Deep learning of robust market making under regime-switching order flow", https://arxiv.org/abs/2609.11614 — Local PDF: `papers/moret-lillo-2026-deep-learning-robust-mm-regime-switching-flow.pdf`. See Section 11.5 for details (GLFT gives negative P&L under persistent directional flow; a change-point filter on flow bias restores profitability). Relevance 4.
- Fernández Vicente (2025) — PhD thesis "Market making strategies with RL", https://arxiv.org/abs/2507.18680 — multi-objective RL for inventory, and POW-dTS (discounted Thompson sampling over pretrained policies) for non-stationarity (not downloaded). Relevance 2.

---

## 11. Crypto-specific market making / microstructure papers (2020–2026)

### 11.1 Le (2026) — "Funding-aware optimal market making for perpetual DEXs"
- Author / year: Nam Anh Le, 2026. https://arxiv.org/abs/2605.06405
- Local PDF: `papers/le-2026-funding-aware-optimal-mm-perpetual-dexs.pdf`
- Key ideas (verified in text)
  - Extends AS to perpetuals where the funding rate f_t is a stochastic state variable: inventory creates both mark-to-market exposure *and* a state-dependent funding cash flow −q·f per period.
  - Reduced inventory–funding HJB solved with a monotone finite-difference scheme; bid/ask offsets recovered from discrete inventory value differences (θ(q) − θ(q±1)).
  - Funding calibrated on Hyperliquid ETH/BTC/SOL: Gaussian OU is the tractable baseline; OU-plus-jump fits every asset better (heavy-tailed funding innovations).
  - 100-seed hold-out simulations: the funding-aware HJB improves mean ETH/BTC performance and lowers inventory RMS vs classical AS; SOL gains are not a Pareto improvement once a risk-scaled AS baseline is included. The author is explicit that the backtest is not a queue-position simulator.
- Formulas / parameters: funding enters the cash account as a source term −q·f, where f is the cash funding amount per unit inventory per hour (= fractional funding rate per hour × price, so that it is in the same units as spread revenue); in the historical simulator it is applied at the observed hourly timestamps with Δτ = 1 h. Funding follows an OU process with mean-reversion speed κ > 0 (plus jumps in the diagnostic model). Quote offsets are recovered from neighbouring inventory values in the HJB table: δ^b ↔ θ(q) − θ(q+1), δ^a ↔ θ(q) − θ(q−1).
- How to apply to a crypto MM bot (OKX/Binance/Bybit perps)
  - Treat expected funding as a *carry* term on inventory: when predicted funding is positive (longs pay), skew quotes to prefer being short into the funding timestamp, and vice versa; the magnitude is E[f]·S·(time to funding) per unit inventory, comparable to a few ticks for BTC at typical 0.01%/8h rates, but large at 0.1–0.3%/8h extremes.
  - Use premium index / predicted funding fields from the exchange APIs (Binance `premiumIndex`, OKX `funding-rate`, Bybit `tickers`) as the state variable; model it as mean-reverting with jumps.
  - Caveat: results are DEX-calibrated (Hyperliquid, hourly funding); CEX funding is 8-hourly (Binance/Bybit) with some 4-hourly/1-hourly contracts, and CEX fill dynamics differ.
- Relevance: 4

### 11.2 Zeng & Liu (2026) — "Optimal adaptive market making: a theoretical framework for high-yield liquidity provision in perpetual futures markets"
- https://arxiv.org/abs/2607.11888 — Local PDF: `papers/zeng-liu-2026-optimal-adaptive-mm-perpetual-futures.pdf`
- Key ideas (verified in abstract/text)
  - Perp MM as stochastic control with adaptive spreads, inventory gating and *cross-exchange hedging* under CARA utility, on zero-maker-fee venues.
  - PnL decomposition theorem: spread income − latency adverse selection − informed adverse selection − inventory cost (− hedging friction − funding exposure).
  - "High-APY regime" theorems in five dimensionless parameters; a "Master APY formula"; optimal hedge threshold/ratio/timing with a hedge-regime trichotomy; drawdown bounds; Kelly-optimal leverage with ruin boundaries; multi-pair allocation.
  - Positions itself as unifying AS, GLFT and Glosten–Milgrom for DEX perps; 23 numerical figures show phase transitions between profitable and unprofitable regimes.
- Formulas / parameters: too many to restate; the useful skeleton is E[PnL] = Σ fills × half-spread − Σ fills × E[adverse move | fill] − γσ²∫q²dt − hedge cost − q·funding. Treat the APY theorems as heuristics — this is a long theoretical preprint without an empirical backtest.
- How to apply: adopt the *P&L attribution* as a monitoring standard: log per-fill realised spread, post-fill markout at 1s/10s/60s (adverse selection), inventory cost, hedge cost and funding separately. The hedge trichotomy (never hedge / hedge beyond a threshold / always hedge) maps to a configurable policy.
- Relevance: 3

### 11.3 He, Manela, Ross & von Wachter (2022–2026) — "Fundamentals of perpetual futures"; Ackerer, Hugonnier & Jermann (2023/24) — "Perpetual futures pricing"
- Links: https://arxiv.org/abs/2212.06888 (v7, Sept 2026) ; https://arxiv.org/abs/2310.11771
- Local PDFs: `papers/he-manela-ross-vonwachter-2022-fundamentals-of-perpetual-futures.pdf`, `papers/ackerer-hugonnier-jermann-2024-perpetual-futures-pricing.pdf`
- Key ideas (from abstracts)
  - He et al.: no-arbitrage perpetual prices in frictionless markets and bounds with trading costs; empirically, crypto perp–spot deviations are larger than in FX, co-move across coins and shrink over time; an implied arbitrage strategy earns high Sharpe ratios.
  - Ackerer et al.: explicit no-arbitrage prices for linear, inverse and quanto perps; the perp price equals the risk-neutral expectation of spot sampled at a random time whose intensity reflects the strength of funding anchoring; funding specifications that make perp = spot allow replication by dynamic trading.
- How to apply: the perp "fair value" for an MM is spot (index) + a basis determined by expected funding; deviations are mean-reverting → quote around index + expected basis rather than around the perp's own mid when the two diverge sharply (e.g., liquidation cascades). Cross-venue basis dispersion is itself a signal of stress.
- Relevance: 3

### 11.4 Bieganowski & Ślepaczuk (2026) — "Explainable patterns in cryptocurrency microstructure"
- https://arxiv.org/abs/2602.00776 — Local PDF: `papers/bieganowski-slepaczuk-2026-explainable-patterns-crypto-microstructure-binance-perps.pdf`
- Key ideas (verified in text)
  - Binance Futures perpetual order books + trades at 1-second frequency, Jan 2022 – Oct 2025, five assets spanning an order of magnitude in market cap (BTC, LTC, ETC, ENJ, ROSE).
  - CatBoost with a direction-aware objective; SHAP shows that the *same* engineered features have remarkably similar importance and dependence shapes across assets; the top feature is order-book imbalance, with spread and adverse-selection-related features following.
  - Tradability validated with a conservative top-of-book taker backtest and a fixed-depth maker backtest; both profitable on most assets, the maker strategy weaker on less liquid names (slight losses on LTC).
  - Natural experiment: the 10 October 2025 flash crash ("over $19 billion in leveraged positions liquidated within 24 hours", BTC −18%). The taker strategy profited by reading extreme imbalance; the divergent taker/maker performance "empirically validates classic microstructure theories of adverse selection" — makers are the losers during cascades. They also note a single large shallow bid at ~23:27 caused a sharp model prediction, highlighting spoofing risk.
- How to apply: (i) a portable feature library (imbalance across levels, spread, trade-flow features) works across Binance perps — build once, apply to many pairs; (ii) implement a *crash mode*: when imbalance/trade-flow features hit extreme quantiles, pull quotes or quote only on the safe side; (iii) do not trust single large L1 orders (spoofing) — use time-weighted depth.
- Relevance: 4

### 11.5 Moret & Lillo (2026) — "Deep learning of robust market making under regime-switching order flow"
- https://arxiv.org/abs/2609.11614 — Local PDF: `papers/moret-lillo-2026-deep-learning-robust-mm-regime-switching-flow.pdf`
- Key ideas (verified in abstract/text)
  - AS/GLFT closed forms assume stationary order flow; real flow has regimes (e.g., algorithmic execution of metaorders). "In this case, existing methods provide negative PnL."
  - GLFT is calibrated to a queue-faithful event-driven (Santa Fe zero-intelligence) LOB simulator via censored waiting-time estimation of A, k; a Rainbow-style distributional DQN (C51) beats GLFT across the whole observed risk–return frontier under paired seeds in the stationary setting.
  - Both GLFT and the RL agent suffer large drawdowns from inventory saturation under persistent directional imbalance; adding two state signals — a Bayesian online change-point filter on directional flow bias and a queue-adjusted quote-exposure imbalance — restores profitability; a scenario-bandit reweighting further improves stress performance.
- How to apply: this is the clearest academic evidence for (a) a *flow-regime detector* (Bayesian change-point on signed trade flow) feeding the quoting engine, (b) treating persistent one-sided flow as a distinct state that overrides the stationary skew (widen/pull the side being run over), and (c) calibrating A, k with censoring (quotes that were cancelled before filling are censored observations, not zeros).
- Relevance: 4

### 11.6 Hummingbot's Avellaneda–Stoikov adaptation (2021–2026, open-source practitioner reference)
- Links: docs https://hummingbot.org/strategies/v1-strategies/avellaneda-market-making/ ; math deep-dive https://hummingbot.org/blog/technical-deep-dive-into-the-avellaneda--stoikov-strategy/ ; code https://github.com/hummingbot/hummingbot/blob/master/hummingbot/strategy/avellaneda_market_making/avellaneda_market_making.pyx
- Key ideas (verified on the pages)
  - Implements r = s − qγσ²(T−t) and δ^a + δ^b = γσ²(T−t) + (2/γ) ln(1+γ/κ) with live estimators: `instant_volatility` for σ and a `trading_intensity` indicator that fits α (=A) and κ (=k) from observed trades vs distance to mid.
  - Crypto adaptations: (1) `order_amount_shape_factor` η — order size multiplied by exp(−ηq) on the side that would increase the deviation from target inventory (from Fushimi, González Rojas & Herman 2018, "Optimal High-Frequency Market Making", Stanford report); (2) `vol_to_spread_multiplier` — a volatility threshold that triggers parameter recalculation; (3) a finite `closing_time` T with a recurring time fraction and recalibration each cycle so the bot can run indefinitely; (4) user-specified `min_spread`/`max_spread` from which γ_max = (MaxSpread − MinSpread)/(2|q|σ²) and γ = γ_max·IRA with `inventory_risk_aversion` IRA ∈ (0,1]; κ chosen so the t=0 spread equals a target derived from the spread bounds.
  - q is defined as the *normalised deviation from target inventory* (fraction of total inventory), not raw units — which makes γ roughly comparable across assets (docs still warn γ can need ~10× different values across assets).
  - Limits: γ → 0 recovers pure symmetric market making; the docs note the model was "predicated on assumptions that may not align well with the needs of a crypto trader".
- How to apply: a proven parameterisation for operators: expose (min_spread, max_spread, IRA, target inventory %, T cycle) instead of raw (γ, k); use η-style size shaping to reduce inventory build-up instead of only price skew; recalibrate σ/A/k every cycle.
- Relevance: 4

### 11.7 Barone & Lillo (2026) — "Trading in the sunshine or in the shade: market impact and adverse selection on Hyperliquid"
- https://arxiv.org/abs/2606.15715 — Local PDF: `papers/barone-lillo-2026-market-impact-adverse-selection-hyperliquid.pdf`
- Key ideas (from abstract): on-chain perp LOB with address-level data; 4.3 M hidden metaorders reconstructed and compared with 465 k visible TWAPs. Hidden metaorders follow front-loaded U-shaped schedules; visible TWAPs get lower costs and smaller permanent impact; when visible TWAP flow is active, displayed depth rises and the book tilts toward the absorbing side.
- How to apply: metaorder flow is detectable (persistent same-direction child orders at regular intervals); when detected, liquidity providers *lean* into it (quote more on the absorbing side, wider on the other) — consistent with Moret & Lillo's regime signal. Also shows that metaorder detection matters for MM P&L on crypto perps.
- Relevance: 3

### 11.8 Raheman, Kolonin, Glushchenko, Fokin & Ansari (2022) — "Adaptive multi-strategy market-making agent for volatile markets"
- https://arxiv.org/abs/2204.13265 — Local PDF: `papers/raheman-2022-adaptive-multi-strategy-mm-agent-volatile-crypto.pdf`
- Key ideas (from abstract): a meta-agent that runs several MM sub-strategies, back-tests them on the most recent sub-period, and re-selects the active sub-agents each period; performance depends on refresh rate, sub-period length and number of active agents; claims a high probability of positive alpha with well-chosen hyper-parameters on historical crypto data.
- How to apply: a light-weight ensemble/bandit over quoting parameter sets (e.g., several γ, spread multipliers) re-selected on recent realised performance — cheap robustness to regime change. Treat the specific claims with caution (small study, no peer review).
- Relevance: 2

### 11.9 Other crypto-microstructure references found (not downloaded)
- Plazuelo Pascual et al. (2025) — "Price discovery in cryptocurrency markets", https://arxiv.org/abs/2506.08718 : Binance leads Uniswap v2 in ETH price discovery; futures generally lead spot except in high-volatility periods (Hasbrouck information share, Gonzalo–Granger). Implication: for a perp MM the *futures* mid on the largest venue is usually the leading price, and the leader can flip in stress.
- Kim & Park (2025) — "Designing funding rates for perpetual futures in cryptocurrency markets", https://arxiv.org/abs/2506.08573 : funding-rate designs that keep perp price aligned with target; replicating portfolios via path-dependent BSDEs (theory).
- Zheng & Ding (2024) and others listed in Section 10.6.

---

## 12. Latency, stale quotes and sniping

### 12.1 Budish, Cramton & Shim (2015) — "The high-frequency trading arms race: frequent batch auctions as a market design response"
- Quarterly Journal of Economics 130(4), 1547–1621. DOI https://doi.org/10.1093/qje/qjv027 ; open PDF https://ericbudish.org/files/high_frequency_trading_arms_race.pdf ; SSRN https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2388265
- Local PDF: `papers/budish-cramton-shim-2015-hft-arms-race-frequent-batch-auctions.pdf`
- Key ideas (verified in text)
  - Empirics (ES vs SPY, 2005–2011): correlations that are ~1 at human time scales "completely break down" at millisecond horizons (e.g., in 2011 the ES–SPY correlation reaches only 0.50 at a 142 ms interval); this creates mechanical arbitrage opportunities worth ≈ $306,000/day ≈ $75 million/year in ES–SPY alone; the median duration of these opportunities fell from 97 ms (2005) to 7 ms (2011) while their size and frequency did not shrink — competition only raised the speed bar.
  - Theory: in a continuous limit order book, *symmetrically observed public information* creates arbitrage rents because orders are processed serially: when a public signal moves, stale quotes are "sniped" by the fastest taker before the MM can cancel. Liquidity providers price this into wider spreads; the result is a socially wasteful arms race.
  - Remedy proposed: frequent batch auctions (e.g., every 100 ms) — discrete time + uniform-price auction turns competition on speed into competition on price.
- Formulas / parameters: in the model, the equilibrium spread satisfies (spread/2)·λ_invest = (probability of a jump larger than the half-spread) × (expected loss to snipers) — the MM's spread is set so that revenue from investors covers the losses from being sniped; with N fast traders, the MM wins the race to cancel with probability 1/N (from memory of the model; not re-verified in detail).
- How to apply to a crypto MM bot
  - Crypto venues are continuous LOBs with 5–50 ms matching-engine latency and no speed bumps; the same "sniping" occurs: after a BTC move on the leading venue (often Binance perp), stale quotes on OKX/Bybit are picked off. A bot whose quote refresh is slower than the cross-venue propagation (tens of ms) *will* be adversely selected on every jump.
  - Mitigations: (i) subscribe to the leading venue's trade/book stream and cancel/re-price immediately on jumps; (ii) widen quotes by the expected sniping cost = P(|jump| > half-spread within your reaction time) × E[loss]; (iii) prefer post-only orders and use the exchanges' cancel-on-disconnect / batch cancel endpoints; (iv) size down when your measured reaction latency deteriorates.
- Relevance: 4

### 12.2 Aquilina, Budish & O'Neill (2020 FCA OP50 / 2022 QJE) — "Quantifying the high-frequency trading 'arms race'"
- QJE 137(1), 493–564. DOI https://doi.org/10.1093/qje/qjab032 ; open PDFs: FCA OP50 http://www.fca.org.uk/publication/occasional-papers/occasional-paper-50.pdf and addendum https://www.fca.org.uk/publication/occasional-papers/occasional-paper-50-addendum.pdf
- Local PDF: `papers/aquilina-budish-oneill-2020-hft-arms-race-fca-op50.pdf`
- Key ideas (verified from the abstracts / FCA page)
  - Uses LSE *message* data (including failed attempts to trade/cancel) so both winners and losers of latency races are observed.
  - Races are very frequent (~1 per minute per FTSE 100 symbol), extremely fast (modal race 5–10 µs), and account for ~20% of volume; participation is concentrated (top 6 firms > 80% of wins/losses).
  - Each race is worth about half a tick, but in aggregate races make up roughly one-third of price impact and of the effective spread; latency arbitrage is a ~0.5 bp tax on trading; eliminating it would cut the cost of liquidity by ~17%; ~$5 bn/year at stake in global equities.
- How to apply: expect that a meaningful share of your fills as a passive MM are "race losses" (you were the stale quote). Measure it: markout of each fill at 100 ms–1 s; fills with sharply negative markouts clustered right after a mid jump are sniping. That statistic decides whether to invest in lower latency (co-location zones: AWS Tokyo for Binance/Bybit-adjacent, Hong Kong/Singapore for OKX) or in wider spreads.
- Relevance: 4

### 12.3 Gao & Wang (2018/2020) — "Optimal market making in the presence of latency"
- https://arxiv.org/abs/1806.05849 (Quantitative Finance 2020) — Local PDF: `papers/gao-wang-2020-optimal-mm-presence-of-latency.pdf`
- Key ideas (verified in text)
  - Large-tick asset, random-walk price, MM's problem as an MDP with latency Δτ between decision and order arrival; the *value of an order* plays the role of the one-period reward.
  - Explicit profitability criterion: compare (1) the rate at which the MM's limit orders are *adversely* filled because the price trades through them (jumps) with (2) the rate of small/"uninformed" market orders that hit the quotes without moving the price. If (2) ≤ (1), order values are non-positive and *no* quoting policy is profitable regardless of horizon; if (2) > (1), there is a quote pair with positive value and a long enough horizon yields positive expected profit.
  - Latency is an additional source of risk and reduces MM performance: the MM cannot update orders in time when the price moves.
- How to apply: a go/no-go test per market: estimate λ_uninformed (fills at best that are followed by no mid move) vs λ_adverse (fills occurring as the mid trades through) from your own fill/markout data; if the ratio is ≤ 1, the pair/venue is not quotable at your latency — widen, quote deeper, or leave.
- Relevance: 4

### 12.4 Cartea, Jaimungal & Sánchez-Betancourt (2019) — "Latency and liquidity risk"
- https://arxiv.org/abs/1908.03281 (IJTAF 2021) — Local PDF: `papers/cartea-jaimungal-sanchez-betancourt-2019-latency-and-liquidity-risk.pdf`
- Key ideas (from abstract): for liquidity *takers*, latency means the LOB may change between decision and arrival; a latency-optimal marketable limit order carries a price limit that trades off missing the fill vs walking the book; characterised via FBSDEs driven by random measures.
- How to apply: relevant for the *hedging leg* of the MM: when hedging inventory with an aggressive order across venues, use a marketable limit with a computed price limit rather than a pure market order.
- Relevance: 2

---

## 13. Synthesis: what the literature says a good MM strategy must do

1. Quote around a *fair value*, not the mid. Use the micro-price / imbalance-adjusted price (Stoikov; Lipton et al.; Cartea–Donnelly–Jaimungal) plus a short-term alpha from OFI/trade flow (Cont–Kukanov–Stoikov; Cartea–Jaimungal–Ricci). Ignoring short-term alpha makes an MM systematically adversely selected — "driven out of the market" in Cartea–Jaimungal–Ricci's simulations.
2. Skew quotes linearly in inventory with a principled slope. GLFT / Guéant (2017): bid distance = base + c·(q + Δ/2), ask distance = base − c·(q − Δ/2), c = √(γσ²(e or (1+γ/k)^(1+k/γ))/(2AΔk)). Skew scales with σ and inversely with √(fill rate).
3. Keep the spread ≥ inventory term + liquidity term + adverse-selection buffer. Base half-spread (1/γ)ln(1+γ/k) or 1/k covers the fill/spread trade-off; add an explicit buffer for expected post-fill markout (Glosten–Milgrom; Cartea–Jaimungal 2015; Zeng–Liu decomposition).
4. Use the asymptotic (time-independent) quotes for an always-on bot; the AS finite-horizon term γσ²(T−t) is an artefact of the terminal date (GLFT, Guéant 2017). If you keep a T (Hummingbot), recalibrate each cycle.
5. Enforce hard inventory limits ±Q and stop quoting the breaching side (GLFT boundary condition). In perps map Q to max notional/leverage and margin usage.
6. Separate internalisation from hedging: skew inside an inventory band; hedge with taker orders (same or other venue) outside it; the band width comes from taker cost vs γσ²q²τ (Barzykin–Bergault–Guéant; Ganesh et al.).
7. Manage inventory at the *portfolio* level across correlated instruments/venues: skew each instrument by (Σq)_i (Bergault–Evangelista–Guéant–Vieira).
8. Estimate A, k, σ continuously and with censoring: fit ln λ(δ) = ln A − kδ from your own quotes' fill outcomes, treating cancelled-before-fill as censored (Moret & Lillo); σ at the quoting horizon (seconds), not daily.
9. Detect flow regimes and override the stationary rule: persistent one-sided flow / metaorders produce negative P&L for AS/GLFT (Moret & Lillo; Barone & Lillo; Jafree et al.). Run a Bayesian change-point or simple z-score on signed trade flow; when triggered, widen or pull the side being run over.
10. Treat every fill as information: post-fill markouts at 100 ms / 1 s / 10 s / 60 s are the primary diagnostic (Aquilina–Budish–O'Neill; Zeng–Liu attribution). Fills followed immediately by an adverse mid jump are sniping — count them and price them into the spread or fix latency.
11. Respect latency as a first-class risk: the profitability condition is (rate of uninformed fills) > (rate of adverse fills) at *your* reaction time (Gao & Wang; Budish et al.). Subscribe to the leading venue's stream, cancel-on-jump, use post-only and cancel-on-disconnect, and measure your decision-to-ack latency (Jiang et al. simulate 30–100 ms).
12. Quote event-driven, not clock-driven: re-quote on mid/imbalance/flow thresholds (Sadighian 2020 found event-based framing improved profit and stability) — this also economises API rate limits.
13. Use size shaping as well as price skew: multiply order size by exp(−η·q_dev) on the side that would grow the deviation from target (Hummingbot / Fushimi et al.); quote ladders with size-dependent widths (Bergault–Guéant).
14. Include perp-specific carry: expected funding × time-to-funding is a per-unit inventory cost/benefit that should enter the skew (Le 2026); quote around index + expected basis when perp–spot diverge (He et al.; Ackerer et al.).
15. Have a crash mode. In liquidation cascades makers lose and takers win (Bieganowski & Ślepaczuk on 10 Oct 2025); extreme imbalance/flow quantiles → pull quotes or quote only the safe side; ignore single large flickering L1 orders (spoofing).
16. If using RL, shape rewards toward spread capture (asymmetrically dampened P&L, Spooner et al.; trade-completion reward, Sadighian), train on clustered-flow (Hawkes) simulators with latency and scheduled cancels (Gašperov–Kostanjčar; Jiang et al.), and sanity-check that the agent recovers AS/GLFT in the stationary case (Selser et al.).

## 14. Recommended reading order

1. Avellaneda & Stoikov (2008) — the model everyone builds on (Section 2). Read with the Hummingbot deep-dive (11.6) for a practitioner parameterisation.
2. Guéant, Lehalle & Fernandez-Tapia (2013) — the asymptotic/closed-form quotes you will actually implement (Section 3).
3. Guéant (2017) — general intensities, Δ trade size, Model B (risk-neutral + running penalty), multi-asset (Section 4).
4. Cont, Kukanov & Stoikov (2014) + Lipton, Pesavento & Sotiropoulos (2013) + Stoikov micro-price (2018) — the fair-value / signal layer (Sections 7–8).
5. Cartea, Jaimungal & Ricci (2014) and Cartea & Jaimungal (2015) — why you must include short-term alpha and an adverse-selection buffer (Section 5); then the Cartea–Jaimungal–Penalva book chapter on MM.
6. Budish–Cramton–Shim (2015), Aquilina–Budish–O'Neill (2022), Gao & Wang (2020) — latency, sniping and the profitability condition (Section 12).
7. Moret & Lillo (2026), Bieganowski & Ślepaczuk (2026), Barone & Lillo (2026) — what goes wrong in real crypto flow and how to detect it (Section 11).
8. Le (2026), He et al. (2022), Zeng & Liu (2026) — perpetual-futures specifics: funding, basis, hedging (Section 11).
9. Barzykin–Bergault–Guéant (2022), Bergault et al. (2022) — hedging bands and multi-asset skew (Section 9).
10. Spooner et al. (2018), Sadighian (2019/2020), Gašperov–Kostanjčar (2021/22), Jiang et al. (2025) — RL, only after the analytic baseline works (Section 10).
11. Ho–Stoll, Glosten–Milgrom, Kyle, Fodra–Labadie, Fodra–Pham — background (Sections 1, 6).

## 15. Index of downloaded PDFs (`papers/`)

| File | Paper |
|---|---|
| avellaneda-stoikov-2008-hft-limit-order-book.pdf | Avellaneda & Stoikov 2008 |
| gueant-lehalle-fernandez-tapia-2012-dealing-with-inventory-risk.pdf | GLFT 2012/13 |
| gueant-2017-optimal-market-making.pdf | Guéant 2017 |
| cartea-jaimungal-ricci-2014-buy-low-sell-high-short-term-alpha.pdf | Cartea, Jaimungal & Ricci 2014 (working-paper version) |
| fodra-labadie-2012-hf-market-making-inventory-constraints-directional-bets.pdf | Fodra & Labadie 2012 |
| fodra-pham-2013-semi-markov-model-market-microstructure.pdf | Fodra & Pham 2013 |
| fodra-pham-2015-hft-asymptotics-markov-renewal.pdf | Fodra & Pham 2015 |
| cont-kukanov-stoikov-2014-price-impact-order-book-events.pdf | Cont, Kukanov & Stoikov 2014 |
| cont-delarrard-2013-price-dynamics-markovian-lob.pdf | Cont & de Larrard 2013 |
| lipton-pesavento-sotiropoulos-2013-trade-arrival-quote-imbalance.pdf | Lipton, Pesavento & Sotiropoulos 2013 |
| bergault-evangelista-gueant-vieira-2022-closed-form-multi-asset-mm.pdf | Bergault et al. 2022 |
| bergault-gueant-2022-size-matters-otc-market-makers.pdf | Bergault & Guéant 2022 |
| barzykin-bergault-gueant-2022-algorithmic-mm-dealer-markets-hedging-market-impact.pdf | Barzykin, Bergault & Guéant 2022 |
| spooner-2018-market-making-via-rl.pdf | Spooner et al. 2018 |
| ganesh-2019-rl-market-making-multiagent-dealer.pdf | Ganesh et al. (JPM) 2019 |
| gasperov-kostanjcar-2022-deep-rl-mm-hawkes-lob.pdf | Gašperov & Kostanjčar 2022 |
| sadighian-2019-deep-rl-crypto-market-making.pdf | Sadighian 2019 |
| sadighian-2020-extending-deep-rl-crypto-market-making.pdf | Sadighian 2020 |
| selser-kreiner-maurette-2021-optimal-mm-by-rl.pdf | Selser, Kreiner & Maurette 2021 |
| he-zheng-yang-2023-tick-data-periodical-signal-hf-mm-crypto.pdf | He, Zheng & Yang 2023 |
| raheman-2022-adaptive-multi-strategy-mm-agent-volatile-crypto.pdf | Raheman et al. 2022 |
| jiang-2025-resolving-latency-inventory-risk-mm-rl.pdf | Jiang et al. 2025 |
| moret-lillo-2026-deep-learning-robust-mm-regime-switching-flow.pdf | Moret & Lillo 2026 |
| zeng-liu-2026-optimal-adaptive-mm-perpetual-futures.pdf | Zeng & Liu 2026 |
| le-2026-funding-aware-optimal-mm-perpetual-dexs.pdf | Le 2026 |
| he-manela-ross-vonwachter-2022-fundamentals-of-perpetual-futures.pdf | He, Manela, Ross & von Wachter 2022–26 |
| ackerer-hugonnier-jermann-2024-perpetual-futures-pricing.pdf | Ackerer, Hugonnier & Jermann 2024 |
| barone-lillo-2026-market-impact-adverse-selection-hyperliquid.pdf | Barone & Lillo 2026 |
| bieganowski-slepaczuk-2026-explainable-patterns-crypto-microstructure-binance-perps.pdf | Bieganowski & Ślepaczuk 2026 |
| budish-cramton-shim-2015-hft-arms-race-frequent-batch-auctions.pdf | Budish, Cramton & Shim 2015 |
| aquilina-budish-oneill-2020-hft-arms-race-fca-op50.pdf | Aquilina, Budish & O'Neill 2020 (FCA OP50) |
| gao-wang-2020-optimal-mm-presence-of-latency.pdf | Gao & Wang 2020 |
| cartea-jaimungal-sanchez-betancourt-2019-latency-and-liquidity-risk.pdf | Cartea, Jaimungal & Sánchez-Betancourt 2019 |

Not downloaded (paywalled or session-gated), linked in text: Ho & Stoll 1981; Glosten & Milgrom 1985; Kyle 1985; Stoikov micro-price (SSRN); Cartea & Jaimungal 2015 (SSRN); Cartea, Donnelly & Jaimungal 2018 (SSRN); Gašperov & Kostanjčar 2021 (IEEE Xplore); the Guéant and Cartea–Jaimungal–Penalva books.
