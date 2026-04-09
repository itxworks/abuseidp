# Use an official Python runtime as a parent image
FROM python:3.14-slim

# Set the working directory in the container
WORKDIR /app

RUN mkdir /app/config /app/logs

# Copy the current directory contents into the container at /app
COPY requirements.txt abuseidp_file_downloader.py abussidp_bl_server.py /app/
COPY config.ini /app/config/

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt


# Expose the port the app runs on
EXPOSE 8000

# Run the scripts and keep the container running interactively
CMD ["python", "/app/abussidp_bl_server.py"]