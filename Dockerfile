FROM python:3.9-slim
RUN apt-get update && \
    apt-get install -y \
        build-essential \
        make \
        gcc

RUN apt-get install -y python3-pandas

RUN apt-get install -y protobuf-compiler
RUN apt-get install -y systemd
RUN apt-get install -y rsyslog
RUN apt-get install -y sqlite3

RUN apt-get install -y python3-pandas

COPY rsyslog.conf /etc/rsyslog.conf
COPY m9bsyslog /etc/logrotate.d/m9bsyslog
RUN chmod 644 /etc/logrotate.d/m9bsyslog

WORKDIR /usr/src/app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install ./bottle-utils
COPY app/ .
RUN chmod 644 -R log

CMD ["/bin/bash", "./start.sh"]

#CMD service rsyslog restart && \
#    python ./SnomM9BProvisioningServer.py
