import os
from typing import Tuple

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from talib import EMA, SMA, STOCHRSI

FIGURE_PATH = "figures"


def supertrend_analysis(high, low, close, look_back, multiplier):
    # ATR
    tr1 = pd.DataFrame(high - low)
    tr2 = pd.DataFrame(abs(high - close.shift(1)))
    tr3 = pd.DataFrame(abs(low - close.shift(1)))
    frames = [tr1, tr2, tr3]
    tr = pd.concat(frames, axis=1, join='inner').max(axis=1)
    atr = tr.ewm(look_back).mean()

    # H/L AVG AND BASIC UPPER & LOWER BAND
    hl_avg = (high + low) / 2
    upper_band = (hl_avg + multiplier * atr).dropna()
    lower_band = (hl_avg - multiplier * atr).dropna()

    # FINAL UPPER BAND
    final_bands = pd.DataFrame(columns=['upper', 'lower'])
    final_bands.iloc[:, 0] = [x for x in upper_band - upper_band]
    final_bands.iloc[:, 1] = final_bands.iloc[:, 0]

    for i in range(len(final_bands)):
        if i == 0:
            final_bands.iloc[i, 0] = 0
        else:
            if (upper_band[i] < final_bands.iloc[i - 1, 0]) | (close[i - 1] > final_bands.iloc[i - 1, 0]):
                final_bands.iloc[i, 0] = upper_band[i]
            else:
                final_bands.iloc[i, 0] = final_bands.iloc[i - 1, 0]

    # FINAL LOWER BAND
    for i in range(len(final_bands)):
        if i == 0:
            final_bands.iloc[i, 1] = 0
        else:
            if (lower_band[i] > final_bands.iloc[i - 1, 1]) | (close[i - 1] < final_bands.iloc[i - 1, 1]):
                final_bands.iloc[i, 1] = lower_band[i]
            else:
                final_bands.iloc[i, 1] = final_bands.iloc[i - 1, 1]

    # SUPERTREND

    supertrend = pd.DataFrame(columns=[f'supertrend_{look_back}'])
    supertrend.iloc[:, 0] = [x for x in final_bands['upper'] - final_bands['upper']]

    for i in range(len(supertrend)):
        if i == 0:
            supertrend.iloc[i, 0] = 0
        elif supertrend.iloc[i - 1, 0] == final_bands.iloc[i - 1, 0] and close[i] < final_bands.iloc[i, 0]:
            supertrend.iloc[i, 0] = final_bands.iloc[i, 0]
        elif supertrend.iloc[i - 1, 0] == final_bands.iloc[i - 1, 0] and close[i] > final_bands.iloc[i, 0]:
            supertrend.iloc[i, 0] = final_bands.iloc[i, 1]
        elif supertrend.iloc[i - 1, 0] == final_bands.iloc[i - 1, 1] and close[i] > final_bands.iloc[i, 1]:
            supertrend.iloc[i, 0] = final_bands.iloc[i, 1]
        elif supertrend.iloc[i - 1, 0] == final_bands.iloc[i - 1, 1] and close[i] < final_bands.iloc[i, 1]:
            supertrend.iloc[i, 0] = final_bands.iloc[i, 0]

    supertrend = supertrend.set_index(upper_band.index)
    supertrend = supertrend.dropna()[1:]

    # ST UPTREND/DOWNTREND
    upt = []
    dt = []
    close = close.iloc[len(close) - len(supertrend):]

    for i in range(len(supertrend)):
        if close[i] > supertrend.iloc[i, 0]:
            upt.append(supertrend.iloc[i, 0])
            dt.append(np.nan)
        elif close[i] < supertrend.iloc[i, 0]:
            upt.append(np.nan)
            dt.append(supertrend.iloc[i, 0])
        else:
            upt.append(np.nan)
            dt.append(np.nan)

    st, upt, dt = pd.Series(supertrend.iloc[:, 0]), pd.Series(upt), pd.Series(dt)
    upt.index, dt.index = supertrend.index, supertrend.index

    return st, upt, dt


def get_supertrend_signals(prices, st):
    long_trigger = []
    short_trigger = []
    st_signal = []
    signal = 0

    for i in range(len(st)):
        if st[i - 1] > prices[i - 1] and st[i] < prices[i]:
            if signal != 1:
                long_trigger.append(prices[i])
                short_trigger.append(np.nan)
                signal = 1
                st_signal.append(signal)
            else:
                long_trigger.append(np.nan)
                short_trigger.append(np.nan)
                st_signal.append(0)
        elif st[i - 1] < prices[i - 1] and st[i] > prices[i]:
            if signal != -1:
                long_trigger.append(np.nan)
                short_trigger.append(prices[i])
                signal = -1
                st_signal.append(signal)
            else:
                long_trigger.append(np.nan)
                short_trigger.append(np.nan)
                st_signal.append(0)
        else:
            long_trigger.append(np.nan)
            short_trigger.append(np.nan)
            st_signal.append(0)

    return long_trigger, short_trigger, st_signal


def calculate_sma(df: pd.DataFrame, time_period: int = 200) -> pd.DataFrame:
    return SMA(df.close, timeperiod=time_period)


def calculate_ema(df: pd.DataFrame, time_period: int = 200) -> pd.DataFrame:
    return EMA(df.close, timeperiod=time_period)


def calculate_stoch_rsi(df: pd.DataFrame) -> pd.DataFrame:
    return STOCHRSI(df.close, timeperiod=14, fastk_period=5, fastd_period=3, fastd_matype=0)


def take_profit_calc(close: float, profit_percent: float, precision: int) -> Tuple[float, float]:
    long_profit = round(close + close * profit_percent / 100, precision)
    short_profit = round(close - close * profit_percent / 100, precision)
    return long_profit, short_profit


def plot_and_save_figure(market: str, df: pd.DataFrame) -> str:
    # Plot and save results
    fig, ax = plt.subplots()
    ax.plot(df.index, df.close, ".-", color="tab:blue")
    ax.plot(df.index, df.ema200, color="tab:orange")
    ax.plot(df.index, df.st, color="tab:gray")

    ax.plot(df.index, df.short_trig, marker='^', color='tab:red', markersize=8, linewidth=0, label='Short')
    ax.plot(df.index, df.long_trig, marker='v', color='tab:green', markersize=8, linewidth=0, label='Long')

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b-%d %H:%m'))
    fig.autofmt_xdate()
    ax.set_title(market)
    plt.close(fig)
    ax.legend()
    figure_path = os.path.join(FIGURE_PATH, f"{market}.jpg")
    fig.savefig(figure_path, dpi=300)
    return figure_path


def calculate_pnl(markets: list, trades: dict, leverage: float = 1):
    pnl_list = []
    for market in markets:
        if len(trades[market]) >= 2:
            for idx in range(len(trades[market])):
                if idx + 1 < len(trades[market]):
                    if trades[market][idx]["side"] == "sell":
                        pnl = (trades[market][idx]["entry"] - trades[market][idx + 1]["entry"]) / \
                              trades[market][idx + 1]["entry"] * 100
                    else:
                        pnl = (trades[market][idx + 1]["entry"] - trades[market][idx]["entry"]) / trades[market][idx][
                            "entry"] * 100
                    pnl *= leverage
                    print(f"{market} {round(pnl, 1)}%")
                    pnl_list.append(pnl)

    print(f"Average pnl = {sum(pnl_list) / len(pnl_list)}")
