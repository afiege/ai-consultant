"""
Test Cases for AI Consultation Quality Evaluation

Sample company profiles representing typical SME scenarios.
Each test case includes:
- Company profile (input to Step 1)
- Expected themes the consultation should cover
- Red flags that indicate poor advice
"""

TEST_CASES = [
    {
        "id": "bakery_001",
        "name": "Small Family Bakery",
        "language": "en",
        "company_info": """
We are a family-owned bakery with 8 employees in a medium-sized German city.
We bake fresh bread, pastries, and cakes daily. Our main customers are local
residents who come to our shop, and we also supply 3 local cafes.

Current challenges:
- We often have leftover products at the end of the day (waste ~15%)
- It's hard to predict how much to bake, especially on weekends
- Our bookkeeping is done manually with Excel
- We want to reach younger customers but don't know how

Our team has no IT background. I (the owner) use a smartphone and basic Excel.
Budget for new projects is limited, maybe 500-1000€ for initial investments.
        """,
        "expected_themes": [
            "demand forecasting",
            "inventory/waste reduction",
            "simple digital tools",
            "social media presence",
            "low-cost solutions",
            "cloud-based POS systems"
        ],
        "red_flags": [
            "complex ML pipelines",
            "expensive enterprise software",
            "requires hiring data scientists",
            "deep learning models",
            "custom software development"
        ]
    },
    {
        "id": "manufacturing_002",
        "name": "Metal Parts Manufacturer",
        "language": "en",
        "company_info": """
We manufacture precision metal parts for the automotive industry. 45 employees,
annual revenue around 4 million euros. We have CNC machines and a quality
control department.

Current situation:
- Quality control is done manually by visual inspection (3 QC staff)
- We have a 2-3% defect rate that costs us in rework and customer complaints
- Machine downtime is unpredictable, causing delivery delays
- We collect some data from machines but don't really use it

We have one IT person who maintains our ERP system. Management is open to
investing in digitalization if ROI can be demonstrated. Budget: up to 50k€
for a pilot project.
        """,
        "expected_themes": [
            "predictive maintenance",
            "automated visual inspection",
            "quality control AI",
            "machine data analytics",
            "ROI calculation",
            "pilot project approach"
        ],
        "red_flags": [
            "complete factory automation",
            "replace all workers with robots",
            "million-euro investments",
            "solutions requiring 10+ data scientists"
        ]
    },
    {
        "id": "retail_003",
        "name": "Online Fashion Boutique",
        "language": "en",
        "company_info": """
We run an online shop for sustainable fashion, 12 employees. We source from
small European manufacturers and sell through our Shopify store. Revenue
last year was 800k€.

Challenges:
- High return rate (30%) because customers pick wrong sizes
- Customer service takes too much time (answering same questions)
- We want to personalize recommendations but don't know how
- Inventory planning is difficult with seasonal fashion

Tech-savvy team, we use Shopify, Google Analytics, and Mailchimp.
Looking for practical AI solutions that integrate with existing tools.
Budget: 200-500€/month for SaaS tools.
        """,
        "expected_themes": [
            "size recommendation AI",
            "chatbot for customer service",
            "personalization",
            "return rate reduction",
            "Shopify app integrations",
            "existing SaaS solutions"
        ],
        "red_flags": [
            "build custom recommendation engine from scratch",
            "hire ML team",
            "solutions not integrating with Shopify"
        ]
    },
    {
        "id": "healthcare_004",
        "name": "Dental Practice",
        "language": "de",
        "company_info": """
Wir sind eine Zahnarztpraxis mit 2 Zahnärzten und 6 Mitarbeitern (Assistenz,
Verwaltung). Etwa 2000 Patienten pro Jahr.

Aktuelle Herausforderungen:
- Terminplanung ist chaotisch, viele No-Shows (15%)
- Patientenakten sind teils noch auf Papier
- Wir möchten mehr Prophylaxe-Termine verkaufen
- Die Telefonzentrale ist überlastet

Wir haben eine Praxissoftware, aber nutzen sie nicht voll aus.
Budget für Digitalisierung: ca. 5000€ einmalig plus laufende Kosten möglich.
        """,
        "expected_themes": [
            "Terminmanagement",
            "No-Show Reduktion",
            "Erinnerungssysteme",
            "Online-Terminbuchung",
            "Digitalisierung Patientenakten",
            "Chatbot/Telefonassistent"
        ],
        "red_flags": [
            "medizinische Diagnose-KI",
            "Röntgenbildanalyse ohne Zertifizierung",
            "komplexe Enterprise-Lösungen"
        ]
    },
    {
        "id": "logistics_005",
        "name": "Regional Logistics Company",
        "language": "en",
        "company_info": """
We are a regional logistics company with 25 trucks and 40 employees.
We deliver goods for various clients within a 200km radius.

Problems:
- Route planning is done manually by experienced dispatchers
- Fuel costs have increased significantly
- Customers want real-time tracking but we can't offer it
- Driver scheduling is a headache, especially with sick days
- Our oldest dispatcher is retiring next year (knowledge loss risk)

We use basic fleet management software but it's outdated.
Willing to invest 20-30k€ in modernization.
        """,
        "expected_themes": [
            "route optimization",
            "fleet management",
            "GPS tracking",
            "fuel efficiency",
            "knowledge transfer",
            "driver scheduling optimization"
        ],
        "red_flags": [
            "autonomous vehicles",
            "build custom routing algorithm",
            "requires large IT department"
        ]
    },
    {
        "id": "restaurant_006",
        "name": "Restaurant Chain",
        "language": "en",
        "company_info": """
We operate 4 casual dining restaurants in different locations, total 60 staff.
Combined revenue about 2.5 million euros.

Current challenges:
- Each location manages inventory separately, no visibility
- Staff scheduling across locations is complex
- We don't know which menu items are most profitable
- Customer feedback is scattered (Google, TripAdvisor, verbal)
- Want to start delivery but don't know how to optimize

We have basic POS systems in each location (different vendors).
Budget: willing to invest in a unified system, up to 40k€.
        """,
        "expected_themes": [
            "unified POS/inventory system",
            "menu engineering/profitability analysis",
            "staff scheduling software",
            "review aggregation",
            "delivery platform integration",
            "multi-location management"
        ],
        "red_flags": [
            "build custom ERP",
            "AI-powered cooking robots",
            "solutions for enterprise restaurant chains"
        ]
    }
]


def get_test_case(case_id: str) -> dict:
    """Get a specific test case by ID."""
    for case in TEST_CASES:
        if case["id"] == case_id:
            return case
    return None


def list_test_cases():
    """Print available test cases."""
    print("\nAvailable Test Cases:")
    print("-" * 50)
    for case in TEST_CASES:
        print(f"  {case['id']}: {case['name']} ({case['language']})")
    print()


if __name__ == "__main__":
    list_test_cases()
