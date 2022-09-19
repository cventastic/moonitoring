from python:bullseye


RUN pip install --upgrade pip
RUN pip install substrate-interface
RUN pip install requests

COPY script.py script.py
COPY networks.py networks.py

CMD ["python", "-u", "script.py"]
