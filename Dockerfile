FROM python:3.8-slim-buster

WORKDIR /app

RUN apt update; apt install -y libgl1
RUN apt-get install -y libglib2.0-0

COPY . .

RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt
VOLUME /Netz
VOLUME /roi


CMD [ "python3", "update_dataset.py"]

# docker run --name container_name -v '/home/raisul/roi':'/roi' docker_image_name