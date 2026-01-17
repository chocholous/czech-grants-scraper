# Use Apify's Python base image
FROM apify/actor-python:3.13

# Copy all files
COPY . ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install poppler-utils for pdftotext
USER root
RUN apt-get update && apt-get install -y poppler-utils && rm -rf /var/lib/apt/lists/*
USER myuser

# Run the actor
CMD ["python3", "-m", "src.main"]
