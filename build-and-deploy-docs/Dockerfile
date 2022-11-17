FROM python:3.8.1

RUN apt-get update && \
    apt-get install --no-install-recommends -y git libssl-dev build-essential && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir /src

COPY ./ /src/

RUN pip install -r /src/requirements.txt

RUN chmod -R 777 /src

# Add a new user/group called bldocker
RUN groupadd -g 500001 bldocker && \
    useradd -r -u 500001 -g bldocker bldocker

# Change the default user to bldocker from root
USER bldocker

ENTRYPOINT ["/src/action.sh"]

LABEL maintainer="Chenghao Zhu, ChenghaoZhu@mednet.ucla.com"
