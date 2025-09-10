"""
FastAPI application for insurance policy management and customer information system.
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging
import os
import uvicorn
from dotenv import load_dotenv

from database import get_db, engine, Base, CustomerPolicies, InsuranceClaims, CustomerInfo

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Pydantic Models ---
from pydantic import BaseModel

class CustomerPolicyResponse(BaseModel):
    customer_name: str
    vehicle_insurance: Optional[str]
    medical_insurance: Optional[str]
    life_insurance: Optional[str]
    travel_insurance: Optional[str]
    home_insurance: Optional[str]
    vehicle_policy_numbers: Optional[str]
    medical_policy_numbers: Optional[str]
    life_policy_numbers: Optional[str]
    travel_policy_numbers: Optional[str]
    home_policy_numbers: Optional[str]
    last_policy_renewal: Optional[str]
    customer_since: str
    age: Optional[str]
    location: Optional[str]
    vehicle_addons: Optional[str]
    medical_addons: Optional[str]
    home_addons: Optional[str]
    travel_addons: Optional[str]
    life_addons: Optional[str]

class ClaimResponse(BaseModel):
    claim_id: str
    policy_number: str
    claim_type: str
    amount: str
    date_submitted: str
    description: str
    status: str
    rejection_reason: Optional[str]

class CustomerInfoResponse(BaseModel):
    customer_policy: CustomerPolicyResponse
    claims: List[ClaimResponse]
    claims_summary: dict

class SimpleCustomerInfoResponse(BaseModel):
    customer_name: str
    final_premium_amount: Optional[str]
    addons_with_amount: Optional[str]

class CustomerInfoUpdateRequest(BaseModel):
    customer_name: str
    final_premium_amount: Optional[str] = None
    addons_with_amount: Optional[str] = None

class CustomerPolicyUpdateRequest(BaseModel):
    customer_name: str
    vehicle_insurance: Optional[str] = None
    medical_insurance: Optional[str] = None
    life_insurance: Optional[str] = None
    travel_insurance: Optional[str] = None
    home_insurance: Optional[str] = None
    vehicle_policy_numbers: Optional[str] = None
    medical_policy_numbers: Optional[str] = None
    life_policy_numbers: Optional[str] = None
    travel_policy_numbers: Optional[str] = None
    home_policy_numbers: Optional[str] = None
    age: Optional[str] = None
    location: Optional[str] = None
    vehicle_addons: Optional[str] = None
    medical_addons: Optional[str] = None
    home_addons: Optional[str] = None
    travel_addons: Optional[str] = None
    life_addons: Optional[str] = None
    
    class Config:
        # Ignore extra fields that are not in the model
        extra = "ignore"

class UpdateCustomerInfoRequest(BaseModel):
    customer_info: Optional[CustomerInfoUpdateRequest] = None
    customer_policy: Optional[CustomerPolicyUpdateRequest] = None

# Create database tables
Base.metadata.create_all(bind=engine)

# Get root_path from environment variable, default to "" for local development
root_path = os.getenv("ROOT_PATH", "")

app = FastAPI(
    title="Policy Expert API",
    description="REST API for insurance policy management and customer information. Provides personalized insurance recommendations and claims history.",
    version="1.0.0",
    root_path=root_path,
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    servers=[
        {
            "url": "https://policyexpert.azurewebsites.net"
        }
    ],
    openapi_tags=[
        {
            "name": "CustomerInfo",
            "description": "Customer information and policy operations"
        },
        {
            "name": "root",
            "description": "Root endpoint operations"
        },
        {
            "name": "health",
            "description": "Health check operations"
        }
    ]
)

# Add CORS middleware with security considerations
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"]
)

@app.get("/customerinfo/{customer_name}", 
         tags=["CustomerInfo"], 
         response_model=CustomerInfoResponse)
async def get_customer_info(
    customer_name: str,
    db: Session = Depends(get_db)
):
    """
    Get comprehensive customer information including policies and claims history.
    
    Parameters:
    - customer_name: Name of the customer to retrieve information for
    - db: Database session dependency
    
    Returns:
    - CustomerInfoResponse: Customer policy details, claims history, and summary
    """
    try:
        # Get customer policy information
        customer_policy = db.query(CustomerPolicies).filter(
            CustomerPolicies.customer_name == customer_name
        ).first()
        
        if not customer_policy:
            raise HTTPException(
                status_code=404,
                detail=f"Customer '{customer_name}' not found in customer policies"
            )
        
        # Get claims history
        claims = db.query(InsuranceClaims).filter(
            InsuranceClaims.customer_name == customer_name
        ).order_by(InsuranceClaims.date_submitted.desc()).all()
        
        # Process claims data
        claims_list = []
        for claim in claims:
            claims_list.append(ClaimResponse(
                claim_id=claim.claim_id,
                policy_number=claim.policy_number,
                claim_type=claim.claim_type,
                amount=claim.amount,
                date_submitted=claim.date_submitted.isoformat() if claim.date_submitted else "",
                description=claim.description,
                status=claim.status,
                rejection_reason=claim.rejection_reason
            ))
        
        # Calculate claims summary
        total_claims = len(claims)
        approved_claims = [c for c in claims if c.status == "APPROVED"]
        rejected_claims = [c for c in claims if c.status == "REJECTED"]
        under_review_claims = [c for c in claims if c.status == "UNDER_REVIEW"]
        
        # Calculate total claim amounts (remove ₹, ?, and commas if present)
        total_approved_amount = 0
        total_rejected_amount = 0
        
        for claim in approved_claims:
            amount_str = claim.amount.replace("₹", "").replace("?", "").replace(",", "").strip()
            if amount_str.isdigit():
                total_approved_amount += int(amount_str)
        
        for claim in rejected_claims:
            amount_str = claim.amount.replace("₹", "").replace("?", "").replace(",", "").strip()
            if amount_str.isdigit():
                total_rejected_amount += int(amount_str)
        
        claims_summary = {
            "total_claims": total_claims,
            "approved_claims": len(approved_claims),
            "rejected_claims": len(rejected_claims),
            "under_review_claims": len(under_review_claims),
            "approval_rate": round((len(approved_claims) / total_claims * 100), 2) if total_claims > 0 else 0,
            "total_approved_amount": f"{total_approved_amount:,}",
            "total_rejected_amount": f"{total_rejected_amount:,}",
            "last_claim_date": claims[0].date_submitted.isoformat() if claims else None
        }
        
        # Prepare customer policy response
        customer_policy_response = CustomerPolicyResponse(
            customer_name=customer_policy.customer_name,
            vehicle_insurance=customer_policy.vehicle_insurance,
            medical_insurance=customer_policy.medical_insurance,
            life_insurance=customer_policy.life_insurance,
            travel_insurance=customer_policy.travel_insurance,
            home_insurance=customer_policy.home_insurance,
            vehicle_policy_numbers=customer_policy.vehicle_policy_numbers,
            medical_policy_numbers=customer_policy.medical_policy_numbers,
            life_policy_numbers=customer_policy.life_policy_numbers,
            travel_policy_numbers=customer_policy.travel_policy_numbers,
            home_policy_numbers=customer_policy.home_policy_numbers,
            last_policy_renewal=customer_policy.last_policy_renewal.isoformat() if customer_policy.last_policy_renewal else None,
            customer_since=customer_policy.customer_since.isoformat(),
            age=customer_policy.age,
            location=customer_policy.location,
            vehicle_addons=customer_policy.vehicle_addons,
            medical_addons=customer_policy.medical_addons,
            home_addons=customer_policy.home_addons,
            travel_addons=customer_policy.travel_addons,
            life_addons=customer_policy.life_addons
        )
        
        return CustomerInfoResponse(
            customer_policy=customer_policy_response,
            claims=claims_list,
            claims_summary=claims_summary
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/customerinfo", 
         tags=["CustomerInfo"])
async def search_customers(
    name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Search for customers by name or get all customers.
    
    Parameters:
    - name: Optional name to search for (case-insensitive partial match)
    - db: Database session dependency
    
    Returns:
    - List of customers with basic information
    """
    try:
        query = db.query(CustomerPolicies)
        
        if name:
            # Search for customers with similar names (case-insensitive)
            query = query.filter(CustomerPolicies.customer_name.ilike(f"%{name}%"))
        
        customers = query.all()
        
        if not customers:
            if name:
                raise HTTPException(
                    status_code=404,
                    detail=f"No customers found with name containing '{name}'"
                )
            else:
                return {"customers": [], "total": 0}
        
        # Return list of customers with basic info
        results = []
        for customer in customers:
            results.append({
                "customer_name": customer.customer_name,
                "age": customer.age,
                "location": customer.location,
                "customer_since": customer.customer_since.isoformat(),
                "last_policy_renewal": customer.last_policy_renewal.isoformat() if customer.last_policy_renewal else None,
                "active_policies": [
                    policy_type for policy_type, value in [
                        ("vehicle", customer.vehicle_insurance),
                        ("medical", customer.medical_insurance),
                        ("life", customer.life_insurance),
                        ("travel", customer.travel_insurance),
                        ("home", customer.home_insurance)
                    ] if value is not None
                ]
            })
        
        return {
            "search_term": name,
            "total": len(results),
            "customers": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/",
         tags=["root"])
def read_root():
    """
    Welcome endpoint for the Policy Expert API.
    
    Returns:
    - Dict: Welcome message
    """
    return {
        "message": "Welcome to Policy Expert API",
        "description": "Insurance policy management and customer information system",
        "version": "1.0.0",
        "endpoints": {
            "customer_info": "/customerinfo/{customer_name}",
            "search_customers": "/customerinfo?name={optional_name}",
            "update_customer": "/updatecustomerinfo",
            "simple_customer": "/customerinfo/simple/{customer_name}",
            "health_check": "/health",
            "api_docs": "/docs"
        }
    }

@app.get("/health",
         tags=["health"])
async def health_check(
    db: Session = Depends(get_db)
):
    """
    Health check endpoint that verifies database connectivity.
    """
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        
        # Get basic stats
        customer_count = db.query(CustomerPolicies).count()
        claims_count = db.query(InsuranceClaims).count()
        
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "connected",
            "stats": {
                "total_customers": customer_count,
                "total_claims": claims_count
            },
            "details": {
                "api_version": "1.0.0",
                "environment": os.getenv("ENVIRONMENT", "development"),
                "port": os.getenv("PORT", "8000")
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "database": "disconnected",
            "error": str(e),
            "details": {
                "api_version": "1.0.0",
                "environment": os.getenv("ENVIRONMENT", "development")
            }
        }

@app.post("/updatecustomerinfo",
          tags=["CustomerInfo"])
async def update_customer_info(
    update_request: UpdateCustomerInfoRequest,
    db: Session = Depends(get_db)
):
    """
    Update customer information in both customer_info and customer_policies tables.
    Agent can update all fields for both UI and policy management purposes.
    
    Parameters:
    - update_request: Contains optional customer_info and customer_policy updates
    - db: Database session dependency
    
    Returns:
    - Dict: Updated customer information from both tables
    """
    try:
        updated_info = {}
        
        # Update customer_info table (3-column table for UI)
        if update_request.customer_info:
            customer_info_data = update_request.customer_info
            
            # Check if customer exists in customer_info table
            customer_info = db.query(CustomerInfo).filter(
                CustomerInfo.customer_name == customer_info_data.customer_name
            ).first()
            
            if customer_info:
                # Update existing record
                if customer_info_data.final_premium_amount is not None:
                    # Store the amount as-is without any currency prefix
                    customer_info.final_premium_amount = customer_info_data.final_premium_amount.strip()
                
                # Always update addons_with_amount even if it's None/null (to clear the field)
                customer_info.addons_with_amount = customer_info_data.addons_with_amount
            else:
                # Create new record
                customer_info = CustomerInfo(
                    customer_name=customer_info_data.customer_name,
                    final_premium_amount=customer_info_data.final_premium_amount.strip() if customer_info_data.final_premium_amount else None,
                    addons_with_amount=customer_info_data.addons_with_amount
                )
                db.add(customer_info)
            
            db.commit()
            db.refresh(customer_info)
            
            updated_info["customer_info"] = {
                "customer_name": customer_info.customer_name,
                "final_premium_amount": customer_info.final_premium_amount,
                "addons_with_amount": customer_info.addons_with_amount
            }
        
        # Update customer_policies table (detailed policy information)
        if update_request.customer_policy:
            customer_policy_data = update_request.customer_policy
            
            # Check if customer exists in customer_policies table
            customer_policy = db.query(CustomerPolicies).filter(
                CustomerPolicies.customer_name == customer_policy_data.customer_name
            ).first()
            
            if customer_policy:
                # Update existing record with all possible fields
                for field, value in customer_policy_data.dict(exclude_unset=True).items():
                    if field != 'customer_name' and value is not None:
                        setattr(customer_policy, field, value)
                
                # Update timestamp
                customer_policy.updated_at = datetime.utcnow()
            else:
                # Create new record (customer_name is required)
                customer_policy = CustomerPolicies(
                    customer_name=customer_policy_data.customer_name,
                    vehicle_insurance=customer_policy_data.vehicle_insurance,
                    medical_insurance=customer_policy_data.medical_insurance,
                    life_insurance=customer_policy_data.life_insurance,
                    travel_insurance=customer_policy_data.travel_insurance,
                    home_insurance=customer_policy_data.home_insurance,
                    vehicle_policy_numbers=customer_policy_data.vehicle_policy_numbers,
                    medical_policy_numbers=customer_policy_data.medical_policy_numbers,
                    life_policy_numbers=customer_policy_data.life_policy_numbers,
                    travel_policy_numbers=customer_policy_data.travel_policy_numbers,
                    home_policy_numbers=customer_policy_data.home_policy_numbers,
                    age=customer_policy_data.age,
                    location=customer_policy_data.location,
                    vehicle_addons=customer_policy_data.vehicle_addons,
                    medical_addons=customer_policy_data.medical_addons,
                    home_addons=customer_policy_data.home_addons,
                    travel_addons=customer_policy_data.travel_addons,
                    life_addons=customer_policy_data.life_addons,
                    customer_since=datetime.utcnow().date()
                )
                db.add(customer_policy)
            
            db.commit()
            db.refresh(customer_policy)
            
            updated_info["customer_policy"] = {
                "customer_name": customer_policy.customer_name,
                "vehicle_insurance": customer_policy.vehicle_insurance,
                "medical_insurance": customer_policy.medical_insurance,
                "life_insurance": customer_policy.life_insurance,
                "travel_insurance": customer_policy.travel_insurance,
                "home_insurance": customer_policy.home_insurance,
                "vehicle_policy_numbers": customer_policy.vehicle_policy_numbers,
                "medical_policy_numbers": customer_policy.medical_policy_numbers,
                "life_policy_numbers": customer_policy.life_policy_numbers,
                "travel_policy_numbers": customer_policy.travel_policy_numbers,
                "home_policy_numbers": customer_policy.home_policy_numbers,
                "last_policy_renewal": customer_policy.last_policy_renewal.isoformat() if customer_policy.last_policy_renewal else None,
                "customer_since": customer_policy.customer_since.isoformat(),
                "age": customer_policy.age,
                "location": customer_policy.location,
                "vehicle_addons": customer_policy.vehicle_addons,
                "medical_addons": customer_policy.medical_addons,
                "home_addons": customer_policy.home_addons,
                "travel_addons": customer_policy.travel_addons,
                "life_addons": customer_policy.life_addons,
                "updated_at": customer_policy.updated_at.isoformat()
            }
        
        if not updated_info:
            raise HTTPException(
                status_code=400,
                detail="No update data provided. Please provide either customer_info or customer_policy data."
            )
        
        return {
            "message": "Customer information updated successfully",
            "updated_data": updated_info,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/customerinfo/simple/{customer_name}",
         tags=["CustomerInfo"],
         response_model=SimpleCustomerInfoResponse)
async def get_simple_customer_info(
    customer_name: str,
    db: Session = Depends(get_db)
):
    """
    Get simple customer information from the customer_info table (3 columns only).
    This is used by UI for basic customer info display.
    
    Parameters:
    - customer_name: Name of the customer to retrieve information for
    - db: Database session dependency
    
    Returns:
    - SimpleCustomerInfoResponse: Basic customer info with final premium and addons
    """
    try:
        customer_info = db.query(CustomerInfo).filter(
            CustomerInfo.customer_name == customer_name
        ).first()
        
        if not customer_info:
            raise HTTPException(
                status_code=404,
                detail=f"Customer '{customer_name}' not found in customer info"
            )
        
        return SimpleCustomerInfoResponse(
            customer_name=customer_info.customer_name,
            final_premium_amount=customer_info.final_premium_amount,
            addons_with_amount=customer_info.addons_with_amount
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("ENV", "dev") == "dev"
    )
