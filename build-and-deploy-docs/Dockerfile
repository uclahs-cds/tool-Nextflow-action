FROM python:3.8.1

RUN apt-get update && \
    apt-get install --no-install-recommends -y git libssl-dev build-essential && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /src

COPY ./ /src/

RUN pip install -r /src/requirements.txt && \
    chmod +x /src/action.sh

ENTRYPOINT ["/src/action.sh"]

LABEL maintainer="Chenghao Zhu, ChenghaoZhu@mednet.ucla.com"
