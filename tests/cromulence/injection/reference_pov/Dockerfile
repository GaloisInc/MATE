FROM localhost:5000/cs_base:2019_05_10

RUN mkdir /bryant-pov
COPY . /bryant-pov
WORKDIR /bryant-pov

ENV PORT 3002
ENV HOST challenge_container

CMD ["ruby", "bryant-pov.rb"]

