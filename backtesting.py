import itertools

import numpy as np
import pandas as pd

import supertrend as spt


def get_base_positions(st_signal: np.ndarray, close: np.ndarray) -> list:
    positions = []

    for idx, signal in enumerate(st_signal):
        if signal == 1:
            positions.append({"side": "long", "price": close[idx], "idx": idx})
        elif signal == -1:
            positions.append({"side": "short", "price": close[idx], "idx": idx})

    return positions


def get_drawdown(positions: list, high: np.ndarray, low: np.ndarray) -> np.ndarray:
    drawdown = []
    for idx in range(len(positions) - 1):
        if positions[idx]["side"] == "long":
            min_price_in_range = np.min(low[positions[idx]["idx"]:positions[idx+1]["idx"]])
            drawdown.append((positions[idx]["price"] - min_price_in_range) / min_price_in_range * 100)
        if positions[idx]["side"] == "short":
            max_price_in_range = np.max(high[positions[idx]["idx"]:positions[idx+1]["idx"]])
            drawdown.append((max_price_in_range - positions[idx]["price"]) / positions[idx]["price"] * 100)
    return np.array(drawdown)


def optimize_m_l(df: pd.DataFrame, optimize_to: str = "PosNegRetRatio") -> dict:
    analysis_df = pd.DataFrame(
        columns=["M_L", "AvgReturns", "StdDev", "RetDevRatio", "MinReturns", "MaxReturns",
                 "AvgNegReturns", "AvgPosReturns", "PosNegRetRatio", "MedReturns", "MedNegReturns",
                 "MedPosReturns", "MedPosNegRetRatio", "TheDfactor"])

    multipliers = [3, 4]
    lookbacks = [10, 11]

    for multiplier, lookback in itertools.product(multipliers, lookbacks):
        profits = backtest_dataframe(df, look_back=lookback, multiplier=multiplier)
        profits["M_L"] = f"{multiplier}_{lookback}"
        analysis_df = analysis_df.append(profits, ignore_index=True)

    analysis_df = analysis_df.sort_values(optimize_to, ascending=False)
    analysis_df = analysis_df.reset_index(drop=True)
    opt_multiplier, opt_lookback = [int(val) for val in analysis_df["M_L"][0].split("_")]
    return {"Multiplier": opt_multiplier, "Lookback": opt_lookback}


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


def profits_calculator(positions: list, strategy: str = None) -> np.ndarray:
    profits = []

    for idx in range(len(positions) - 1):
        if positions[idx]["side"] == "short" and short_strategy(positions[idx], strategy):
            percent_change = (positions[idx]["price"] - positions[idx + 1]["price"]) / positions[idx + 1]["price"] * 100
            profits.append(percent_change)
        elif positions[idx]["side"] == "long" and long_strategy(positions[idx], strategy):
            percent_change = (positions[idx + 1]["price"] - positions[idx]["price"]) / positions[idx]["price"] * 100
            profits.append(percent_change)
    return np.array(profits)


def profits_analysis(profits: np.ndarray, drawdown: np.ndarray) -> dict:
    # Basic statistics
    std_dev = np.std(profits)
    minimum = np.min(profits)
    maximum = np.max(profits)

    # Average drawdown
    avg_drawdown = np.average(drawdown)

    # Profits and losses
    neg_returns = profits[profits < 0]
    pos_returns = profits[profits > 0]

    # Average returns and ratio calculations
    avg_returns = np.average(profits)
    avg_pos_return = np.average(pos_returns)

    if neg_returns.size == 0:
        avg_neg_return = 0
        avg_pos_neg_ratio = np.abs(avg_pos_return)
    else:
        avg_neg_return = np.average(neg_returns)
        avg_pos_neg_ratio = np.abs(avg_pos_return / avg_neg_return)

    # Median returns and ratio calculations
    med_returns = np.median(profits)
    med_pos_return = np.median(pos_returns)

    if neg_returns.size == 0:
        med_neg_return = 0
        med_pos_neg_ratio = np.abs(med_pos_return)
    else:
        med_neg_return = np.median(neg_returns)
        med_pos_neg_ratio = np.abs(med_pos_return / med_neg_return)

    result = {
        "AvgReturns": avg_returns,
        "StdDev": std_dev,
        "AvgDrawdown": avg_drawdown,
        "RetDevRatio": avg_returns / std_dev,
        "MinReturns": minimum,
        "MaxReturns": maximum,
        "AvgNegReturns": avg_neg_return,
        "AvgPosReturns": avg_pos_return,
        "PosNegRetRatio": avg_pos_neg_ratio,
        "MedReturns": med_returns,
        "MedNegReturns": med_neg_return,
        "MedPosReturns": med_pos_return,
        "MedPosNegRetRatio": med_pos_neg_ratio,
        "TheDfactor": med_pos_neg_ratio / avg_drawdown
    }
    return result


def backtest_dataframe(df: pd.DataFrame, look_back: int = 9, multiplier: int = 2) -> dict:
    st, _, _ = spt.supertrend_analysis(df.high, df.low, df.close, look_back=look_back, multiplier=multiplier)
    _, _, st_signal = spt.get_supertrend_signals(df.close, st)

    positions = get_base_positions(st_signal, df.close)
    drawdown = get_drawdown(positions, high=df.high, low=df.low)
    profits = profits_calculator(positions)

    return profits_analysis(profits, drawdown)


def get_backtest_ranking(new_value: float, filename: str, sort_by_column: str = "TheDfactor") -> str:
    if not filename.endswith(".csv"):
        filename += ".csv"

    df = pd.read_csv(filename)

    ranking_column = np.append(df[sort_by_column].values, new_value)
    reverse_sorted = np.sort(ranking_column)[::-1]
    rank = np.where(reverse_sorted == new_value)[0][0]
    return f"{rank}/{len(ranking_column)}"


def get_all_rankings(filename: str, sort_by_column: str = "TheDfactor", till_rank: int = -1) -> str:
    if not filename.endswith(".csv"):
        filename += ".csv"

    df = pd.read_csv(filename)

    df = df.sort_values(sort_by_column, ascending=False)
    names = df["Name"].values
    rankings = df[sort_by_column].values

    text = ""
    for idx, (name, ranking) in enumerate(zip(names, rankings)):
        if idx < till_rank or till_rank == -1:
            text += f"{idx + 1}. {name} {ranking}\n"

    return text
