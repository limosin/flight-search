"""
Utilities for data ingestion
"""

from datetime import datetime, timezone
from typing import Dict, Optional
import pytz


# Mapping of IATA codes to airport details
AIRPORT_DATA = {
    'DEL': {'name': 'Indira Gandhi Airport', 'city': 'New Delhi', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'BOM': {'name': 'Chatrapati Shivaji Airport', 'city': 'Mumbai', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'BLR': {'name': 'Kempegowda International Airport', 'city': 'Bengaluru', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'MAA': {'name': 'Chennai International Airport', 'city': 'Chennai', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'CCU': {'name': 'Netaji Subhas Chandra Bose International Airport', 'city': 'Kolkata', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'HYD': {'name': 'Rajiv Gandhi International', 'city': 'Hyderabad', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'AMD': {'name': 'Sardar Vallabh Bhai Patel', 'city': 'Ahmedabad', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'PNQ': {'name': 'Lohegaon', 'city': 'Pune', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'GOI': {'name': 'Dabolim Airport', 'city': 'Goa', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'GOX': {'name': 'Manohar International Airport', 'city': 'Goa', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'COK': {'name': 'Cochin International Airport', 'city': 'Kochi', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'JAI': {'name': 'Jaipur International Airport', 'city': 'Jaipur', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'ISK': {'name': 'Ozhar Airport', 'city': 'Nasik', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'IDR': {'name': 'Devi Ahilya Bai Holkar Airport', 'city': 'Indore', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'LKO': {'name': 'Chaudhary Charan Singh International Airport', 'city': 'Lucknow', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'PAT': {'name': 'Lok Nayak Jayaprakash Airport', 'city': 'Patna', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'VNS': {'name': 'Lal Bahadur Shastri Airport', 'city': 'Varanasi', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'IXR': {'name': 'Birsa Munda Airport', 'city': 'Ranchi', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'RPR': {'name': 'Swami Vivekananda Airport', 'city': 'Raipur', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'BBI': {'name': 'Biju Patnaik International Airport', 'city': 'Bhubaneswar', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'IXB': {'name': 'Bagdogra Airport', 'city': 'Bagdogra', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'GAU': {'name': 'Lokpriya Gopinath Bordoloi International Airport', 'city': 'Guwahati', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'IXZ': {'name': 'Veer Savarkar International Airport', 'city': 'Port Blair', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'NAG': {'name': 'Dr. Babasaheb Ambedkar International Airport', 'city': 'Nagpur', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'TRV': {'name': 'Trivandrum International Airport', 'city': 'Thiruvananthapuram', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'CCJ': {'name': 'Calicut International Airport', 'city': 'Kozhikode', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'VGA': {'name': 'Vijayawada Airport', 'city': 'Vijayawada', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'VTZ': {'name': 'Visakhapatnam Airport', 'city': 'Visakhapatnam', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'IXE': {'name': 'Mangalore International Airport', 'city': 'Mangaluru', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'DBR': {'name': 'Darbhanga Airport', 'city': 'Darbhanga', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'HDO': {'name': 'Halwara Airport', 'city': 'Ludhiana', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'AYJ': {'name': 'Maharana Pratap Airport', 'city': 'Udaipur', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'CJB': {'name': 'Coimbatore International Airport', 'city': 'Coimbatore', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'IXC': {'name': 'Chandigarh International Airport', 'city': 'Chandigarh', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'IXD': {'name': 'Allahabad Airport', 'city': 'Prayagraj', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'IXG': {'name': 'Belgaum Airport', 'city': 'Belagavi', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'JDH': {'name': 'Jodhpur Airport', 'city': 'Jodhpur', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
    'STV': {'name': 'Surat Airport', 'city': 'Surat', 'country': 'India', 'country_code': 'IN', 'timezone': 'Asia/Kolkata'},
}

# Carrier data
CARRIER_DATA = {
    '6E': {'name': 'IndiGo'},
    'AI': {'name': 'Air India'},
    'IX': {'name': 'Air India Express'},
    'QP': {'name': 'Akasa Air'},
    'SG': {'name': 'SpiceJet'},
    'S5': {'name': 'Star Air'},
}


def parse_datetime_from_api(datetime_str: str, timezone_str: str = 'Asia/Kolkata') -> datetime:
    """
    Parse datetime string from API response and convert to UTC
    
    Args:
        datetime_str: ISO format datetime string (e.g., "2025-10-10T23:00:00.000+05:30")
        timezone_str: Timezone name for the datetime
        
    Returns:
        datetime object in UTC
    """
    # Parse the datetime string (it should already have timezone info)
    dt = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
    
    # If no timezone info, assume the provided timezone
    if dt.tzinfo is None:
        tz = pytz.timezone(timezone_str)
        dt = tz.localize(dt)
    
    # Convert to UTC
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def get_service_date(departure_time_utc: datetime, origin_timezone: str) -> datetime:
    """
    Get service date (local departure date at origin)
    
    Args:
        departure_time_utc: Departure time in UTC
        origin_timezone: Origin airport timezone
        
    Returns:
        Date object representing the service date
    """
    tz = pytz.timezone(origin_timezone)
    local_time = departure_time_utc.replace(tzinfo=timezone.utc).astimezone(tz)
    return local_time.date()


def calculate_duration_minutes(departure_time: datetime, arrival_time: datetime) -> int:
    """
    Calculate duration in minutes between two datetimes
    
    Args:
        departure_time: Departure datetime
        arrival_time: Arrival datetime
        
    Returns:
        Duration in minutes
    """
    delta = arrival_time - departure_time
    return int(delta.total_seconds() / 60)


def extract_carriers_from_route_data(carriers_str: str) -> list:
    """
    Extract carrier codes from comma-separated string
    
    Args:
        carriers_str: Comma-separated carrier codes (e.g., "6E, AI, IX")
        
    Returns:
        List of carrier codes
    """
    if not carriers_str:
        return []
    return [c.strip() for c in carriers_str.split(',')]


def extract_layover_airports(layover_str: str) -> list:
    """
    Extract layover airport codes from comma-separated string
    
    Args:
        layover_str: Comma-separated airport codes (e.g., "BOM, DEL, GOI")
        
    Returns:
        List of airport codes
    """
    if not layover_str:
        return []
    return [a.strip() for a in layover_str.split(',')]


def generate_fare_key(flight_data: Dict) -> str:
    """
    Generate a unique fare key from flight data
    This is simplified - in production, use the actual fareId from API
    
    Args:
        flight_data: Dictionary containing flight information
        
    Returns:
        Unique fare key string
    """
    # In real implementation, this would use the fareId from the API response
    # For now, create a simple composite key
    return flight_data.get('fareId', f"{flight_data.get('travelOptionId', '')}_{datetime.utcnow().timestamp()}")


def safe_get(data: Dict, *keys, default=None):
    """
    Safely get nested dictionary values
    
    Args:
        data: Dictionary to search
        *keys: Sequence of keys to traverse
        default: Default value if key not found
        
    Returns:
        Value at the nested key or default
    """
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key, default)
        else:
            return default
    return data
