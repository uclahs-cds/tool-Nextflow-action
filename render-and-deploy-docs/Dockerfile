FROM python:3.8.1

RUN apt-get update && apt-get install -y git libssl-dev build-essential

RUN mkdir /src
WORKDIR /src

COPY ./ /src/

RUN pip install -r /src/requirements.txt

ENTRYPOINT ["/bin/bash", "/src/action.sh"]

LABEL maintainer="Chenghao Zhu, ChenghaoZhu@mednet.ucla.com"
