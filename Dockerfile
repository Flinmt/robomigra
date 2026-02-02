FROM python:3.11-slim-bullseye

# Variáveis de ambiente para Python e Timezone
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=America/Sao_Paulo

# Instalar dependências de sistema necessárias
# unixodbc-dev e g++ são importantes para compilar pyodbc se necessário (embora wheels existam)
# curl e gnupg2 são para baixar a chave da Microsoft
RUN apt-get update && apt-get install -y \
    curl \
    gnupg2 \
    unixodbc \
    unixodbc-dev \
    g++ \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Adicionar repositório da Microsoft e instalar Driver ODBC 17 para SQL Server
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17

# Configurar o diretório de trabalho
WORKDIR /app

# Copiar requirements e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o código fonte
COPY . .

# Comando de execução
CMD ["python", "main.py"]
