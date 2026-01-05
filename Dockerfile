# Usa Python 3.11 (Compatível com bibliotecas novas)
FROM python:3.11-slim

# 1. Instala Chrome e dependências do sistema
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    chromium \
    chromium-driver \
    git \
    && rm -rf /var/lib/apt/lists/*

# 2. Configura variáveis de ambiente do Chrome
ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

# 3. Cria usuário não-root (Segurança do Hugging Face)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# 4. Configura pasta de trabalho
WORKDIR /app

# 5. Instala bibliotecas Python
COPY --chown=user requirements.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 6. Copia TODO o código (Site + Scraper + CSV)
COPY --chown=user . .

# 7. COMANDO FINAL: Roda APENAS o Site (app.py)
# O scraper (apply.py) fica lá guardado, mas não roda automático
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]