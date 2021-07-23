import numpy as np
import pandas as pd

import supertrend as spt


def get_base_positions(st_signal: np.ndarray, close: np.ndarray) -> list:
    positions = []

    for idx, signal in enumerate(st_signal):
        if signal == 1:
            positions.append({"side": "long", "price": close[idx]})
        elif signal == -1:
            positions.append({"side": "short", "price": close[idx]})
    return positions


def short_strategy(pos: dict, strategy: str) -> bool:
    if strategy:
        if strategy == "sma":
            if pos["price"] < pos["sma"]:
                return True
            else:
                return False
        elif strategy == "ema":
            if pos["price"] < pos["ema"]:
                return True
            else:
                return False
    else:
        return True


def long_strategy(pos: dict, strategy: str) -> bool:
    if strategy:
        if "sma" in strategy:
            if pos["price"] > pos["sma"]:
                return True
            else:
                return False
        if "ema" in strategy:
            if pos["price"] > pos["ema"]:
                return True
            else:
                return False
    else:
        return True


def profits_calculator(positions: list, strategy: str = None) -> list:
    profits = []

    for idx in range(len(positions) - 1):
        if positions[idx]["side"] == "short" and short_strategy(positions[idx], strategy):
            percent_change = (positions[idx]["price"] - positions[idx + 1]["price"]) / positions[idx + 1]["price"] * 100
            profits.append(percent_change)
        elif positions[idx]["side"] == "long" and long_strategy(positions[idx], strategy):
            percent_change = (positions[idx + 1]["price"] - positions[idx]["price"]) / positions[idx]["price"] * 100
            profits.append(percent_change)
    return profits


def profits_analysis(profits: list) -> dict:
    avg_returns = np.average(profits)
    std_dev = np.std(profits)
    minimum = np.min(profits)
    maximum = np.max(profits)

    avg_neg_return = (np.average([val for val in profits if val < 0]))
    avg_pos_return = (np.average([val for val in profits if val > 0]))
    avg_pos_neg_ratio = np.abs(avg_pos_return / avg_neg_return)

    result = {
        "AvgReturns": avg_returns,
        "StdDev": std_dev,
        "RetDevRatio": avg_returns / std_dev,
        "MinReturns": minimum,
        "MaxReturns": maximum,
        "AvgNegReturns": avg_neg_return,
        "AvgPosReturns": avg_pos_return,
        "PosNegRetRatio": avg_pos_neg_ratio
    }
    return result


def backtest_dataframe(df: pd.DataFrame, look_back: int = 9, multiplier: int = 2) -> dict:
    st, _, _ = spt.supertrend_analysis(df.high, df.low, df.close, look_back=look_back, multiplier=multiplier)
    _, _, st_signal = spt.get_supertrend_signals(df.close, st)

    positions = get_base_positions(st_signal, df.close)
    profits = profits_calculator(positions)

    return profits_analysis(profits)


def get_backtest_ranking(new_value: float, filename: str, sort_by_column: str = "PosNegRetRatio") -> str:
    if not filename.endswith(".csv"):
        filename += ".csv"

    df = pd.read_csv(filename)

    avg_pos_neg_ratio = np.append(df[sort_by_column].values, new_value)
    reverse_sorted = np.sort(avg_pos_neg_ratio)[::-1]
    rank = np.where(reverse_sorted == new_value)[0][0]
    return f"{rank + 1}/{len(avg_pos_neg_ratio)}"
