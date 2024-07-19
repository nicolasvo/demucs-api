FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt bot.py .env /app/
RUN pip install -r requirements.txt

ENTRYPOINT [ "python" ]
CMD [ "bot.py" ]
