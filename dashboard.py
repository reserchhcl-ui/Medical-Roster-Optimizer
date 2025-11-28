import streamlit as st
import requests
import pandas as pd
from datetime import date, timedelta
import json

# --- Configurações ---
API_URL = "http://127.0.0.1:8000/api/v1"
st.set_page_config(page_title="Medical Roster AI", layout="wide", page_icon="🏥")

# --- Estilos CSS Customizados ---
st.markdown("""
    <style>
    .stButton>button {
        width: 100%;
        background-color: #ff4b4b;
        color: white;
    }
    .status-card {
        padding: 20px;
        border-radius: 10px;
        background-color: #f0f2f6;
        margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- Funções Auxiliares de API ---
def get_doctors():
    try:
        response = requests.get(f"{API_URL}/doctors/")
        if response.status_code == 200:
            return response.json()
        return []
    except:
        st.error("❌ Não foi possível conectar à API. Verifique se o backend está rodando.")
        return []

def post_roster_optimization(payload):
    try:
        response = requests.post(f"{API_URL}/roster/optimize", json=payload)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 422:
            st.warning("⚠️ Solução Inviável: Restrições muito rígidas ou falta de médicos.")
            return None
        else:
            st.error(f"Erro na API: {response.text}")
            return None
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

# --- Interface Principal ---

st.title("🏥 Medical Roster Optimizer")
st.markdown("Sistema de Otimização de Escalas Médicas com **Google OR-Tools**")

tabs = st.tabs(["📊 Dashboard da Escala", "👨‍⚕️ Gestão de Médicos", "⚙️ Configurar Plantões"])

# === TAB 1: GERADOR DE ESCALA ===
with tabs[0]:
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.subheader("Parâmetros")
        
        start_date = st.date_input("Início do Período", date.today())
        days_to_generate = st.slider("Dias para gerar", 1, 30, 7)
        end_date = start_date + timedelta(days=days_to_generate - 1)
        
        st.markdown("---")
        st.markdown("**Pesos do Algoritmo**")
        w_cost = st.slider("Minimizar Custos", 0.0, 5.0, 1.0)
        w_pref = st.slider("Priorizar Preferências", 0.0, 5.0, 2.0)
        
        sector_select = st.selectbox("Setor", ["Emergencia", "UTI-A", "UTI-B"])
        req_specialty = st.selectbox("Especialidade Requerida", 
                                     ["clinica_geral", "pediatria", "cardiologia", "ortopedia"])
        
        generate_btn = st.button("🚀 Gerar Escala Otimizada")

    with col2:
        if generate_btn:
            with st.spinner("🤖 O Robô está calculando a melhor combinação matemática..."):
                # 1. Gerar Slots Automaticamente baseado nos inputs
                slots_payload = []
                current = start_date
                while current <= end_date:
                    # Slot Diurno
                    slots_payload.append({
                        "id": f"{sector_select}_{current}_day",
                        "date": str(current),
                        "shift_type": "diurno",
                        "required_specialties": [req_specialty],
                        "required_count": 1,
                        "sector_id": sector_select
                    })
                    # Slot Noturno
                    slots_payload.append({
                        "id": f"{sector_select}_{current}_night",
                        "date": str(current),
                        "shift_type": "noturno",
                        "required_specialties": [req_specialty],
                        "required_count": 1,
                        "sector_id": sector_select
                    })
                    current += timedelta(days=1)
                
                # 2. Montar Request
                request_data = {
                    "period_start": str(start_date),
                    "period_end": str(end_date),
                    "weight_cost": w_cost,
                    "weight_preference": w_pref,
                    "slots_to_fill": slots_payload
                }
                
                # 3. Chamar API
                result = post_roster_optimization(request_data)
                
                if result:
                    st.success(f"✅ Escala gerada com sucesso! {len(result)} plantões alocados.")
                    
                    # 4. Visualização
                    df = pd.DataFrame(result)
                    
                    # Buscar nomes dos médicos (cruzamento simples)
                    docs = get_doctors()
                    doc_map = {d['id']: d['name'] for d in docs}
                    df['Nome do Médico'] = df['doctor_id'].map(doc_map)
                    
                    # Tabela Simples
                    st.subheader("📋 Lista de Plantões")
                    st.dataframe(df[['date', 'slot_id', 'Nome do Médico']].sort_values('date'), use_container_width=True)
                    
                    # Pivot Table (Visualização de Calendário Simplificada)
                    st.subheader("📅 Visualização Matricial")
                    try:
                        pivot = df.pivot_table(
                            index='date', 
                            columns='slot_id', 
                            values='Nome do Médico', 
                            aggfunc=lambda x: ' '.join(x)
                        )
                        st.dataframe(pivot)
                    except:
                        st.info("A visualização matricial requer mais dados para ser exibida corretamente.")

# === TAB 2: GESTÃO DE MÉDICOS ===
with tabs[1]:
    st.header("Corpo Clínico")
    
    docs = get_doctors()
    if docs:
        df_docs = pd.DataFrame(docs)
        # Flatten attributes para exibição
        if 'attributes' in df_docs.columns:
            df_attr = pd.json_normalize(df_docs['attributes'])
            df_docs = pd.concat([df_docs.drop(['attributes', 'availability'], axis=1), df_attr], axis=1)
        
        st.dataframe(
            df_docs, 
            column_config={
                "cost_per_hour": st.column_config.NumberColumn("Custo/Hora", format="R$ %.2f"),
                "specialties": st.column_config.ListColumn("Especialidades")
            },
            use_container_width=True
        )
    else:
        st.info("Nenhum médico cadastrado ou API offline.")

    with st.expander("➕ Cadastrar Novo Médico"):
        with st.form("new_doctor"):
            name = st.text_input("Nome Completo")
            crm = st.text_input("CRM")
            specs = st.multiselect("Especialidades", ["clinica_geral", "pediatria", "cardiologia", "cirurgia"])
            seniority = st.slider("Senioridade (1-5)", 1, 5, 2)
            cost = st.number_input("Custo Hora", 100.0)
            
            submit = st.form_submit_button("Salvar Médico")
            
            if submit:
                payload = {
                    "id": f"doc_{crm}", # Gerando ID baseado no CRM para simplificar
                    "name": name,
                    "crm": crm,
                    "specialties": specs,
                    "attributes": {
                        "seniority_level": seniority,
                        "is_preceptor": False,
                        "cost_per_hour": cost
                    },
                    "availability": {
                        "unavailable_dates": [],
                        "preferred_dates": [],
                        "max_shifts_per_month": 20
                    }
                }
                res = requests.post(f"{API_URL}/doctors/", json=payload)
                if res.status_code == 201:
                    st.success("Médico cadastrado!")
                    st.rerun()
                else:
                    st.error(f"Erro: {res.text}")

# === TAB 3: CONFIGURAÇÃO (Placeholder) ===
with tabs[2]:
    st.info("Configurações avançadas de slots e regras hospitalares ficariam aqui.")
    st.write("Ex: Definir feriados, regras de interjornada customizadas, etc.")