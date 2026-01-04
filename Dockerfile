# Usa uma imagem leve do Python
FROM python:3.11-slim

# 1. Instala Chrome, Driver e dependências do sistema
# (Isso é vital para o Selenium funcionar no futuro se precisar)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    chromium \
    chromium-driver \
    git \
    && rm -rf /var/lib/apt/lists/*

# 2. Configura variáveis pro Chrome não travar
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# 3. Cria usuário seguro (Hugging Face exige isso)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# 4. Configura pasta de trabalho
WORKDIR /app

# 5. Instala as bibliotecas Python
COPY --chown=user requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. Copia todo o seu código para dentro do container
COPY --chown=user . .

# 7. Comando que liga o site (Aponta para o app.py)
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]