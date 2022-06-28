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

@bot.listen(hikari.MessageCreateEvent)
async def on_message_create(event: hikari.MessageCreateEvent):
	logging.info(f"New message {event.channel_id}/{event.message_id} by {event.author_id}.")
#	logging.debug(f"event:{event} {dir(event)}")

	# If messages is a reply set reff to the id of the message its replying to | else set it to None
	ref = event.message.referenced_message
	if ref:
		reff = ref.id
	else:
		reff = None
	data = {
		"user_id": event.author_id,
		"username": event.author.username,
		"user_discriminator": event.author.discriminator,
		"channel_id": event.channel_id,
		"guild_id": event.message.guild_id,
		"timestamp": event.message.timestamp,
		"text": event.message.content[:30],  # limit size of text sent 
		"text_len": len(event.message.content),
		"attachments": [i.url for i in event.message.attachments], 
		"in_reply_to": reff
	}

	# add the event to the flush queue
	# we use event.__class__.__name__ to get the name of the event
	mp_client.track(event.author_id, event.__class__.__name__, data)


@bot.listen(hikari.ReactionAddEvent)
async def on_reaction_add(event: hikari.ReactionAddEvent):
	logging.info(f"New reaction to {event.channel_id}/{event.message_id} by {event.user_id}: {event.emoji_name}.")
	
	# Getting the guild id of the channel
	cha = await bot.rest.fetch_channel(event.channel_id)
	try:
		# Try getting it
		gid = cha.guild_id
	except:
		# Else set it to None
		gid = None
	
	# if emoji is a custom emoji set its name to emoji_id:emoji_name | else set it to the unicode emoji
	if event.emoji_id:
		emoji_name = f"{event.emoji_id}:{event.emoji_name}"
	else:
		emoji_name = event.emoji_name

	# Fetching the user so we can get their username and the discriminator
	user = await bot.rest.fetch_user(event.user_id)
	data = {
		"user_id": event.user_id,
		"username": user.username,
		"user_discriminator": user.discriminator,
		"channel_id": event.channel_id,
		"guild_id": gid,
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
