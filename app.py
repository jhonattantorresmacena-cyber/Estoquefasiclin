import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
import io

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
# DICA: Em servidores como Streamlit Cloud, arquivos .db locais são temporários.
conn = sqlite3.connect('manutencao_v2.db', check_same_thread=False)
c = conn.cursor()

def create_tables():
    # Criação da tabela principal garantindo que os dados persistam
    c.execute('''CREATE TABLE IF NOT EXISTS manutencoes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, curso TEXT, laboratorio TEXT, 
                  tipo TEXT, descricao TEXT, status TEXT, data_entrada TIMESTAMP, 
                  data_saida TIMESTAMP, tempo_total TEXT, foto BLOB, tecnico_responsavel TEXT)''')
    
    c.execute('CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT)')
    c.execute("INSERT OR IGNORE INTO usuarios (username, password) VALUES ('Admin', '12345')")
    conn.commit()

create_tables()

# --- INTERFACE ---
st.set_page_config(page_title='Sistema de Manutenção Universitário', layout='wide')

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
    nome_usuario = st.session_state.get('user_logged', 'Usuário')
    st.sidebar.success(f'Logado como: {nome_usuario}')
    
    # Menu com Histórico para todos verem o que já foi feito
    if nome_usuario == 'Admin':
        opcoes_menu = ['OS Pendentes', 'Histórico Geral', 'Dashboard', 'Gestão de Usuários']
    else:
        opcoes_menu = ['OS Pendentes', 'Histórico Geral']
    
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
            desc = st.text_area('Descreva o problema')
        
        if st.form_submit_button('Enviar Solicitação'):
            if lab and desc:
                foto_bytes = foto_arquivo.read() if foto_arquivo else None
                data_e = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                c.execute('''INSERT INTO manutencoes (curso, laboratorio, tipo, descricao, status, data_entrada, foto) 
                             VALUES (?,?,?,?,?,?,?)''', (curso, lab, tipo, desc, 'Pendente', data_e, foto_bytes))
                conn.commit()
                st.success('Solicitação enviada com sucesso! Ela ficará salva até que um técnico a finalize.')
            else:
                st.warning('Preencha os campos obrigatórios.')

else:
    if menu_tecnico == 'OS Pendentes':
        st.title('📋 Ordens de Serviço em Aberto')
        # Aqui garantimos que buscamos tudo que não foi finalizado, independente do tempo
        df_p = pd.read_sql("SELECT * FROM manutencoes WHERE status = 'Pendente' ORDER BY data_entrada DESC", conn)
        
        if not df_p.empty:
            for _, row in df_p.iterrows():
                with st.expander(f"OS #{row['id']} - {row['laboratorio']} ({row['curso']})"):
                    st.info(f"Registrado em: {row['data_entrada']}")
                    st.write(f"**Descrição:** {row['descricao']}")
                    if row['foto']:
                        st.image(row['foto'], width=300)
                    
                    if st.button(f"Finalizar Manutenção #{row['id']}", key=f"fin_{row['id']}"):
                        data_s_dt = datetime.now()
                        data_s_str = data_s_dt.strftime('%Y-%m-%d %H:%M:%S')
                        tecnico = st.session_state['user_logged']
                        
                        # Cálculo de tempo
                        data_e_dt = datetime.strptime(row['data_entrada'], '%Y-%m-%d %H:%M:%S')
                        diff = data_s_dt - data_e_dt
                        horas, rem = divmod(diff.total_seconds(), 3600)
                        minutos, _ = divmod(rem, 60)
                        tempo_total = f"{int(horas)}h {int(minutos)}min"
                        
                        c.execute('''UPDATE manutencoes 
                                     SET status='Realizado', data_saida=?, tecnico_responsavel=?, tempo_total=? 
                                     WHERE id=?''', (data_s_str, tecnico, tempo_total, row['id']))
                        conn.commit()
                        st.success("Manutenção movida para o histórico!")
                        st.rerun()
        else:
            st.info('Nenhuma manutenção pendente no momento.')

    elif menu_tecnico == 'Histórico Geral':
        st.title('📚 Histórico de Manutenções')
        status_filtro = st.selectbox('Filtrar por Status', ['Todos', 'Realizado', 'Pendente'])
        
        query = "SELECT * FROM manutencoes"
        if status_filtro != 'Todos':
            query += f" WHERE status = '{status_filtro}'"
        
        df_hist = pd.read_sql(query, conn)
        st.dataframe(df_hist.drop(columns=['foto'], errors='ignore'), use_container_width=True)

    elif menu_tecnico == 'Dashboard':
        st.title('📊 Relatório de Gestão (Admin)')
        df_all = pd.read_sql("SELECT * FROM manutencoes WHERE status = 'Realizado'", conn)
        if not df_all.empty:
            st.subheader('Atendimentos por Unidade')
            st.bar_chart(df_all['curso'].value_counts())
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export = df_all.drop(columns=['foto'], errors='ignore')
                df_export.to_excel(writer, index=False, sheet_name='Relatorio')
            st.download_button('📥 Baixar Planilha Excel', output.getvalue(), 'relatorio_manutencao.xlsx')
        else:
            st.warning('Nenhuma manutenção finalizada para gerar gráficos.')

    elif menu_tecnico == 'Gestão de Usuários':
        # ... (Mantido o código original de gestão de usuários)
        st.title('👥 Gestão de Equipe')
        with st.form('cad_tec'):
            n_user = st.text_input('Login do Novo Técnico')
            n_pw = st.text_input('Senha', type='password')
            if st.form_submit_button('Cadastrar'):
                try:
                    c.execute('INSERT INTO usuarios VALUES (?,?)', (n_user, n_pw))
                    conn.commit()
                    st.success(f'Técnico {n_user} cadastrado!')
                    st.rerun()
                except: st.error('Erro ao cadastrar.')
