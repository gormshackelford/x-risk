FROM python:3.6-buster

WORKDIR /usr/src/x-risk

ENV PYTHONUNBUFFERED 1

RUN pip install --upgrade pip
COPY ./requirements.txt /usr/src/x-risk/requirements.txt
RUN pip install -r requirements.txt

COPY . /usr/src/x-risk/

# For development:
CMD python manage.py runserver 0.0.0.0:8000

# For production (uncomment the next line and comment the previous line, to use Gunicorn instead of the Django development server):
#CMD python manage.py collectstatic --no-input --clear && gunicorn xrisk.wsgi:application --bind 0.0.0.0:8000
