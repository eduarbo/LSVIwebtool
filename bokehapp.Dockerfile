
FROM ubuntu:18.04
FROM python:3.7

ENV PATH="/root/miniconda3/bin:${PATH}"
ARG PATH="/root/miniconda3/bin:${PATH}"
RUN apt-get update

#SHELL [ "/bin/bash", "--login", "-c" ]

ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . $APP_HOME

RUN apt-get install -y wget && rm -rf /var/lib/apt/lists/*

RUN wget \
    https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
    && mkdir /root/.conda \
    && bash Miniconda3-latest-Linux-x86_64.sh -b \
    && rm -f Miniconda3-latest-Linux-x86_64.sh

RUN conda --version

RUN conda install --yes mkl-service
RUN conda clean -ay
#install packages with pip
RUN pip install --trusted-host pypi.python.org -r bokehapp_requirements.txt


EXPOSE 5006
#ENTRYPOINT ["bokeh","serve", "--port 5006", ""--allow-websocket-origin=*", "/app/script.py"]
CMD bokeh serve --port 5006 --allow-websocket-origin="*" /app/script.py



