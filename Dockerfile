FROM python:3.10-buster as builder

ENV MULTIDICT_NO_EXTENSIONS=1
ENV YARL_NO_EXTENSIONS=1

RUN apt-get update
RUN apt-get install -y --no-install-recommends build-essential gcc

COPY requirements.txt requirements.txt

RUN pip3 install --user -r requirements.txt

FROM python:3.10-slim-buster AS build-image

COPY --from=builder /root/.local /root/.local

RUN apt update
RUN apt install ffmpeg -y --no-install-recommends

ENV PYTHONUNBUFFERED=1

COPY . ./app/

CMD [ "python3", "-m", "app"]
