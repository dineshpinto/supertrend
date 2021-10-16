import logging
import os
import sys

import telegram

import config


class TelegramAPIManager:
    def __init__(self, group=False):
        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                            stream=sys.stdout, level=logging.INFO)
        self.logger = logging.getLogger(__name__)

        self.bot = telegram.Bot(token=config.TELEGRAM_TOKEN)

        if group:
            self.chat_id = config.TELEGRAM_GROUP_CHAT_ID
        else:
            self.chat_id = config.TELEGRAM_CHAT_ID

        bot_name, bot_username = self.bot.get_me()["first_name"], self.bot.get_me()["username"]
        startup_text = f'{bot_name} (@{bot_username}) is now running using Telegram' \
                       f' {"group" if group else "personal"} chat id'
        self.logger.info(startup_text)

    def send_message(self, text: str, markdown: bool = False) -> telegram.Message:
        if markdown:
            return self.bot.send_message(self.chat_id, text, parse_mode=telegram.ParseMode.MARKDOWN_V2)
        else:
            return self.bot.send_message(self.chat_id, text)

    def send_photo(self, image_path: str, caption: str = None, markdown: bool = False) -> telegram.Message:
        if markdown:
            return self.bot.send_photo(self.chat_id, photo=open(image_path, "rb"), caption=caption,
                                       parse_mode=telegram.ParseMode.MARKDOWN_V2)
        else:
            return self.bot.send_photo(self.chat_id, photo=open(image_path, "rb"), caption=caption)

    def send_video(self, video_path: str, caption: str = None) -> telegram.Message:
        return self.bot.send_video(self.chat_id, video=open(video_path, "rb"), supports_streaming=True, caption=caption)

    def send_animation(self, animation_path: str, caption: str = None) -> telegram.Message:
        return self.bot.send_animation(self.chat_id, animation=open(animation_path, "rb"), caption=caption)

    def send_captioned_media(self, filepath: str) -> bool:
        """ The filepath consists of the full path, name of the file and the extension."""
        filename, ext = os.path.splitext(os.path.basename(filepath))

        if ext == ".jpg" or ext == ".png":
            self.send_photo(filepath, caption=filename)
        elif ext == ".gif":
            self.send_animation(filepath, caption=filename)
        elif ext == ".mp4":
            self.send_video(filepath, caption=filename)
        else:
            self.logger.warning(f"Unrecognized extension '{ext}' in '{filepath}'")
            return False
        self.logger.info(f"Sent {filepath} to Telegram chat")
        return True
