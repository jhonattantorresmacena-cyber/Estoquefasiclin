import streamlit as st
import pandas as pd
from datetime import datetime
import sqlite3
import io

# --- CONFIGURAÇÃO DO BANCO DE DADOS ---
def create_tables():
    # Adicionada a coluna 'foto' (BLOB para armazenar o arquivo binário)
    c.execute('''CREATE TABLE IF NOT EXISTS manutencoes 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, curso TEXT, laboratorio TEXT, 
                  tipo TEXT, descricao TEXT, status TEXT, data_entrada TIMESTAMP, 
                  data_saida TIMESTAMP, tempo_total TEXT, foto BLOB)''')
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
            # NOVO: Campo de Upload de Foto
            foto_arquivo = st.file_uploader("Anexar foto do problema (Opcional)", type=['png', 'jpg', 'jpeg'])
        with col2:
            tipo = st.selectbox('Tipo de Problema', ['Elétrica', 'Hidráulica', 'Manutenção Preventiva', 'Sanitária', 'Ar condicionado'])
            desc = st.text_area('Descreva o que precisa ser feito')
        
        enviar = st.form_submit_button('Enviar Solicitação')
        if enviar:
            if lab and desc:
                # Converte a foto em bytes para salvar no SQLite
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
        df_pendentes = pd.read_sql("SELECT * FROM manutencoes WHERE status = 'Pendente'", conn)
        if not df_pendentes.empty:
            for index, row in df_pendentes.iterrows():
                with st.expander(f"OS #{row['id']} - {row['laboratorio']} ({row['curso']})"):
                    st.write(f"**Tipo:** {row['tipo']}")
                    st.write(f"**Descrição:** {row['descricao']}")
                    
                    # NOVO: Exibição da Foto se ela existir
                    if row['foto']:
                        st.image(row['foto'], caption=f"Evidência OS #{row['id']}", width=400)
                    else:
                        st.info("Nenhuma foto anexada a esta solicitação.")
                        
                    if st.button(f"Confirmar Realização #{row['id']}", key=row['id']):
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
            # Remove a coluna de foto (bytes) antes de mostrar a tabela de dados para não travar a UI
            st.dataframe(df_all[['curso', 'laboratorio', 'tipo', 'data_entrada', 'data_saida', 'tempo_total']], use_container_width=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Remove a foto também do Excel, pois arquivos binários podem corromper a planilha simples
                df_export = df_all.drop(columns=['foto'])
                df_export.to_excel(writer, index=False, sheet_name='Relatorio')
            st.download_button(label='📥 Exportar para Excel', data=output.getvalue(), file_name='relatorio.xlsx')
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
                    st.error('Erro ao cadastrar.')
