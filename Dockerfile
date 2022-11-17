FROM python:3.10

ARG TWITTER_ACCESS_TOKEN \
    TWITTER_ACCESS_TOKEN_SECRET \
    TWITTER_BEARER_TOKEN \
    TWITTER_CONSUMER_KEY \
    TWITTER_CONSUMER_SECRET \
    TWITTER_MIXPANEL_TOKEN \
    TWITTER_ACCOUNT_ID \
    DISCORD_TOKEN \
    DISCORD_MIXPANEL_TOKEN \
    DISCORD_SERVER_ID

ENV TWITTER_ACCESS_TOKEN $TWITTER_ACCESS_TOKEN \
    TWITTER_ACCESS_TOKEN_SECRET $TWITTER_ACCESS_TOKEN_SECRET \
    TWITTER_BEARER_TOKEN $TWITTER_BEARER_TOKEN \
    TWITTER_CONSUMER_KEY $TWITTER_CONSUMER_KEY \
    TWITTER_CONSUMER_SECRET $TWITTER_CONSUMER_SECRET \
    TWITTER_MIXPANEL_TOKEN $TWITTER_MIXPANEL_TOKEN \
    TWITTER_ACCOUNT_ID $TWITTER_ACCOUNT_ID \
    DISCORD_TOKEN $DISCORD_TOKEN \
    DISCORD_MIXPANEL_TOKEN $DISCORD_MIXPANEL_TOKEN \
    DISCORD_SERVER_ID $DISCORD_SERVER_ID

WORKDIR /usr/src/app

COPY requirements.txt ./

RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

#CMD [ "python", "./main.py" ]
CMD [ "/bin/bash" ]