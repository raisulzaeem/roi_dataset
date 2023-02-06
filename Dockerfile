FROM python:3.8-slim-buster

WORKDIR /app

RUN apt update; apt install -y libgl1
RUN apt-get install -y libglib2.0-0

COPY ./requirements.txt /app/requirements.txt

RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt
VOLUME /Netz
VOLUME /roi

CMD [ "python3", "update_dataset.py"]
# docker run --name container_name -v '/home/raisul/roi':'/roi' -v '/Netz':'/Netz' -v '/home/raisul/roi/roi_dataset':'/app' docker_image_name
# docker run --name fetch_dataset -it -v '/home/raisul/roi':'/roi' -v '/Netz':'/Netz' -v '/home/raisul/roi/roi_dataset':'/app' roi_dataset