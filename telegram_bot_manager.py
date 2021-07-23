import json
import logging
import sys

from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

import backtesting as bt
import config
from config import API_KEY, API_SECRET
from ftx_client import FtxClient

STATE = None
CONFIRM_ORDER = 1
EXECUTE_ORDER = 2


class TelegramBotManager(FtxClient):
    def __init__(self):
        super(TelegramBotManager, self).__init__(api_key=API_KEY, api_secret=API_SECRET)
        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                            stream=sys.stdout, level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        # create the updater, that will automatically create also a dispatcher and a queue to
        # make them dialogue
        self._chat_id = config.TELEGRAM_CHAT_ID
        self._updater = Updater(token=config.TELEGRAM_TOKEN, use_context=True)
        self.dispatcher = self._updater.dispatcher

        # add handlers for start and help commands
        self.dispatcher.add_handler(CommandHandler("start", self.start))
        self.dispatcher.add_handler(CommandHandler("help", self.help))
        self.dispatcher.add_handler(CommandHandler("backtest", self.backtest))
        self.dispatcher.add_handler(CommandHandler("makeorder", self.make_order))
        self.dispatcher.add_handler(CommandHandler("takeprofit", self.modify_take_profit))
        self.dispatcher.add_handler(CommandHandler("stoploss", self.modify_stop_loss))
        self.dispatcher.add_handler(CommandHandler("account", self.modify_account_percent))
        self.dispatcher.add_handler(CommandHandler("stop", self.exit))

        # add an handler for normal text (not commands)
        self.dispatcher.add_handler(MessageHandler(Filters.text, self.text))

        # add an handler for errors
        self.dispatcher.add_error_handler(self.error)

        self.send_msg("@supertrending_bot has started")

        # set up variables
        self.trades = []
        self.order_to_place = {}
        self.sl_order = {}
        self.tp_order = {}

        # Set up initial values
        self.trades_4h_json = "trades_4h.json"
        self.tp_percent = 7.5
        self.sl_percent = 5
        self.account_percent = 25

    def send_msg(self, msg: str):
        try:
            self._updater.bot.send_message(
                self._chat_id,
                text=msg,
                disable_notification=False
            )
        except Exception as e:
            print(f'Error sending telegram message: {e}')
            try:
                self._updater.bot.send_message(
                    self._chat_id,
                    text=f'Error sending message: {e}',
                    disable_notification=False
                )
            except Exception as fe:
                print(f'Failed to send error message: {fe}')

    @staticmethod
    def _array_formatter(arr: list) -> str:
        arr_string = ""
        for idx, a in enumerate(arr):
            if idx == 0:
                arr_string += f"{a}"
            elif idx == len(arr) - 1:
                arr_string += f" or {a}"
            else:
                arr_string += f", {a}"
        return arr_string

    # function to handle the /start command
    @staticmethod
    def start(update: Update, _: CallbackContext):
        update.message.reply_text('Start command received')

    # function to handle the /help command
    def help(self, update: Update, _: CallbackContext):
        msg = "The following commands are available:\n" \
              "/backtest: Backtest a market\n" \
              "/makeorder: Open a new trade*\n" \
              "/takeprofit: Current take profit percentage*\n" \
              "/stoploss: Current stop loss percentage*\n" \
              "/account: Current percent of account used*\n" \
              "/help: This help page\n" \
              "*Pass arguments: command <argument>"
        self.send_msg(msg)

    def backtest(self, update: Update, context: CallbackContext):
        if context.args:
            try:
                market = context.args[0].upper()
                update.message.reply_text(f"Backtesting {market}...")

                df = FtxClient.get_historical_market_data(self, market, interval="4h", start_time="100 days ago")
                result = bt.backtest_dataframe(df)

                for k, v in result.items():
                    result[k] = str(round(v, 2))
                    if "ratio" not in k.lower():
                        result[k] += "%"

                update.message.reply_text("<b>Backtesting result</b>\n" + self.tabulate_dict(result),
                                          parse_mode=ParseMode.HTML)
            except Exception as exc:
                update.message.reply_text(f"Error: {exc}")
        else:
            update.message.reply_text(f"Enter a market to backtest")

    def modify_take_profit(self, update: Update, context: CallbackContext):
        if context.args:
            try:
                self.tp_percent = float(context.args[0])
            except Exception as exc:
                self.logger.warning(exc)
                update.message.reply_text(f"Unable to change take profit. Error: {exc}")
            else:
                update.message.reply_text(f"Take profit changed to {self.tp_percent}%")
        else:
            update.message.reply_text(f"Take profit is {self.tp_percent}%")

    def modify_stop_loss(self, update: Update, context: CallbackContext):
        if context.args:
            try:
                self.sl_percent = float(context.args[0])
            except Exception as exc:
                self.logger.warning(exc)
                update.message.reply_text(f"Unable to change stop loss. Error: {exc}")
            else:
                update.message.reply_text(f"Stop loss changed to {self.sl_percent}%")
        else:
            update.message.reply_text(f"Stop loss is {self.sl_percent}%")

    def modify_account_percent(self, update: Update, context: CallbackContext):
        if context.args:
            try:
                self.account_percent = float(context.args[0])
            except Exception as exc:
                self.logger.warning(exc)
                update.message.reply_text(f"Unable to change account percent. Error {exc}")
            else:
                update.message.reply_text(f"Account percentage changed to {self.account_percent}%")
        else:
            update.message.reply_text(f"Account percentage used is {self.account_percent}%")

    @staticmethod
    def tabulate_dict(dictionary: dict) -> str:
        max_len = max([len(str(k)) for k in dictionary.keys()])
        padding = 1
        table = ""
        for k, v in dictionary.items():
            table += '{k:{v_len:d}s} {v:3s}\n'.format(v_len=max_len + padding, v=str(v), k=k)
        return table

    # function to handle errors occurred in the dispatcher
    @staticmethod
    def error(update: Update, context: CallbackContext):
        update.message.reply_text(f'Error: {context.error}')

    def make_order(self, update: Update, context: CallbackContext):
        global STATE
        super(TelegramBotManager, self).__init__(api_key=API_KEY, api_secret=API_SECRET)

        try:
            trades_4h = json.load(open(self.trades_4h_json))
        except Exception as exc:
            update.message.reply_text(f'Unable to load {self.trades_4h_json}. Error: {exc}')
            self.logger.warning(exc)
        else:
            self.logger.info(f'Successfully loaded {self.trades_4h_json}')
            trade_idx = -1
            if context.args:
                for idx, trade in enumerate(trades_4h):
                    if context.args[0].lower() in trade["market"].lower():
                        trade_idx = idx

            self.order_to_place, self.sl_order, self.tp_order = \
                FtxClient.generate_order(self, trades_4h[trade_idx], take_profit_percent=self.tp_percent,
                                         stop_loss_percent=self.sl_percent, account_percent=self.account_percent)

            text = (
                    f"<b>Order ({self.account_percent}%)</b>\n" + self.tabulate_dict(self.order_to_place) + "\n" +
                    f"<b>Stop loss ({self.sl_percent}%)</b>\n" + self.tabulate_dict(self.sl_order) + "\n" +
                    f"<b>Take profit ({self.tp_percent}%)</b>\n" + self.tabulate_dict(self.tp_order)
            )

            update.message.reply_text(text, parse_mode=ParseMode.HTML)

            update.message.reply_text(f'Do you want to execute this trade?')
            STATE = CONFIRM_ORDER

    def confirm_order(self, update: Update, context: CallbackContext):
        global STATE

        response = str(update.message.text)
        if response.lower() == "yes" or response.lower() == "yep" or response == "👍":
            self.execute_order(update, context)
        elif response.lower() == "no" or response.lower() == "nope" or response == "👎":
            update.message.reply_text(f'Okay, not executing')
            STATE = None

    def execute_order(self, update: Update, _: CallbackContext):
        global STATE
        update.message.reply_text(f'Placing orders...')

        FtxClient.place_order(
            self,
            market=self.order_to_place["market"],
            side=self.order_to_place["side"],
            price=self.order_to_place["price"],
            size=self.order_to_place["size"],
            type=self.order_to_place["type"],
        )

        FtxClient.place_conditional_order(
            self,
            market=self.sl_order["market"],
            side=self.sl_order["side"],
            size=self.sl_order["size"],
            type=self.sl_order["type"],
            reduce_only=self.sl_order["reduce_only"],
            trigger_price=self.sl_order["trigger_price"],
            limit_price=self.sl_order["limit_price"]
        )

        FtxClient.place_conditional_order(
            self,
            market=self.tp_order["market"],
            side=self.tp_order["side"],
            size=self.tp_order["size"],
            type=self.tp_order["type"],
            reduce_only=self.tp_order["reduce_only"],
            trigger_price=self.tp_order["trigger_price"],
            limit_price=self.tp_order["limit_price"]
        )

        update.message.reply_text(f'Orders placed successfully!')
        STATE = None

    # function to handle normal text
    def text(self, update: Update, context: CallbackContext):
        global STATE

        if STATE == CONFIRM_ORDER:
            return self.confirm_order(update, context)
        if STATE == EXECUTE_ORDER:
            return self.execute_order(update, context)

    def start_polling(self):
        # start your shiny new bot
        self._updater.start_polling()

        # run the bot until Ctrl-C
        self._updater.idle()

    def exit(self, update: Update, context: CallbackContext):
        try:
            text = f'Shutting down bot'
            self.logger.info(text)
            update.message.reply_text(text)
            self._updater.stop()
        except Exception as exc:
            text = "Failed to shut down bot"
            update.message.reply_text(text + f"{exc}")
            self.logger.warning(text + f"{exc}")
        else:
            text = "Bot stopped successfully"
            update.message.reply_text(text)
            self.logger.info(text)


if __name__ == '__main__':
    tbm = TelegramBotManager()
    tbm.start_polling()
