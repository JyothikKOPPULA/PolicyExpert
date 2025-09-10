from sqlalchemy import create_engine, Column, String, DateTime, Text, Date, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
import urllib.parse
from datetime import datetime, date

# Load environment variables
load_dotenv()

# Connection parameters for insurance database
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = urllib.parse.quote_plus(os.getenv('DB_PASSWORD'))
DB_SERVER = os.getenv('DB_SERVER')
DB_NAME = os.getenv('DB_NAME')

# Create connection string for insurance database
SQLALCHEMY_DATABASE_URL = (
    f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}@{DB_SERVER}/{DB_NAME}?"
    "driver=ODBC+Driver+18+for+SQL+Server&"
    "encrypt=yes&"
    "trustservercertificate=no&"
    "connection+timeout=30"
)

# Create SQLAlchemy engine with optimized settings for Azure SQL
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=True,
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,   # Recycle connections after 1 hour
    pool_size=5,         # Maximum number of permanent connections
    max_overflow=10,     # Allow up to 10 additional temporary connections
    pool_timeout=30,     # Connection timeout of 30 seconds
    fast_executemany=True  # Optimize batch operations
)

# Create session
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Create Base class
Base = declarative_base()

# Keep existing insurance_claims table structure (already exists in Azure)
class InsuranceClaims(Base):
    __tablename__ = "insurance_claims"
    
    claim_id = Column(String(50), primary_key=True)  # Auto-generated claim ID
    policy_number = Column(String(50), nullable=False)  # DCAR00920600359/00 or DMED00920600359/00
    customer_name = Column(String(100), nullable=False)  # Primary identifier for claims
    claim_type = Column(String(20), nullable=False)  # Medical or Vehicle
    amount = Column(String(20), nullable=False)  # Amount in string format like ₹45,000
    date_submitted = Column(DateTime, default=datetime.utcnow)
    description = Column(Text, nullable=False)
    status = Column(String(20), nullable=False)  # Under Review, Approved, Rejected, Processing
    rejection_reason = Column(Text, nullable=True)  # Reason if rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# New customer_policies table for personalization and recommendations
class CustomerPolicies(Base):
    __tablename__ = "customer_policies"
    
    customer_name = Column(String(100), primary_key=True)  # Unique name of the customer (PK)
    vehicle_insurance = Column(String(100), nullable=True)  # e.g., "Car, Bike"
    medical_insurance = Column(String(100), nullable=True)  # e.g., "Individual, Family"
    life_insurance = Column(String(100), nullable=True)  # e.g., "Term, Whole"
    travel_insurance = Column(String(100), nullable=True)  # e.g., "International"
    home_insurance = Column(String(100), nullable=True)  # e.g., "Apartment, Villa"
    
    # Policy numbers for reference
    vehicle_policy_numbers = Column(String(200), nullable=True)  # Comma-separated if multiple
    medical_policy_numbers = Column(String(200), nullable=True)  # Comma-separated if multiple
    life_policy_numbers = Column(String(200), nullable=True)  # Comma-separated if multiple
    travel_policy_numbers = Column(String(200), nullable=True)  # Comma-separated if multiple
    home_policy_numbers = Column(String(200), nullable=True)  # Comma-separated if multiple
    
    # Customer metadata
    last_policy_renewal = Column(Date, nullable=True)  # Last policy renewal date
    customer_since = Column(Date, nullable=False)  # When the customer first joined
    
    # Demographics for better recommendations
    age = Column(String(10), nullable=True)  # Age range like "25-30"
    location = Column(String(50), nullable=True)  # City/State
    
    # Add-on tracking (what they currently have)
    vehicle_addons = Column(String(500), nullable=True)  # e.g., "Zero Depreciation, Engine Protection"
    medical_addons = Column(String(500), nullable=True)  # e.g., "Critical Illness, Dental"
    home_addons = Column(String(500), nullable=True)  # e.g., "Fire Protection, Theft Coverage"
    travel_addons = Column(String(500), nullable=True)  # e.g., "Emergency Medical, Flight Delay"
    life_addons = Column(String(500), nullable=True)  # e.g., "Accidental Death, Critical Illness Rider"
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# New customer_info table for UI and agent updates (simplified table with 3 columns)
class CustomerInfo(Base):
    __tablename__ = "customer_info"
    
    customer_name = Column(String(100), primary_key=True)  # Unique name of the customer (PK)
    final_premium_amount = Column(String(50), nullable=True)  # Final premium amount e.g., "₹25,000"
    addons_with_amount = Column(Text, nullable=True)  # Add-ons with their amounts e.g., "Zero Depreciation: ₹2,500, Roadside Assistance: ₹500"

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Function to create all tables
def create_tables():
    Base.metadata.create_all(bind=engine)

# Function to insert sample data for customer_info table
def insert_sample_customer_info():
    db = SessionLocal()
    try:
        # Sample customer info data
        customer_info_data = [
            {
                "customer_name": "Diya",
                "final_premium_amount": "₹15,000",
                "addons_with_amount": "Consumables Coverage: ₹1,500, Extra Car Protect: ₹2,000"
            },
            {
                "customer_name": "Lakshmi Srinivas",
                "final_premium_amount": "₹8,500",
                "addons_with_amount": "Dental Coverage: ₹1,200"
            }
        ]
        
        for info_data in customer_info_data:
            customer_info = CustomerInfo(**info_data)
            db.add(customer_info)
        
        db.commit()
        print("✅ Sample customer info data inserted successfully!")
        print("📊 Data Summary:")
        print(f"   - {len(customer_info_data)} customer info records added")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error inserting customer info data: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("🏗️  Creating database tables...")
    create_tables()
    print("📝 Inserting sample customer info data...")
    insert_sample_customer_info()
    print("🎉 Database setup complete!")
