# /usr/bin/python
import json, time, logging
import os

import hikari

from mixpanel import Mixpanel
from mixpanel_async import AsyncBufferedConsumer

import requests
import threading

logger = logging.getLogger(__name__)

# get logging level from config file - default to INFO
logger.setLevel(logging.getLevelName("INFO"))

# Creating an AsyncBufferedConsumer instance
mp_consumer = AsyncBufferedConsumer(max_size=25)
# Creating a Mixpanel instance and registering the AsyncBufferedConsumer as the consumer
mp_client = Mixpanel(os.environ['DISCORD_MIXPANEL_TOKEN'], consumer=mp_consumer)

# Creating a GatewayBot instance so we can listen to events from the gateway
bot = hikari.GatewayBot(
    token=os.environ["DISCORD_TOKEN"],
    force_color=True
)


def get_event_properties(event):
    return {
        "user_id": event.member.id,
        "username": event.member.username,
        "is_bot": event.member.is_bot,
        "user_discriminator": event.member.discriminator,
        "user_displayname": event.member.display_name,
        "channel_id": event.channel_id,
        #		"timestamp": event.message.timestamp,
    }


def send_to_mixpanel(event, properties):
    dbg = ''  # use '-dbueg' when runing locally
    mp_client.track(event.member.username, event.__class__.__name__ + dbg, properties)


@bot.listen(hikari.GuildMessageCreateEvent)
async def on_message_create(event: hikari.GuildMessageCreateEvent):
    logger.debug(f"New message {event.channel_id}/{event.message_id} by {event.author_id}.")
    logger.debug(f"event: {event}")

    properties = get_event_properties(event)

    cha = bot.cache.get_guild_channel(event.channel_id)
    if cha is None:
        logger.debug(f"{event.channel_id} not cached, fetching")
        cha = await bot.rest.fetch_channel(event.channel_id)
        await bot._cache.set_guild_channel(cha)
    properties["channel_name"] = cha.name

    # ensure msg_text is a string
    msg_text = event.message.content if isinstance(event.message.content, str) else ""
    properties["text"] = msg_text[:30]
    properties["text_len"] = len(msg_text)

    if event.message.attachments:
        properties["attachments"] = [i.url for i in event.message.attachments]

    # If messages is a reply add ref to properties
    ref = event.message.referenced_message
    if ref:
        properties["in_reply_to"] = ref.id

    logger.info(f"New msg @{event.member.display_name} in #{cha.name}: {msg_text[:30]} .")
    send_to_mixpanel(event, properties)


@bot.listen(hikari.GuildReactionAddEvent)
async def on_reaction_add(event: hikari.GuildReactionAddEvent):
    logger.debug(f"New reaction to {event.channel_id}/{event.message_id} by {event.user_id}: {event.emoji_name}.")
    logger.debug(f"event: {event}")

    # Getting the guild id of the channel
    cha = bot.cache.get_guild_channel(event.channel_id)
    if cha is None:
        logger.debug(f"{event.channel_id} not cached, fetching")
        cha = await bot.rest.fetch_channel(event.channel_id)
        await bot._cache.set_guild_channel(cha)

    properties = get_event_properties(event)

    # if emoji is a custom emoji set its name to emoji_id:emoji_name | else set it to the unicode emoji
    if event.emoji_id:
        emoji_name = f"{event.emoji_name}(Custom)"
    else:
        emoji_name = event.emoji_name

    properties["channel_name"] = cha.name
    properties["to_message_id"] = event.message_id
    properties["emoji_name"] = emoji_name
    properties["emoji_id"] = event.emoji_id

    logger.info(f"New reaction: @{event.member.display_name} in #{cha.name}: {emoji_name}")
    send_to_mixpanel(event, properties)


def member_count():
    while True:
        # get data of server members
        url = f"https://discordapp.com/api/guilds/{os.environ['DISCORD_SERVER_ID']}/members"
        headers = {
            "Authorization": 'Bot ' + os.environ["DISCORD_TOKEN"]
        }
        params = {
            "limit": 1000
        }
        response = requests.get(url=url, headers=headers, params=params)

        # divides into users and bots
        try:
            users = []
            bots = []
            for user_data in response.json():
                try:
                    if user_data['user']['bot'] is True:
                        bots.append(user_data)
                    else:
                        users.append(user_data)
                except KeyError:
                    users.append(user_data)
        except TypeError:
            logging.error(response.text)
            raise SystemExit

        # send counters to mixpanel
        properties = {
            "usersCount": len(users),
            "botsCount": len(bots)
        }

        mp_client.track("The mixpanel Bot", "MembersCount", properties)
        logger.info(f'usersCount: {len(users)} and botsCount: {len(bots)}  sent to mixpanel.')
        time.sleep(3600)


def discord_main():
    # start the second thread for the infinite operation of the function
    threading.Thread(target=member_count).start()

    logger.info('--- bot starting ---')
    bot.run()

    logger.info("Flushing events...")
    # Flush the AsyncBufferedConsumer after on exit
    mp_consumer.flush()

    logging.info('--- bot done ---')
