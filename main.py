import logging
import threading

from github_activity.geo import githubGeo_main
from github_activity.main import github_main
from discord_activity.main import discord_main
from twitter_activity.main import twitter_main
from .poll_bot.paul_bot.main import _main

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info('--- Social activity starting ---')
    threading.Thread(target=twitter_main).start()
    threading.Thread(target=github_main).start()
    threading.Thread(target=githubGeo_main).start()
    threading.Thread(target=_main()).start()
    discord_main()
    logger.info('--- Social activity done ---')