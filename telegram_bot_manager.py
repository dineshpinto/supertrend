import json
import config
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from telegram import Update

STATE = None
CHECK_TRADE = 1
CONFIRM_TRADE = 2
EXECUTE_TRADE = 3


class TelegramBotManager:
    def __init__(self):
        # create the updater, that will automatically create also a dispatcher and a queue to
        # make them dialogue
        self._chat_id = config.TELEGRAM_CHAT_ID
        self._updater = Updater(token=config.TELEGRAM_TOKEN, use_context=True)
        self.dispatcher = self._updater.dispatcher

        # add handlers for start and help commands
        self.dispatcher.add_handler(CommandHandler("start", self.start))
        self.dispatcher.add_handler(CommandHandler("help", self.help))
        self.dispatcher.add_handler(CommandHandler("trade", self.trade))

        # add an handler for normal text (not commands)
        self.dispatcher.add_handler(MessageHandler(Filters.text, self.text))

        # add an handler for errors
        self.dispatcher.add_error_handler(self.error)

        # set up variables
        self.trades = []
        self.market = None
        self.send_msg("@supertrending_bot has started")

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
        msg = "The following commands are avaiable:\n" \
              "/trade: Open a new trade\n" \
              "/open_positions: Check open positions\n" \
              "/help: This help page"
        self.send_msg(msg)

    # function to handle errors occurred in the dispatcher
    @staticmethod
    def error(update: Update, _: CallbackContext):
        update.message.reply_text('An error occurred bruh')

    def trade(self, update: Update, context: CallbackContext):
        try:
            self.trades = json.load(open("trades.json"))
        except Exception as exc:
            update.message.reply_text('No new trades or was unable to load the json...')
        else:
            self.start_getting_trade_info(update, context)

    def start_getting_trade_info(self, update: Update, _: CallbackContext):
        global STATE
        STATE = CHECK_TRADE
        update.message.reply_text('Okay, so you want to make a trade. Which one?')

        if len(self.trades) <= 3:
            update.message.reply_text(self._array_formatter([trade["market"] for trade in self.trades]))
        else:
            update.message.reply_text(self._array_formatter([trade["market"] for trade in self.trades[-3:]]))

    def check_trade(self, update: Update, _: CallbackContext):
        global STATE
        self.market = str(update.message.text).upper()

        for trade in reversed(self.trades):
            if self.market in trade["market"]:
                update.message.reply_text(json.dumps(trade, indent=2, default=str))
                update.message.reply_text(f'Is this the correct trade?')
                STATE = CONFIRM_TRADE

    def confirm_trade(self, update: Update, context: CallbackContext):
        global STATE

        response = str(update.message.text)
        if response.lower() == "yes" or response.lower() == "yep" or response == "👍":
            self.execute_trade(update, context)
        elif response.lower() == "no" or response.lower() == "nope" or response == "👎":
            update.message.reply_text(f'Yo...wtf bitch')
            STATE = None

    def execute_trade(self, update: Update, _: CallbackContext):
        global STATE
        update.message.reply_text(f'Executing trade with {self.market}...')
        for trade in reversed(self.trades):
            if self.market in trade["market"] :
                update.message.reply_text("Trade executed: \n" + json.dumps(trade, indent=2, default=str))
        STATE = None

    # function to handle normal text
    def text(self, update: Update, context: CallbackContext):
        global STATE
        if STATE == CHECK_TRADE:
            return self.check_trade(update, context)
        if STATE == CONFIRM_TRADE:
            return self.confirm_trade(update, context)
        if STATE == EXECUTE_TRADE:
            return self.execute_trade(update, context)

    def start_polling(self):
        # start your shiny new bot
        self._updater.start_polling()

        # run the bot until Ctrl-C
        self._updater.idle()

    def exit(self):
        try:
            print("\nStopping telegram bot...")
            self._updater.stop()
            print("\nTelegram was stopped succesfully")
        except:
            print("\nFailed to shutdown telegram bot. Please make sure it is correctly terminated")


if __name__ == '__main__':
    tbm = TelegramBotManager()
    tbm.start_polling()
