import os
import pytest
from dotenv import load_dotenv

load_dotenv()


@pytest.fixture
def sample_sites() -> list[dict]:
    """Sample sites data as would come from the Sites sheet tab."""
    return [
        {
            "Site ID": "ASM-TR-01",
            "Customer": "Anadolu Sağlık Merkezi",
            "City": "Gebze",
            "Country": "TR",
            "Facility Type": "Healthcare",
            "Contract Status": "Active",
        },
        {
            "Site ID": "MIG-TR-01",
            "Customer": "Migros",
            "City": "Istanbul",
            "Country": "TR",
            "Facility Type": "Food",
            "Contract Status": "Active",
        },
        {
            "Site ID": "MCD-EG-01",
            "Customer": "McDonald's",
            "City": "Cairo",
            "Country": "EG",
            "Facility Type": "Food",
            "Contract Status": "Active",
        },
    ]
