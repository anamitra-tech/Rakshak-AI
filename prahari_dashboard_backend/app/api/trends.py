import urllib.parse
import xml.etree.ElementTree as ET
import requests
from fastapi import APIRouter, Query
from typing import List, Optional
from pydantic import BaseModel
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

class TrendItem(BaseModel):
    title: str
    link: str
    pubDate: str

@router.get("/trends", response_model=List[TrendItem])
def get_trends(scam_type: Optional[str] = Query(None)):
    """
    Fetches live internet OSINT (news headlines) for the specified scam type,
    or general cyber fraud trends if no type is specified.
    """
    if scam_type:
        # Convert e.g., 'authority_impersonation' to 'authority impersonation'
        clean_type = scam_type.replace('_', ' ')
        query_str = f"{clean_type} scam india latest"
    else:
        query_str = "cyber fraud scams india latest"
        
    query = urllib.parse.quote(query_str)
    url = f"https://news.google.com/rss/search?q={query}&hl=en-IN&gl=IN&ceid=IN:en"
    
    try:
        res = requests.get(url, timeout=5)
        res.raise_for_status()
        
        root = ET.fromstring(res.text)
        items = root.findall(".//item")
        
        trends = []
        for item in items[:4]:  # Top 4 headlines
            title = item.find("title").text if item.find("title") is not None else ""
            link = item.find("link").text if item.find("link") is not None else ""
            pubDate = item.find("pubDate").text if item.find("pubDate") is not None else ""
            
            # Clean up title by removing the source at the end (e.g., " - The Times of India")
            if " - " in title:
                title = title.rsplit(" - ", 1)[0]
                
            trends.append(TrendItem(title=title, link=link, pubDate=pubDate))
            
        return trends
    except Exception as e:
        logger.error(f"Error fetching live trends from RSS: {e}")
        # Fallback if internet request fails
        return [
            TrendItem(
                title="Authorities warn of new sophisticated cyber fraud tactics across India.",
                link="#",
                pubDate="Just now"
            ),
            TrendItem(
                title="Increase in targeted phishing attacks reported this week.",
                link="#",
                pubDate="Just now"
            )
        ]
