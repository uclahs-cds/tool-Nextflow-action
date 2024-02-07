FROM python:3.12.1

COPY action.sh create_mkdocs_config.py requirements.txt /src/

RUN python -m pip install --no-cache-dir -r /src/requirements.txt && \
    chmod +x /src/action.sh

ENTRYPOINT ["/src/action.sh"]

LABEL maintainer="Chenghao Zhu, ChenghaoZhu@mednet.ucla.com"
