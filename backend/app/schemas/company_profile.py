"""Schema for structured company profile extracted from raw company info."""

from pydantic import BaseModel, Field
from typing import Optional, List


class CompanyProfile(BaseModel):
    """
    Structured company profile extracted from raw company information.

    All fields except 'name' are optional - the extraction LLM must NOT
    invent or assume data that is not explicitly stated in the source material.
    """

    # === BASIC INFO ===
    name: str = Field(description="Company name")
    industry: Optional[str] = Field(default=None, description="Primary industry sector")
    sub_industry: Optional[str] = Field(default=None, description="Specific sub-sector or niche")
    employee_count: Optional[str] = Field(default=None, description="Number of employees, can be range like '30-50'")
    founding_year: Optional[int] = Field(default=None, description="Year the company was founded")
    ownership: Optional[str] = Field(
        default=None,
        description="Ownership structure: 'family-owned', 'founder-led', 'PE-backed', 'corporate subsidiary', etc."
    )

    # === LOCATIONS ===
    headquarters: Optional[str] = Field(default=None, description="HQ location (City, Country)")
    other_locations: Optional[List[str]] = Field(default=None, description="Other office/plant locations")
    markets_served: Optional[List[str]] = Field(default=None, description="Geographic markets: 'DACH', 'EU', 'Global', etc.")

    # === FINANCIAL KPIs ===
    annual_revenue: Optional[str] = Field(default=None, description="Annual revenue range, e.g., '€5-10M'")
    profit_margin: Optional[str] = Field(default=None, description="Profit margin if mentioned")
    cash_flow_status: Optional[str] = Field(default=None, description="Cash flow situation: 'positive', 'tight', etc.")
    growth_rate: Optional[str] = Field(default=None, description="Growth rate, e.g., '15% YoY'")

    # === OPERATIONAL KPIs ===
    production_volume: Optional[str] = Field(default=None, description="Production volume, e.g., '50,000 units/year'")
    capacity_utilization: Optional[str] = Field(default=None, description="Capacity utilization percentage")

    # === BUSINESS MODEL ===
    core_business: Optional[str] = Field(default=None, description="1-2 sentence description of core business")
    products_services: Optional[List[str]] = Field(default=None, description="Main products or services (max 5)")
    customer_segments: Optional[List[str]] = Field(default=None, description="Target customers: 'B2B manufacturing', 'SME retailers', etc.")

    # === OPERATIONS & TECH ===
    key_processes: Optional[List[str]] = Field(default=None, description="Key business processes (max 5)")
    current_systems: Optional[List[str]] = Field(default=None, description="Current IT systems: 'SAP ERP', 'Excel-based', etc.")
    data_sources: Optional[List[str]] = Field(default=None, description="Available data sources: 'ERP', 'sensors', 'CRM', etc.")
    automation_level: Optional[str] = Field(default=None, description="Current automation: 'manual', 'partially automated', etc.")

    # === CHALLENGES & GOALS ===
    pain_points: Optional[List[str]] = Field(default=None, description="Main challenges (max 3)")
    digitalization_goals: Optional[List[str]] = Field(default=None, description="Digitalization objectives (max 3)")
    competitive_pressures: Optional[str] = Field(default=None, description="Competitive situation if mentioned")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "Müller Maschinenbau GmbH",
                "industry": "Manufacturing",
                "sub_industry": "CNC Machine Tools",
                "employee_count": "45",
                "founding_year": 1987,
                "ownership": "family-owned",
                "headquarters": "Stuttgart, Germany",
                "other_locations": ["Prague, Czech Republic"],
                "markets_served": ["DACH", "Eastern Europe"],
                "annual_revenue": "€8-12M",
                "profit_margin": None,
                "cash_flow_status": None,
                "growth_rate": "stable",
                "production_volume": "200 machines/year",
                "capacity_utilization": "75%",
                "core_business": "Custom CNC machining centers for automotive suppliers",
                "products_services": ["5-axis CNC machines", "Retrofit services", "Maintenance contracts"],
                "customer_segments": ["Automotive Tier 1-2 suppliers", "Aerospace"],
                "key_processes": ["Order configuration", "Production planning", "Quality control"],
                "current_systems": ["Legacy ERP", "Excel production planning"],
                "data_sources": ["ERP orders", "Machine logs"],
                "automation_level": "partially automated",
                "pain_points": ["Manual production scheduling", "No real-time visibility"],
                "digitalization_goals": ["Predictive maintenance", "Automated scheduling"],
                "competitive_pressures": "Price pressure from Asian competitors"
            }
        }


class CompanyProfileResponse(BaseModel):
    """Response model for company profile extraction."""
    profile: CompanyProfile
    extraction_quality: str = Field(description="Quality indicator: 'high', 'medium', 'low' based on data completeness")
    missing_critical_info: Optional[List[str]] = Field(
        default=None,
        description="List of important fields that could not be extracted"
    )
