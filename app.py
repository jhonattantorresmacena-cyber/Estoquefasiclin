import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
import io

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
conn = sqlite3.connect('manutencao_v2.db', check_same_thread=False)
c = conn.cursor()

def create_tables():
    # Tabela principal
    c.execute('''CREATE TABLE IF NOT EXISTS manutencoes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, curso TEXT, laboratorio TEXT, 
                  tipo TEXT, descricao TEXT, status TEXT, data_entrada TIMESTAMP, 
                  data_saida TIMESTAMP, tempo_total TEXT)''')
    
    # Migração Automática de Colunas (Foto e Técnico)
    c.execute("PRAGMA table_info(manutencoes)")
    colunas = [coluna[1] for coluna in c.fetchall()]
    if 'foto' not in colunas:
        c.execute("ALTER TABLE manutencoes ADD COLUMN foto BLOB")
    if 'tecnico_responsavel' not in colunas:
        c.execute("ALTER TABLE manutencoes ADD COLUMN tecnico_responsavel TEXT")
    
    # Tabela de Usuários
    c.execute('CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT)')
    c.execute("INSERT OR IGNORE INTO usuarios (username, password) VALUES ('Admin', '12345')")
    conn.commit()

create_tables()

# --- INTERFACE ---
st.set_page_config(page_title='Sistema de Manutenção Universitário', layout='wide')

# Inicialização segura do estado da sessão
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_logged' not in st.session_state:
    st.session_state['user_logged'] = ""

# --- BARRA LATERAL ---
st.sidebar.title('🔐 Área Técnica')
if not st.session_state['logged_in']:
    with st.sidebar:
        user_input = st.text_input('Usuário')
        pw_input = st.text_input('Senha', type='password')
        if st.button('Acessar Painel'):
            c.execute('SELECT * FROM usuarios WHERE username = ? AND password = ?', (user_input, pw_input))
            if c.fetchone():
                st.session_state['logged_in'] = True
                st.session_state['user_logged'] = user_input
                st.rerun()
            else:
                st.error('Credenciais inválidas')
else:
    # Correção do erro da imagem: Uso de .get() para evitar KeyError
    nome_usuario = st.session_state.get('user_logged', 'Usuário')
    st.sidebar.success(f'Logado como: {nome_usuario}')
    
    opcoes_menu = ['Baixar Manutenções', 'Dashboard']
    if nome_usuario == 'Admin':
        opcoes_menu.append('Gestão de Usuários')
    
    menu_tecnico = st.sidebar.radio('Navegação Técnica', opcoes_menu)
    
    if st.sidebar.button('Sair'):
        st.session_state['logged_in'] = False
        st.session_state['user_logged'] = ""
        st.rerun()

# --- CORPO PRINCIPAL (VISÃO PÚBLICA) ---
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
            desc = st.text_area('Descreva o problema')
        
        if st.form_submit_button('Enviar Solicitação'):
            if lab and desc:
                foto_bytes = foto_arquivo.read() if foto_arquivo else None
                data_e = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                c.execute('''INSERT INTO manutencoes (curso, laboratorio, tipo, descricao, status, data_entrada, foto) 
                             VALUES (?,?,?,?,?,?,?)''', (curso, lab, tipo, desc, 'Pendente', data_e, foto_bytes))
                conn.commit()
                st.success('Solicitação enviada!')
            else:
                st.warning('Preencha os campos obrigatórios.')
else:
    # --- ÁREA TÉCNICA ---
    if menu_tecnico == 'Baixar Manutenções':
        st.title('📋 OS Pendentes')
        df_p = pd.read_sql("SELECT * FROM manutencoes WHERE status = 'Pendente'", conn)
        if not df_p.empty:
            for _, row in df_p.iterrows():
                with st.expander(f"OS #{row['id']} - {row['laboratorio']} ({row['curso']})"):
                    st.write(f"**Descrição:** {row['descricao']}")
                    if row['foto']:
                        st.image(row['foto'], width=300)
                    
                    if st.button(f"Confirmar Realização #{row['id']}", key=f"fin_{row['id']}"):
                        data_s = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        tecnico = st.session_state['user_logged']
                        c.execute('''UPDATE manutencoes 
                                     SET status='Realizado', data_saida=?, tecnico_responsavel=? 
                                     WHERE id=?''', (data_s, tecnico, row['id']))
                        conn.commit()
                        st.success("OS Finalizada!")
                        st.rerun()
        else:
            st.info('Nenhuma pendência encontrada.')

    elif menu_tecnico == 'Dashboard':
        st.title('📊 Relatório de Gestão')
        df_all = pd.read_sql("SELECT * FROM manutencoes WHERE status = 'Realizado'", conn)
        if not df_all.empty:
            st.subheader('Desempenho por Unidade')
            st.bar_chart(df_all['curso'].value_counts())
            
            # Exibição da Tabela com a nova coluna de Técnico
            col_ver = ['id', 'curso', 'laboratorio', 'tipo', 'data_entrada', 'data_saida', 'tecnico_responsavel']
            st.dataframe(df_all[col_ver], use_container_width=True)
            
            # Exportação com Técnico Responsável
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export = df_all.drop(columns=['foto'], errors='ignore')
                df_export.to_excel(writer, index=False, sheet_name='Relatorio')
            st.download_button('📥 Exportar Planilha (Rastreabilidade)', output.getvalue(), 'relatorio_manutencao.xlsx')
        else:
            st.warning('Sem manutenções concluídas para gerar relatório.')

    elif menu_tecnico == 'Gestão de Usuários':
        st.title('👥 Gestão de Equipe')
        with st.form('cad_tec'):
            n_user = st.text_input('Novo Técnico')
            n_pw = st.text_input('Senha', type='password')
            if st.form_submit_button('Cadastrar'):
                try:
                    c.execute('INSERT INTO usuarios VALUES (?,?)', (n_user, n_pw))
                    conn.commit()
                    st.success(f'Técnico {n_user} cadastrado!')
                    st.rerun()
                except: st.error('Erro ao cadastrar.')

        st.subheader("Técnicos do Sistema")
        users_db = pd.read_sql("SELECT username FROM usuarios", conn)
        for u in users_db['username']:
            c1, c2 = st.columns([3, 1])
            c1.write(f"👤 {u}")
            if u != 'Admin' and c2.button('Excluir', key=f'del_{u}'):
                c.execute("DELETE FROM usuarios WHERE username = ?", (u,))
                conn.commit()
                st.rerun()
```[cite: 1]
