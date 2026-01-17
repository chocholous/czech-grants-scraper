FROM apify/actor-python:3.11

COPY . /usr/src/app

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "-m", "src.main"]
