FROM python:3.12-slim
RUN groupadd -r pavelgroup && useradd -r -g pavelgroup pavel

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends gettext \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOME=/tmp

RUN pip install --upgrade pip
WORKDIR /app/www/breakfast_lecture_planner
RUN mkdir -p media staticfiles logs \
    && chown -R pavel:pavelgroup /app/www/breakfast_lecture_planner

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN django-admin compilemessages -l en -l lt -l ru
RUN chown -R pavel:pavelgroup /app/www/breakfast_lecture_planner/media/
RUN chmod -R 755 /app/www/breakfast_lecture_planner/media/
USER pavel
