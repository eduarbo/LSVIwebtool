
FROM python:3.8
# Create app folder
RUN mkdir -p /var/app
WORKDIR /var/app

# Copy app files into app folder
COPY . /var/app
RUN pip install --trusted-host pypi.python.org -r requirements.txt
EXPOSE 8080
EXPOSE 8081
CMD ["gunicorn", "app:app", "-b", ":8080"]
CMD bokeh serve --port 8081 --allow-websocket-origin="*" script.py

