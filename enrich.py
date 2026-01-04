import pandas as pd
import google.generativeai as genai
import os
import json
import time
import re
from dotenv import load_dotenv
from tqdm import tqdm

# Carrega API Key
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("ERRO: API Key não encontrada no .env")
    exit()

# Configura Gemini
genai.configure(api_key=api_key)

# MUDANÇA 1: Usando o alias estável que apareceu na sua lista.
# Esse modelo tem limites muito maiores que o 2.0 experimental.
model = genai.GenerativeModel('models/gemini-flash-latest')

def clean_and_parse_json(response_text):
    """Limpa a resposta da IA tentando extrair JSON válido."""
    if not response_text: return None
    try:
        return json.loads(response_text)
    except:
        pass
    try:
        match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except:
        return None
    return None

def get_ai_data(description):
    # MUDANÇA 2: Reduzi de 15000 para 6000 caracteres.
    # Job descriptions raramente passam disso e economiza tokens (evita erro de cota).
    texto_reduzido = description[:6000]

    prompt = f"""
    Analise a descrição de vaga abaixo. Extraia as skills técnicas.
    
    DESCRIÇÃO:
    {texto_reduzido}

    IMPORTANTE: Retorne APENAS um JSON válido. Não use Markdown.
    Se não encontrar a informação, use "N/A" ou lista vazia [].

    Formato obrigatório:
    {{
        "senioridade": "Texto",
        "tech_stack": ["Skill1", "Skill2"],
        "educacao": "Texto",
        "tipo": "Texto",
        "soft_skills": ["Skill1"],
        "cloud": ["AWS", "Azure", "etc"],
        "linguas": ["Inglês", "etc"]
    }}
    """
    
    # MUDANÇA 3: Lógica de Retry (Tentar Novamente)
    # Em vez de falhar e pular a linha, ele tenta até 3 vezes com espera exponencial
    tentativas = 0
    max_tentativas = 5
    
    while tentativas < max_tentativas:
        try:
            response = model.generate_content(prompt)
            return clean_and_parse_json(response.text)
        
        except Exception as e:
            erro_str = str(e)
            if "429" in erro_str or "quota" in erro_str.lower():
                wait_time = (tentativas + 1) * 10 # Espera 10s, 20s, 30s...
                tqdm.write(f"  ⏳ Cota atingida (429). Esperando {wait_time}s para tentar de novo...")
                time.sleep(wait_time)
                tentativas += 1
            else:
                tqdm.write(f"  ❌ Erro desconhecido na API: {e}")
                return None
    
    return None # Desiste após 5 tentativas

# --- PROCESSAMENTO ---

arquivo_csv = 'dados_vagas_linkedin.csv'
print(f"📂 Lendo {arquivo_csv}...")

try:
    df = pd.read_csv(arquivo_csv)
except FileNotFoundError:
    print("Arquivo não encontrado!")
    exit()

colunas_alvo = ["senioridade", "tech_stack", "educacao", "tipo", "soft_skills", "cloud", "linguas"]
for col in colunas_alvo:
    if col not in df.columns:
        df[col] = None
    df[col] = df[col].astype(object)

print(f"🚀 Iniciando enriquecimento de {len(df)} vagas com modelo 'gemini-flash-latest'...")

alteracoes = 0

for index, row in tqdm(df.iterrows(), total=df.shape[0]):
    
    # Pula se já estiver preenchido
    stack_atual = str(row['tech_stack'])
    if len(stack_atual) > 5 and "[]" not in stack_atual and "N/A" not in stack_atual:
        continue

    descricao = row['descricao_raw']
    
    if pd.isna(descricao) or len(str(descricao)) < 10:
        continue
    
    # Chama a IA
    dados_ia = get_ai_data(str(descricao))
    
    if dados_ia:
        df.at[index, 'senioridade'] = dados_ia.get('senioridade', 'N/A')
        df.at[index, 'tech_stack']  = str(dados_ia.get('tech_stack', []))
        df.at[index, 'educacao']    = dados_ia.get('educacao', 'N/A')
        df.at[index, 'tipo']        = dados_ia.get('tipo', 'N/A')
        df.at[index, 'soft_skills'] = str(dados_ia.get('soft_skills', []))
        df.at[index, 'cloud']       = str(dados_ia.get('cloud', []))
        df.at[index, 'linguas']     = str(dados_ia.get('linguas', []))
        alteracoes += 1
    
    # MUDANÇA 4: Pausa menor. O modelo Flash aguenta mais. 
    # 4 segundos é seguro para o Free Tier (15 requests/minuto)
    time.sleep(4) 

    if index % 5 == 0:
        df.to_csv(arquivo_csv, index=False)

df.to_csv(arquivo_csv, index=False)
print(f"\n✅ Concluído! {alteracoes} linhas foram atualizadas.")