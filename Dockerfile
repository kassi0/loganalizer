FROM registry.access.redhat.com/ubi9/s2i-base:9.8-1788331823

USER 0

# Instala Python 3.12 (ou versão padrão do stream Python no UBI9) e ferramentas de compilação
RUN dnf -y update && \
    dnf -y install python3 python3-pip python3-devel gcc gcc-c++ make libpq-devel && \
    dnf clean all

WORKDIR /opt/app-root/src

# Copia e instala dependências primeiro para aproveitar o cache de camadas
COPY requirements.txt .
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# Copia a aplicação
COPY . .

# Remove diretório .git se porventura tiver sido copiado e ajusta permissões
RUN rm -rf .git logs_analysis.db && \
    mkdir -p uploads && \
    chown -R 1001:0 /opt/app-root/src && \
    chmod -R g=u /opt/app-root/src

USER 1001

EXPOSE 8080

ENV PORT=8080
ENV PYTHONUNBUFFERED=1

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "4", "--timeout", "300", "app:app"]
