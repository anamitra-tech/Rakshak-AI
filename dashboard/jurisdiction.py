"""
Jurisdiction-based routing: given a citizen's SELF-REPORTED state/city
(never a phone number, never a telecom circle, never GPS), look up the
correct state/UT cybercrime cell's nodal-officer contact info to surface
alongside -- never instead of -- the national 1930 helpline / NCRP portal.

This is explicitly NOT location tracking and NOT phone-number-based
geolocation. Two hard rules, both enforced in code below, not just in
this docstring:

  1. If no self-reported state/city is given, `lookup_jurisdiction()`
     returns a "location not provided" result. It never falls back to
     `telecom_circles.lookup_circle()` on a phone number -- that module is
     not even imported here.
  2. City fallback is a small, explicit table of ~20 unambiguous major
     cities (state capitals / metros), not a geocoder -- an unrecognized
     city is reported as unrecognized, never guessed.

Data source and its real limits (read before trusting this for anything
beyond a demo -- see also the module docstring's staleness warning):

  - `STATE_CYBERCRIME_CONTACTS` was captured from cybercrime.gov.in's own
    public "State/UT Nodal Officer & Grievance Officer" list
    (https://cybercrime.gov.in/Webform/Crime_NodalGrivanceList.aspx) on
    2026-07-17. All 36 states/UTs are covered by that single official
    source -- a genuinely complete table, not a partial one.
  - BUT: nodal officers are IPS/state-police postings that rotate with
    transfers. A name and direct phone number captured today WILL go
    stale on a timescale of months, unlike "1930" or "cybercrime.gov.in"
    which are stable, permanent infrastructure. Every entry below carries
    the capture date and a `verify_at` link back to the live official
    page for exactly this reason -- present the officer name/phone as
    "was correct as of the capture date", not as a guaranteed-current fact.
  - Three entries (Andhra Pradesh, Chhattisgarh, Madhya Pradesh) have NO
    phone number on the official page as captured -- email only. Flagged
    explicitly per-entry as `phone: None`, not silently omitted.
  - A finer-grained layer exists in reality (district-level cyber police
    stations, city-specific helplines e.g. Mumbai Cyber PS) that this
    table does not attempt to cover -- it is state/UT-level nodal contact
    only, matching what cybercrime.gov.in itself publishes as the single
    authoritative escalation-of-last-resort contact per state.
"""
from dataclasses import dataclass, asdict

SOURCE_URL = "https://cybercrime.gov.in/Webform/Crime_NodalGrivanceList.aspx"
CAPTURED_ON = "2026-07-17"
STALENESS_WARNING = (
    "Officer name and direct phone number are as captured from the official "
    f"portal on {CAPTURED_ON} and may be outdated (nodal officer postings "
    "rotate with IPS/state-police transfers). The email domain and "
    f"{SOURCE_URL} link are the most durable part of this record -- "
    "re-verify there before relying on a name or number for anything urgent."
)


@dataclass
class JurisdictionContact:
    state_or_ut: str
    officer_name: str
    designation: str
    phone: str | None
    email: str
    source_url: str = SOURCE_URL
    captured_on: str = CAPTURED_ON


# Captured verbatim from cybercrime.gov.in's public Nodal/Grievance Officer
# list on 2026-07-17. Keyed by canonical state/UT name.
STATE_CYBERCRIME_CONTACTS: dict[str, JurisdictionContact] = {
    "Andaman & Nicobar": JurisdictionContact("Andaman & Nicobar", "Jitendra Kumar Meena, IPS", "SSP (CID)", None, "spcid.and@nic.in"),
    "Andhra Pradesh": JurisdictionContact("Andhra Pradesh", "Adhiraj Singh Rana, IPS", "SP Cyber Crimes, CID", None, "cybercrimes1930@cid.appolice.gov.in"),
    "Arunachal Pradesh": JurisdictionContact("Arunachal Pradesh", "Shivendu Bhushan, IPS", "Nodal Officer", "9436040703", "spsit@arunpol.nic.in"),
    "Assam": JurisdictionContact("Assam", "Saurav Jyoti Saikia, APS", "SP Cyber Crime-2, CID", "0361-2521618", "sp-cid-cyber2@assampolice.gov.in"),
    "Bihar": JurisdictionContact("Bihar", "Sushil Kumar, IPS", "SP", "0612-2238098", "cybercell-bih@nic.in"),
    "Chandigarh": JurisdictionContact("Chandigarh", "Geetanjali", "SP, Cyber Crime", "0172-2700056", "spops-chd@nic.in"),
    "Chhattisgarh": JurisdictionContact("Chhattisgarh", "Kavi Gupta", "AIG", None, "aigtech-phq.cg@gov.in"),
    "Dadra & Nagar Haveli and Daman & Diu": JurisdictionContact("Dadra & Nagar Haveli and Daman & Diu", "Ketan Bansal, IPS", "IPS", "0260-2220140", "sp-dmn-dd@nic.in"),
    "Delhi": JurisdictionContact("Delhi", "Vinit Kumar, IPS", "DCP/IFSO", "011-20892633", "dcp-ifso@delhipolice.gov.in"),
    "Goa": JurisdictionContact("Goa", "Rajendra Raut Dessai", "SP, Cyber Crime", "0832-2420883", "spcyber@goapolice.gov.in"),
    "Gujarat": JurisdictionContact("Gujarat", "Vivek Bheda", "Superintendent of Police", "079-23250798", "cc-cid@gujarat.gov.in"),
    "Haryana": JurisdictionContact("Haryana", "Sibash Kabiraj, IPS", "ADGP Cyber Haryana", "0172-2524058", "sp-cybercrimephq.pol@hry.gov.in"),
    "Himachal Pradesh": JurisdictionContact("Himachal Pradesh", "Mohit Chawla, IPS", "DIG", "0177-2620331", "dig-cybercr-hp@nic.in"),
    "Jammu & Kashmir": JurisdictionContact("Jammu & Kashmir", "Ramnesh Gupta, JKPS", "SSP CICE J&K", "0191-25822926", "ssp-cicejk@jkpolice.gov.in"),
    "Jharkhand": JurisdictionContact("Jharkhand", "Ehtesham Waquarib, IPS", "SP, CID", "0651-2220060", "sp-cid@jhpolice.gov.in"),
    "Karnataka": JurisdictionContact("Karnataka", "S Ravi, ADGP", "ADGP (Intl.)", "080-22942475", "spctrcid@ksp.gov.in"),
    "Kerala": JurisdictionContact("Kerala", "Ankit Ashokan, IPS", "SP Cyber Crime", "0471-2300042", "spcyberops.pol@kerala.gov.in"),
    "Ladakh": JurisdictionContact("Ladakh", "Altaf Ahmad Shah, IPS", "SSP", "9541902324", "soto-igp@police.ladakh.gov.in"),
    "Lakshadweep": JurisdictionContact("Lakshadweep", "Utkarsha, IPS", "SP Cyber Crime", "04896262258", "lak-sop@nic.in"),
    "Madhya Pradesh": JurisdictionContact("Madhya Pradesh", "Shiyas A", "IG Cyber", None, "dig2-cybercell@mppolice.gov.in"),
    "Maharashtra": JurisdictionContact("Maharashtra", "Sanjay Shintre", "DIG Cyber Crime", "022-22160080", "dig.cbr-mah@gov.in"),
    "Manipur": JurisdictionContact("Manipur", "N. John", "Superintendent of Police", "0385-2444888", "sp-cybercrime.mn@manipur.gov.in"),
    "Meghalaya": JurisdictionContact("Meghalaya", "Basant Kumar Mishra, MPS", "DSP", "9402519391", "ccw-meg@gov.in"),
    "Mizoram": JurisdictionContact("Mizoram", "Zonun Sanga, MPS", "Nodal Officer", "0389-2334682", "cybercrime.sp@mizoram.gov.in"),
    "Nagaland": JurisdictionContact("Nagaland", "Vikram M Khalate, IPS", "IGP CID", "6009308003", "spcyber-ngl@gov.in"),
    "Odisha": JurisdictionContact("Odisha", "Shefeen Ahamed K, IPS", "IGP, CID CB", "0674-2913100", "igp2-cidcb@odishapolice.gov.in"),
    "Puducherry": JurisdictionContact("Puducherry", "Shruti Yaragatti, IPS", "SP Cyber Crime", "0413-2231313", "cybercell-police.py@gov.in"),
    "Punjab": JurisdictionContact("Punjab", "Jashandeep Singh Gill", "Superintendent of Police", "0172-2226258", "aigcc@punjabpolice.gov.in"),
    "Rajasthan": JurisdictionContact("Rajasthan", "Shantanu Kumar Singh", "Superintendent of Police", "01412821741", "sp.cybercrime@rajpolice.gov.in"),
    "Sikkim": JurisdictionContact("Sikkim", "Tenzing Loden Lepcha, IPS", "DIGP CB-CID", "9046245066", "spcid@sikkimpolice.nic.in"),
    "Tamil Nadu": JurisdictionContact("Tamil Nadu", "Shahnaz Illiyas", "SP Cyber", "044-29580300", "sp1-ccdtnpolice@gov.in"),
    "Telangana": JurisdictionContact("Telangana", "B. Sai Sri", "SP, TGCSB", "040-29320049", "spoperations-csb-ts@tspolice.gov.in"),
    "Tripura": JurisdictionContact("Tripura", "Nabadwip Jamatia, TPS", "Nodal Officer", "0381-2376979", "spcybercrime@tripurapolice.nic.in"),
    "Uttar Pradesh": JurisdictionContact("Uttar Pradesh", "Rajesh Kumar", "SP, Cyber Crime", "0522-2390538", "sp-cyber.lu@up.gov.in"),
    "Uttarakhand": JurisdictionContact("Uttarakhand", "Nilesh Anand Bharne, IPS", "IG Cyber Crime/STF", "0135-2655900", "nileshanad.bharne@ips.gov.in"),
    "West Bengal": JurisdictionContact("West Bengal", "Suresh Kumar Chadive, IPS", "DIG Cyber Crime", "033-22021200", "dig1-ccw@policewb.gov.in"),
}

# Common alternate spellings / abbreviations / former names -> canonical key.
# Extend deliberately (only add an alias you can attribute), never guess.
_STATE_ALIASES = {
    "andaman and nicobar islands": "Andaman & Nicobar", "a&n islands": "Andaman & Nicobar",
    "ap": "Andhra Pradesh",
    "arunachal": "Arunachal Pradesh",
    "chandigarh ut": "Chandigarh",
    "cg": "Chhattisgarh",
    "dnh": "Dadra & Nagar Haveli and Daman & Diu",
    "dadra and nagar haveli": "Dadra & Nagar Haveli and Daman & Diu",
    "daman and diu": "Dadra & Nagar Haveli and Daman & Diu",
    "new delhi": "Delhi", "nct of delhi": "Delhi", "delhi ncr": "Delhi",
    "j&k": "Jammu & Kashmir", "jammu and kashmir": "Jammu & Kashmir", "jk": "Jammu & Kashmir",
    "jharkhand state": "Jharkhand",
    "mp": "Madhya Pradesh",
    "maharastra": "Maharashtra", "mh": "Maharashtra",
    "pondicherry": "Puducherry",
    "orissa": "Odisha",
    "tn": "Tamil Nadu",
    "up": "Uttar Pradesh",
    "uttaranchal": "Uttarakhand",
    "wb": "West Bengal",
}

# Small, explicit major-city -> state map for the self-reported CITY
# fallback only (used when a citizen gives a city but not a state).
# Deliberately not exhaustive and never treated as a geocoder: an
# unrecognized city returns "unrecognized", not a guess.
_CITY_TO_STATE = {
    "mumbai": "Maharashtra", "pune": "Maharashtra", "nagpur": "Maharashtra", "nashik": "Maharashtra",
    "delhi": "Delhi", "new delhi": "Delhi",
    "bengaluru": "Karnataka", "bangalore": "Karnataka", "mysuru": "Karnataka",
    "chennai": "Tamil Nadu", "coimbatore": "Tamil Nadu", "madurai": "Tamil Nadu",
    "hyderabad": "Telangana", "warangal": "Telangana",
    "vijayawada": "Andhra Pradesh", "visakhapatnam": "Andhra Pradesh",
    "kolkata": "West Bengal", "howrah": "West Bengal",
    "ahmedabad": "Gujarat", "surat": "Gujarat", "vadodara": "Gujarat",
    "jaipur": "Rajasthan", "jodhpur": "Rajasthan",
    "lucknow": "Uttar Pradesh", "kanpur": "Uttar Pradesh", "varanasi": "Uttar Pradesh", "noida": "Uttar Pradesh",
    "patna": "Bihar", "gaya": "Bihar",
    "bhopal": "Madhya Pradesh", "indore": "Madhya Pradesh",
    "chandigarh": "Chandigarh",
    "kochi": "Kerala", "thiruvananthapuram": "Kerala", "kozhikode": "Kerala",
    "guwahati": "Assam",
    "bhubaneswar": "Odisha",
    "raipur": "Chhattisgarh",
    "ranchi": "Jharkhand",
    "dehradun": "Uttarakhand",
    "shimla": "Himachal Pradesh",
    "srinagar": "Jammu & Kashmir", "jammu": "Jammu & Kashmir",
    "panaji": "Goa",
    "gurugram": "Haryana", "gurgaon": "Haryana", "faridabad": "Haryana",
    "amritsar": "Punjab", "ludhiana": "Punjab", "chandigarh city": "Punjab",
}


def normalize_state(raw: str | None) -> str | None:
    """Returns a canonical state/UT name, or None if unrecognized. Never
    guesses -- exact match or a known alias only."""
    if not raw or not raw.strip():
        return None
    cleaned = raw.strip()
    if cleaned in STATE_CYBERCRIME_CONTACTS:
        return cleaned
    lowered = cleaned.lower()
    for key in STATE_CYBERCRIME_CONTACTS:
        if key.lower() == lowered:
            return key
    return _STATE_ALIASES.get(lowered)


def state_from_city(raw_city: str | None) -> str | None:
    """Small explicit lookup only -- see _CITY_TO_STATE's docstring note.
    Returns None (not a guess) for any city not in that table."""
    if not raw_city or not raw_city.strip():
        return None
    return _CITY_TO_STATE.get(raw_city.strip().lower())


def lookup_jurisdiction(state: str | None = None, city: str | None = None) -> dict:
    """The only entry point this module exposes for routing. Takes ONLY
    self-reported state/city text -- never a phone number, never a
    telecom circle. If both are absent/unrecognized, returns a
    "location not provided" result rather than falling back to any
    number-derived signal (that fallback does not exist in this codebase
    on purpose)."""
    resolved = normalize_state(state)
    resolved_via = "state" if resolved else None

    if not resolved and city:
        resolved = state_from_city(city)
        resolved_via = "city" if resolved else None

    if not resolved:
        return {
            "resolved": False,
            "reason": (
                "location not provided" if not state and not city
                else "state/city text not recognized -- not guessed from any other signal"
            ),
            "state_or_ut": None,
            "contact": None,
            "national_escalation": _national_escalation(),
        }

    contact = STATE_CYBERCRIME_CONTACTS[resolved]
    return {
        "resolved": True,
        "resolved_via": resolved_via,
        "state_or_ut": resolved,
        "contact": {**asdict(contact), "staleness_warning": STALENESS_WARNING},
        "national_escalation": _national_escalation(),
    }


def _national_escalation() -> dict:
    return {
        "helpline": "1930",
        "portal": "https://cybercrime.gov.in",
        "note": "Always available regardless of state -- report here first/in parallel; the state contact above is a supplementary escalation channel, not a replacement.",
    }


if __name__ == "__main__":
    import json
    for query in [{"state": "Maharashtra"}, {"state": "mh"}, {"city": "Bengaluru"}, {}, {"state": "Atlantis"}]:
        print(query, "->", json.dumps(lookup_jurisdiction(**query), indent=2)[:300])
