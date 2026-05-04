import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3

# --- CONFIGURAÇÃO E BANCO DE DADOS ---
conn = sqlite3.connect('manutencao.db', check_same_thread=False)
c = conn.cursor()

def create_tables():
    c.execute('''CREATE TABLE IF NOT EXISTS manutencoes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, curso TEXT, laboratorio TEXT, 
                  tipo TEXT, descricao TEXT, status TEXT, data_entrada TIMESTAMP, 
                  data_saida TIMESTAMP, tempo_total TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios 
                 (username TEXT PRIMARY KEY, password TEXT)''')
    # Criar admin padrão se não existir
    c.execute("INSERT OR IGNORE INTO usuarios (username, password) VALUES ('Admin', '12345')")
    conn.commit()

create_tables()

# --- INTERFACE ---
st.set_page_config(page_title="Sistema de Manutenção", layout="wide")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user_role'] = None

# --- LOGIN ---
if not st.session_state['logged_in']:
    st.title("🔐 Login")
    user = st.text_input("Usuário")
    pw = st.text_input("Senha", type="password")
    if st.button("Entrar"):
        c.execute("SELECT * FROM usuarios WHERE username = ? AND password = ?", (user, pw))
        if c.fetchone():
            st.session_state['logged_in'] = True
            st.session_state['user_role'] = 'Admin' if user == 'Admin' else 'User'
            st.rerun()
        else:
            st.error("Credenciais inválidas")
else:
    # --- MENU LATERAL ---
    menu = ["Nova Manutenção", "Manutenções Pendentes", "Dashboard"]
    if st.session_state['user_role'] == 'Admin':
        menu.append("Gestão de Usuários")
    
    choice = st.sidebar.selectbox("Navegação", menu)
    if st.sidebar.button("Sair"):
        st.session_state['logged_in'] = False
        st.rerun()

    # --- 1. CADASTRO DE MANUTENÇÃO ---
    if choice == "Nova Manutenção":
        st.header("🛠️ Abrir Ordem de Serviço")
        
        col1, col2 = st.columns(2)
        with col1:
            curso = st.selectbox("Curso", ["Odontologia", "Fisioterapia", "Nutrição", "Psicologia", 
                                           "Estética", "Gastronomia", "Biomedicina", "Arquitetura", 
                                           "Eng. Civil", "Agronomia", "ADS"])
            lab = st.text_input("Identificação do Laboratório")
        
        with col2:
            tipo = st.selectbox("Tipo de Manutenção", ["Elétrica", "Hidráulica", "Manutenção Preventiva", 
                                                       "Sanitária", "Ar condicionado"])
            desc = st.text_area("Descrição do Problema")

        if st.button("Registrar Entrada"):
            data_entrada = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            c.execute("INSERT INTO manutencoes (curso, laboratorio, tipo, descricao, status, data_entrada) VALUES (?,?,?,?,?,?)",
                      (curso, lab, tipo, desc, "Pendente", data_entrada))
            conn.commit()
            st.success("Manutenção registrada com sucesso!")

    # --- 2. MANUTENÇÕES PENDENTES (BAIXA) ---
    elif choice == "Manutenções Pendentes":
        st.header("📋 Ordens em Aberto")
        df_pendentes = pd.read_sql("SELECT * FROM manutencoes WHERE status = 'Pendente'", conn)
        
        if not df_pendentes.empty:
            for index, row in df_pendentes.iterrows():
                with st.expander(f"OS #{row['id']} - {row['laboratorio']} ({row['curso']})"):
                    st.write(f"**Tipo:** {row['tipo']}")
                    st.write(f"**Entrada:** {row['data_entrada']}")
                    st.write(f"**Descrição:** {row['descricao']}")
                    
                    if st.button(f"Confirmar Realização #{row['id']}"):
                        data_saida_dt = datetime.now()
                        data_entrada_dt = datetime.strptime(row['data_entrada'], "%Y-%m-%d %H:%M:%S")
                        
                        # Cálculo de tempo
                        duracao = data_saida_dt - data_entrada_dt
                        horas, rem = divmod(duracao.total_seconds(), 3600)
                        minutos, _ = divmod(rem, 60)
                        tempo_str = f"{int(horas)}h {int(minutos)}min"
                        
                        c.execute('''UPDATE manutencoes SET status='Realizado', data_saida=?, tempo_total=? 
                                     WHERE id=?''', (data_saida_dt.strftime("%Y-%m-%d %H:%M:%S"), tempo_str, row['id']))
                        conn.commit()
                        st.rerun()
        else:
            st.info("Não há manutenções pendentes.")

    # --- 3. DASHBOARD ---
    elif choice == "Dashboard":
        st.header("📊 Relatório de Desempenho")
        df_all = pd.read_sql("SELECT * FROM manutencoes WHERE status = 'Realizado'", conn)
        
        if not df_all.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Manutenções por Curso")
                st.bar_chart(df_all['curso'].value_counts())
                
            with col2:
                st.subheader("Tipos mais Frequentes")
                st.table(df_all.groupby(['curso', 'tipo']).size().reset_index(name='Quantidade'))
            
            st.subheader("Histórico Detalhado")
            st.dataframe(df_all[['curso', 'laboratorio', 'tipo', 'data_entrada', 'data_saida', 'tempo_total']])
        else:
            st.warning("Sem dados suficientes para gerar o dashboard.")

    # --- 4. GESTÃO DE USUÁRIOS (ADMIN) ---
    elif choice == "Gestão de Usuários":
        st.header("👥 Cadastro de Usuários")
        new_user = st.text_input("Novo Usuário")
        new_pw = st.text_input("Senha Temporária", type="password")
        if st.button("Cadastrar"):
            try:
                c.execute("INSERT INTO usuarios (username, password) VALUES (?,?)", (new_user, new_pw))
                conn.commit()
                st.success(f"Usuário {new_user} criado!")
            except:
                st.error("Usuário já existe.")
