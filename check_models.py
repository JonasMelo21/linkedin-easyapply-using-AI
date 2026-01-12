import google.generativeai as genai
import os
from dotenv import load_dotenv

# Carrega a API Key do .env
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("Erro: API Key não encontrada.")
    exit()

genai.configure(api_key=api_key)

print("--- CONSULTANDO MODELOS DISPONÍVEIS ---")
try:
    # Lista todos os modelos disponíveis para a sua chave
    for m in genai.list_models():
        # Filtra apenas os que servem para gerar texto (generateContent)
        if 'generateContent' in m.supported_generation_methods:
            print(f"- {m.name}")
            
except Exception as e:
    print(f"Erro ao listar modelos: {e}")