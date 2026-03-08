"""
Insight Rules Configuration

This module defines the keyword-based rules for parsing qualitative insight notes
and generating quantitative score adjustments to the Five Cs credit scorecard.

Each rule specifies:
- keywords: List of phrases to match (case-insensitive)
- pillar: The Five Cs pillar to adjust (Character, Capacity, Capital, Collateral, Conditions)
- delta: Point adjustment (negative or positive)
- reason: Human-readable explanation for the adjustment
"""

INSIGHT_RULES = [
    # Negative Adjustment Rules (8 rules)
    {
        "keywords": ["40% capacity", "low capacity", "underutilization"],
        "pillar": "Capacity",
        "delta": -8,
        "reason": "Low capacity utilization noted"
    },
    {
        "keywords": ["evasive", "uncooperative", "management refused"],
        "pillar": "Character",
        "delta": -10,
        "reason": "Management evasiveness raises concerns"
    },
    {
        "keywords": ["litigation pending", "court notice", "FIR"],
        "pillar": "Character",
        "delta": -12,
        "reason": "Litigation or legal issues identified"
    },
    {
        "keywords": ["key man", "single promoter", "no succession"],
        "pillar": "Character",
        "delta": -5,
        "reason": "Key man risk identified"
    },
    {
        "keywords": ["inventory pileup", "unsold stock"],
        "pillar": "Capacity",
        "delta": -6,
        "reason": "Inventory management concerns"
    },
    {
        "keywords": ["customer concentrated", "single customer"],
        "pillar": "Conditions",
        "delta": -7,
        "reason": "Customer concentration risk"
    },
    {
        "keywords": ["regulatory notice", "GST notice", "income tax notice"],
        "pillar": "Character",
        "delta": -8,
        "reason": "Regulatory compliance issues"
    },
    {
        "keywords": ["collateral disputed", "encumbrance", "mortgage"],
        "pillar": "Collateral",
        "delta": -10,
        "reason": "Collateral quality concerns"
    },
    
    # Positive Adjustment Rules (5 rules)
    {
        "keywords": ["new order", "export order", "long term contract"],
        "pillar": "Conditions",
        "delta": 5,
        "reason": "New order secured"
    },
    {
        "keywords": ["expansion", "capex", "new plant"],
        "pillar": "Capacity",
        "delta": 4,
        "reason": "Business expansion underway"
    },
    {
        "keywords": ["promoter infusion", "equity infusion"],
        "pillar": "Capital",
        "delta": 6,
        "reason": "Promoter capital infusion"
    },
    {
        "keywords": ["clean title", "clear title", "unencumbered"],
        "pillar": "Collateral",
        "delta": 5,
        "reason": "Clean collateral title confirmed"
    },
    {
        "keywords": ["experienced management", "second generation"],
        "pillar": "Character",
        "delta": 4,
        "reason": "Strong management credentials"
    }
]
