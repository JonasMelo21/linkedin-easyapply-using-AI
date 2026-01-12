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

# --- FUNÇÕES DE EXTRAÇÃO POR REGEX (Executam ANTES da IA) ---

def extract_cargo_from_title(titulo):
    """Extrai cargo do título usando REGEX antes de chamar IA"""
    titulo_lower = titulo.lower()
    
    # Padrões de cargos (português e inglês)
    cargos_map = {
        'Data Engineer': [
            r'data\s*engineer', 
            r'engenh[ea]ir[oa]\s*(?:\(a\))?\s*de\s*dados',  # Captura Engenheiro(a), Engenheira, Engenheiro
            r'eng\.?\s*(?:\(a\))?\s*dados',  # Eng. Dados ou Eng(a) Dados
            r'data\s*platform\s*engineer'
        ],
        'Data Scientist': [
            r'data\s*scientist', 
            r'cientista\s*de\s*dados', 
            r'data\s*science(?!\s*engineer)'  # Evita pegar "Data Science Engineer"
        ],
        'Machine Learning Engineer': [
            r'machine\s*learning\s*engineer', 
            r'ml\s*engineer', 
            r'mlops\s*engineer', 
            r'ai\s*engineer', 
            r'artificial\s*intelligence\s*engineer'
        ],
        'Analytics Engineer': [
            r'analytics\s*engineer', 
            r'engenh[ea]ir[oa]\s*(?:\(a\))?\s*de\s*analytics', 
            r'bi\s*engineer'
        ],
        'Data Analyst': [
            r'data\s*analyst', 
            r'analista\s*de\s*dados', 
            r'business\s*intelligence\s*analyst', 
            r'bi\s*analyst'
        ],
        'Software Engineer': [
            r'software\s*engineer', 
            r'engenh[ea]ir[oa]\s*(?:\(a\))?\s*de\s*software', 
            r'backend\s*engineer', 
            r'full\s*stack', 
            r'fullstack'
        ]
    }
    
    for cargo, patterns in cargos_map.items():
        for pattern in patterns:
            if re.search(pattern, titulo_lower):
                return cargo
    
    return None  # Retorna None se não encontrar

def extract_senioridade_from_title(titulo):
    """Extrai senioridade do título usando REGEX antes de chamar IA"""
    titulo_lower = titulo.lower()
    
    # Padrões de senioridade (português e inglês) - ordem importa (mais específico primeiro)
    senioridade_patterns = {
        'Estágio': [
            r'\bintern\b', 
            r'\btrainee\b', 
            r'\bestag', 
            r'\bestagiário\b'
        ],
        'Junior': [
            r'\bjr\.?\b',  # Jr ou Jr.
            r'\bjunior\b', 
            r'\bjúnior\b', 
            r'\bi\b(?!\s*\w)',  # I isolado
            r'\bj[úu]nior\b'  # Aceita júnior e junior
        ],
        'Pleno': [
            r'\bpleno\b', 
            r'\bmid\b', 
            r'\bpl\b',  # PL (case insensitive por causa do .lower())
            r'\bmid-level\b', 
            r'\bmidlevel\b', 
            r'\bii\b', 
            r'\biii\b'
        ],
        'Senior': [
            r'\bsenior\b', 
            r'\bs[êe]nior\b',  # Aceita sênior e senior
            r'\bsr\.?\b',  # Sr ou Sr.
            r'\biv\b', 
            r'\bv\b'
        ],
        'Especialista': [
            r'\bstaff\b', 
            r'\bprincipal\b', 
            r'\blead\b', 
            r'\bexpert\b', 
            r'\bspecialist\b', 
            r'\bespecialista\b', 
            r'\barchitect\b'
        ],
        'Gestão': [
            r'\bmanager\b', 
            r'\bgerente\b', 
            r'\bhead\b', 
            r'\bdirector\b', 
            r'\bdiretor\b', 
            r'\bvp\b', 
            r'\bchief\b'
        ]
    }
    
    for senioridade, patterns in senioridade_patterns.items():
        for pattern in patterns:
            if re.search(pattern, titulo_lower):
                return senioridade
    
    return None  # Retorna None se não encontrar

def extract_tipo_trabalho_from_text(texto):
    """Extrai tipo de trabalho (Remoto/Híbrido/Presencial) de título ou local usando REGEX"""
    texto_lower = texto.lower()
    
    # Padrões de tipo de trabalho
    if re.search(r'\b(remote|remoto|100%\s*remote|work\s*from\s*home|wfh|anywhere|fully\s*remote)\b', texto_lower):
        return 'Remoto'
    elif re.search(r'\b(hybrid|híbrido|hibrido|flex)\b', texto_lower):
        return 'Híbrido'
    elif re.search(r'\b(on-site|onsite|presencial|in-office|office)\b', texto_lower):
        return 'Presencial'
    
    return None  # Retorna None se não encontrar

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

def classify_from_title(titulo):
    """ETAPA 1: Analisa APENAS o título para classificação rápida"""
    prompt = f"""
    Analise o título da vaga e classifique com base em padrões comuns da indústria:
    
    TÍTULO: {titulo}
    
    TAREFA:
    1. "cargo_simplificado": Identifique o cargo principal. Escolha UM:
       - "Data Engineer" (se mencionar: Data Engineer, Engenheiro de Dados, Data Platform, Pipeline Engineer)
       - "Data Scientist" (se mencionar: Data Scientist, Cientista de Dados)
       - "Machine Learning Engineer" (se mencionar: ML Engineer, Machine Learning, MLOps Engineer)
       - "Analytics Engineer" (se mencionar: Analytics Engineer, BI Engineer)
       - "Data Analyst" (se mencionar: Data Analyst, Analista de Dados, BI Analyst)
       - "Software Engineer" (se mencionar: Software Engineer, Backend Engineer, Full Stack)
       - "Outros" (apenas se nenhuma opção acima se aplicar)
    
    2. "senioridade_simplificada": Identifique o nível. REGRAS:
       - "Estágio" → APENAS se tiver: Intern, Trainee, Estagiário
       - "Junior" → Se tiver: Jr, Junior, I, ou se não mencionar nível (assuma Junior por padrão para vagas genéricas)
       - "Pleno" → Se tiver: Pleno, Mid, Mid-Level, II, III
       - "Senior" → Se tiver: Senior, Sr, Sênior, IV, V
       - "Especialista" → Se tiver: Staff, Principal, Lead, Expert, Specialist, Architect
       - "Gestão" → Se tiver: Manager, Head, Director, VP, Chief
       
       IMPORTANTE: Se o título NÃO mencionar explicitamente o nível, analise o contexto:
       - Título simples "Data Engineer" sem qualificador → "Pleno" (padrão da indústria)
       - Título com "Azure", "AWS" ou tecnologias avançadas → "Senior"
    
    Retorne APENAS JSON válido (sem markdown, sem texto extra):
    {{
        "cargo_simplificado": "Data Engineer",
        "senioridade_simplificada": "Pleno"
    }}
    """
    
    tentativas = 0
    max_tentativas = 3
    
    while tentativas < max_tentativas:
        try:
            response = model.generate_content(prompt)
            return clean_and_parse_json(response.text)
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                time.sleep((tentativas + 1) * 5)
                tentativas += 1
            else:
                return None
    return None

def extract_skills_from_description(description, titulo):
    """ETAPA 2: Analisa a descrição completa para extrair skills e detalhes"""
    texto_reduzido = description[:8000]
    
    prompt = f"""
    Extraia TODAS as informações técnicas da descrição. Seja completo e detalhado.
    
    TÍTULO: {titulo}
    DESCRIÇÃO:
    {texto_reduzido}

    INSTRUÇÕES OBRIGATÓRIAS:
    
    1. "tipo_padronizado": Identifique o modelo de trabalho. REGRAS:
       - "Remoto" → Se mencionar: Remote, 100% remoto, work from home, WFH, anywhere, fully remote
       - "Híbrido" → Se mencionar: Hybrid, híbrido, X days in office, flexible location
       - "Presencial" → Se mencionar: On-site, presencial, in-office, escritório
       - Se NÃO mencionar explicitamente, mas a vaga é para "Brazil" ou "LATAM" → assuma "Remoto" (padrão da indústria tech)
    
    2. "tech_stack": LISTE TODAS as tecnologias mencionadas. Incluir:
       - Linguagens: Python, SQL, Scala, Java, R, etc
       - Frameworks: Spark, Pandas, Airflow, dbt, Kafka, etc
       - Bancos: PostgreSQL, MySQL, MongoDB, Redis, etc
       - Ferramentas: Docker, Kubernetes, Terraform, Git, CI/CD, etc
       - Big Data: Hadoop, Hive, Presto, Flink, etc
       - IMPORTANTE: Extraia TUDO que for tecnologia, mesmo se mencionado de passagem
    
    3. "cloud": LISTE TODAS as ferramentas cloud específicas:
       - Cloud Platforms: AWS, Azure, GCP
       - Data Platforms: Databricks, Snowflake, BigQuery, Redshift
       - Serviços AWS: S3, Glue, Lambda, EMR, Kinesis, Athena, etc
       - Serviços Azure: ADF, Synapse, Data Lake, Cosmos DB, etc
       - Serviços GCP: BigQuery, Dataflow, Pub/Sub, etc
    
    4. "soft_skills": Extraia soft skills mencionadas:
       - Comunicação, Liderança, Trabalho em equipe, Resolução de problemas
       - Pensamento analítico, Colaboração, Proatividade, etc
       - Se NÃO houver soft skills explícitas, INFIRA do contexto (ex: "work with stakeholders" = Comunicação)
    
    5. "educacao": Requisitos educacionais:
       - "Graduação em TI" / "Computer Science degree" / "Engenharia"
       - "Não especificado" (se não mencionar)
    
    6. "linguas": Idiomas requeridos:
       - SEMPRE inclua "Inglês" se mencionar: English, B2, C1, advanced English, fluent
       - Inclua "Português" se mencionar explicitamente
       - Se não mencionar nenhum idioma mas vaga é para Brazil/LATAM → ["Inglês"] (padrão)

    Retorne APENAS JSON válido (sem markdown, sem explicações):
    {{
        "tipo_padronizado": "Remoto",
        "tech_stack": ["Python", "SQL", "Spark", "Airflow", "Docker"],
        "cloud": ["AWS", "Databricks", "S3", "Glue"],
        "soft_skills": ["Comunicação", "Trabalho em equipe", "Resolução de problemas"],
        "educacao": "Graduação em TI",
        "linguas": ["Inglês", "Português"]
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
    
    # Verifica quais campos estão vazios
    cargo_ok = str(row['cargo_simplificado']) not in ["None", "nan", "", "N/A"]
    senior_ok = str(row['senioridade_simplificada']) not in ["None", "nan", "", "N/A"]
    tipo_ok = str(row['tipo_padronizado']) not in ["None", "nan", "", "N/A"]
    
    titulo = str(row['titulo'])
    local = str(row['local']) if 'local' in row else ""
    descricao = str(row['descricao_raw'])
    
    # Pula se título ou descrição estão vazios
    if pd.isna(titulo) or pd.isna(descricao) or len(descricao) < 10:
        continue
    
    # --- PRÉ-PROCESSAMENTO: REGEX ANTES DA IA ---
    
    # 1. Tenta extrair CARGO do título por REGEX
    if not cargo_ok:
        cargo_regex = extract_cargo_from_title(titulo)
        if cargo_regex:
            df.at[index, 'cargo_simplificado'] = cargo_regex
            cargo_ok = True
            alteracoes += 1
            print(f"✓ Cargo extraído por REGEX: {cargo_regex}")
    
    # 2. Tenta extrair SENIORIDADE do título por REGEX
    if not senior_ok:
        senioridade_regex = extract_senioridade_from_title(titulo)
        if senioridade_regex:
            df.at[index, 'senioridade_simplificada'] = senioridade_regex
            senior_ok = True
            alteracoes += 1
            print(f"✓ Senioridade extraída por REGEX: {senioridade_regex}")
    
    # 3. Tenta extrair TIPO de trabalho do título ou local por REGEX
    if not tipo_ok:
        tipo_regex = extract_tipo_trabalho_from_text(f"{titulo} {local}")
        if tipo_regex:
            df.at[index, 'tipo_padronizado'] = tipo_regex
            tipo_ok = True
            alteracoes += 1
            print(f"✓ Tipo de trabalho extraído por REGEX: {tipo_regex}")
    
    # --- ETAPA 1: Classifica pelo TÍTULO com IA (apenas se REGEX não conseguiu) ---
    if not cargo_ok or not senior_ok:
        print(f"\n📋 Analisando título com IA: {titulo[:50]}...")
        dados_titulo = classify_from_title(titulo)
        
        if dados_titulo:
            if not cargo_ok:
                df.at[index, 'cargo_simplificado'] = dados_titulo.get('cargo_simplificado', 'Outros')
                cargo_ok = True
            if not senior_ok:
                df.at[index, 'senioridade_simplificada'] = dados_titulo.get('senioridade_simplificada', 'N/A')
                senior_ok = True
            alteracoes += 1
        
        time.sleep(2)  # Pausa menor entre chamadas
    
    # --- ETAPA 2: Analisa DESCRIÇÃO para Skills e Tipo de Trabalho ---
    # Verifica se precisa analisar a descrição
    tech_ok = str(row['tech_stack']) not in ["None", "nan", "", "[]"]
    
    if not tipo_ok or not tech_ok:
        print(f"🔍 Analisando descrição completa...")
        dados_descricao = extract_skills_from_description(descricao, titulo)
        
        if dados_descricao:
            if not tipo_ok:
                df.at[index, 'tipo_padronizado'] = dados_descricao.get('tipo_padronizado', 'N/A')
            
            # Atualiza skills mesmo se já existir, para melhorar qualidade
            skills = dados_descricao.get('tech_stack', [])
            cloud_tools = dados_descricao.get('cloud', [])
            
            # Junta Cloud dentro de Tech Stack (sem duplicar)
            tech_completa = list(set(skills + cloud_tools))
            
            df.at[index, 'tech_stack']  = str(tech_completa)
            df.at[index, 'cloud']       = str(cloud_tools)
            df.at[index, 'soft_skills'] = str(dados_descricao.get('soft_skills', []))
            df.at[index, 'educacao']    = dados_descricao.get('educacao', 'N/A')
            df.at[index, 'linguas']     = str(dados_descricao.get('linguas', []))
            alteracoes += 1
        
        time.sleep(4)  # Pausa maior após análise completa
    
    # Salva checkpoint a cada 5 vagas
    if index % 5 == 0:
        df.to_csv(arquivo_csv, index=False)
        print(f"💾 Checkpoint salvo ({alteracoes} alterações até agora)")

df.to_csv(arquivo_csv, index=False)
print(f"\n✅ Concluído! {alteracoes} linhas foram atualizadas.")