#!/usr/bin/env python3
"""Script to create all database tables - run this on Railway"""
import os
import sys

def create_tables():
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set!")
        print("Please set DATABASE_URL to your PostgreSQL connection string")
        sys.exit(1)
    
    # Fix Railway postgres:// to postgresql://
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    print(f"Connecting to database...")
    
    try:
        import psycopg2
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        cur = conn.cursor()
        
        print("Creating table: classifications")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS classifications (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("Creating table: dataset_images")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS dataset_images (
                id SERIAL PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                classification VARCHAR(255) NOT NULL,
                image_data BYTEA,
                image_path VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("Creating table: embeddings")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                id SERIAL PRIMARY KEY,
                classification VARCHAR(255) NOT NULL,
                embedding_data BYTEA NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("Creating table: scan_history")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scan_history (
                id SERIAL PRIMARY KEY,
                predicted_class VARCHAR(255) NOT NULL,
                confidence FLOAT NOT NULL,
                scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create indexes
        print("Creating indexes...")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_classifications_name ON classifications(name)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_dataset_images_classification ON dataset_images(classification)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_classification ON embeddings(classification)")
        
        # Verify tables exist
        cur.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public'
        """)
        tables = [row[0] for row in cur.fetchall()]
        
        print("\n=== TABLES IN DATABASE ===")
        for table in tables:
            print(f"  - {table}")
        
        required_tables = ['classifications', 'dataset_images', 'embeddings', 'scan_history']
        missing = [t for t in required_tables if t not in tables]
        
        if missing:
            print(f"\nERROR: Missing tables: {missing}")
            sys.exit(1)
        else:
            print("\nSUCCESS: All 4 tables created and verified!")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    create_tables()
