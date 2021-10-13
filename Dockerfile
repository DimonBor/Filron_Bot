FROM python:3.8-buster

WORKDIR /app

ENV MULTIDICT_NO_EXTENSIONS=1
ENV YARL_NO_EXTENSIONS=1

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

RUN apt update 
RUN apt install ffmpeg --no-install-recommends

COPY . .

CMD [ "python3", "main.py"]
