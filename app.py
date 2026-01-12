import streamlit as st
import pandas as pd
import ast
import plotly.express as px

# 1. Configuração da Página
st.set_page_config(page_title="Job Hunter Skills", layout="wide", page_icon="💼")

st.markdown("""
<style>
    .metric-card { background-color: #f0f2f6; padding: 20px; border-radius: 10px; text-align: center; }
</style>
""", unsafe_allow_html=True)

st.title("💼 Job Hunter AI: Análise de Mercado Tech")
st.markdown("Descubra as tecnologias e skills mais pedidas nas vagas do LinkedIn.")

# 2. Carregar Dados
@st.cache_data
def load_data():
    try:
        df = pd.read_csv('dados_vagas_linkedin.csv')
        # Garante colunas mínimas
        cols_obrigatorias = ['cargo_simplificado', 'senioridade_simplificada', 'tipo_padronizado']
        for col in cols_obrigatorias:
            if col not in df.columns:
                df[col] = 'N/A'
        return df
    except FileNotFoundError:
        return pd.DataFrame()

df_raw = load_data()

if df_raw.empty:
    st.warning("⚠️ Nenhum dado encontrado. Suba o arquivo 'dados_vagas_linkedin.csv'.")
    st.stop()

# 4. Limpeza e Conversão
def limpar_lista(item):
    try:
        if pd.isna(item) or item == 'N/A' or item == '[]': return []
        return ast.literal_eval(item)
    except: return []

if 'tech_stack' in df_raw.columns:
    df_raw['tech_stack_lista'] = df_raw['tech_stack'].apply(limpar_lista)
# Cloud ainda existe separado, mas Tech Stack agora engloba tudo
if 'cloud' in df_raw.columns:
    df_raw['cloud_lista'] = df_raw['cloud'].apply(limpar_lista)

# --- NORMALIZAÇÃO E EXPANSÃO DE SKILLS ---
def normalizar_techs(lista_techs):
    if not isinstance(lista_techs, list): return []
    nova_lista = []
    
    # Mapa de EXPANSÃO (1 skill vira várias)
    # Ex: 'Azure Databricks' -> Conta como Azure e como Databricks
    mapa_expansao = {
        'azure databricks': ['Azure', 'Databricks'],
        'azure sql': ['Azure', 'SQL', 'Azure SQL'],
        'azure sql database': ['Azure', 'SQL', 'Azure SQL'],
        'aws glue': ['AWS', 'Glue'],
        'aws lambda': ['AWS', 'Lambda'],
        'google bigquery': ['GCP', 'BigQuery'],
        'bigquery': ['GCP', 'BigQuery']
    }

    # Mapa de SUBSTITUIÇÃO SIMPLES (Padronização)
    mapa_substituicao = {
        'data bricks': 'Databricks',
        'powerbi': 'Power BI',
        'microsoft power bi': 'Power BI',
        'sql server': 'SQL',
        'transact-sql': 'SQL',
        't-sql': 'SQL',
        'amazon web services': 'AWS',
        'gcp': 'GCP',
        'google cloud platform': 'GCP',
        'google cloud': 'GCP',
        'azure': 'Microsoft Azure', # Padroniza nome da cloud
        'microsoft azure': 'Microsoft Azure',
        'excel': 'Excel',
        'ms excel': 'Excel'
    }

    for tech in lista_techs:
        tech_lower = tech.strip().lower()
        
        # 1. Verifica se deve expandir
        if tech_lower in mapa_expansao:
            nova_lista.extend(mapa_expansao[tech_lower])
        
        # 2. Verifica se deve substituir
        elif tech_lower in mapa_substituicao:
            nova_lista.append(mapa_substituicao[tech_lower])
            
        # 3. Mantém original se não houver regra
        else:
            nova_lista.append(tech)
    
    # Remove duplicatas finais (Ex: se já tinha Azure e adicionou Azure de novo)
    return list(set(nova_lista))

# Aplica a normalização nas duas colunas de lista
if 'tech_stack_lista' in df_raw.columns:
    df_raw['tech_stack_lista'] = df_raw['tech_stack_lista'].apply(normalizar_techs)

if 'cloud_lista' in df_raw.columns:
    df_raw['cloud_lista'] = df_raw['cloud_lista'].apply(normalizar_techs)

# --- SIDEBAR (3 FILTROS) ---
st.sidebar.header("🔍 Filtros de Busca")

# 1. Cargo
cargos_unicos = sorted(df_raw['cargo_simplificado'].dropna().unique().tolist())
cargo_selecionado = st.sidebar.selectbox("Área / Cargo:", ["Todos"] + cargos_unicos)

# 2. Senioridade
ordem_senioridade = ["Estágio", "Junior", "Pleno", "Senior", "Especialista", "Gestão", "N/A"]
senioridades_existentes = df_raw['senioridade_simplificada'].dropna().unique().tolist()
senioridades_ordenadas = [s for s in ordem_senioridade if s in senioridades_existentes]
senioridades_ordenadas += [s for s in senioridades_existentes if s not in ordem_senioridade]
senior_selecionado = st.sidebar.selectbox("Nível de Experiência:", ["Todos"] + senioridades_ordenadas)

# 3. Modelo de Trabalho (NOVO)
tipos_unicos = ["Remoto", "Híbrido", "Presencial", "N/A"]
# Filtra apenas os que existem no CSV para não mostrar opção vazia
tipos_existentes = [t for t in tipos_unicos if t in df_raw['tipo_padronizado'].unique()]
tipo_selecionado = st.sidebar.selectbox("Modelo de Trabalho:", ["Todos"] + tipos_existentes)

# --- APLICAR FILTROS ---
df_filtered = df_raw.copy()

if cargo_selecionado != "Todos":
    df_filtered = df_filtered[df_filtered['cargo_simplificado'] == cargo_selecionado]

if senior_selecionado != "Todos":
    df_filtered = df_filtered[df_filtered['senioridade_simplificada'] == senior_selecionado]

if tipo_selecionado != "Todos":
    df_filtered = df_filtered[df_filtered['tipo_padronizado'] == tipo_selecionado]

# --- DASHBOARD ---
st.divider()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Vagas Filtradas", len(df_filtered))
col2.metric("Empresas", df_filtered['empresa'].nunique() if 'empresa' in df_filtered.columns else 0)

# Métrica de Local ou Remoto
if tipo_selecionado == "Todos":
    # Se não filtrou tipo, mostra qual ganha (Ex: Maioria Remoto)
    label_tipo = "Modelo Predominante"
    mode_tipo = df_filtered['tipo_padronizado'].mode()
    val_tipo = mode_tipo[0] if not mode_tipo.empty else "N/A"
    col3.metric(label_tipo, val_tipo)
else:
    # Se já filtrou, mostra o local físico mais comum
    val_local = "N/A"
    if 'local' in df_filtered.columns:
        mode_local = df_filtered['local'].mode()
        val_local = mode_local[0] if not mode_local.empty else "N/A"
    col3.metric("Local Principal", val_local)

# Métrica de Salário/Senioridade
label_info = "Nível Mais Comum"
mode_info = df_filtered['senioridade_simplificada'].mode()
val_info = mode_info[0] if not mode_info.empty else "N/A"
col4.metric(label_info, val_info)

st.divider()

if df_filtered.empty:
    st.info("Nenhuma vaga corresponde aos filtros selecionados.")
else:
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("🛠️ Top Skills (Tech + Cloud)")
        # Como tech_stack agora inclui cloud, esse gráfico mostra tudo
        if 'tech_stack_lista' in df_filtered.columns:
            tech_counts = df_filtered.explode('tech_stack_lista')['tech_stack_lista'].value_counts().head(12).reset_index()
            tech_counts.columns = ['Tecnologia', 'Contagem']
            
            fig_tech = px.bar(tech_counts, x='Contagem', y='Tecnologia', orientation='h', 
                             color='Contagem', color_continuous_scale='viridis', text='Contagem')
            fig_tech.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_tech, use_container_width=True)

    with col_right:
        st.subheader("☁️ Ferramentas de Nuvem (Específico)")
        # Mantivemos este separado para quem quer ver SÓ cloud
        if 'cloud_lista' in df_filtered.columns:
            cloud_counts = df_filtered.explode('cloud_lista')['cloud_lista'].value_counts().head(10).reset_index()
            cloud_counts.columns = ['Ferramenta', 'Contagem']
            
            if not cloud_counts.empty:
                fig_cloud = px.bar(cloud_counts, x='Contagem', y='Ferramenta', orientation='h', 
                                  color='Contagem', color_continuous_scale='magma', text='Contagem')
                fig_cloud.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_cloud, use_container_width=True)
            else:
                st.info("Nenhuma ferramenta de nuvem específica detectada nestas vagas.")

    with st.expander(f"Ver lista de vagas filtradas ({len(df_filtered)})"):
        cols_show = ['titulo', 'cargo_simplificado', 'senioridade_simplificada', 'tipo_padronizado', 'empresa', 'link']
        cols_show = [c for c in cols_show if c in df_filtered.columns]
        st.dataframe(df_filtered[cols_show], hide_index=True)