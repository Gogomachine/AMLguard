FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy app
COPY . .

EXPOSE 8000

CMD ["python", "-m", "bot.main", "webhook"]
