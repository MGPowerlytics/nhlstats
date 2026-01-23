import sys
import os
from sqlalchemy import text, inspect

# Add plugins to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../plugins')))

from db_manager import DBManager

db = DBManager()

try:
    print("Inspecting tables...")
    inspector = inspect(db.get_engine())
    tables = inspector.get_table_names()
    print(f"Tables: {tables}")

except Exception as e:
    print(f"Error checking DB: {e}")
