
import os
from supabase import create_client, Client
from typing import Optional, Dict, Any

# For production, do something like:
# SUPABASE_URL = os.environ.get("SUPABASE_URL")
# SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
#
# For demonstration, we can inline them here, but you should NOT commit your real keys!

SUPABASE_URL = "https://nryaarklafuymrwxhgdn.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im5yeWFhcmtsYWZ1eW1yd3hoZ2RuIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MzQ5MjgxMDQsImV4cCI6MjA1MDUwNDEwNH0.CI6LQFVpparoPEd1ta9OKJKK31SDQsXSErgng_8U7y8"

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_last_inserted_patient():
    """
    Fetch the most recently created patient record from the 'patients' table.
    """
    response = (
        supabase
        .table("patients")
        .select("*")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None