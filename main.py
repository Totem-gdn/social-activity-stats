#/usr/bin/python
import json, time, logging
import hikari
from mixpanel import Mixpanel
from mixpanel_async import AsyncBufferedConsumer

# Loading the config
try:
        with open("config.json", 'r') as f:
            config: dict = json.load(f)
except FileNotFoundError:
        logging.error("The config.json file is missing.")
        raise SystemExit
except json.decoder.JSONDecodeError as je:
        logging.error(f"Bad config.json file. Content is not a valid json:\n{je}")
        raise SystemExit

# Creating an AsyncBufferedConsumer instance
mp_consumer = AsyncBufferedConsumer(max_size=25)
# Creating a Mixpanel instance and registering the AsyncBufferedConsumer as the consumer
mp_client = Mixpanel(config['mixpanel_token'], consumer=mp_consumer)

# Creating a GatewayBot instance so we can listen to events from the gateway
bot = hikari.GatewayBot(
	token=config["discord_token"],
        force_color=True
)

@bot.listen(hikari.GuildMessageCreateEvent)
async def on_message_create(event: hikari.GuildMessageCreateEvent):
	logging.info(f"New message {event.channel_id}/{event.message_id} by {event.author_id}.")
	#logging.debug(f"event:{event} {dir(event)}")

	cha = bot.cache.get_guild_channel(event.channel_id)
	if cha is None:
		logging.info(f"{event.channel_id} not cached, fetching")
		cha = await bot.rest.fetch_channel(event.channel_id)
		await bot._cache.set_guild_channel(cha)

	# If messages is a reply set reff to the id of the message its replying to | else set it to None
	ref = event.message.referenced_message
	if ref:
		reff = ref.id
	else:
		reff = None

	data = {
		"user_id": event.member.id,
		"username": event.member.username,
		"user_discriminator": event.member.discriminator,
		"user_displayname": event.member.display_name,
		"channel_id": event.channel_id,
		"channel_name":cha.name,
		"guild_id": event.message.guild_id,
		"timestamp": event.message.timestamp,
		"text": event.message.content[:30] if isinstance(event.message.content, str) else "",
		"text_len": len(event.message.content) if isinstance(event.message.content, str) else 0,
		"attachments": [i.url for i in event.message.attachments],
		"in_reply_to": reff
	}
	# add the event to the flush queue
	# we use event.__class__.__name__ to get the name of the event
	mp_client.track(event.author_id, event.__class__.__name__, data)


@bot.listen(hikari.GuildReactionAddEvent)
async def on_reaction_add(event: hikari.GuildReactionAddEvent):
	logging.info(f"New reaction to {event.channel_id}/{event.message_id} by {event.user_id}: {event.emoji_name}.")
	
	# Getting the guild id of the channel
	cha = bot.cache.get_guild_channel(event.channel_id)
	if cha is None:
		logging.info(f"{event.channel_id} not cached, fetching")
		cha = await bot.rest.fetch_channel(event.channel_id)
		await bot._cache.set_guild_channel(cha)	

	# if emoji is a custom emoji set its name to emoji_id:emoji_name | else set it to the unicode emoji
	if event.emoji_id:
		emoji_name = f"{event.emoji_id}:{event.emoji_name}"
	else:
		emoji_name = event.emoji_name

	data = {
		"user_id": event.user_id,
		"username": event.member.username,
		"user_discriminator": event.member.discriminator,
		"user_displayname": event.member.display_name,
		"channel_id": event.channel_id,
		"channel_name": cha.name,
		"guild_id": event.guild_id,
		"timestamp": int(time.time()),
		"to_message_id": event.message_id,
		"emoji_name": emoji_name,
		"emoji_id": event.emoji_id
	}
	# add the event to the flush queue
	# we use event.__class__.__name__ to get the name of the event
	mp_client.track(event.user_id, event.__class__.__name__, data)


if __name__ == "__main__":
	logging.info('--- bot starting ---')

	bot.run()
	
	logging.info("Flushing events...")

	# Flush the AsyncBufferedConsumer after on exit
	mp_consumer.flush()
	logging.info('--- bot done ---')
