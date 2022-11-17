#FROM python:3.9
FROM ubuntu/nginx:latest

ARG TWITTER_ACCESS_TOKEN
ARG TWITTER_ACCESS_TOKEN_SECRET
ARG TWITTER_BEARER_TOKEN
ARG TWITTER_CONSUMER_KEY
ARG TWITTER_CONSUMER_SECRET
ARG TWITTER_MIXPANEL_TOKEN
ARG TWITTER_ACCOUNT_ID
ARG DISCORD_TOKEN
ARG DISCORD_MIXPANEL_TOKEN
ARG DISCORD_SERVER_ID

ENV TWITTER_ACCESS_TOKEN $TWITTER_ACCESS_TOKEN
ENV TWITTER_ACCESS_TOKEN_SECRET $TWITTER_ACCESS_TOKEN_SECRET
ENV TWITTER_BEARER_TOKEN $TWITTER_BEARER_TOKEN
ENV TWITTER_CONSUMER_KEY $TWITTER_CONSUMER_KEY
ENV TWITTER_CONSUMER_SECRET $TWITTER_CONSUMER_SECRET
ENV TWITTER_MIXPANEL_TOKEN $TWITTER_MIXPANEL_TOKEN
ENV TWITTER_ACCOUNT_ID $TWITTER_ACCOUNT_ID
ENV DISCORD_TOKEN $DISCORD_TOKEN
ENV DISCORD_MIXPANEL_TOKEN $DISCORD_MIXPANEL_TOKEN
ENV DISCORD_SERVER_ID $DISCORD_SERVER_ID

#WORKDIR /usr/src/app

#OPY requirements.txt ./

#RUN pip install --upgrade pip
#RUN pip install --no-cache-dir -r requirements.txt

#COPY . .
EXPOSE 80
#CMD [ "python", "./main.py" ]