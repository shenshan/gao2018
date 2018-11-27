FROM datajoint/jupyter:python3.6

ADD . /src/gao2018

RUN pip install -e /src/gao2018

