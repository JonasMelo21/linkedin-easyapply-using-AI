import time
import random
import traceback
import warnings
import json
import os
import pandas as pd
import re
import sys
from datetime import datetime

# Imports Selenium
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# IA e Env
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
warnings.filterwarnings('ignore')

# --- CONFIGURAÇÃO INICIAL ---
try:
    json_file = f'{sys.argv[1]}.json'
    with open(json_file, 'r', encoding='utf-8') as file:
        data = json.load(file)
except:
    print("Erro no config.json")
    sys.exit()

for key in data: globals()[key] = data[key]

# Segredos (Só precisamos da API KEY agora, o login vc faz na mão)
gemini_api_key = os.getenv("GEMINI_API_KEY")

if not gemini_api_key:
    print("ERRO: Faltando API Key no .env")
    sys.exit()

# --- FUNÇÕES IA ---
def ask_ia(prompt):
    try:
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-pro')
        result = model.generate_content(prompt, generation_config=genai.types.GenerationConfig(max_output_tokens=2048, temperature=0.0)).text
        return result
    except: return None

def clean_json_response(response_text):
    try:
        if not response_text: return None
        match = re.search(r'```json\s*(.*?)\s*```', response_text, re.DOTALL)
        json_str = match.group(1) if match else re.search(r'\{.*\}', response_text, re.DOTALL).group(0)
        return json.loads(json_str)
    except: return None

def get_extraction_prompt(description):
    return f"""Atue como Recrutador Tech. Extraia dados em JSON da descrição: {description[:8000]}
    JSON ESPERADO: {{"nivel_senioridade": "Texto", "tech_stack": ["Lista"], "educacao": "Texto", "tipo_trabalho": "Texto", "soft_skills": ["Lista"], "ferramentas_cloud": ["Lista"], "linguas": ["Lista"]}}"""

# --- CLASSE PRINCIPAL ---
class LinkedinScraper:
    def __init__(self):
        
        options = Options()
        
        # --- MODO VISUAL (COM TELA) ---
        options.add_argument("--start-maximized")
        options.add_argument("--incognito") # Sempre anônimo para não pegar cache velho
        
        # Disfarces
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        options.add_argument(f'user-agent={user_agent}')
        options.add_argument("--disable-blink-features=AutomationControlled") 
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        print("Iniciando navegador...")
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        
        # --- LOGIN SEMI-AUTOMÁTICO ---
        print("Abrindo página de Login...")
        self.driver.get('https://www.linkedin.com/login')
        
        print("\n" + "="*60)
        print("🛑 PAUSA PARA LOGIN MANUAL 🛑")
        print("1. Vá na janela do Chrome que abriu.")
        print("2. Faça o login na sua conta (resolva captcha se precisar).")
        print("3. Espere carregar o FEED (Página inicial).")
        print("4. VOLTE AQUI e aperte ENTER para continuar.")
        print("="*60 + "\n")
        
        input("👉 APERTE ENTER AQUI DEPOIS DE LOGAR...")
        
        print("Retomando automação...")

    def scrape_jobs(self):
        global locations, keywords, remote, hybrid
        output_file = 'dados_vagas_linkedin.csv'
        
        if not os.path.isfile(output_file):
            pd.DataFrame(columns=["data_coleta", "titulo", "empresa", "local", "link", "senioridade", "tech_stack", "educacao", "tipo", "soft_skills", "cloud", "linguas", "descricao_raw"]).to_csv(output_file, index=False)

        job_ids_scraped = [] 

        for location in locations:
            print(f"--- Buscando em: {location} ---")
            for keyword in keywords:
                print(f"Keyword: {keyword}")
                f_WT = "&f_WT=1%2C2" if remote and hybrid else ("&f_WT=2" if remote else ("&f_WT=1" if hybrid else ""))
                
                url = f'https://www.linkedin.com/jobs/search/?keywords={keyword}&location={location}{f_WT}&refresh=true'
                self.driver.get(url)
                
                # Pausa extra para garantir que a página de busca carregue sem bloquear
                time.sleep(random.uniform(5, 8))
                
                try:
                    job_cards = self.driver.find_elements(By.XPATH, '//div[@data-job-id]')
                    print(f"Encontrados {len(job_cards)} vagas.")
                except:
                    print("Nenhuma vaga encontrada ou erro de carregamento.")
                    continue

                for card in job_cards:
                    try:
                        job_id = card.get_attribute("data-job-id")
                        if job_id in job_ids_scraped: continue
                        
                        self.driver.execute_script("arguments[0].scrollIntoView();", card)
                        self.driver.execute_script("arguments[0].click();", card)
                        time.sleep(random.uniform(2, 4))
                        
                        try: title = self.driver.find_element(By.CLASS_NAME, 'job-details-jobs-unified-top-card__job-title').text.strip()
                        except: title = "N/A"
                        try: company = self.driver.find_element(By.CLASS_NAME, 'job-details-jobs-unified-top-card__company-name').text.strip()
                        except: company = "N/A"
                        
                        try:
                            try:
                                self.driver.find_element(By.CLASS_NAME, 'jobs-description__footer-button').click()
                                time.sleep(1)
                            except: pass
                            desc = self.driver.find_element(By.ID, 'job-details').text
                        except: continue

                        print(f"Lendo: {title} @ {company}")
                        prompt = get_extraction_prompt(desc)
                        response_ia = ask_ia(prompt)
                        data_json = clean_json_response(response_ia) or {}
                        
                        new_row = {
                            "data_coleta": datetime.now().strftime("%Y-%m-%d"),
                            "titulo": title, "empresa": company, "local": location,
                            "link": f"https://www.linkedin.com/jobs/view/{job_id}",
                            "senioridade": data_json.get("nivel_senioridade", "N/A"),
                            "tech_stack": str(data_json.get("tech_stack", [])),
                            "educacao": data_json.get("educacao", "N/A"),
                            "tipo": data_json.get("tipo_trabalho", "N/A"),
                            "soft_skills": str(data_json.get("soft_skills", [])),
                            "cloud": str(data_json.get("ferramentas_cloud", [])),
                            "linguas": str(data_json.get("linguas", [])),
                            "descricao_raw": desc[:] 
                        }
                        pd.DataFrame([new_row]).to_csv(output_file, mode='a', header=False, index=False)
                        print("✅ Salvo!")
                        job_ids_scraped.append(job_id)
                    except: continue

if __name__ == "__main__":
    try:
        scraper = LinkedinScraper()
        scraper.scrape_jobs()
    except Exception as e:
        print(f"Erro fatal: {e}")
        traceback.print_exc()