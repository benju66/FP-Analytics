import os
import json
import logging
import urllib.parse
import requests
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

# --- 1. ENTERPRISE SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

CLIENT_ID = os.getenv('PROCORE_CLIENT_ID')
CLIENT_SECRET = os.getenv('PROCORE_CLIENT_SECRET')
COMPANY_ID = os.getenv('PROCORE_COMPANY_ID')
DB_PASSWORD = os.getenv('SUPABASE_DB_PASSWORD')
POOLER_HOST = os.getenv('SUPABASE_POOLER_HOST')

# --- LIVE PRODUCTION ROUTING ---
BASE_API_URL = 'https://api.procore.com'
AUTH_URL = 'https://login.procore.com/oauth/token'

# --- 2. CORE EXTRACTION FUNCTIONS ---

def get_access_token() -> str:
    logging.info("Requesting Procore access token...")
    payload = {'grant_type': 'client_credentials', 'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET}
    response = requests.post(AUTH_URL, data=payload)
    response.raise_for_status()
    return response.json().get('access_token')

def get_all_projects(token: str) -> list:
    logging.info("Fetching all active projects from Procore...")
    headers = {'Authorization': f'Bearer {token}', 'Procore-Company-Id': str(COMPANY_ID)}
    endpoint = f"{BASE_API_URL}/rest/v1.0/projects?company_id={COMPANY_ID}"
    response = requests.get(endpoint, headers=headers)
    response.raise_for_status()
    return response.json()

def get_budget_line_items(token: str, project_id: int) -> list:
    headers = {'Authorization': f'Bearer {token}', 'Procore-Company-Id': str(COMPANY_ID)}
    endpoint = f"{BASE_API_URL}/rest/v1.1/budget_line_items?project_id={project_id}"
    response = requests.get(endpoint, headers=headers)
    return response.json() if response.status_code == 200 else []

def get_rfis(token: str, project_id: int) -> list:
    """Fetches ALL RFIs for a project using pagination."""
    headers = {'Authorization': f'Bearer {token}', 'Procore-Company-Id': str(COMPANY_ID)}
    all_rfis = []
    page = 1
    
    while True:
        endpoint = f"{BASE_API_URL}/rest/v1.0/projects/{project_id}/rfis?page={page}&per_page=100"
        response = requests.get(endpoint, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            all_rfis.extend(data)
            
            if len(data) < 100:
                break
            page += 1
        else:
            break
            
    return all_rfis

def get_submittals(token: str, project_id: int) -> list:
    """Fetches ALL Submittals for a project using pagination."""
    headers = {'Authorization': f'Bearer {token}', 'Procore-Company-Id': str(COMPANY_ID)}
    all_submittals = []
    page = 1
    
    while True:
        endpoint = f"{BASE_API_URL}/rest/v1.1/projects/{project_id}/submittals?page={page}&per_page=100"
        response = requests.get(endpoint, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            all_submittals.extend(data)
            
            if len(data) < 100:
                break
            page += 1
        else:
            break
            
    return all_submittals

def clean_for_sql(df: pd.DataFrame) -> pd.DataFrame:
    """Scans dataframe and converts unhashable lists/dicts into JSON strings for SQL injection."""
    for col in df.columns:
        df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, (dict, list)) else x)
    return df

# --- 3. THE MASTER LOOP EXECUTION ENGINE ---

def run_pipeline():
    try:
        token = get_access_token()
        projects = get_all_projects(token)
        logging.info(f"Discovered {len(projects)} projects. Starting extraction loop...")
        
        all_budgets, all_rfis, all_submittals = [], [], []

        for proj in projects:
            p_id = proj.get('id')
            p_name = proj.get('name')
            logging.info(f"Processing: {p_name} (ID: {p_id})")
            
            # 1. Budgets
            b_data = get_budget_line_items(token, p_id)
            if b_data:
                df_b = pd.json_normalize(b_data)
                df_b['project_id'], df_b['project_name'] = p_id, p_name
                all_budgets.append(clean_for_sql(df_b))

            # 2. RFIs
            r_data = get_rfis(token, p_id)
            if r_data:
                df_r = pd.json_normalize(r_data)
                df_r['project_id'], df_r['project_name'] = p_id, p_name
                all_rfis.append(clean_for_sql(df_r))

            # 3. Submittals
            s_data = get_submittals(token, p_id)
            if s_data:
                df_s = pd.json_normalize(s_data)
                df_s['project_id'], df_s['project_name'] = p_id, p_name
                all_submittals.append(clean_for_sql(df_s))

        # Connect to Supabase
        logging.info("Connecting to Supabase Database...")
        safe_password = urllib.parse.quote_plus(DB_PASSWORD)
        db_uri = f'postgresql://postgres.thqmpvnewyppmdedfpec:{safe_password}@{POOLER_HOST}:5432/postgres'
        engine = create_engine(db_uri, connect_args={'sslmode': 'require'})

        # Push Master Tables
        if all_budgets:
            pd.concat(all_budgets, ignore_index=True).to_sql('procore_budgets_master', engine, if_exists='replace', index=False)
            logging.info(f"Pushed {len(all_budgets)} project budgets.")
            
        if all_rfis:
            pd.concat(all_rfis, ignore_index=True).to_sql('procore_rfis_master', engine, if_exists='replace', index=False)
            logging.info(f"Pushed {len(all_rfis)} project RFIs.")
            
        if all_submittals:
            pd.concat(all_submittals, ignore_index=True).to_sql('procore_submittals_master', engine, if_exists='replace', index=False)
            logging.info(f"Pushed {len(all_submittals)} project Submittals.")

        logging.info("SUCCESS! Full enterprise pipeline execution complete.")

    except Exception as e:
        logging.error(f"Pipeline failed: {str(e)}")

if __name__ == "__main__":
    run_pipeline()