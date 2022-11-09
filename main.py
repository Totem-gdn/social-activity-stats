import logging
import threading

logger = logging.getLogger(__name__)

from discord_activity.main import discord_main
from twitter_activity.main import twitter_main

if __name__ == "__main__":
    logger.info('--- Social activity starting ---')
    threading.Thread(target=twitter_main).start()
    discord_main()
    logger.info('--- Social activity done ---')