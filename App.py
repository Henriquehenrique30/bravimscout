import streamlit as st
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
import matplotlib.pyplot as plt
import streamlit_authenticator as stauth
import bcrypt
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os

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
passwords = [hash_password("senha123"), hash_password("outrasenha")]
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
                ['Passes into the penalty box', 'Passes into the penalty box accurate', 'Final third entries
