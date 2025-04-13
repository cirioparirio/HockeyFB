# Configurazione della pagina Streamlit deve essere la prima chiamata Streamlit
import streamlit as st
st.set_page_config(
    page_title="Filtraggio Inverso Hockey",
    page_icon="🏒",
    layout="wide",
    initial_sidebar_state="expanded"
)

import pandas as pd
import numpy as np
from itertools import combinations
import re
import os
import base64
from io import BytesIO

# Funzione per il filtraggio inverso
def inverse_filtering(data, target_column, target_percentage, filter_cols, min_matches=50, max_combinations=None, max_results=None):
    """
    Trova combinazioni di filtri che producono una percentuale di successo superiore al target.
    
    Args:
        data: DataFrame con i dati
        target_column: Colonna di risultato target (es. '1X')
        target_percentage: Percentuale target da raggiungere (es. 80)
        filter_cols: Lista di colonne di filtro da considerare
        min_matches: Numero minimo di partite per considerare una combinazione valida
        max_combinations: Numero massimo di filtri da combinare (None per illimitato)
        max_results: Numero massimo di risultati da restituire (None per illimitato)
    
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
    
    # Determina il numero massimo di combinazioni da analizzare
    max_comb = max_combinations if max_combinations is not None else len(filter_cols)
    
    # Analizza combinazioni di filtri (fino a max_combinations)
    for n_filters in range(2, max_comb + 1):
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
    
    # Limita il numero di risultati se specificato
    if max_results is not None:
        return results[:max_results]
    else:
        return results

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
    # Colonne di filtro specificate dall'utente (F, H, O, P, Q, R, S, T)
    filter_columns = [
        'PRONO',        # Colonna F (indice 5)
        'SOMMA GOAL',   # Colonna H (indice 7)
        '% HOME',       # Colonna O (indice 14)
        '% AWAY',       # Colonna P (indice 15)
        'POIS H',       # Colonna Q (indice 16)
        'POIS A',       # Colonna R (indice 17)
        'Diff Poiss',   # Colonna S (indice 18)
        'Somma Poiss'   # Colonna T (indice 19) - Nuova colonna aggiunta
    ]
    
    # Verifica quali colonne di filtro sono effettivamente presenti nel DataFrame
    actual_filter_columns = [col for col in filter_columns if col in data_df.columns]
    
    # Colonne di risultato (mercati di interesse da AD a AT)
    result_columns = []
    for col in data_df.columns:
        # Converti la colonna in stringa per evitare errori con colonne numeriche
        col_str = str(col)
        if col_str in ['1', '2', '1X', 'X2'] or (isinstance(col, str) and col.startswith('OVER')):
            result_columns.append(col)
    
    # Se le colonne non sono già rinominate correttamente, usa i numeri di colonna
    if len(result_columns) == 0:
        # Colonne numeriche basate sull'analisi (indici da 29 a 45, corrispondenti a AD-AT)
        numeric_result_cols = list(range(29, 46))  # Da 29 a 45 incluso
        result_columns = [data_df.columns[i] for i in numeric_result_cols if i < len(data_df.columns)]
    
    return actual_filter_columns, result_columns

# Funzione per generare un link di download per un DataFrame
def get_table_download_link(df, filename, text):
    """Genera un link per scaricare il dataframe come file CSV"""
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">📥 {text}</a>'
    return href

# Titolo dell'applicazione
st.title("🏒 Filtraggio Inverso Hockey")
st.markdown("""
Questa applicazione permette di identificare quali combinazioni di filtri portano a percentuali elevate nei mercati di scommesse sull'hockey.
""")

# Aggiungi un avviso per dispositivi mobili
st.warning("""
**Ottimizzato per dispositivi mobili**: Questa versione è stata modificata per funzionare meglio su smartphone e tablet.
""")

# Crea due colonne per l'interfaccia
col1, col2 = st.columns([1, 2])

with col1:
    st.header("Impostazioni")
    
    # Caricamento del file Excel
    uploaded_file = st.file_uploader("Carica il file Excel", type=["xlsx"])
    
    # Aggiungi un messaggio di debug per verificare il caricamento del file
    if uploaded_file is not None:
        file_details = {"Filename": uploaded_file.name, "FileType": uploaded_file.type, "FileSize": uploaded_file.size}
        st.write("File caricato:")
        st.json(file_details)
    
    # Aggiungi istruzioni per dispositivi Android
    st.info("""
    **Suggerimenti per Android**:
    - Se hai problemi con il caricamento, prova un browser diverso
    - Assicurati che il file sia in formato .xlsx
    - Verifica che il file non sia troppo grande
    """)

with col2:
    if uploaded_file is not None:
        # Carica il file Excel
        with st.spinner("Caricamento del file in corso..."):
            stats_df, data_df = load_excel_file(uploaded_file)
        
        if data_df is not None:
            # Identifica le colonne di filtro e risultato
            filter_columns, result_columns = identify_columns(data_df)
            
            # Mostra informazioni sul file caricato
            st.success(f"File caricato con successo: {uploaded_file.name}")
            st.info(f"Numero di partite: {len(data_df)}")
            
            # Parametri per il filtraggio inverso
            st.subheader("Parametri di Filtraggio")
            
            # Crea due colonne per i parametri
            param_col1, param_col2 = st.columns(2)
            
            with param_col1:
                # Selezione del mercato
                target_column = st.selectbox("Seleziona il mercato", result_columns)
                
                # Selezione della percentuale target (sostituito slider con number_input)
                target_percentage = st.number_input(
                    "Percentuale target", 
                    min_value=50, 
                    max_value=100, 
                    value=80, 
                    step=1,
                    help="Percentuale minima di successo desiderata"
                )
            
            with param_col2:
                # Selezione del numero minimo di partite (sostituito slider con number_input)
                min_matches = st.number_input(
                    "Numero minimo di partite", 
                    min_value=10, 
                    max_value=1000, 
                    value=100, 
                    step=10,
                    help="Numero minimo di partite per considerare valida una combinazione"
                )
                
                # Opzioni avanzate in un expander
                with st.expander("Opzioni avanzate"):
                    # Numero massimo di filtri da combinare (sostituito slider con number_input)
                    max_combinations = st.number_input(
                        "Numero massimo di filtri da combinare", 
                        min_value=1, 
                        max_value=8, 
                        value=3,
                        help="Numero massimo di filtri da combinare insieme (valori più alti aumentano il tempo di elaborazione)"
                    )
                    
                    # Numero massimo di risultati da mostrare (sostituito slider con number_input)
                    max_results = st.number_input(
                        "Numero massimo di risultati da mostrare", 
                        min_value=5, 
                        max_value=1000, 
                        value=20,
                        help="Numero massimo di risultati da mostrare (valori più alti potrebbero rallentare la visualizzazione)"
                    )
                    
                    # Opzione per risultati illimitati
                    unlimited_results = st.checkbox(
                        "Mostra tutti i risultati disponibili", 
                        value=False,
                        help="Se selezionato, ignora il limite massimo di risultati (può rallentare l'applicazione)"
                    )
                    
                    # Opzione per combinazioni illimitate
                    unlimited_combinations = st.checkbox(
                        "Usa tutte le combinazioni possibili", 
                        value=False,
                        help="Se selezionato, ignora il limite massimo di combinazioni (aumenta significativamente il tempo di elaborazione)"
                    )
                    
                    # Selezione delle colonne di filtro da considerare
                    selected_filter_columns = st.multiselect(
                        "Colonne di filtro da considerare",
                        filter_columns,
                        default=filter_columns
                    )
                    
                    if selected_filter_columns:
                        filter_columns = selected_filter_columns
            
            # Pulsante per eseguire il filtraggio inverso (spostato nel corpo principale)
            if st.button("Esegui Filtraggio Inverso", type="primary", use_container_width=True):
                # Mostra un messaggio di caricamento
                with st.spinner(f"Ricerca delle combinazioni di filtri per {target_column} > {target_percentage}% con almeno {min_matches} partite..."):
                    # Gestisci le opzioni illimitate
                    max_comb = None if unlimited_combinations else max_combinations
                    max_res = None if unlimited_results else max_results
                    
                    # Esegui il filtraggio inverso
                    results = inverse_filtering(
                        data_df, 
                        target_column, 
                        target_percentage, 
                        filter_columns, 
                        min_matches=min_matches,
                        max_combinations=max_comb,
                        max_results=max_res
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
                        st.dataframe(results_df, use_container_width=True)
                        
                        # Aggiungi un link per scaricare i risultati
                        st.markdown(get_table_download_link(results_df, "risultati_filtri.csv", "Scarica i risultati come CSV"), unsafe_allow_html=True)
                        
                        # Nota informativa sui grafici
                        st.info("I grafici sono stati disabilitati per garantire la compatibilità con Streamlit Cloud.")
