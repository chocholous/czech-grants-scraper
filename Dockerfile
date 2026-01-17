# Use Apify Python base image with Playwright (Python 3.12 for crawlee compatibility)
FROM apify/actor-python-playwright:3.12

# Set working directory (already set in base image, but being explicit)
WORKDIR /usr/src/app

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Install Playwright browsers
RUN playwright install chromium

# Set the main entry point
CMD ["python", "-m", "src.main"]
