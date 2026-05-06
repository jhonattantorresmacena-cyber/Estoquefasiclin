import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
import io

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
conn = sqlite3.connect('manutencao_v2.db', check_same_thread=False)
c = conn.cursor()

def create_tables():
    # Cria as tabelas básicas se não existirem
    c.execute('''CREATE TABLE IF NOT EXISTS manutencoes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, curso TEXT, laboratorio TEXT, 
                  tipo TEXT, descricao TEXT, status TEXT, data_entrada TIMESTAMP, 
                  data_saida TIMESTAMP, tempo_total TEXT)''')
    
    # LÓGICA DE MIGRAÇÃO: Verifica se a coluna 'foto' existe, se não, adiciona
    c.execute("PRAGMA table_info(manutencoes)")
    colunas = [coluna[1] for coluna in c.fetchall()]
    if 'foto' not in colunas:
        c.execute("ALTER TABLE manutencoes ADD COLUMN foto BLOB")
        conn.commit()

    c.execute('CREATE TABLE IF NOT EXISTS usuarios (username TEXT PRIMARY KEY, password TEXT)')
    c.execute("INSERT OR IGNORE INTO usuarios (username, password) VALUES ('Admin', '12345')")
    conn.commit()

create_tables()

# --- INTERFACE ---
st.set_page_config(page_title='Sistema de Manutenção Universitário', layout='wide')

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

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
                st.rerun()
            else:
                st.error('Credenciais inválidas')
else:
    st.sidebar.success('Logado como: Equipe Técnica')
    menu_tecnico = st.sidebar.radio('Navegação Técnica', ['Baixar Manutenções', 'Dashboard', 'Gestão de Usuários'])
    if st.sidebar.button('Sair'):
        st.session_state['logged_in'] = False
        st.rerun()

# --- CORPO PRINCIPAL ---
if not st.session_state['logged_in']:
    st.title('🛠️ Reportar Manutenção - Laboratórios')
    st.info('Utilize este formulário para informar qualquer problema técnico.')
    
    with st.form('form_aluno', clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            curso = st.selectbox('Seu Curso', ['Odontologia', 'Fisioterapia', 'Nutrição', 'Psicologia', 'Estética', 'Gastronomia', 'Biomedicina', 'Arquitetura', 'Eng. Civil', 'Agronomia', 'ADS'])
            lab = st.text_input('Nome/Número do Laboratório')
            foto_arquivo = st.file_uploader("Anexar foto do problema (Opcional)", type=['png', 'jpg', 'jpeg'])
        with col2:
            tipo = st.selectbox('Tipo de Problema', ['Elétrica', 'Hidráulica', 'Manutenção Preventiva', 'Sanitária', 'Ar condicionado'])
            desc = st.text_area('Descreva o que precisa ser feito')
        
        enviar = st.form_submit_button('Enviar Solicitação')
        if enviar:
            if lab and desc:
                foto_bytes = foto_arquivo.read() if foto_arquivo else None
                data_entrada = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                c.execute('''INSERT INTO manutencoes (curso, laboratorio, tipo, descricao, status, data_entrada, foto) 
                             VALUES (?,?,?,?,?,?,?)''', (curso, lab, tipo, desc, 'Pendente', data_entrada, foto_bytes))
                conn.commit()
                st.success('Solicitação enviada com sucesso!')
            else:
                st.warning('Por favor, preencha todos os campos.')
else:
    if menu_tecnico == 'Baixar Manutenções':
        st.title('📋 Ordens de Serviço Pendentes')
        # Buscamos explicitamente as colunas para evitar erros de mapeamento
        df_pendentes = pd.read_sql("SELECT id, curso, laboratorio, tipo, descricao, status, data_entrada, foto FROM manutencoes WHERE status = 'Pendente'", conn)
        
        if not df_pendentes.empty:
            for index, row in df_pendentes.iterrows():
                with st.expander(f"OS #{row['id']} - {row['laboratorio']} ({row['curso']})"):
                    st.write(f"**Tipo:** {row['tipo']}")
                    st.write(f"**Descrição:** {row['descricao']}")
                    
                    # Verifica se a coluna foto existe e tem conteúdo
                    if 'foto' in row and row['foto']:
                        st.image(row['foto'], caption=f"Evidência OS #{row['id']}", width=400)
                        
                    if st.button(f"Confirmar Realização #{row['id']}", key=f"btn_{row['id']}"):
                        data_saida_dt = datetime.now()
                        data_entrada_dt = datetime.strptime(row['data_entrada'], '%Y-%m-%d %H:%M:%S')
                        duracao = data_saida_dt - data_entrada_dt
                        horas, rem = divmod(duracao.total_seconds(), 3600)
                        minutos, _ = divmod(rem, 60)
                        tempo_str = f'{int(horas)}h {int(minutos)}min'
                        c.execute("UPDATE manutencoes SET status='Realizado', data_saida=?, tempo_total=? WHERE id=?", 
                                  (data_saida_dt.strftime('%Y-%m-%d %H:%M:%S'), tempo_str, row['id']))
                        conn.commit()
                        st.success(f"OS #{row['id']} finalizada!")
                        st.rerun()
        else:
            st.info('Nenhuma manutenção pendente.')

    elif menu_tecnico == 'Dashboard':
        st.title('📊 Relatório de Gestão')
        df_all = pd.read_sql("SELECT * FROM manutencoes WHERE status = 'Realizado'", conn)
        if not df_all.empty:
            st.subheader('Atendimentos por Unidade')
            df_counts = df_all['curso'].value_counts().reset_index()
            df_counts.columns = ['Unidade', 'Atendimentos']
            st.bar_chart(df_counts.set_index('Unidade'))
            
            # Mostra apenas colunas de texto/data na tabela do Streamlit
            colunas_visiveis = [c for c in df_all.columns if c != 'foto']
            st.dataframe(df_all[colunas_visiveis], use_container_width=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_export = df_all.drop(columns=['foto']) if 'foto' in df_all.columns else df_all
                df_export.to_excel(writer, index=False, sheet_name='Relatorio')
            st.download_button(label='📥 Exportar para Excel', data=output.getvalue(), file_name='relatorio_manutencao.xlsx')
        else:
            st.warning('Sem dados concluídos.')

    elif menu_tecnico == 'Gestão de Usuários':
        st.title('👥 Cadastrar Equipe')
        with st.form('add_user'):
            new_user = st.text_input('Novo Usuário')
            new_pw = st.text_input('Senha', type='password')
            if st.form_submit_button('Cadastrar Técnico'):
                try:
                    c.execute('INSERT INTO usuarios (username, password) VALUES (?,?)', (new_user, new_pw))
                    conn.commit()
                    st.success(f'Técnico {new_user} cadastrado!')
                except:
                    st.error('Erro ao cadastrar ou usuário já existe.')
