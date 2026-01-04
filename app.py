import streamlit as st
import pandas as pd
import ast
import plotly.express as px

# 1. Configuração da Página
st.set_page_config(page_title="Job Hunter Skills", layout="wide", page_icon="💼")

# --- CSS para deixar bonito ---
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

st.title("💼 Job Hunter AI: Análise de Mercado Tech")
st.markdown("Descubra as tecnologias e skills mais pedidas nas vagas do LinkedIn.")

# 2. Carregar Dados
@st.cache_data
def load_data():
    try:
        df = pd.read_csv('dados_vagas_linkedin.csv')
        return df
    except FileNotFoundError:
        return pd.DataFrame()

df_raw = load_data()

# 3. Verificar se tem dados
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
if 'cloud' in df_raw.columns:
    df_raw['cloud_lista'] = df_raw['cloud'].apply(limpar_lista)

# --- SIDEBAR (FILTROS) ---
st.sidebar.header("🔍 Filtros de Busca")

# Filtro 1: Cargo (Título da Vaga)
# Pegamos todos os títulos únicos do CSV para não errar
cargos_unicos = sorted(df_raw['titulo'].dropna().unique().tolist())
# Adicionamos a opção "Todos" no começo
opcoes_cargo = ["Todos"] + cargos_unicos
cargo_selecionado = st.sidebar.selectbox("Escolha o Cargo:", opcoes_cargo)

# Filtro 2: Senioridade (Se a coluna existir)
if 'senioridade' in df_raw.columns:
    senioridades = sorted(df_raw['senioridade'].dropna().unique().tolist())
    opcoes_senior = ["Todas"] + senioridades
    senior_selecionado = st.sidebar.selectbox("Nível de Senioridade:", opcoes_senior)
else:
    senior_selecionado = "Todas"

# --- APLICAR FILTROS ---
df_filtered = df_raw.copy()

if cargo_selecionado != "Todos":
    df_filtered = df_filtered[df_filtered['titulo'] == cargo_selecionado]

if senior_selecionado != "Todas":
    df_filtered = df_filtered[df_filtered['senioridade'] == senior_selecionado]

# --- DASHBOARD (Usando df_filtered) ---

st.divider()

# Métricas
col1, col2, col3, col4 = st.columns(4)
col1.metric("Vagas Encontradas", len(df_filtered))
col2.metric("Empresas Únicas", df_filtered['empresa'].nunique() if 'empresa' in df_filtered.columns else 0)
col3.metric("Local Principal", df_filtered['local'].mode()[0] if not df_filtered.empty and 'local' in df_filtered.columns else "N/A")
# Se filtrou cargo, mostra o salário ou senioridade comum. Se não, mostra o cargo top.
if cargo_selecionado != "Todos":
    top_info = df_filtered['senioridade'].mode()[0] if 'senioridade' in df_filtered.columns and not df_filtered.empty else "N/A"
    label_info = "Senioridade Comum"
else:
    top_info = df_filtered['titulo'].mode()[0] if not df_filtered.empty else "N/A"
    label_info = "Cargo Mais Ofertado"
col4.metric(label_info, top_info)

st.divider()

if df_filtered.empty:
    st.info("Nenhuma vaga corresponde aos filtros selecionados.")
else:
    # Gráficos Lado a Lado
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("🛠️ Top Hard Skills")
        if 'tech_stack_lista' in df_filtered.columns:
            tech_counts = df_filtered.explode('tech_stack_lista')['tech_stack_lista'].value_counts().head(10).reset_index()
            tech_counts.columns = ['Tecnologia', 'Contagem']
            
            fig_tech = px.bar(tech_counts, x='Contagem', y='Tecnologia', orientation='h', 
                             color='Contagem', color_continuous_scale='viridis', text='Contagem')
            fig_tech.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_tech, use_container_width=True)

    with col_right:
        st.subheader("☁️ Cloud & Infra")
        if 'cloud_lista' in df_filtered.columns:
            cloud_counts = df_filtered.explode('cloud_lista')['cloud_lista'].value_counts().head(10).reset_index()
            cloud_counts.columns = ['Ferramenta', 'Contagem']
            
            if not cloud_counts.empty:
                fig_cloud = px.bar(cloud_counts, x='Contagem', y='Ferramenta', orientation='h', 
                                  color='Contagem', color_continuous_scale='magma', text='Contagem')
                fig_cloud.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_cloud, use_container_width=True)
            else:
                st.info("Sem dados de Cloud para essa seleção.")

    # Tabela de Dados
    with st.expander(f"Ver detalhes das {len(df_filtered)} vagas"):
        cols_show = [c for c in ['data_coleta', 'titulo', 'empresa', 'local', 'senioridade', 'link'] if c in df_filtered.columns]
        st.dataframe(df_filtered[cols_show], hide_index=True)