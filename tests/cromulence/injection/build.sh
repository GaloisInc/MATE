#!/bin/bash

BIN_NAME=build

pushd challenge_src/
cat > Dockerfile.build << EOF
FROM localhost:5000/cs_base:2019_05_10

ADD ./ /home/challenge
RUN chown -R chess:chess /home

USER chess
WORKDIR /home/challenge
RUN make clean
RUN make
CMD sleep 10
EOF

docker build --network=host -f Dockerfile.build -t build_ex:v0 .
docker run -d --net=host --name=build_ex -it build_ex:v0
docker cp build_ex:/home/challenge/$BIN_NAME ../challenge_bin
sleep 10
docker rm -f build_ex
docker rmi -f build_ex:v0
rm Dockerfile.build
popd


