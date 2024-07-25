# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3-slim

# Install pip requirements
COPY ./translate-mod-summary/requirements.txt translate-mod-summary-requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip pip install -r translate-mod-summary-requirements.txt

WORKDIR /translate-mod-summary
COPY ./translate-mod-summary/main.py .
COPY ./translate-mod-summary/utils ./utils

ENTRYPOINT ["python", "main.py"]