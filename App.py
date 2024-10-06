import os
import bcrypt
import smtplib
import streamlit as st
import pandas as pd
import streamlit_authenticator as stauth
from dotenv import load_dotenv
from email.mime.text import MIMEText
from sklearn.preprocessing import MinMaxScaler
import matplotlib.pyplot as plt

# Carrega as variáveis de ambiente
load_dotenv()

# Função para gerar um hash da senha
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

# Função para verificar a senha
def check_password(plain_text_password, hashed_password):
    return bcrypt.checkpw(plain_text_password.encode(), hashed_password.encode())   


# Função para enviar email
def send_email(to_email, password):
    msg = MIMEText(f"Sua senha é: {password}")
    msg["Subject"] = "Sua senha"
    msg["From"] = os.getenv("EMAIL_ADDRESS")
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.getenv("EMAIL_ADDRESS"), os.getenv("EMAIL_PASSWORD"))
        server.sendmail(os.getenv("EMAIL_ADDRESS"), to_email, msg.as_string())

# Nomes de usuário, senhas e e-mails
names = ["Fulano de Tal", "Ciclano"]
usernames = ["fulano", "ciclano"]
passwords = [hash_password("senha123"), hash_password("outrasenha")]  # Lista de strings
emails = ["fulano@email.com", "ciclano@email.com"]

# Cria o autenticador
authenticator = stauth.Authenticate(
    names,
    usernames,
    passwords,
    "avaliacao_jogadores",  # Nome do cookie
    "abcdefg",  # Chave secreta para criptografar o cookie
    cookie_expiry_days=30,
)

# Tela de login
name, authentication_status, username = authenticator.login("Login", "main")

if authentication_status:
    st.write(f"Bem-vindo, {name}!")
    # Seu código do aplicativo aqui
    st.title('Formulário de Avaliação de Jogadores')

# Caching the position groups to avoid redefinition
@st.cache_data
def agrupar_posicoes_em_portugues():
    return {
        'Goleiros': ['GK'],
        'Laterais Direitos': ['RD'],
        'Laterais Esquerdos': ['LD'],
        'Zagueiros': ['CD', 'LCD', 'RCD'],
        'Volantes/Meio defensivos': ['CDM', 'RCDM', 'LCDM', 'LDM', 'RDM'],
        'Segundos Volantes': ['RCM', 'LCM'],
        'Meio-Atacantes': ['CAM'],
        'Extremos/Pontas': list(set(['LM', 'RM', 'LCF', 'RCF', 'LAM', 'RAM'])),
        'Atacantes': ['CF']
    }

def calcular_pontuacao(df, posicoes, tier1_cols, tier2_cols, tier3_cols, tier_weights, min_minutos, max_minutos, max_idade):
    df['Age'] = pd.to_numeric(df['Age'], errors='coerce')
    df_filtered = df[
        df['Position'].isin(posicoes) & 
        (df['Minutes played'] >= min_minutos) &
        (df['Minutes played'] <= max_minutos) &
        (df['Age'] <= max_idade)
    ].copy()

    if df_filtered.empty:
        st.warning("Nenhum jogador encontrado para as condições especificadas.")
        return pd.DataFrame()

    required_metrics = tier1_cols + tier2_cols + tier3_cols
    missing_cols = [col for col in required_metrics if col not in df_filtered.columns]
    if missing_cols:
        st.error(f"As seguintes métricas estão faltando no arquivo: {missing_cols}")
        return pd.DataFrame()

    # Replace and convert columns
    for col in required_metrics:
        df_filtered[col] = df_filtered[col].astype(str).str.replace('-', '0').str.replace('%', '')
        df_filtered[col] = pd.to_numeric(df_filtered[col], errors='coerce').fillna(0)

    # Normalize using Min-Max Scaler
    scaler = MinMaxScaler(feature_range=(0, 10))
    df_filtered[[col + '_norm' for col in required_metrics]] = scaler.fit_transform(df_filtered[required_metrics])

    # Calculate tier scores
    df_filtered['Tier 1'] = df_filtered[[col + '_norm' for col in tier1_cols]].mean(axis=1)
    df_filtered['Tier 2'] = df_filtered[[col + '_norm' for col in tier2_cols]].mean(axis=1)
    df_filtered['Tier 3'] = df_filtered[[col + '_norm' for col in tier3_cols]].mean(axis=1)

    # Final Score
    df_filtered['Pontuação Final'] = (
        tier_weights['Tier 1'] * df_filtered['Tier 1'] +
        tier_weights['Tier 2'] * df_filtered['Tier 2'] +
        tier_weights['Tier 3'] * df_filtered['Tier 3']
    )

    # Impact per Minute
    df_filtered['Impacto por Minuto'] = (df_filtered['Pontuação Final'] / df_filtered['Minutes played']) * 1000

    return df_filtered

def definir_tiers_por_grupo(grupo_escolhido):
    tiers = {
        'Goleiros': (
            ['Goals Conceded', 'Saves', 'Clean sheets'],
            ['Passes', 'Passes accurate, %', 'Long Passes', 'Long Passes Completed'],
            ['Crosses', 'Crosses won', 'Goal Kicks', 'Tackles successful']
        ),
        'Laterais Direitos': (
            ['Defensive challenges', 'Defensive challenges won, %', 'Final third entries', 'Final third entries through carry', 'Crosses', 'Crosses accurate'],
            ['Tackles', 'Tackles successful', 'Interceptions'],
            ['Passes', 'Passes accurate, %', 'Progressive passes', 'Long passes', 'Long passes accurate', 'Attacking challenges', 'Attacking challenges won, %','Goals']
        ),
        'Laterais Esquerdos': (
            ['Defensive challenges', 'Defensive challenges won, %', 'Final third entries', 'Final third entries through carry', 'Crosses', 'Crosses accurate'],
            ['Tackles', 'Tackles successful', 'Interceptions'],
            ['Passes', 'Passes accurate, %', 'Progressive passes', 'Long passes', 'Long passes accurate', 'Attacking challenges', 'Attacking challenges won, %','Goals']
        ),
        'Zagueiros': (
            ['Defensive challenges', 'Defensive challenges won, %', 'Air challenges', 'Air challenges won'],
            ['Tackles', 'Tackles successful', 'Interceptions', 'Passes accurate, %', 'Passes'],
            ['Challenges', 'Challenges won', 'Progressive passes', 'Progressive passes accurate', 'Crosses', 'Crosses accurate','Goals']
        ),
        'Segundos Volantes': (
            ['Defensive challenges', 'Defensive challenges won, %', 'Interceptions','Passes', 'Passes accurate, %', 'Progressive passes', 'Progressive passes accurate'],
            ['Tackles', 'Tackles successful', 'Crosses', 'Crosses accurate', 'Picking up', 'Key passes', 'Key passes accurate'],
            ['Challenges', 'Challenges won, %', 'Long passes', 'Long passes accurate', 'Attacking challenges', 'Attacking challenges won, %', 'Final third entries', 'Final third entries through carry', 'Shots', 'Shots on target', 'Goals']
        ),
        'Volantes/Meio defensivos': (
            ['Defensive challenges', 'Defensive challenges won', 'Picking up'],
            ['Tackles', 'Tackles successful', 'Interceptions', 'Crosses', 'Crosses accurate', 'Passes', 'Passes accurate, %'],
            ['Challenges', 'Challenges won, %', 'Progressive passes', 'Progressive passes accurate', 'Long passes', 'Long passes accurate', 'Attacking challenges', 'Attacking challenges won, %','Goals']
        ),
        'Meio-Atacantes': (
            ['Passes', 'Passes accurate, %', 'Key passes', 'Key passes accurate', 'Progressive passes', 'Progressive passes accurate'],
            ['Passes into the penalty box', 'Passes into the penalty box accurate', 'Final third entries', 'Final third entries through carry', 'Shots', 'Shots on target','Goals'],
            ['Challenges', 'Challenges won, %', 'Defensive challenges', 'Defensive challenges won, %', 'Attacking challenges', 'Attacking challenges won, %', 'Tackles', 'Tackles successful', 'Interceptions', 'Crosses', 'Crosses accurate']
        ),
        'Extremos/Pontas': (
            ['Final third entries', 'Final third entries through carry', 'Crosses', 'Crosses accurate', 'Dribbles', 'Dribbles successful, %','Goals'],
            ['Chances', 'Chances successful', 'Chances successful, %', 'Shots', 'Shots on target', 'Key passes', 'Key passes accurate', 'Passes into the penalty box', 'Passes into the penalty box accurate'],
            ['Challenges', 'Challenges won, %', 'Defensive challenges', 'Defensive challenges won, %', 'Attacking challenges', 'Attacking challenges won, %', 'Tackles', 'Tackles successful', 'Interceptions', 'Crosses', 'Crosses accurate']
        ),
        'Atacantes': (
            ['Goals', 'xG', 'Shots on target', 'Shots on target, %', 'Final third entries', 'Final third entries through carry'],
            ['Actions', 'Actions successful', 'Actions successful, %', 'Assists', 'Chances', 'Chances successful'],
            ['Chances successful, %', 'Shots', 'Shots off target', 'Shots blocked', 'Shots on post / bar', 'Ball recoveries', 'Ball recoveries in opponent\'s half']
        )
    }
    return tiers.get(grupo_escolhido, ([], [], []))

# Pesos dos tiers (now adjustable by the user)
tier_weights = {'Tier 1': 0.6, 'Tier 2': 0.3, 'Tier 3': 0.1}

# --- Interface do Streamlit ---
st.set_page_config(page_title='Avaliação de Jogadores', layout='wide')
st.title('Formulário de Avaliação de Jogadores')

# Sidebar for configuration
st.sidebar.header("Configurações")

# Permitir upload de até 30 arquivos
uploaded_files = st.sidebar.file_uploader(
    "Escolha até 30 arquivos de dados (CSV ou XLSX)", 
    type=["xlsx", "csv"], 
    accept_multiple_files=True
)

if uploaded_files:
    if len(uploaded_files) > 30:
        st.sidebar.error("Você pode fazer upload de no máximo 30 arquivos.")
        st.stop()
    
    # Lista para armazenar DataFrames
    dataframes = []
    # Lista para rastrear arquivos com erro
    erro_arquivos = []

    # Carregar cada arquivo
    for uploaded_file in uploaded_files:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_temp = pd.read_csv(uploaded_file, encoding='latin1')
            elif uploaded_file.name.endswith('.xlsx'):
                df_temp = pd.read_excel(uploaded_file)
            dataframes.append(df_temp)
        except Exception as e:
            erro_arquivos.append(f"{uploaded_file.name}: {e}")

    # Se houver erros no carregamento de algum arquivo, exibir mensagens de erro
    if erro_arquivos:
        for erro in erro_arquivos:
            st.error(f"Erro ao carregar o arquivo {erro}")
        st.stop()

    # Concatenar todos os DataFrames
    try:
        df = pd.concat(dataframes, ignore_index=True)
    except Exception as e:
        st.error(f"Erro ao concatenar os arquivos: {e}")
        st.stop()

    # Validar colunas essenciais
    required_columns = ['Player', 'Team', 'Age', 'Minutes played', 'Position']
    missing_required = [col for col in required_columns if col not in df.columns]
    if missing_required:
        st.error(f"Faltam as seguintes colunas essenciais no(s) arquivo(s): {missing_required}")
        st.stop()

    grupos_posicoes = agrupar_posicoes_em_portugues()
    grupo_escolhido = st.sidebar.selectbox('Selecione o grupo de posições:', list(grupos_posicoes.keys()))
    posicoes_selecionadas = grupos_posicoes[grupo_escolhido]

    # Filtros
    st.sidebar.subheader("Filtros")
    min_minutos = st.sidebar.number_input('Minutos jogados mínimos:', min_value=0, value=200, step=50)
    max_minutos = st.sidebar.number_input('Minutagem máxima (opcional):', min_value=0, value=3000, step=500)
    max_idade = st.sidebar.number_input('Idade máxima:', min_value=0, value=40, step=1)

    # Definir os Tiers de acordo com o grupo de posições escolhido
    tier1_cols, tier2_cols, tier3_cols = definir_tiers_por_grupo(grupo_escolhido)

    # Ajuste de pesos pelo usuário
    st.sidebar.subheader("Pesos dos Tiers")
    tier_weights['Tier 1'] = st.sidebar.slider('Peso Tier 1', 0.0, 1.0, 0.6, step=0.05)
    tier_weights['Tier 2'] = st.sidebar.slider('Peso Tier 2', 0.0, 1.0, 0.3, step=0.05)
    tier_weights['Tier 3'] = st.sidebar.slider('Peso Tier 3', 0.0, 1.0, 0.1, step=0.05)
    total_weight = sum(tier_weights.values())
    if total_weight != 1.0:
        st.sidebar.warning("A soma dos pesos deve ser igual a 1. Ajustando automaticamente.")
        tier_weights = {k: v / total_weight for k, v in tier_weights.items()}

    # Calcular a pontuação
    resultados = calcular_pontuacao(
        df, posicoes_selecionadas, tier1_cols, tier2_cols, tier3_cols,
        tier_weights, min_minutos, max_minutos, max_idade
    )

    # Exibir os resultados
    if not resultados.empty:
        st.subheader("Resultados")
        sorted_results = resultados[['Player', 'Team', 'Age', 'Minutes played', 'Pontuação Final', 'Impacto por Minuto']].sort_values('Pontuação Final', ascending=False).reset_index(drop=True)

        # Formatação das colunas
        formatted_results = sorted_results.style \
            .highlight_max(subset=['Pontuação Final'], color='lightgreen') \
            .format({
                'Age': '{:.0f}',
                'Pontuação Final': '{:.1f}',
                'Impacto por Minuto': '{:.1f}'
            }) \
            .hide(axis="index")  # Remove a exibição do índice

        st.dataframe(formatted_results, height=600)

        # Visualizações com Matplotlib com tamanho reduzido
        st.subheader("Distribuição das Pontuações Finais")
        fig, ax = plt.subplots(figsize=(5, 3))  # Tamanho reduzido: largura=5, altura=3
        ax.hist(sorted_results['Pontuação Final'], bins=20, color='skyblue', edgecolor='black')
        ax.set_xlabel('Pontuação Final')
        ax.set_ylabel('Frequência')
        ax.set_title('Distribuição das Pontuações Finais')
        plt.tight_layout()  # Ajusta o layout para evitar cortes
        st.pyplot(fig)

        st.subheader("Top 10 Jogadores")
        top_players = sorted_results.head(10)
        fig2, ax2 = plt.subplots(figsize=(5, 3))  # Tamanho reduzido: largura=5, altura=3
        ax2.barh(top_players['Player'], top_players['Pontuação Final'], color='green')
        ax2.set_xlabel('Pontuação Final')
        ax2.set_title('Top 10 Jogadores')
        ax2.invert_yaxis()  # Para exibir o maior valor no topo
        plt.tight_layout()  # Ajusta o layout para evitar cortes
        st.pyplot(fig2)

        # Opcional: Botão para baixar os resultados
        csv = sorted_results.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Baixar Resultados como CSV",
            data=csv,
            file_name='resultados_pontuacao.csv',
            mime='text/csv',
        )

else:
    st.info("Por favor, faça o upload de até 30 arquivos CSV ou XLSX para começar.")
