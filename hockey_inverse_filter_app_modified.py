import streamlit as st
import pandas as pd
import numpy as np
from itertools import combinations
import re
import os
import base64
from io import BytesIO
import matplotlib.pyplot as plt
import seaborn as sns

# Configurazione della pagina Streamlit
st.set_page_config(
    page_title="Filtraggio Inverso Hockey",
    page_icon="🏒",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Titolo dell'applicazione
st.title("🏒 Filtraggio Inverso Hockey")
st.markdown("""
Questa applicazione permette di identificare quali combinazioni di filtri portano a percentuali elevate nei mercati di scommesse sull'hockey.
""")

# Funzione per il filtraggio inverso
def inverse_filtering(data, target_column, target_percentage, filter_cols, min_matches=50, max_combinations=3, max_results=20):
    """
    Trova combinazioni di filtri che producono una percentuale di successo superiore al target.
    
    Args:
        data: DataFrame con i dati
        target_column: Colonna di risultato target (es. '1X')
        target_percentage: Percentuale target da raggiungere (es. 80)
        filter_cols: Lista di colonne di filtro da considerare
        min_matches: Numero minimo di partite per considerare una combinazione valida
        max_combinations: Numero massimo di filtri da combinare
        max_results: Numero massimo di risultati da restituire
    
    Returns:
        Lista di dizionari con le combinazioni di filtri e le relative percentuali
    """
    results = []
    
    # Verifica se la colonna target esiste
    if target_column not in data.columns:
        # Prova a trovare la colonna corrispondente
        for col in data.columns:
            if str(col) == str(target_column) or (isinstance(col, str) and target_column in col):
                target_column = col
                break
    
    # Funzione per calcolare la percentuale di successo
    def calculate_success_percentage(filtered_data, target_col):
        # Conta i successi (V) e i fallimenti (X)
        if target_col in filtered_data.columns:
            success_count = (filtered_data[target_col] == 'V').sum()
            total_count = filtered_data[target_col].count()
            if total_count > 0:
                return (success_count / total_count) * 100, total_count
        return 0, 0
    
    # Analizza singoli filtri
    for col in filter_cols:
        # Determina i valori unici nella colonna di filtro
        unique_values = data[col].unique()
        
        # Per ogni valore unico, calcola la percentuale di successo
        for val in unique_values:
            # Crea diversi tipi di filtri: uguale, maggiore, minore
            filters = [
                {'type': '=', 'condition': data[col] == val},
                {'type': '>', 'condition': data[col] > val},
                {'type': '<', 'condition': data[col] < val}
            ]
            
            for filter_info in filters:
                filtered_data = data[filter_info['condition']]
                if len(filtered_data) >= min_matches:  # Ignora filtri con pochi dati
                    success_percentage, count = calculate_success_percentage(filtered_data, target_column)
                    if success_percentage >= target_percentage:
                        results.append({
                            'filters': [{
                                'column': col,
                                'operator': filter_info['type'],
                                'value': val
                            }],
                            'percentage': success_percentage,
                            'count': count
                        })
    
    # Analizza combinazioni di filtri (fino a max_combinations)
    for n_filters in range(2, max_combinations + 1):
        # Genera tutte le possibili combinazioni di colonne di filtro
        for cols_combo in combinations(filter_cols, n_filters):
            # Per ogni combinazione, genera combinazioni di condizioni
            for i in range(10):  # Limita il numero di tentativi casuali
                filter_conditions = []
                combined_condition = pd.Series([True] * len(data), index=data.index)
                
                for col in cols_combo:
                    # Scegli casualmente un valore dalla colonna
                    val = np.random.choice(data[col].dropna().unique())
                    
                    # Scegli casualmente un operatore
                    operator = np.random.choice(['=', '>', '<'])
                    
                    if operator == '=':
                        condition = data[col] == val
                    elif operator == '>':
                        condition = data[col] > val
                    else:  # operator == '<'
                        condition = data[col] < val
                    
                    filter_conditions.append({
                        'column': col,
                        'operator': operator,
                        'value': val
                    })
                    
                    combined_condition = combined_condition & condition
                
                filtered_data = data[combined_condition]
                if len(filtered_data) >= min_matches:  # Ignora filtri con pochi dati
                    success_percentage, count = calculate_success_percentage(filtered_data, target_column)
                    if success_percentage >= target_percentage:
                        results.append({
                            'filters': filter_conditions,
                            'percentage': success_percentage,
                            'count': count
                        })
    
    # Ordina i risultati per percentuale decrescente e poi per numero di partite decrescente
    results.sort(key=lambda x: (-x['percentage'], -x['count']))
    
    # Limita il numero di risultati
    return results[:max_results]

# Funzione per caricare il file Excel
def load_excel_file(uploaded_file):
    try:
        # Leggi le prime 6 righe che contengono le statistiche
        stats_df = pd.read_excel(uploaded_file, nrows=6)
        
        # Leggi il file Excel, saltando le prime 6 righe che contengono statistiche
        data_df = pd.read_excel(uploaded_file, skiprows=6)
        
        return stats_df, data_df
    except Exception as e:
        st.error(f"Errore durante il caricamento del file: {e}")
        return None, None

# Funzione per identificare le colonne di filtro e risultato
def identify_columns(data_df):
    # Colonne di filtro (O-AA nella legenda, 14-26 nel DataFrame)
    filter_columns = [
        '% HOME', '% AWAY', 'POIS H', 'POIS A', 'Diff Poiss',
        'P1 H', 'P1 A', 'P2 H', 'P2 A', 'P3 H', 'P3 A', 'FT H', 'FT A'
    ]
    
    # Verifica quali colonne di filtro sono effettivamente presenti nel DataFrame
    actual_filter_columns = [col for col in filter_columns if col in data_df.columns]
    
    # Colonne di risultato (AC-AS nella legenda)
    result_columns = []
    for col in data_df.columns:
        # Converti la colonna in stringa per evitare errori con colonne numeriche
        col_str = str(col)
        if col_str in ['1', '2', '1X', 'X2'] or (isinstance(col, str) and col.startswith('OVER')):
            result_columns.append(col)
    
    # Se le colonne non sono già rinominate correttamente, usa i numeri di colonna
    if len(result_columns) == 0:
        # Colonne numeriche basate sull'analisi precedente
        numeric_result_cols = [28, 29, 31, 32, 34, 35, 36, 37, 38, 39, 41, 42, 43, 44]
        result_columns = [data_df.columns[i] for i in numeric_result_cols if i < len(data_df.columns)]
    
    return actual_filter_columns, result_columns

# Funzione per generare un link di download per un DataFrame
def get_table_download_link(df, filename, text):
    """Genera un link per scaricare il dataframe come file CSV"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">📥 {text}</a>'
    return href

# Funzione per creare un grafico a barre delle percentuali di successo
def create_percentage_chart(results_df):
    """Crea un grafico a barre delle percentuali di successo"""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Converti le percentuali da stringhe a numeri
    percentages = results_df['Percentuale'].str.rstrip('%').astype(float)
    
    # Crea il grafico a barre
    bars = ax.bar(
        results_df['Opzione'], 
        percentages,
        color=plt.cm.viridis(percentages/100)
    )
    
    # Aggiungi le etichette
    ax.set_title('Percentuali di Successo per Opzione', fontsize=16)
    ax.set_xlabel('Opzione', fontsize=14)
    ax.set_ylabel('Percentuale di Successo (%)', fontsize=14)
    ax.set_ylim(0, 105)  # Imposta il limite dell'asse y a 105% per lasciare spazio alle etichette
    
    # Aggiungi i valori sopra le barre
    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width()/2.,
            height + 1,
            f'{height:.1f}%',
            ha='center',
            fontsize=12
        )
    
    # Aggiungi una griglia orizzontale
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    
    # Imposta lo sfondo del grafico
    ax.set_facecolor('#f8f9fa')
    fig.patch.set_facecolor('#f8f9fa')
    
    plt.tight_layout()
    return fig

# Funzione per creare un grafico a barre del numero di partite
def create_matches_chart(results_df):
    """Crea un grafico a barre del numero di partite"""
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Crea il grafico a barre
    bars = ax.bar(
        results_df['Opzione'], 
        results_df['Partite'],
        color=plt.cm.plasma(results_df['Partite']/results_df['Partite'].max())
    )
    
    # Aggiungi le etichette
    ax.set_title('Numero di Partite per Opzione', fontsize=16)
    ax.set_xlabel('Opzione', fontsize=14)
    ax.set_ylabel('Numero di Partite', fontsize=14)
    
    # Aggiungi i valori sopra le barre
    for bar in bars:
        height = bar.get_height()
        ax.text(
            bar.get_x() + bar.get_width()/2.,
            height + 1,
            f'{int(height)}',
            ha='center',
            fontsize=12
        )
    
    # Aggiungi una griglia orizzontale
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    
    # Imposta lo sfondo del grafico
    ax.set_facecolor('#f8f9fa')
    fig.patch.set_facecolor('#f8f9fa')
    
    plt.tight_layout()
    return fig

# Sidebar per il caricamento del file e le impostazioni
st.sidebar.header("Impostazioni")

# Verifica se il dispositivo è mobile (Android)
is_mobile = st.sidebar.checkbox("Sto usando un dispositivo Android", value=False)

# Istruzioni per dispositivi Android
if is_mobile:
    st.sidebar.info("""
    **Istruzioni per dispositivi Android:**
    1. Se hai problemi con il caricamento dei file, prova a utilizzare un browser diverso da Chrome (come Firefox o Samsung Internet).
    2. In alternativa, puoi caricare il file tramite il pulsante qui sotto.
    """)
    
    # Utilizzo del componente personalizzato per Android
    try:
        import st_file_uploader as stf
        
        # Utilizzo della versione italiana del componente
        uploaded_file = stf.it.file_uploader(
            "Carica il file Excel",
            type=["xlsx"],
            accept_multiple_files=False
        )
    except ImportError:
        st.sidebar.warning("""
        Per una migliore esperienza su Android, è consigliabile installare il componente personalizzato.
        
        L'amministratore dell'app deve eseguire:
        ```
        pip install st_file_uploader
        ```
        
        Per ora, prova a utilizzare l'uploader standard qui sotto.
        """)
        # Fallback all'uploader standard
        uploaded_file = st.sidebar.file_uploader("Carica il file Excel", type=["xlsx"])
else:
    # Uploader standard per dispositivi desktop
    uploaded_file = st.sidebar.file_uploader("Carica il file Excel", type=["xlsx"])

if uploaded_file is not None:
    # Carica il file Excel
    stats_df, data_df = load_excel_file(uploaded_file)
    
    if data_df is not None:
        # Identifica le colonne di filtro e risultato
        filter_columns, result_columns = identify_columns(data_df)
        
        # Mostra informazioni sul file caricato
        st.sidebar.success(f"File caricato con successo: {uploaded_file.name}")
        st.sidebar.info(f"Numero di partite: {len(data_df)}")
        
        # Parametri per il filtraggio inverso
        st.sidebar.header("Parametri di Filtraggio")
        
        # Selezione del mercato
        target_column = st.sidebar.selectbox("Seleziona il mercato", result_columns)
        
        # Selezione della percentuale target
        target_percentage = st.sidebar.slider("Percentuale target", min_value=50, max_value=100, value=80, step=5)
        
        # Selezione del numero minimo di partite
        min_matches = st.sidebar.slider("Numero minimo di partite", min_value=10, max_value=500, value=100, step=10)
        
        # Opzioni avanzate
        st.sidebar.header("Opzioni Avanzate")
        show_advanced = st.sidebar.checkbox("Mostra opzioni avanzate")
        
        max_combinations = 3
        max_results = 20
        
        if show_advanced:
            max_combinations = st.sidebar.slider("Numero massimo di filtri da combinare", min_value=1, max_value=5, value=3)
            max_results = st.sidebar.slider("Numero massimo di risultati da mostrare", min_value=5, max_value=50, value=20)
            
            # Selezione delle colonne di filtro da considerare
            selected_filter_columns = st.sidebar.multiselect(
                "Colonne di filtro da considerare",
                filter_columns,
                default=filter_columns
            )
            
            if selected_filter_columns:
                filter_columns = selected_filter_columns
        
        # Pulsante per eseguire il filtraggio inverso
        if st.sidebar.button("Esegui Filtraggio Inverso"):
            # Mostra un messaggio di caricamento
            with st.spinner(f"Ricerca delle combinazioni di filtri per {target_column} > {target_percentage}% con almeno {min_matches} partite..."):
                # Esegui il filtraggio inverso
                results = inverse_filtering(
                    data_df, 
                    target_column, 
                    target_percentage, 
                    filter_columns, 
                    min_matches=min_matches,
                    max_combinations=max_combinations,
                    max_results=max_results
                )
                
                # Mostra i risultati
                st.header(f"Risultati per {target_column} > {target_percentage}% (min. {min_matches} partite)")
                
                if not results:
                    st.warning("Nessuna combinazione di filtri trovata che soddisfi i criteri specificati.")
                else:
                    st.success(f"Trovate {len(results)} combinazioni di filtri che soddisfano i criteri.")
                    
                    # Crea un DataFrame con i risultati
                    results_data = []
                    for i, result in enumerate(results, 1):
                        filter_str = " AND ".join([f"{f['column']} {f['operator']} {f['value']}" for f in result['filters']])
                        results_data.append({
                            "Opzione": i,
                            "Filtri": filter_str,
                            "Percentuale": f"{result['percentage']:.2f}%",
                            "Partite": result['count']
                        })
                    
                    results_df = pd.DataFrame(results_data)
                    
                    # Mostra i risultati in una tabella
                    st.dataframe(results_df)
                    
                    # Aggiungi un link per scaricare i risultati
                    st.markdown(get_table_download_link(results_df, "risultati_filtraggio.csv", "Scarica i risultati come CSV"), unsafe_allow_html=True)
                    
                    # Crea e mostra i grafici
                    st.subheader("Visualizzazioni")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.pyplot(create_percentage_chart(results_df))
                    
                    with col2:
                        st.pyplot(create_matches_chart(results_df))
    else:
        st.sidebar.error("Errore durante il caricamento del file. Assicurati che il file sia nel formato corretto.")
else:
    # Mostra istruzioni quando nessun file è caricato
    st.info("""
    ### Come utilizzare questa applicazione:
    
    1. Carica il tuo file Excel di hockey utilizzando il selettore di file nella barra laterale.
    2. Seleziona il mercato di interesse (es. 1X, OVER 3.5).
    3. Imposta la percentuale target desiderata.
    4. Specifica il numero minimo di partite per garantire la robustezza statistica.
    5. Clicca su "Esegui Filtraggio Inverso" per ottenere i risultati.
    
    L'applicazione ti mostrerà le combinazioni di filtri che producono percentuali di successo superiori al target specificato.
    """)
    
    # Mostra un esempio di risultati
    st.header("Esempio di Risultati")
    
    example_data = [
        {"Opzione": 1, "Filtri": "% HOME > 60 AND POIS H > 3", "Percentuale": "92.5%", "Partite": 120},
        {"Opzione": 2, "Filtri": "FT A = 0", "Percentuale": "90.2%", "Partite": 215},
        {"Opzione": 3, "Filtri": "P1 H > 1 AND P2 A < 2", "Percentuale": "88.7%", "Partite": 168},
    ]
    
    example_df = pd.DataFrame(example_data)
    st.dataframe(example_df)

# Footer
st.markdown("---")
st.markdown("Sviluppato con ❤️ da Manus")
