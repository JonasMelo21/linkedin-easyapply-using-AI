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

genai.configure(api_key=api_key)
model = genai.GenerativeModel('models/gemini-flash-latest')

def clean_and_parse_json(response_text):
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

def get_ai_data(description, titulo_original):
    texto_reduzido = description[:6000]

    # --- PROMPT REFORMULADO 3.0 ---
    prompt = f"""
    Analise a descrição e o título da vaga. Extraia as skills e CLASSIFIQUE a vaga.
    
    TÍTULO ORIGINAL: {titulo_original}
    DESCRIÇÃO:
    {texto_reduzido}

    TAREFA OBRIGATÓRIA:
    1. "cargo_simplificado": Escolha UM: "Data Engineer", "Data Scientist", "Machine Learning Engineer", "Analytics Engineer", "Data Analyst", "Software Engineer", "Outros".
    
    2. "senioridade_simplificada": Escolha UM: "Estágio", "Junior", "Pleno", "Senior", "Especialista", "Gestão", "N/A".
    
    3. "tipo_padronizado": Escolha UM: 
       - "Remoto" (100% home office, anywhere)
       - "Híbrido" (Alguns dias no escritório)
       - "Presencial" (100% no escritório)
       - "N/A" (Se não for mencionado)

    Retorne APENAS um JSON válido neste formato:
    {{
        "cargo_simplificado": "Data Engineer",
        "senioridade_simplificada": "Pleno",
        "tipo_padronizado": "Remoto",
        "tech_stack": ["Python", "SQL", "Spark"],
        "cloud": ["AWS", "Databricks"],
        "soft_skills": ["Comunicação"],
        "educacao": "Graduação em TI",
        "linguas": ["Inglês"]
    }}
    """
    
    tentativas = 0
    max_tentativas = 5
    
    while tentativas < max_tentativas:
        try:
            response = model.generate_content(prompt)
            return clean_and_parse_json(response.text)
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                time.sleep((tentativas + 1) * 10)
                tentativas += 1
            else:
                return None
    return None

# --- PROCESSAMENTO ---

arquivo_csv = 'dados_vagas_linkedin.csv'
print(f"📂 Lendo {arquivo_csv}...")

try:
    df = pd.read_csv(arquivo_csv)
except FileNotFoundError:
    print("Arquivo não encontrado!")
    exit()

# Adicionei 'tipo_padronizado' nas colunas alvo
colunas_alvo = ["cargo_simplificado", "senioridade_simplificada", "tipo_padronizado", "tech_stack", "educacao", "soft_skills", "cloud", "linguas"]
for col in colunas_alvo:
    if col not in df.columns:
        df[col] = None
    df[col] = df[col].astype(object)

print(f"🚀 Iniciando padronização e fusão de Tech+Cloud...")

alteracoes = 0

for index, row in tqdm(df.iterrows(), total=df.shape[0]):
    
    # Lógica de Pular: Só pula se as 3 colunas principais já estiverem preenchidas
    cargo_ok = str(row['cargo_simplificado']) not in ["None", "nan", ""]
    senior_ok = str(row['senioridade_simplificada']) not in ["None", "nan", ""]
    tipo_ok = str(row['tipo_padronizado']) not in ["None", "nan", ""]
    
    if cargo_ok and senior_ok and tipo_ok:
        continue

    descricao = row['descricao_raw']
    titulo = row['titulo']
    
    if pd.isna(descricao) or len(str(descricao)) < 10:
        continue
    
    dados_ia = get_ai_data(str(descricao), str(titulo))
    
    if dados_ia:
        df.at[index, 'cargo_simplificado'] = dados_ia.get('cargo_simplificado', 'Outros')
        df.at[index, 'senioridade_simplificada'] = dados_ia.get('senioridade_simplificada', 'N/A')
        df.at[index, 'tipo_padronizado'] = dados_ia.get('tipo_padronizado', 'N/A')
        
        # --- FUSÃO INTELIGENTE DE LISTAS ---
        skills = dados_ia.get('tech_stack', [])
        cloud_tools = dados_ia.get('cloud', [])
        
        # Junta Cloud dentro de Tech Stack (sem duplicar)
        tech_completa = list(set(skills + cloud_tools))
        
        df.at[index, 'tech_stack']  = str(tech_completa) # Agora salva tudo junto!
        df.at[index, 'cloud']       = str(cloud_tools)   # Mantém cloud separado tbm se quiser consultar depois
        
        df.at[index, 'soft_skills'] = str(dados_ia.get('soft_skills', []))
        df.at[index, 'educacao']    = dados_ia.get('educacao', 'N/A')
        df.at[index, 'linguas']     = str(dados_ia.get('linguas', []))
        alteracoes += 1
    
    time.sleep(4) 

    if index % 5 == 0:
        df.to_csv(arquivo_csv, index=False)

df.to_csv(arquivo_csv, index=False)
print(f"\n✅ Concluído! {alteracoes} linhas foram atualizadas.")