# -*- coding: utf-8 -*-
import pymongo
import streamlit as st
import pandas as pd
import asyncio
import threading
from langchain.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import LLMChain
import re
import networkx as nx
import matplotlib.pyplot as plt

lista_palavras_chaves = [
    # Tipos de carros
    "carro", "carros", "suv", "suvs", "suv's", "sedan", "sedans", "hatch", "hatches",
    "picape", "picapes", "pickup", "pickups", "caminhonete", "caminhonetes",

    # Preço e valores
    "preço", "preços", "barato", "baratos", "caro", "caros", "custo", "custos",
    "desconto", "descontos", "taxa", "taxas", "gratuito", "grátis",

    # Disponibilidade e reserva
    "disponível", "disponíveis", "alugado", "alugados", "reservado", "reservados",
    "reserva", "reservas", "cancelar", "cancelamento", "alugar", "aluguel", "alugueis",

    # Informações do veículo
    "modelo", "modelos", "marca", "marcas", "ano", "anos", "categoria", "categorias",
    "potência", "potente", "velocidade", "rápido", "lento",

    # Tipos de câmbio e combustível
    "manual", "automático", "automatica", "flex", "diesel", "gasolina", "elétrico", "elétricos",

    # Cliente e suporte
    "cliente", "clientes", "cadastrar", "cadastro", "login", "entrar",
    "dúvida", "dúvidas", "problema", "problemas", "ajuda", "suporte",

    # Outros termos úteis
    "vaga", "vagas", "documento", "documentos", "cnh", "telefone",

    # Marcas
    "toyota", "honda", "ford", "chevrolet", "volkswagen", "hyundai"
    ]

def obter_palavras_chave_bd(db, lista_palavras_chaves):
    registros = db["historico_chat"].find()
    todas_palavras = []

    for registro in registros:
        for interacao in registro.get("conversa", []):
            texto = interacao.get("pergunta", "") + " " + interacao.get("resposta", "")
            palavras_encontradas = extrair_palavras_chave(texto.lower(), lista_palavras_chaves)
            todas_palavras.extend(palavras_encontradas)

    return todas_palavras

def limpar_texto(texto):
    """Remove pontuações e transforma em minúsculas"""
    return re.sub(r"[^\w\s]", "", texto.lower())

def criar_grafo_conversa(conversa):
    """
    Cria um grafo a partir de uma conversa.
    Cada nó é uma palavra e as arestas representam coocorrência na mesma pergunta/resposta.

    Param conversa: lista de tuplas (pergunta, resposta)
    Return: grafo networkx.Graph
    """
    G = nx.Graph()

    for pergunta, resposta in conversa:
        for frase in [pergunta, resposta]:
            palavras = limpar_texto(frase).split()
            for i, palavra in enumerate(palavras):
                G.add_node(palavra)
                for j in range(i + 1, len(palavras)):
                    if palavras[i] != palavras[j]:
                        G.add_edge(palavras[i], palavras[j])

    return G

def plotar_grafo_palavras(chat_history, lista_palavras_chaves):
    G = nx.Graph()
    palavras_encontradas = []

    # Extract keywords from current chat history
    for pergunta, resposta in chat_history:
        texto = limpar_texto(pergunta + " " + resposta)
        palavras = texto.split()
        for palavra in palavras:
            if palavra in lista_palavras_chaves:
                palavras_encontradas.append(palavra)

    # Add sequential connections
    for i in range(len(palavras_encontradas) - 1):
        G.add_edge(palavras_encontradas[i], palavras_encontradas[i + 1])

    plt.figure(figsize=(10, 6))
    pos = nx.spring_layout(G, seed=42)
    nx.draw(G, pos, with_labels=True, node_color='lightblue', edge_color='gray', node_size=1000, font_size=10)
    st.pyplot(plt)

def nome_valido(nome):
    return bool(re.match("^[A-Za-zÀ-ÖØ-öø-ÿ '-]+$", nome))

def extrair_palavras_chave(texto, lista_palavras_chaves):
    """
    Extrai as palavras-chave que estão presentes no texto do usuário.
    
    texto: string da conversa do usuário
    lista_palavras_chaves: lista com palavras a serem detectadas
    Retorna uma lista com as palavras-chave encontradas."""
    texto = texto.lower()
    palavras_encontradas = []
    for palavra in lista_palavras_chaves:
        # Cria um padrão que reconhece a palavra isolada (com espaços ou pontuação em volta)
        padrao = r'\b' + re.escape(palavra.lower()) + r'\b'
        if re.search(padrao, texto):
            palavras_encontradas.append(palavra)

    return palavras_encontradas

def salvar_historico_chat(nome, doc, historico):
    if not historico:
        return  # não salva se estiver vazio

    conversa_formatada = []
    for pergunta, resposta in historico:
        palavras = extrair_palavras_chave(pergunta, lista_palavras_chaves)
        conversa_formatada.append({
            "pergunta": pergunta,
            "resposta": resposta,
            "palavras_chave": palavras
        })

    entrada = {
        "usuario": nome,
        "documento": doc,
        "data": pd.to_datetime("today").strftime("%d/%m/%Y"),
        "conversa": conversa_formatada
    }

    db["historico_chat"].insert_one(entrada)


    conversa_formatada = []
    for pergunta, resposta in historico:
        palavras = extrair_palavras_chave(pergunta, lista_palavras_chaves)
        conversa_formatada.append({
            "pergunta": pergunta,
            "resposta": resposta,
            "palavras_chave": palavras
        })

    entrada = {
        "usuario": nome,
        "documento": doc,
        "data": pd.to_datetime("today").strftime("%d/%m/%Y"),
        "conversa": conversa_formatada
    }

    db["historico_chat"].insert_one(entrada)

# Configurações iniciais
senhaadm = "adm123"
api="AIzaSyB0yC8yWBpdbifI22JyHGxR6enhFjyThms"

client_mongo = pymongo.MongoClient(f"mongodb+srv://adm:{senhaadm}@aulamongo01.ihl4f.mongodb.net/?retryWrites=true&w=majority&appName=AulaMongo01")
db = client_mongo.Mydb
Frota_Carros = pd.read_csv("frota_carros.csv")

st.set_page_config(page_title="Sistema de Aluguel", page_icon="🚗")

# --- Inicializa variáveis de sessão ---
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.nome_usuario = ""
    st.session_state.doc_usuario = ""
    st.session_state.tela = "login"




# --- Tela de Login ou Cadastro ---
if st.session_state.tela == "login":
    st.title("🔐 Login ou Cadastro")
    opcao = st.radio("Você já tem cadastro?", ["Entrar", "Cadastrar"])

    if opcao == "Entrar":
        doc = st.text_input("CPF (11 dígitos) ou CNPJ (14 dígitos)")
        senha_user_input = st.text_input("Senha", type="password")

        if st.button("Entrar"):
            cliente = db["clientes"].find_one({
                "$or": [{"CPF": doc}, {"CNPJ": doc}],
                "Senha": senha_user_input
            })

            if cliente:
                st.session_state.autenticado = True
                st.session_state.nome_usuario = cliente["Nome"]  #Pega o nome diretamente do banco
                st.session_state.doc_usuario = doc
                st.session_state.tela = "sistema"
                st.rerun()
            else:
                st.error("❌ Cadastro não encontrado.")


    elif opcao == "Cadastrar":
        nome = st.text_input("Nome")
        sobrenome = st.text_input("Sobrenome (opcional)")
        if not nome_valido(nome):
            st.error("⚠️ Nome inválido. Use apenas letras, espaços, acentos e apóstrofos.")
        doc = st.text_input("CPF (11 dígitos) ou CNPJ (14 dígitos)")
        if len(doc) not in [11, 14]:
            st.error("⚠️ CPF deve ter 11 dígitos ou CNPJ deve ter 14 dígitos.")
        else:
            doc = doc.replace(".", "").replace("-", "").replace("/", "")
        idade = st.number_input("Idade", min_value=18, max_value=120, step=1)
        telefone = st.text_input("Telefone (11 dígitos)")
        cnh = st.text_input("CNH (11 dígitos)")
        validade_cnh = st.date_input("Validade da CNH")
        if validade_cnh < pd.to_datetime("today").date():
            st.error("⚠️ A validade da CNH não pode ser anterior a hoje.")
        senha_user_input = st.text_input("Defina sua Senha", type="password")

        if st.button("Cadastrar"):
            entrada = "CPF" if len(doc) == 11 else "CNPJ"
            if db["clientes"].find_one({entrada: doc}):
                st.warning("⚠️ CPF ou CNPJ já cadastrado.")
            else:
                cliente = {
                    "Nome": nome.capitalize(),
                    "Sobrenome": sobrenome.capitalize() if sobrenome else "",
                    "Idade": idade,
                    entrada: doc,
                    "Telefone": telefone,
                    "CNH": cnh,
                    "Validade CNH": validade_cnh.strftime("%d/%m/%Y"),
                    "Senha": senha_user_input
                }
                db["clientes"].insert_one(cliente)
                st.success("✅ Cadastro realizado com sucesso! Agora você pode entrar.")

# --- Tela do Sistema ---
elif st.session_state.tela == "sistema":
    if not st.session_state.autenticado:
        st.warning("⚠️ Você precisa estar autenticado para acessar o sistema.")
        st.session_state.tela = "login"
        st.rerun()
    
    menu = st.sidebar.selectbox("📋 Menu", [
        "Consultar Carros",
        "Reservar Carro",
        "Consultar Reserva",
        "Chatbot Atendimento"
    ])

    if st.sidebar.button("Sair"):
        st.session_state.autenticado = False
        st.session_state.tela = "login"
        st.rerun()

    # --- Consulta de Carros ---
    if menu == "Consultar Carros":
        st.title("🚙 Carros Disponíveis")
        carros = list(db["frota"].find({"Status": "Disponível"}))
        if carros:
            df_carros = pd.DataFrame(carros).drop("_id", axis=1)
            if "Carro" in df_carros.columns:
                df_carros = df_carros.drop("Carro", axis=1)
            st.dataframe(df_carros)
        else:
            st.warning("Nenhum carro disponível no momento.")

 
# --- Reserva de Carro ---

    elif menu == "Reservar Carro":
        st.title("📅 Reservar Carro")

        tipo_busca = st.radio("Buscar carro por:", ["Categoria", "Marca", "Modelo"])
        valor = st.text_input(f"Digite a {tipo_busca.lower()} para filtrar os carros")

        if valor:
            filtro = {
                tipo_busca: {"$regex": valor, "$options": "i"},
                "Status": "Disponível"
            }
            carros_encontrados = list(db["frota"].find(filtro))
            if carros_encontrados:
                df_carros = pd.DataFrame(carros_encontrados).drop("_id", axis=1)
                if "Carro" in df_carros.columns:
                    df_carros = df_carros.drop("Carro", axis=1)
                st.dataframe(df_carros)

                placas = [carro["Placa"] for carro in carros_encontrados]
                placa_selecionada = st.selectbox("Escolha a placa do carro que deseja reservar:", placas)

                if st.button("Reservar"):
                    carro = next(c for c in carros_encontrados if c["Placa"] == placa_selecionada)

                    db["frota"].update_one({"Placa": carro["Placa"]}, {"$set": {"Status": "Alugado"}})
                    db["reservas"].insert_one({
                        "nome_cliente": st.session_state.nome_usuario,
                        "documento": st.session_state.doc_usuario,
                        "data_reserva": pd.to_datetime("today").strftime("%d/%m/%Y"),
                        "placa": carro["Placa"],
                        "status": "Reservado",
                        "carro": {
                            "Marca": carro["Marca"],
                            "Modelo": carro["Modelo"],
                            "Ano": carro["Ano"],
                            "Categoria": carro["Categoria"]
                        }
                    })
                    st.success(f"Reserva realizada para o carro {carro['Marca']} {carro['Modelo']}!")
            else:
                st.warning("Nenhum carro disponível com esse critério.")

        # Bloco de cancelamento de reserva (dentro da tela "Reservar Carro")
        st.markdown("---")
        st.subheader("❌ Cancelar Reserva")
        placa = st.text_input("Digite a placa do carro que deseja cancelar a reserva:")
        if st.button("Cancelar Reserva"):
            reserva = db["reservas"].find_one({"placa": placa})
            if reserva:
                db["frota"].update_one({"Placa": placa}, {"$set": {"Status": "Disponível"}})
                db["reservas"].delete_one({"placa": placa})
                st.success(f"Reserva para o carro {placa} cancelada com sucesso!")
            else:
                st.error("Reserva não encontrada para essa placa.")

        


        # --- Consulta de Reserva ---
    elif menu == "Consultar Reserva":
        st.title("🔎 Consulta de Reserva")
        nome = st.session_state.nome_usuario
        cpf_cnpj = st.session_state.doc_usuario
        if st.button("Consultar"):
            reserva = db["reservas"].find_one({"nome_cliente": nome.capitalize()})
            if reserva:
                st.success(f"Reserva encontrada!\nStatus: {reserva['status']}")
                st.write(f"Placa do carro: {reserva['placa']} - {reserva['carro']['Marca']} {reserva['carro']['Modelo']}")
                st.write(f"Data da reserva: {reserva['data_reserva']}")
            else:
                st.warning("Reserva não encontrada.")

    # --- Chatbot ---

    elif menu == "Chatbot Atendimento":
        st.title("💬 Atendimento Virtual")
        if st.button("🔄 Reiniciar Chat"):
            st.session_state.chat_history = []
            st.rerun()
        palavras = []
        if st.button("🔗 Visualizar grafo da conversa"):
            palavras = extrair_palavras_chave(" ".join([p + " " + r for p, r in st.session_state.chat_history]), lista_palavras_chaves)
        if palavras:
            plotar_grafo_palavras(st.session_state.chat_history, lista_palavras_chaves)
        else:
            st.warning("Nenhuma palavra-chave encontrada no histórico.")

            dados_csv = Frota_Carros.to_csv(index=False)

        # Inicializa histórico se ainda não existir
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        # Renderiza mensagens anteriores
        for i, (pergunta, resposta) in enumerate(st.session_state.chat_history):
            with st.chat_message("user", avatar="👤"):
                st.markdown(pergunta)
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(resposta)

        # Entrada de mensagem com st.chat_input
        user_input = st.chat_input("Digite sua mensagem...")

        if user_input:
            # Exibe a mensagem do usuário na interface
            with st.chat_message("user", avatar="👤"):
                st.markdown(user_input)

            # Configura o prompt
            template = """
            Você é um assistente virtual de uma locadora de veículos.
            Baseie suas respostas nas informações da frota abaixo (formato CSV):

            {dados_csv}

            Mantenha o contexto da conversa.

            Usuário: {pergunta}
            """

            prompt = PromptTemplate(
                input_variables=["dados_csv", "pergunta"],
                template=template
            )

            if threading.current_thread().name == "ScriptRunner.scriptThread":
                try:
                    asyncio.get_event_loop()
                except RuntimeError:
                    asyncio.set_event_loop(asyncio.new_event_loop())

            llm = ChatGoogleGenerativeAI(
                model="gemini-2.0-flash",
                temperature=0.7,
                google_api_key=api
            )

            chain = LLMChain(llm=llm, prompt=prompt)

            # Constrói contexto a partir do histórico
            contexto = "\n".join([f"Usuário: {p}\nAssistente: {r}" for p, r in st.session_state.chat_history])
            pergunta_formatada = f"{contexto}\nUsuário: {user_input}" if contexto else user_input

            resposta = chain.run(dados_csv=dados_csv, pergunta=pergunta_formatada)

            # Exibe resposta do assistente
            with st.chat_message("assistant", avatar="🤖"):
                st.markdown(resposta.strip())

            # Salva no histórico
            st.session_state.chat_history.append((user_input, resposta.strip()))

        salvar_historico_chat(st.session_state.nome_usuario, st.session_state.doc_usuario, st.session_state.chat_history)
