# 🐳 Executando o Worker no Docker

Este documento explica como rodar o RoboMigra dentro de um container Docker, garantindo um ambiente isolado e estável.

## ✅ Pré-requisitos

1. Ter **Docker** e **Docker Compose** instalados na máquina.
2. Ter o arquivo `.env` configurado na raiz do projeto (use `.env.example` como base).

## 🚀 Como Inicia (Rápido)

Basta rodar o comando abaixo na raiz do projeto:

```bash
docker-compose up -d --build
```

Isso irá:
1. Construir a imagem do worker.
2. Iniciar o container em segundo plano (`-d`).
3. Reiniciar automaticamente se houver falhas ou se o computador reiniciar.

## 📊 Monitorando Logs

Para ver o que o worker está fazendo:

```bash
docker-compose logs -f
```

## 🛑 Parando o Worker

Para parar a execução:

```bash
docker-compose down
```

## ⚠️ Nota Importante sobre Banco de Dados Local

Se o seu banco de dados SQL Server está rodando na **sua máquina local** (Windows host) e você configurou o `.env` com `DB_SERVER=localhost` ou `127.0.0.1`, **isso não funcionará dentro do Docker** por padrão, pois `localhost` dentro do container é o próprio container.

**Solução:**

O arquivo `docker-compose.yml` já vem configurado para mapear o host. Basta alterar seu `.env` ou entender que o código tentará conectar.

Para garantir a conexão, altere o `DB_SERVER` no seu `.env` para:

```ini
DB_SERVER=host.docker.internal
```

Ou use o IP da sua máquina na rede local.

---
**Desenvolvido com ❤️ pelo time de Engenharia.**
