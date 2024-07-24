# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3-slim

# Install pip requirements
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

COPY main.py .
COPY ./utils ./utils

ENTRYPOINT ["python", "main.py"]