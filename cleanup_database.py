"""
Script para limpar completamente o banco de dados Railway.
Apaga todos os dados das tabelas: classifications, dataset_images, embeddings, scan_history.

Para usar externamente, você precisa da URL pública do Railway.
Para usar no Railway, a URL interna funciona.
"""
import os
import sys
from sqlalchemy import create_engine, text

def get_database_url():
    """Get database URL from environment or command line"""
    url = os.getenv("DATABASE_URL")
    if not url and len(sys.argv) > 1:
        url = sys.argv[1]
    if not url:
        print("ERROR: DATABASE_URL not provided!")
        print("Usage: python cleanup_database.py <DATABASE_URL>")
        print("Or set DATABASE_URL environment variable")
        sys.exit(1)
    
    # Convert postgres:// to postgresql://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url

def cleanup_database():
    """Completely wipe all data from the database"""
    db_url = get_database_url()
    print(f"Connecting to database...")
    
    try:
        engine = create_engine(db_url)
        
        with engine.connect() as conn:
            trans = conn.begin()
            try:
                print("Truncating all tables...")
                # Use TRUNCATE with CASCADE to handle foreign keys
                conn.execute(text("""
                    TRUNCATE TABLE scan_history, embeddings, dataset_images, classifications 
                    RESTART IDENTITY CASCADE;
                """))
                trans.commit()
                print("✅ All database tables have been cleared successfully!")
                print("   - classifications: CLEARED")
                print("   - dataset_images: CLEARED") 
                print("   - embeddings: CLEARED")
                print("   - scan_history: CLEARED")
                return True
            except Exception as e:
                trans.rollback()
                print(f"❌ Error clearing database: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Connection error: {e}")
        print("\nNOTE: If using Railway internal URL (postgres.railway.internal),")
        print("you need to run this script from within Railway.")
        print("For external access, use the public Railway database URL.")
        return False

if __name__ == "__main__":
    cleanup_database()
