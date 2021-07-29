import json
import logging
import os
import sys
import time

import matplotlib.pyplot as plt
import pandas as pd
from tqdm import tqdm

import supertrend as spt
from config import API_KEY, API_SECRET
from ftx_client import FtxClient
from telegram_api_manager import TelegramAPIManager

plt.ioff()

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    stream=sys.stdout, level=logging.INFO)
logger = logging.getLogger(__name__)

with open("settings.json") as jsonfile:
    settings = json.load(jsonfile)

testing = False
BACKTEST_FOLDER = settings["filepaths"]["backtest_folder"]
OPTIMIZEDML_FILEPATH = os.path.join(BACKTEST_FOLDER, settings["filepaths"]["optimized_ml_file"])
ANALYSIS_FILEPATH = os.path.join(BACKTEST_FOLDER, settings["filepaths"]["analysis_file"])
FIGURE_PATH = os.path.join(settings["filepaths"]["figure_folder"], settings["filepaths"]["figure_subfolder"])

tapi = TelegramAPIManager(group=False)
trades = []

while True:
    try:
        # Open new FTX Session
        ftx = FtxClient(api_key=API_KEY, api_secret=API_SECRET)
        optimzed_ml = pd.read_csv(OPTIMIZEDML_FILEPATH)
        market_analysis = pd.read_csv(ANALYSIS_FILEPATH)

        # Get list of all markets according to criteria
        markets = []
        for future in ftx.list_futures():
            if future["type"] == "perpetual":
                if (future["volumeUsd24h"] > settings["markets"]["min_volume_usd_24h"] and
                        future["name"] not in settings["markets"]["blacklist"]):
                    markets.append(future["name"])

        # Delete all old images in folder
        for filename in os.listdir(FIGURE_PATH):
            if not filename.endswith(".jpg"):
                continue
            os.remove(os.path.join(FIGURE_PATH, filename))

        pbar = tqdm(markets)
        for market in pbar:
            pbar.set_description(market)

            df = ftx.get_historical_market_data(market, interval=settings["analysis"]["interval"],
                                                start_time=settings["analysis"]["start_time"])

            if len(df) < settings["analysis"]["min_data_length"]:
                continue

            # Get optimized values for supertrend inputs
            try:
                multiplier = optimzed_ml.loc[optimzed_ml['Name'] == market]["Multiplier"].values[0]
                lookback = optimzed_ml.loc[optimzed_ml['Name'] == market]["Lookback"].values[0]
                thedfactor = market_analysis.loc[market_analysis["Name"] == market]["TheDfactor"].values[0]
            except IndexError:
                multiplier = 2
                lookback = 9
                thedfactor = 0
                text = f"{market} not in optimized dataframe, either data is insufficient or database needs to be " \
                       f"updated. Using default Multiplier={multiplier} and Lookback={lookback}..."
                logger.warning(text)

            # Perform supertrend analysis
            df["st"], df["upt"], df["dt"] = spt.supertrend_analysis(df.high, df.low, df.close, look_back=lookback,
                                                                    multiplier=multiplier)
            df["long_trig"], df["short_trig"], df["st_signal"] = spt.get_supertrend_signals(df.close, df.st)

            # Check 200 EMA for confirmation
            df["ema200"] = spt.calculate_ema(df.close, time_period=200)
            df["vol_ema200"] = spt.calculate_ema(df.volume, time_period=200)

            params = {"Multiplier": multiplier, "Lookback": lookback, "TheDfactor": thedfactor}
            figure_path = spt.plot_and_save_figure(market, df, params, folder_path=FIGURE_PATH)
            # Set precision for orders
            precision = len(str(df.close[0]).split(".")[1])

            # Take profit calculator and stop loss
            stop_loss = round(df.st[-1], precision)
            long_profit_10pct, short_profit_10pct = spt.take_profit_calc(df.close[-1], profit_percent=10,
                                                                         precision=precision)
            long_profit_5pct, short_profit_5pct = spt.take_profit_calc(df.close[-1], profit_percent=5,
                                                                       precision=precision)
            long_profit_75pct, short_profit_75pct = spt.take_profit_calc(df.close[-1], profit_percent=7.5,
                                                                         precision=precision)
            long_loss_5pct, short_loss_5pct = spt.stop_loss_calc(df.close[-1], loss_percent=5,
                                                                 precision=precision)
            # Check last element of signal array
            last_signal = df.st_signal[-1]

            if testing:
                last_signal = -1

            if last_signal != 0:
                # Set up dict for new position
                new_position = {
                    "market": market,
                    "interval": "4h",
                    "entry": df.close[-1],
                    "stop_loss": stop_loss,
                }

                if last_signal == 1:
                    # Long position
                    new_position["side"] = "buy"
                    new_position["10pctprofit"] = long_profit_10pct
                    new_position["5pctprofit"] = long_profit_5pct
                    new_position["75pctprofit"] = long_profit_75pct
                    new_position["5pctloss"] = long_loss_5pct
                elif last_signal == -1:
                    # Short position
                    new_position["side"] = "sell"
                    new_position["10pctprofit"] = short_profit_10pct
                    new_position["5pctprofit"] = short_profit_5pct
                    new_position["75pctprofit"] = short_profit_75pct
                    new_position["5pctloss"] = short_loss_5pct

                if df.close[-1] < df.ema200[-1]:
                    new_position["ema200"] = "under"
                else:
                    new_position["ema200"] = "over"

                # Use slowd for StochRSI
                _, slowd = spt.calculate_stoch_rsi(df)
                new_position["stoch_rsi"] = int(slowd[-1])

                logger.info(new_position)
                tapi.send_photo(figure_path, caption=json.dumps(new_position, indent=2, default=str))
                trades.append(new_position)

                with open(settings["filepaths"]["trades_file"], 'w') as json_file:
                    json.dump(trades, json_file)

                # Close position if needed
                open_position = ftx.check_open_position(market)
                if open_position:
                    if open_position["side"] != new_position["side"]:
                        success, response = ftx.market_close_and_cancel_orders(
                            market,
                            side=new_position["side"],
                            size=open_position["size"]
                        )

                        if success:
                            close_position_text = f"({market}) Position closed at {response['price']}"
                        else:
                            close_position_text = f"({market}) Position failed to close: Error: {response}"

                        tapi.send_photo(figure_path, caption=close_position_text)
                if testing:
                    break

    except Exception as exc:
        logger.error(f"{exc}")
        tapi.send_message(f"Exception: {exc}")

    logger.info("Sleeping for 4 hours")
    time.sleep(60 * 60 * 4)
