# AI Trader: IQ Option signal indicator (5 / 10 / 15 min)

Two tools that give **CALL / PUT** signals with an **entry time and expiry time**. They only show signals and never place trades.

## 1. AI Trader web app (`index.html`), the main tool
Open it on your phone (it can be installed as an app). Paste a free [Twelve Data](https://twelvedata.com) API key, pick your IQ Option payout, then tap **Start**.

* Choose an expiry: **5, 10 or 15 min**. Every expiry uses 5-minute candles. An entry is made at the candle close, and the expiry falls 1, 2 or 3 candles later. Those times line up with IQ Option's clock-based expiries.
* What it analyses: 49 values per candle. These are RSI, MACD, Stochastic, ADX/DMI, CCI, Aroon, Bollinger bands and squeeze, EMA 20/50/200, RSI divergence, 32 candle patterns (weighted by where they form), patterns on the last 15-minute candle, support and resistance, the **15-minute and 1-hour trend**, and the time of day.
* **AI:** two models are trained in a background thread for each pair and each expiry: gradient-boosted trees and logistic regression. They must agree before the AI gives a signal.
* **10 classic strategies** are tested alongside the models.
* **Validation:** a model or strategy can raise a signal only if it beat IQ Option break-even (`1/(1+payout)`) on unseen recent history, with a statistical safety margin. Quality **A+** means the AI and a strategy agree, **A** means AI only, **B** means strategy only. A dashed yellow card is an unproven lean, so use it on demo only.
* There is a beep and vibration on every validated signal, plus a win/loss log so you can track your real results.
* Free-plan credits: about 12 per pair per hour. Three pairs run for about 22 hours a day within the 800-credit limit.

## 2. TradingView indicator (`tradingview/IQ_Signal_Indicator.pine`)
In TradingView, open **Pine Editor**, paste the file, then click **Add to chart**. Use a 1-minute or 5-minute chart of the same pair you trade on IQ Option.
* A CALL or PUT arrow and label appears at candle close, showing the expiry time. Enter at the next candle.
* The signal is a confluence score of the indicators, the candle patterns and the 15-minute and 1-hour trend. It does not repaint.
* A table shows the **real win rate of past signals on that chart** compared with break-even.
* You can add alerts ("IQ CALL" / "IQ PUT") to get notifications on your phone.

## Honest warning
No indicator or AI can guarantee wins. Short-expiry binary options are close to a coin flip, and the payout below 100% means you need roughly a 54% win rate just to break even. Trade on the **demo account** until your own logged results stay above break-even, and never risk money you cannot afford to lose.

## Candle pattern analysis
* There are **32 patterns**:
  * Engulfing, hammer, hanging man, inverted hammer and shooting star (decided by the trend before the candle).
  * Morning and evening star, piercing line and dark cloud cover, harami.
  * Three inside up/down and three outside up/down.
  * Kicker, key reversal, rising and falling three methods.
  * Tweezers, marubozu, dragonfly and gravestone doji, three soldiers and three crows.
  * Doji and inside bar.
* **Strength score:** each pattern has a base weight, from 1 for a harami up to 3 for a morning star or three outside. That weight is raised by up to 2.5x when the pattern forms at support or resistance, at a Bollinger band, or at an RSI extreme.
* The pattern on the **last closed 15-minute candle** is also shown and is given to the AI.
* **Pattern history:** each pattern's real win rate on that pair at your chosen expiry is measured on about 17 days of history. A pattern that beats break-even in both the older and the newer half of that history is marked **PROVEN** and can trigger a signal on its own. That includes a "strong candle setup" with a strength of 4 or more.
