import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
import io

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
conn = sqlite3.connect('manutencao_v2.db', check_same_thread=False)
c = conn.cursor()

def create_tables():
    c.execute('''CREATE TABLE IF NOT EXISTS manutencoes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, curso TEXT, laboratorio TEXT, 
                  tipo TEXT, descricao TEXT, status TEXT, data_entrada TIMESTAMP, 
                  data_saida TIMESTAMP, tempo_total TEXT)''')
    
    # Migração para coluna de foto
    c.execute("PRAGMA table_info(manutencoes)")
    colunas = [coluna[1] for coluna in c.fetchall()]
    if 'foto' not in colunas:
        c.execute("ALTER TABLE manutencoes ADD COLUMN foto BLOB")
    
    c.execute('CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT)')
    c.execute("INSERT OR IGNORE INTO usuarios (username, password) VALUES ('Admin', '12345')")
    conn.commit()

create_tables()

# --- INTERFACE ---
st.set_page_config(page_title='Sistema de Manutenção Universitário', layout='wide')

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
    st.session_state['user_logged'] = ""

# --- BARRA LATERAL ---
st.sidebar.title('🔐 Área Técnica')
if not st.session_state['logged_in']:
    with st.sidebar:
        user = st.text_input('Usuário')
        pw = st.text_input('Senha', type='password')
        if st.button('Acessar Painel'):
            c.execute('SELECT * FROM usuarios WHERE username = ? AND password = ?', (user, pw))
            if c.fetchone():
                st.session_state['logged_in'] = True
                st.session_state['user_logged'] = user
                st.rerun()
            else:
                st.error('Credenciais inválidas')
else:
    st.sidebar.success(f'Logado como: {st.session_state["user_logged"]}')
    
    # Menu dinâmico baseado no usuário
    opcoes_menu = ['Baixar Manutenções', 'Dashboard']
    if st.session_state['user_logged'] == 'Admin':
        opcoes_menu.append('Gestão de Usuários')
    
    menu_tecnico = st.sidebar.radio('Navegação Técnica', opcoes_menu)
    
    if st.sidebar.button('Sair'):
        st.session_state['logged_in'] = False
        st.session_state['user_logged'] = ""
        st.rerun()

# --- CORPO PRINCIPAL ---
if not st.session_state['logged_in']:
    st.title('🛠️ Reportar Manutenção - Laboratórios')
    with st.form('form_aluno', clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            curso = st.selectbox('Seu Curso', ['Odontologia', 'Fisioterapia', 'Nutrição', 'Psicologia', 'Estética', 'Gastronomia', 'Biomedicina', 'Arquitetura', 'Eng. Civil', 'Agronomia', 'ADS'])
            lab = st.text_input('Nome/Número do Laboratório')
            foto_arquivo = st.file_uploader("Anexar foto (Opcional)", type=['png', 'jpg', 'jpeg'])
        with col2:
            tipo = st.selectbox('Tipo de Problema', ['Elétrica', 'Hidráulica', 'Manutenção Preventiva', 'Sanitária', 'Ar condicionado'])
            desc = st.text_area('Descreva o que precisa ser feito')
        
        if st.form_submit_button('Enviar Solicitação'):
            if lab and desc:
                foto_bytes = foto_arquivo.read() if foto_arquivo else None
                data_entrada = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                c.execute('''INSERT INTO manutencoes (curso, laboratorio, tipo, descricao, status, data_entrada, foto) 
                             VALUES (?,?,?,?,?,?,?)''', (curso, lab, tipo, desc, 'Pendente', data_entrada, foto_bytes))
                conn.commit()
                st.success('Solicitação enviada!')
            else:
                st.warning('Preencha os campos obrigatórios.')
else:
    if menu_tecnico == 'Baixar Manutenções':
        st.title('📋 OS Pendentes')
        df_pendentes = pd.read_sql("SELECT * FROM manutencoes WHERE status = 'Pendente'", conn)
        if not df_pendentes.empty:
            for index, row in df_pendentes.iterrows():
                with st.expander(f"OS #{row['id']} - {row['laboratorio']}"):
                    st.write(f"**Descrição:** {row['descricao']}")
                    if row.get('foto'):
                        st.image(row['foto'], width=300)
                    if st.button(f"Finalizar #{row['id']}", key=f"fin_{row['id']}"):
                        now = datetime.now()
                        c.execute("UPDATE manutencoes SET status='Realizado', data_saida=? WHERE id=?", (now.strftime('%Y-%m-%d %H:%M:%S'), row['id']))
                        conn.commit()
                        st.rerun()
        else:
            st.info('Sem pendências.')

    elif menu_tecnico == 'Dashboard':
        st.title('📊 Relatório de Gestão')
        df_all = pd.read_sql("SELECT * FROM manutencoes WHERE status = 'Realizado'", conn)
        if not df_all.empty:
            st.subheader('Atendimentos por Unidade')
            st.bar_chart(df_all['curso'].value_counts())
            st.dataframe(df_all.drop(columns=['foto'], errors='ignore'))
            
            # Exportação
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_all.drop(columns=['foto'], errors='ignore').to_excel(writer, index=False)
            st.download_button('📥 Baixar Planilha Completa', output.getvalue(), 'relatorio_final.xlsx')

    elif menu_tecnico == 'Gestão de Usuários':
        st.title('👥 Gestão de Equipe Técnica')
        
        # Parte 1: Cadastro
        with st.expander("➕ Cadastrar Novo Técnico"):
            with st.form('novo_tecnico'):
                new_user = st.text_input('Login')
                new_pw = st.text_input('Senha', type='password')
                if st.form_submit_button('Salvar'):
                    try:
                        c.execute('INSERT INTO usuarios VALUES (?,?)', (new_user, new_pw))
                        conn.commit()
                        st.success(f'Usuário {new_user} criado.')
                        st.rerun()
                    except:
                        st.error('Erro: Usuário já existe.')

        # Parte 2: Listagem e Exclusão
        st.subheader("Técnicos Ativos")
        usuarios_df = pd.read_sql("SELECT username FROM usuarios", conn)
        for u in usuarios_df['username']:
            col_u, col_b = st.columns([3, 1])
            col_u.write(f"👤 {u}")
            if u != 'Admin': # Impede excluir o admin principal
                if col_b.button(f"Excluir", key=f"del_{u}"):
                    c.execute("DELETE FROM usuarios WHERE username = ?", (u,))
                    conn.commit()
                    st.warning(f"Usuário {u} removido.")
                    st.rerun()
            else:
                col_b.write("*(Principal)*")
