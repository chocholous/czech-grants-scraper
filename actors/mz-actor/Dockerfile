FROM apify/actor-python:3.13

WORKDIR /usr/src/app

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy actor code and shared scrapers
COPY . ./

# Run the actor
CMD ["python", "-m", "src.main"]
