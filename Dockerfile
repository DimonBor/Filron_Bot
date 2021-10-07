FROM python:3.8-slim-buster

WORKDIR /app

ENV MULTIDICT_NO_EXTENSIONS=1
ENV YARL_NO_EXTENSIONS=1

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

COPY . .

CMD [ "python3", "main.py"]
