# Vektor Research Foundation
## Curated Academic References for ML-Native Quantitative Trading

**Document Version**: 1.0  
**Compilation Date**: 2026-05-23  
**Focus**: Deterministic ML/RL/DL approaches to institutional-grade algorithmic trading

---

## How to Use This Document

This reference guide is organized by **implementation priority**:
- **Tier 1 (Critical)**: Read first, foundational concepts
- **Tier 2 (High Priority)**: Read before Phase 1 implementation
- **Tier 3 (Implementation Reference)**: Detailed patterns, algorithms, tuning
- **Tier 4 (Advanced)**: Cutting-edge methods, competitive advantage

For each paper:
- **Key Insight**: 1-sentence summary
- **Why It Matters**: Application to Vektor
- **When to Read**: Implementation phase
- **Implementation Notes**: Practical takeaways

---

# TIER 1: FOUNDATIONAL CONCEPTS
## Read These First (Weeks 1–2)

### 1.1 Machine Learning for Financial Markets (Conceptual Foundation)

#### Paper: "Machine Learning for Forecasting Stock Returns" 
- **Authors**: Krauss, Do, Huck (2017)
- **Link**: https://arxiv.org/abs/1702.00500
- **Venue**: Journal of Financial Data Science
- **Key Insight**: Neural networks, random forests, and SVMs consistently outperform traditional econometric models on equity return forecasting.
- **Why It Matters**: Validates the core thesis that ML beats traditional approaches. Compares multiple architectures (RNN, RF, SVM, regularized regression) on same dataset.
- **When to Read**: Week 1 (before model selection)
- **Implementation Notes**:
  - Test 3 architectures on same train/test split
  - Use proper walk-forward CV (they use purged CV)
  - Monitor feature importance to avoid overfitting to noise
  - Benchmark against simple AR(1) + moving average baselines

#### Paper: "Machine Learning in Asset Management"
- **Authors**: Arnott, Beck, Kalesnik, West (2019)
- **Link**: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3441090
- **Venue**: Research Affiliates white paper
- **Key Insight**: ML adds significant alpha in asset management, but only when applied to diversified cross-sectional problems (not pure prediction of single assets).
- **Why It Matters**: Explains when ML works (cross-sectional) vs doesn't (pure prediction). Provides industry validation.
- **When to Read**: Week 1 (before building system architecture)
- **Implementation Notes**:
  - Design your model to leverage cross-sectional structure (predict relative value, not absolute)
  - Multi-asset ensemble beats single-asset models
  - Diversification across models + assets is key

#### Paper: "Advances in Financial Machine Learning"
- **Author**: Marcos López de Prado (2018)
- **Link**: https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086
- **Type**: **Book** (required reading for the team)
- **Key Insight**: Comprehensive guide on ML pitfalls in finance: overfitting, lookahead bias, leakage, regime shifts, and practical solutions.
- **Why It Matters**: **Most important foundational reference**. Covers meta-labeling, feature engineering, purged cross-validation, and portfolio construction.
- **When to Read**: Week 1–2 (read Chapters 1–8 before implementation)
- **Implementation Notes**:
  - Implement purged walk-forward CV exactly as described (Section 4)
  - Use embargo windows (no training data within 5–10 days of test period)
  - Understand meta-labeling (Section 6) for stacking
  - Sample weights for imbalanced data (Section 3.2)

---

### 1.2 Point-in-Time Data & Lookahead Prevention

#### Paper: "The Backtest Overfitting Problem: Causes and Solutions"
- **Authors**: Bailey, Borwein, López de Prado, Zubulake (2016)
- **Link**: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2740059
- **Venue**: Journal of Portfolio Management
- **Key Insight**: Most backtests overfit due to multiple testing and lookahead bias. Proper Sharpe ratio is often 1/3 of reported.
- **Why It Matters**: Explains why backtests fail in live trading. Mandatory before any production deployment.
- **When to Read**: Week 2 (before building backtest harness)
- **Implementation Notes**:
  - Compute Sharpe ratio with deflation (for multiple tests)
  - Log all model configurations tested
  - Validate on out-of-sample data beyond original training period
  - Track how many hyperparameter combinations you tested (inflates Type I error)

#### Paper: "Walk-Forward Analysis"
- **Author**: Pardo (2008)
- **Link**: https://www.wiley.com/en-us/The+Evaluation+and+Optimization+of+Trading+Strategies%2C+2nd+Edition-p-9780470128671
- **Type**: **Book Chapter** (required)
- **Key Insight**: Proper walk-forward CV uses expanding or rolling windows, with embargo periods to prevent data leakage.
- **Why It Matters**: Foundational validation framework. Skip this and your model will fail in production.
- **When to Read**: Week 2 (implement before testing any model)
- **Implementation Notes**:
  - Use rolling 3-year train window, 1-month test window, 5-day embargo
  - Retrain models at each step (don't use single model over entire period)
  - Track out-of-sample Sharpe separately from in-sample
  - Log feature/target distributions to detect drift

---

### 1.3 Ensemble Learning & Meta-Learning

#### Paper: "Stacked Generalization"
- **Author**: Wolpert (1992)
- **Link**: https://scholar.google.com/scholar?q=wolpert+stacked+generalization+1992
- **Venue**: Neural Networks journal
- **Key Insight**: Combining multiple learners via a meta-model reduces model-specific errors. Works best when base models are diverse.
- **Why It Matters**: Foundation of your meta-intent stacking layer. Shows why ensemble > single model.
- **When to Read**: Week 2 (before building meta-intent model)
- **Implementation Notes**:
  - Train base learners (technical, fundamental, sentiment) independently
  - Use diverse model types (tree, neural, linear) for base models
  - Meta-model inputs: predictions + uncertainties + agreement/disagreement metrics
  - Validate that meta-model beats any base model alone

#### Paper: "XGBoost: A Scalable Tree Boosting System"
- **Authors**: Chen & Guestrin (2016)
- **Link**: https://arxiv.org/abs/1603.02754
- **Venue**: KDD (top-tier)
- **Key Insight**: Gradient boosting dominates tabular ML. Fast, interpretable, production-proven.
- **Why It Matters**: Primary recommendation for technical + ensemble models. Industry standard.
- **When to Read**: Week 2 (before implementing gradient boosting models)
- **Implementation Notes**:
  - Start with LightGBM for speed (faster than XGBoost for large datasets)
  - Tune: max_depth=5–8, learning_rate=0.05–0.1, num_leaves=32–128
  - Use early stopping + validation set
  - Extract SHAP values for feature importance
  - Monitor for overfitting (train vs validation divergence)

---

# TIER 2: DOMAIN-SPECIFIC MODELS
## Read Before Phase 1 Implementation (Weeks 3–5)

### 2.1 Technical Analysis & Price Prediction

#### Paper: "Temporal Fusion Transformers for Interpretable Multi-horizon Time Series Forecasting"
- **Authors**: Lim, Arik, Loeff, Pfister (2021)
- **Link**: https://arxiv.org/abs/1912.09300
- **Venue**: ICLR (top-tier)
- **Key Insight**: Transformer architecture with attention mechanisms outperforms LSTMs for multi-step forecasting. Interpretable via attention weights.
- **Why It Matters**: State-of-the-art for predicting returns at multiple horizons (1d, 5d, 20d). Handles non-stationary markets.
- **When to Read**: Week 3 (before implementing deep learning forecasters)
- **Implementation Notes**:
  - Use PyTorch Lightning for training (handles distributed training)
  - Input: multi-horizon OHLCV + technical indicators (sequences)
  - Output: quantile forecasts (captures uncertainty, not just point estimates)
  - Attention weights show which time steps matter (useful for interpretability)
  - Train with embargo: no future data in sequence

#### Paper: "An Introduction to Hidden Markov Models and Bayesian Networks"
- **Authors**: Rabiner & Juang (1986)
- **Link**: http://www.ece.ucsb.edu/Faculty/Rabiner/ece259/Reprints/tutorial%20on%20hmm%20and%20applications.pdf
- **Type**: Classic tutorial
- **Key Insight**: HMMs elegantly model regime switches in markets. Tractable inference via Viterbi + EM.
- **Why It Matters**: Recommended for regime detection (bullish, bearish, high-vol, consolidation).
- **When to Read**: Week 4 (before implementing regime classifiers)
- **Implementation Notes**:
  - States: [bullish_trend, bearish_trend, high_volatility, low_volatility]
  - Observations: [returns, volatility, spread]
  - Use Viterbi algorithm for best state sequence
  - Retrain monthly with EM algorithm
  - Output: regime probabilities (not hard states) for soft signal weighting

#### Paper: "The Dynamics of Exploiting Differences in Volatility in Financial Markets"
- **Authors**: Hung & Yang (2018)
- **Link**: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3144509
- **Venue**: Journal of Futures Markets
- **Key Insight**: Volatility-based trading strategies are profitable. Volatility forecasts add alpha independent of returns.
- **Why It Matters**: Justifies volatility as separate feature in technical model. Shows volatility clustering exploitable.
- **When to Read**: Week 3 (before feature engineering for technical model)
- **Implementation Notes**:
  - Compute realized volatility (close-to-close, Parkinson, Garman-Klass)
  - GARCH/EWMA volatility forecasting
  - Trade when realized > expected (mismatch)
  - Volatility forecast is independent signal from returns

---

### 2.2 Fundamental Analysis & Valuation

#### Paper: "The Cross-Section of Expected Stock Returns"
- **Authors**: Fama & French (2015)
- **Link**: https://www.sciencedirect.com/science/article/pii/S0304405X15000033
- **Venue**: Journal of Financial Economics (top-tier)
- **Key Insight**: Comprehensive review of factors driving returns. Value, profitability, and investment factors documented.
- **Why It Matters**: Defines the expected return model. Foundation for fundamental signal design.
- **When to Read**: Week 3 (understand what drives returns before building model)
- **Implementation Notes**:
  - Implement Fama-French factors: Mkt-RF, SMB, HML, RMW, CMA
  - Test: does your fundamental model capture these factors?
  - Use as baseline to beat
  - Sector-adjust metrics (P/E, P/B relative to sector)

#### Paper: "Accruals and Prediction of Future Cash Flows"
- **Author**: Sloan (1996)
- **Link**: https://scholar.google.com/scholar?q=sloan+accruals+future+cash+flows+1996
- **Venue**: Journal of Accounting and Economics
- **Key Insight**: High-accrual companies underperform. Accrual anomaly exploitable.
- **Why It Matters**: Quality signal for fundamental model. Easy to compute, documented alpha.
- **When to Read**: Week 3 (before fundamental feature engineering)
- **Implementation Notes**:
  - Compute: Accruals = (ΔWC - DepAm) / Total Assets
  - Low-accrual companies outperform
  - Strong effect for 2–5 year holding periods
  - Adjusts for earnings quality

#### Paper: "Deep Learning for Predicting Asset Returns"
- **Authors**: Gu, Kelly, Xiu (2020)
- **Link**: https://arxiv.org/abs/1701.08717
- **Venue**: Journal of Finance
- **Key Insight**: Deep neural networks on fundamental data beat traditional cross-sectional models. Captures nonlinear valuation-growth interactions.
- **Why It Matters**: Justifies using deep tabular models (FT-Transformer, TabNet) for fundamental analysis.
- **When to Read**: Week 4 (before implementing fundamental deep learning model)
- **Implementation Notes**:
  - Input: fundamental factors (P/E, growth, profitability, quality)
  - Architecture: 2–3 layer neural net (avoid overfitting)
  - Output: excess return prediction
  - Compare to linear (Fama-French) baseline
  - Deep learning captures interaction terms automatically

---

### 2.3 Sentiment & Alternative Data

#### Paper: "FinBERT: Financial Sentiment Analysis with Pre-trained Language Models"
- **Authors**: Huang, Wang, Yang (2022)
- **Link**: https://arxiv.org/abs/1908.10063
- **Venue**: ACL (NLP conference)
- **Key Insight**: BERT fine-tuned on financial data outperforms generic NLP for sentiment. Captures finance-specific language patterns.
- **Why It Matters**: Recommendation for NLP pipeline (not LLM generation, pure classification).
- **When to Read**: Week 4 (before implementing sentiment model)
- **Implementation Notes**:
  - Use FinBERT embeddings (pre-trained, frozen)
  - Fine-tune classification head on financial sentiment data
  - Input: news headlines, earnings transcripts, social media text
  - Output: polarity [-1, +1] + confidence + event type
  - Aggregate entity-level (per ticker, not market-wide)

#### Paper: "The Power of Nowcasting using High-Frequency Signals"
- **Authors**: Coullet et al. (2019)
- **Link**: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3394928
- **Venue**: Journal of Financial Economics
- **Key Insight**: Real-time alternative data (web traffic, credit cards, satellite) predicts economic outcomes days/weeks before official releases.
- **Why It Matters**: Alternative data adds unique alpha source orthogonal to price/fundamentals.
- **When to Read**: Week 5 (before incorporating alternative data)
- **Implementation Notes**:
  - Data sources: foot traffic (Safegraph), web analytics (SimilarWeb), credit card (Facteus), job postings (Indeed API)
  - Preprocess: aggregate weekly, lag structure (t-1, t-2, t-3)
  - Targets: same-quarter revenue, earnings growth
  - Train separate models per data source, ensemble later

---

# TIER 3: REINFORCEMENT LEARNING & PORTFOLIO OPTIMIZATION
## Read Before Phase 2 (Weeks 6–10)

### 3.1 Offline RL for Trading

#### Paper: "Conservative Q-Learning for Offline Reinforcement Learning"
- **Authors**: Kumar, Zhou, Tucker, Levine (2020)
- **Link**: https://arxiv.org/abs/2006.04779
- **Venue**: NeurIPS (top-tier)
- **Key Insight**: Conservative Q-Learning (CQL) prevents out-of-distribution actions in offline setting. Safe for trading (no live exploration).
- **Why It Matters**: **Critical for Vektor**. Enables policy learning without risking capital. Proven safe in constrained settings.
- **When to Read**: Week 6 (before implementing RL policy)
- **Implementation Notes**:
  - Use Stable-Baselines3 CQL implementation
  - State: portfolio weights + signals + risk metrics
  - Action: rebalancing deltas (continuous or discrete)
  - Reward: return - cost - slippage - drawdown_penalty
  - Offline dataset: replay buffer from historical backtests
  - Conservative: penalize actions outside historical distribution

#### Paper: "Implicit Q-Learning"
- **Authors**: Kostrikov, Nair, Levine (2021)
- **Link**: https://arxiv.org/abs/2110.06169
- **Venue**: ICLR (top-tier)
- **Key Insight**: Expectile-based Q-learning avoids explicit conservatism while remaining stable. More data-efficient than CQL.
- **Why It Matters**: Alternative offline RL algorithm. Often faster convergence than CQL.
- **When to Read**: Week 6 (as alternative to CQL, compare both)
- **Implementation Notes**:
  - Use expectile loss instead of Bellman residual
  - Better for continuous action spaces (rebalancing deltas)
  - Empirically more stable with fewer hyperparameters

#### Paper: "Deep Reinforcement Learning for Trading"
- **Authors**: Liang et al. (2018)
- **Link**: https://arxiv.org/abs/1811.07522
- **Venue**: ArXiv preprint
- **Key Insight**: End-to-end RL for portfolio management. DQN/DDPG agents learn directly from OHLCV.
- **Why It Matters**: Shows feasibility of RL for trading. Discusses reward design, state representation, action space.
- **When to Read**: Week 6 (understand practical RL trading systems)
- **Implementation Notes**:
  - State space: market features + portfolio state + risk metrics
  - Action space: discrete (buy/hold/sell) or continuous (position deltas)
  - Reward: Sharpe ratio, return - slippage - drawdown penalty
  - Train on historical data via offline RL
  - Key insight: reward function design is 80% of the work

#### Paper: "Risk-Sensitive Reinforcement Learning"
- **Authors**: Mihatsch & Neuneier (2002)
- **Link**: https://scholar.google.com/scholar?q=mihatsch+risk+sensitive+reinforcement+learning+2002
- **Venue**: Reinforcement Learning conference
- **Key Insight**: Incorporate risk constraints (CVaR, drawdown) into RL rewards. Exponential utility framework.
- **Why It Matters**: Explains how to formalize risk-adjusted rewards. Critical for institutional settings.
- **When to Read**: Week 6 (when tuning RL reward function)
- **Implementation Notes**:
  - Use exponential utility: U(r) = -exp(-λ×r)
  - Reward includes: return + (-λ) × tail_risk
  - Tune λ based on institutional drawdown tolerance
  - Alternative: directly constraint CVaR (hard constraint)

---

### 3.2 Portfolio Optimization & Risk Management

#### Paper: "A Critique of the Asset Allocation Methodology"
- **Author**: Michaud (1989)
- **Link**: https://scholar.google.com/scholar?q=michaud+critique+mean+variance+optimization+1989
- **Venue**: Financial Analysts Journal
- **Key Insight**: Mean-variance optimization is fragile. Small input estimate errors → large weight changes.
- **Why It Matters**: Explains why naive mean-variance fails. Motivates robust alternatives (Resampling, HRP).
- **When to Read**: Week 7 (before choosing portfolio optimization method)
- **Implementation Notes**:
  - Don't use raw mean-variance on asset returns
  - Use factor-based returns (reduces noise)
  - Or use shrinkage estimators for covariance
  - Or use Hierarchical Risk Parity (more stable)

#### Paper: "Hierarchical Risk Parity"
- **Author**: Marcos López de Prado (2016)
- **Link**: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2708678
- **Venue**: Journal of Portfolio Management
- **Key Insight**: Hierarchical clustering + recursive bisection creates more stable portfolios than mean-variance. Robust to covariance estimation errors.
- **Why It Matters**: **Recommended primary portfolio construction method for Vektor**. More stable in live trading.
- **When to Read**: Week 7 (before implementing portfolio construction)
- **Implementation Notes**:
  - Implement recursive bisection (detailed in paper)
  - Use correlation distance matrix (not raw covariance)
  - No matrix inversion (numerically stable)
  - Outperforms Markowitz especially with estimation errors
  - Good default: equal-weight allocation across clusters

#### Paper: "Optimal Portfolio Choice with Regime-Switching, Skewness and Kurtosis Preferences"
- **Authors**: Liu, Pan, Wang (2012)
- **Link**: https://www.sciencedirect.com/science/article/pii/S0305050011001479
- **Venue**: Journal of Financial Economics
- **Key Insight**: Portfolio weights should adapt to regime shifts. Skewness/kurtosis preferences matter (not just variance).
- **Why It Matters**: Justifies regime-dependent model routing. Shows value of macro regime classification.
- **When to Read**: Week 8 (before implementing regime-dependent rebalancing)
- **Implementation Notes**:
  - Compute regime probabilities from HMM
  - Reweight portfolio allocations per regime
  - In high-volatility regime: reduce size, increase hedges
  - In risk-on regime: increase exposure to high-beta assets

#### Paper: "Expected Shortfall (CVaR) Optimization"
- **Author**: Pflug (2000)
- **Link**: https://scholar.google.com/scholar?q=pflug+expected+shortfall+2000
- **Venue**: Journal of Computational Finance
- **Key Insight**: CVaR (expected shortfall) is coherent risk metric. Tractable to optimize.
- **Why It Matters**: Better tail-risk control than variance. Implements hard downside constraints.
- **When to Read**: Week 8 (when tuning risk gates)
- **Implementation Notes**:
  - CVaR = expected return of worst 5% outcomes
  - Can be optimized via linear program (unlike VaR)
  - Use in policy gate: hard constraint CVaR > -0.15
  - Better than max drawdown for optimization

---

# TIER 4: ADVANCED & COMPETITIVE ADVANTAGE
## Read for Cutting-Edge Methods (Weeks 10+)

### 4.1 Causal Inference & Factor Models

#### Paper: "Causal Forests for Personalized Medicine"
- **Authors**: Athey & Wager (2019)
- **Link**: https://arxiv.org/abs/1610.01271
- **Venue**: JASA (top stats journal)
- **Key Insight**: Heterogeneous treatment effects via forests. Learn which treatments work for which subpopulations.
- **Why It Matters**: **Advanced**: Apply to regime-based model routing. Which signals work best in which markets?
- **When to Read**: Week 10+ (advanced topic)
- **Implementation Notes**:
  - Train separate models per regime (growth vs value vs turbulent)
  - Use causal forests to detect which factors drive returns in each regime
  - Adaptive model weighting: higher weight for signals that work in current regime
  - Heterogeneous feature importance across regimes

#### Paper: "Market Microstructure and Asset Pricing"
- **Authors**: Biais, Glosten, Spatt (1997)
- **Link**: https://scholar.google.com/scholar?q=biais+market+microstructure+asset+pricing+ticks+1997
- **Venue**: Journal of Finance
- **Key Insight**: Order flow, spreads, and information asymmetry drive short-term prices. Separate from fundamental value.
- **Why It Matters**: Understand execution costs, liquidity constraints, signal decay over time.
- **When to Read**: Week 10+ (for execution optimization)
- **Implementation Notes**:
  - Model slippage as function of order size + volatility + spread
  - Transaction cost budget: critical constraint in RL reward
  - Liquidity scoring: avoid illiquid assets
  - Time-decay on signals (decay faster in low-liquidity markets)

---

### 4.2 Advanced Time-Series & Nonlinear Methods

#### Paper: "Dilated Residual Networks for Wavelet-Based Speech Recognition"
- **Authors**: Oord, Dieleman, Zen, et al. (2016)
- **Link**: https://arxiv.org/abs/1604.00494
- **Type**: Paper on TCN (Temporal Convolutional Networks)
- **Key Insight**: TCNs with dilated convolutions capture long-range dependencies efficiently. Alternative to RNNs.
- **Why It Matters**: For deep learning forecasters (alternative to Transformers). Faster training, no vanishing gradients.
- **When to Read**: Week 8–10 (when implementing neural forecasters)
- **Implementation Notes**:
  - Use PyTorch implementation (easy to customize)
  - Dilated convolutions: receptive field = 2^num_layers
  - Better than LSTM for financial data (more stable training)
  - Compare TCN vs Transformer on same task

#### Paper: "Prophet: Forecasting at Scale"
- **Authors**: Taylor & Letham (2017)
- **Link**: https://research.facebook.com/publications/prophet-forecasting-at-scale/
- **Type**: Methods paper
- **Key Insight**: Decomposable time-series forecasting (trend + seasonality + holidays). Robust to missing data and outliers.
- **Why It Matters**: Quick baseline for time-series forecasting. Production-ready implementation.
- **When to Read**: Week 7 (as baseline before deep learning)
- **Implementation Notes**:
  - Use Prophet for quick prototyping of trend/seasonality
  - Detects breakpoints automatically
  - Handles missing data well
  - Compare to neural models to justify added complexity

---

### 4.3 Explainability & Interpretability

#### Paper: "SHAP: A Unified Approach to Interpreting Model Predictions"
- **Authors**: Lundberg & Lee (2017)
- **Link**: https://arxiv.org/abs/1705.07874
- **Venue**: NeurIPS (top-tier)
- **Key Insight**: SHAP values provide consistent, fair feature attribution via game theory.
- **Why It Matters**: **Regulatory + risk management**. Investors want to know what drives signals.
- **When to Read**: Week 5 (implement immediately in all models)
- **Implementation Notes**:
  - Compute SHAP values for tree models (TreeExplainer, fast)
  - SHAP for neural nets (gradient, slower but interpretable)
  - Visualize: force plots, dependence plots, waterfall charts
  - Log SHAP values in decision logs for auditability

---

### 4.4 Causal & Robust Inference

#### Paper: "Doubly Robust Off-Policy Evaluation"
- **Authors**: Dudík, Langford, Li (2011)
- **Link**: https://arxiv.org/abs/1103.4601
- **Venue**: ICML (top-tier)
- **Key Insight**: Unbiased policy evaluation using historical data. Combines importance sampling + regression.
- **Why It Matters**: Evaluate RL policies without live testing. Critical for risk management.
- **When to Read**: Week 9 (before shipping RL to live)
- **Implementation Notes**:
  - Estimate value of RL policy using offline data
  - Importance weighting: P(a|s, π_new) / P(a|s, π_old)
  - Doubly robust: if either model right, estimate is unbiased
  - Use to estimate true Sharpe before going live

---

# TIER 4B: PRODUCTION ENGINEERING
## Practical Implementation References

### 5.1 Backtesting & Simulation

#### Paper: "A Practical Guide to Backtesting"
- **Authors**: Multiple (industry consensus)
- **Link**: Research Affiliates, AQR, Winton white papers
- **Type**: White papers + practitioner guides
- **Key Insight**: Backtests lie. Document everything, test assumptions, validate assumptions.
- **Why It Matters**: 90% of trading systems fail due to backtest overfitting (not bad ideas).
- **When to Read**: Week 2 (before writing backtest harness)
- **Implementation Notes**:
  - Mock live execution (slippage, commissions, latency)
  - Use multiple data vendors (different prices = different results)
  - Test on crisis periods (2008, 2020)
  - Out-of-sample validation: test on period NOT used for development
  - Walk-forward: retrain regularly, test on fresh data

---

### 5.2 Python Libraries & Tools

#### LightGBM Documentation
- **Link**: https://lightgbm.readthedocs.io/
- **Reason**: Primary tree model. Learn parameter tuning.
- **Implementation Notes**:
  - Start with defaults, Bayesian tune max_depth and learning_rate
  - Use early stopping + validation set
  - Feature importance via gain/split/cover
  - Extract SHAP values

#### PyTorch Lightning
- **Link**: https://www.pytorchlightning.ai/
- **Reason**: Simplifies distributed neural network training.
- **Implementation Notes**:
  - Abstract away boilerplate (train loop, distributed training)
  - Integrates with Ray for hyperparameter tuning
  - Easy mixed precision training (FP32 + FP16)

#### Stable-Baselines3
- **Link**: https://stable-baselines3.readthedocs.io/
- **Reason**: Production RL library. Implements CQL, DQN, PPO.
- **Implementation Notes**:
  - Use DummyVecEnv for parallel environment simulation
  - Custom reward function: plug into Gym interface
  - Deterministic inference (no exploration)

#### Riskfolio-Lib
- **Link**: https://riskfolio-lib.readthedocs.io/
- **Reason**: Portfolio optimization library. Implements HRP, mean-variance, risk parity.
- **Implementation Notes**:
  - Fast portfolio construction
  - Built-in constraints (min/max weights, leverage limits)
  - Compare multiple optimization methods on same problem

---

# READING PLAN BY IMPLEMENTATION PHASE

## Phase 0: Foundation (Weeks 1–2)
Read **in order**:
1. "Machine Learning for Forecasting Stock Returns" (Krauss et al., 2017)
2. "Advances in Financial Machine Learning" Chapters 1–8 (López de Prado, 2018)
3. "The Backtest Overfitting Problem" (Bailey et al., 2016)
4. "Walk-Forward Analysis" (Pardo, 2008)

**Outcome**: Understand ML in finance, lookahead bias, proper backtesting.

---

## Phase 1: Technical Model (Weeks 3–5)
1. "Temporal Fusion Transformers" (Lim et al., 2021)
2. "Hidden Markov Models" (Rabiner & Juang, 1986)
3. "Volatility Trading" (Hung & Yang, 2018)
4. "SHAP" (Lundberg & Lee, 2017)

**Outcome**: Build technical model pack with multi-horizon forecasting + regime detection.

---

## Phase 2: Fundamental Model (Weeks 5–7)
1. "Fama-French Cross-Section" (Fama & French, 2015)
2. "Accruals Anomaly" (Sloan, 1996)
3. "Deep Learning for Predicting Returns" (Gu et al., 2020)
4. "Mean-Variance Critique" (Michaud, 1989)

**Outcome**: Build fundamental model pack with factor exposure + quality signals.

---

## Phase 3: Sentiment & Alternative Data (Weeks 7–8)
1. "FinBERT" (Huang et al., 2022)
2. "Nowcasting with Alt Data" (Coullet et al., 2019)
3. "Market Microstructure" (Biais et al., 1997)

**Outcome**: NLP pipeline + alternative data integration.

---

## Phase 4: Ensemble & Stacking (Week 8)
1. "Stacked Generalization" (Wolpert, 1992)
2. "XGBoost" (Chen & Guestrin, 2016)
3. "Doubly Robust Off-Policy Evaluation" (Dudík et al., 2011)

**Outcome**: Meta-intent model + model validation framework.

---

## Phase 5: RL Policy (Weeks 9–10)
1. "Conservative Q-Learning" (Kumar et al., 2020)
2. "Implicit Q-Learning" (Kostrikov et al., 2021)
3. "Deep RL for Trading" (Liang et al., 2018)
4. "Risk-Sensitive RL" (Mihatsch & Neuneier, 2002)

**Outcome**: RL policy for portfolio optimization, offline training.

---

## Phase 6: Portfolio Optimization (Week 10)
1. "Hierarchical Risk Parity" (López de Prado, 2016)
2. "Regime-Switching Portfolios" (Liu et al., 2012)
3. "CVaR Optimization" (Pflug, 2000)

**Outcome**: Portfolio construction + rebalancing logic.

---

## Phase 7+: Advanced (Weeks 10+, Ongoing)
1. "Causal Forests" (Athey & Wager, 2019)
2. "TCNs for Time Series" (Oord et al., 2016)
3. "Prophet Forecasting" (Taylor & Letham, 2017)

**Outcome**: Competitive advantages, heterogeneous model routing, robust inference.

---

# Quick Reference: Paper by Topic

### Price Prediction
- Krauss et al. (2017): ML comparison
- Lim et al. (2021): Temporal Fusion Transformer
- Gu et al. (2020): Deep learning for cross-section
- Taylor & Letham (2017): Prophet baseline

### Risk Management & Portfolio
- Michaud (1989): Mean-variance critique
- López de Prado (2016): HRP
- Liu et al. (2012): Regime-switching portfolios
- Pflug (2000): CVaR
- Biais et al. (1997): Market microstructure

### Validation & Backtesting
- Bailey et al. (2016): Overfitting
- Pardo (2008): Walk-forward
- López de Prado (2018): Chapters 1–8
- Dudík et al. (2011): Off-policy evaluation

### Reinforcement Learning
- Kumar et al. (2020): CQL
- Kostrikov et al. (2021): IQL
- Liang et al. (2018): Deep RL trading
- Mihatsch & Neuneier (2002): Risk-sensitive RL

### Explainability
- Lundberg & Lee (2017): SHAP
- López de Prado (2018): Feature importance
- Athey & Wager (2019): Causal forests

### Sentiment & NLP
- Huang et al. (2022): FinBERT
- Coullet et al. (2019): Nowcasting

### Fundamentals & Factors
- Fama & French (2015): Factor model
- Sloan (1996): Accruals anomaly
- Arnott et al. (2019): ML in asset management

---

# Key Takeaways

1. **Start with López de Prado's book** (Weeks 1–2). Most important reference for avoiding pitfalls.

2. **Build models in this order**: Technical → Fundamental → Sentiment → Ensemble → RL

3. **Always validate walk-forward**, with embargo windows and purged folds.

4. **Use ensemble methods**. Single models fail. Combine diverse architectures.

5. **Offline RL for policy**. Never do online exploration on real capital.

6. **Monitor drift constantly**. Markets change. Models degrade. Retrain monthly.

7. **Explain your model** (SHAP values). Regulators + investors demand interpretability.

8. **Test on crisis periods** (2008, 2020, etc.). Does your model survive tail events?

9. **Implement risk gates before signals**. Good risk management beats complex ML.

10. **Paper trade first**. Live trading is a privilege, not a right.

---

**End of Research Foundation Document**

**Recommended Next Steps**:
1. Download all papers (Google Scholar, SSRN, arXiv links provided)
2. Create reading schedule: 1–2 papers per week
3. Implement code examples as you read
4. Document learnings in engineering wiki
5. Share with team, discuss at weekly meetings

This is your knowledge base for building a world-class quantitative trading system.

