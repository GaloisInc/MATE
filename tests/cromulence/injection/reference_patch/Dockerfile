FROM localhost:5000/cs_base:2019_05_10

ADD ./ /home/challenge
ADD base_data /data
RUN chown -R chess:chess /home
RUN chown -R chess:chess /data
RUN mkdir /service
RUN chown -R chess:chess /service
RUN echo -n OBCOPNn2SYygIpNDA0pFkPrY6Fds6WBS > /token
RUN chown chess:chess /token

USER chess
WORKDIR /home/challenge
RUN make clean
RUN make
RUN cp -r build /service
WORKDIR /

ENV PORT 3002

CMD /service/build/bryant.bin
