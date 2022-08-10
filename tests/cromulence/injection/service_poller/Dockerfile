FROM localhost:5000/cs_base:2019_05_10

RUN mkdir /bryant-poller
COPY . /bryant-poller
WORKDIR /bryant-poller

ENV PORT 3002
ENV HOST challenge_container

CMD ["ruby", "bryant-poller.rb"]

