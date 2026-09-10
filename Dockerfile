FROM registry.access.redhat.com/ubi9/python-311:latest

WORKDIR /opt/app-root/src

# Instalação das dependências
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Cópia do código-fonte
COPY . .

# Garante permissões adequadas para o usuário arbitrário do OpenShift
RUN mkdir -p uploads && \
    chmod -R g=u /opt/app-root/src

EXPOSE 8080

ENV PORT=8080
ENV PYTHONUNBUFFERED=1

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "4", "--timeout", "300", "app:app"]
