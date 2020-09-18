
FROM ubuntu:18.04
FROM python:3.7

ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . $APP_HOME

#install packages with pip
RUN pip install --trusted-host pypi.python.org -r requirements.txt

EXPOSE 5000
#CMD ["gunicorn", "main:app", "-b", ":5000"]
ENTRYPOINT ["python","/app/app.py"]
#ENTRYPOINT ["gunicorn", "main:app", "-b", ":5000"]
