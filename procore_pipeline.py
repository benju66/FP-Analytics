import os
import logging
import urllib.parse
import requests
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

# --- 1. ENTERPRISE SETUP ---
# Initialize logging (Replaces print statements for cloud observability)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load secure credentials from .env file
load_dotenv()

# Environment Variables
CLIENT_ID = os.getenv('PROCORE_CLIENT_ID')
CLIENT_SECRET = os.getenv('PROCORE_CLIENT_SECRET')
COMPANY_ID = os.getenv('PROCORE_COMPANY_ID')
DB_PASSWORD = os.getenv('SUPABASE_DB_PASSWORD')
POOLER_HOST = os.getenv('SUPABASE_POOLER_HOST')

# --- LIVE PRODUCTION ROUTING ---
BASE_API_URL = 'https://api.procore.com'
AUTH_URL = 'https://login.procore.com/oauth/token'

# --- 2. CORE FUNCTIONS ---

def get_access_token() -> str:
    """Authenticates with Procore and returns a Bearer token."""
    logging.info("Requesting Procore access token...")
    payload = {
        'grant_type': 'client_credentials',
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET
    }
    response = requests.post(AUTH_URL, data=payload)
    response.raise_for_status() # Will fail safely if authentication breaks
    return response.json().get('access_token')

def get_all_projects(token: str) -> list:
    """Fetches a list of all active projects for the company."""
    logging.info("Fetching all active projects from Procore...")
    headers = {
        'Authorization': f'Bearer {token}',
        'Procore-Company-Id': str(COMPANY_ID)
    }
    endpoint = f"{BASE_API_URL}/rest/v1.0/projects?company_id={COMPANY_ID}"
    
    response = requests.get(endpoint, headers=headers)
    response.raise_for_status()
    return response.json()

def get_budget_line_items(token: str, project_id: int) -> list:
    """Fetches the budget line items for a specific project ID."""
    logging.info(f"Fetching budget data for Project ID: {project_id}...")
    headers = {
        'Authorization': f'Bearer {token}',
        'Procore-Company-Id': str(COMPANY_ID)
    }
    endpoint = f"{BASE_API_URL}/rest/v1.1/budget_line_items?project_id={project_id}"
    
    response = requests.get(endpoint, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        logging.warning(f"Could not fetch budget for Project {project_id}: {response.status_code}")
        return []

# --- 3. THE MASTER LOOP ---

def run_pipeline():
    """Main execution block: Authenticates, iterates projects, and pushes to Supabase."""
    try:
        # 1. Authenticate
        token = get_access_token()
        
        # 2. Get all projects
        projects = get_all_projects(token)
        logging.info(f"Discovered {len(projects)} projects.")
        
        all_budget_dataframes = []

        # 3. Iterate through every project (The Master Loop)
        for proj in projects:
            p_id = proj.get('id')
            p_name = proj.get('name')
            
            budget_data = get_budget_line_items(token, p_id)
            
            if budget_data and len(budget_data) > 0:
                # Flatten JSON and append relational tags
                df = pd.json_normalize(budget_data)
                df['project_id'] = p_id
                df['project_name'] = p_name
                
                all_budget_dataframes.append(df)
        
        # 4. Combine all projects into one massive DataFrame
        if not all_budget_dataframes:
            logging.warning("No budget data found across any projects. Exiting.")
            return

        master_df = pd.concat(all_budget_dataframes, ignore_index=True)
        logging.info(f"Combined Master Dataframe ready: {len(master_df)} total rows.")

        # 5. Push to Supabase Cloud
        logging.info("Connecting to Supabase Database...")
        safe_password = urllib.parse.quote_plus(DB_PASSWORD)
        db_uri = f'postgresql://postgres.thqmpvnewyppmdedfpec:{safe_password}@{POOLER_HOST}:5432/postgres'
        
        engine = create_engine(db_uri, connect_args={'sslmode': 'require'})
        
        # Push the master table
        master_df.to_sql('sandbox_budget_master', engine, if_exists='replace', index=False)
        logging.info("SUCCESS! Enterprise pipeline execution complete.")

    except Exception as e:
        logging.error(f"Pipeline failed: {str(e)}")

if __name__ == "__main__":
    run_pipeline()
