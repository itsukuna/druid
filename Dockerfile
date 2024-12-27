FROM python:3.12-slim

# Set the working directory
WORKDIR /app

# Copy the Pipfile and Pipfile.lock
COPY Pipfile Pipfile.lock /app/

# Install pipenv and dependencies
RUN pip install pipenv && pipenv install --deploy --ignore-pipfile

# Copy the rest of the application code
COPY . /app

# Set environment variables
ENV DISCORD_TOKEN=${discord_token}
ENV MONGO_DB=${mongodb_uri}

# Run the bot
CMD ["pipenv", "run", "python", "main.py"]