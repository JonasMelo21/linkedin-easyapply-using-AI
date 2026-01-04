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

# Segredos
username = os.getenv("LINKEDIN_USERNAME")
password = os.getenv("LINKEDIN_PASSWORD")
gemini_api_key = os.getenv("GEMINI_API_KEY")
linkedin_cookie = os.getenv("LINKEDIN_COOKIE") # <--- NOVO SEGREDO

if not gemini_api_key:
    print("ERRO: Faltando API Key")
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
        global linkedin_cookie
        
        options = Options()
        
        # --- MODO COM TELA (GUI) PARA UBUNTU NATIVO ---
        # options.add_argument("--headless=new")  <-- COMENTE ESSA LINHA (põe # na frente)
        # options.add_argument("--no-sandbox")    <-- COMENTE (não precisa no nativo)
        # options.add_argument("--disable-dev-shm-usage") <-- COMENTE
        
        options.add_argument("--start-maximized") # Abre tela cheia
        options.add_argument("--incognito")       # Modo anônimo (MUITO IMPORTANTE manter)
        
        # Truques Anti-Robô (Mantenha isso!)
        options.add_argument("--disable-blink-features=AutomationControlled") 
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        print("Iniciando navegador (COM TELA)...")
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)

        
        # --- LÓGICA DE LOGIN COM COOKIE (BYPASS) ---
        print("Acessando LinkedIn para injetar cookie...")
        self.driver.get('https://www.linkedin.com/404') # Página leve qualquer para setar domínio
        
        if linkedin_cookie:
            print("Injetando cookie de sessão (li_at)...")
            # Adiciona o cookie
            self.driver.add_cookie({
                'name': 'li_at',
                'value': linkedin_cookie,
                'domain': '.linkedin.com'
            })
            
            print("Atualizando página para validar login...")
            self.driver.get('https://www.linkedin.com/feed/')
            time.sleep(5)
            
            print(f"URL atual: {self.driver.current_url}")
            if "feed" in self.driver.current_url:
                print("✅ LOGIN COM COOKIE SUCESSO! Captcha evitado.")
            else:
                print("⚠️ O cookie pode ter expirado ou falhado. Tentando login manual...")
                self.login_manual()
        else:
            print("Cookie não encontrado no .env. Tentando login manual...")
            self.login_manual()

    def login_manual(self):
        # Fallback para o método antigo se o cookie falhar
        global username, password
        self.driver.get('https://www.linkedin.com/login')
        time.sleep(2)
        try:
            self.driver.find_element(By.ID, 'username').send_keys(username)
            self.driver.find_element(By.ID, 'password').send_keys(password)
            self.driver.find_element(By.XPATH, '//button[@type="submit"]').click()
            time.sleep(5)
        except Exception as e:
            print(f"Erro login manual: {e}")

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
                time.sleep(5)
                
                try:
                    job_cards = self.driver.find_elements(By.XPATH, '//div[@data-job-id]')
                    print(f"Encontrados {len(job_cards)} vagas.")
                except:
                    print("Nenhuma vaga encontrada.")
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
                            "descricao_raw": desc[:300] + "..." 
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