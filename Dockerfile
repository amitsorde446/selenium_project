FROM ubuntu:bionic

RUN apt-get update && apt-get install python3 tesseract-ocr python3-pip curl unzip -yf
# Install Chrome
RUN apt-get update -y
RUN apt-get install -y dbus-x11
RUN curl https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb -o /chrome.deb
RUN dpkg -i /chrome.deb || apt-get install -yf
RUN rm /chrome.deb

# Install chromedriver for Selenium
#RUN apt-get install -yqq unzip curl
RUN curl https://chromedriver.storage.googleapis.com/91.0.4472.101/chromedriver_linux64.zip -o /usr/local/bin/chromedriver.zip
#RUN curl https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.bionic_amd64.deb -o /usr/local/bin/wkhtmltox_0.12.6-1.bionic_amd64.deb
RUN cd /usr/local/bin && unzip chromedriver.zip
RUN chmod +x /usr/local/bin/chromedriver

RUN chmod +x /usr/local/bin/chromedriver


RUN apt update
#RUN apt-get install -y scrot
#RUN DEBIAN_FRONTEND=noninteractive apt-get install -y python3-tk
#RUN apt-get install -y python3-dev
#RUN export DISPLAY

#RUN echo "Asia/Kolkata" >/etc/timezone
#RUN apt-get install python-opencv -yf
RUN pip3 install --upgrade pip setuptools wheel
RUN apt-get install -y python3-xlib
RUN apt-get install xvfb -yf
RUN mkdir /app
COPY requirements.txt /app
WORKDIR /app
RUN pip3 install -r requirements.txt
COPY . /app
ENTRYPOINT [ "python3", "runTask.py" ]