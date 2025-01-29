import pandas as pd
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass
import json
from textwrap import dedent
from src.llm_utils import ask_llm, create_prompt
from src.config import MODEL

file_path = '../data/Bret - Client Management - Sheet1.csv'

@dataclass
class Client:
    name: str
    email: str

@dataclass
class ClientPreferences:
    client: Client
    location: str # online or in-person
    session_duration: int # in minutes
    num_weekly_sessions: int
    num_monthly_sessions: int
    preferred_days: List[str]
    preferred_times: List[str] # list of start and end times - e.g., ["6:00 AM to 8:00 AM", "10:00 AM to  12:00 PM"]
    unavailable_dates: Dict[str, List[str]] # list of dates in YYYY-MM-DD format

def clean_raw_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and standardize the raw input data"""
    cleaned = df.copy()
    # Standardize column names - strip, lowercase, and replace spaces with underscores
    cleaned.columns = cleaned.columns.str.strip().str.lower().str.replace(" ", "_")
    # Rename session_duration_(mins) to session_duration
    cleaned.rename(columns={"session_duration_(mins)": "session_duration"}, inplace=True)
    
    # Remove any leading/trailing whitespace
    for col in cleaned.columns:
        if cleaned[col].dtype == 'object':
            cleaned[col] = cleaned[col].str.strip()
    return cleaned

def create_extraction_prompt(row: pd.Series, **kwargs) -> str:
    """Create a prompt for the LLM to extract structured information"""
    # prompt_template = """
    # Extract structured information from the following client scheduling preferences.
    #     Today: {date}
    #     Weekday: {weekday_name}
    #     Location: {location}
    #     Preferred Days: {preferred_days}
    #     Preferred Times: {preferred_times}
    #     Weekly Sessions: {weekly_sessions}
    #     Session Duration: {session_duration}
    #     Monthly Max Sessions: {monthly_max}
    #     Client Message: {responses}
        
    # For prefered times if client says anytime or flexible etc, just leave it blank 
    # if the say early morning, morning, afternoon, evening, night etc then add those times: 6:00 AM to 8:00 AM, 9:00 AM to  12:00 PM etc

    # Please provide a JSON response with this exact structure:
    #     {{
    #         "location": "Lab|Remote",
    #         "session_duration": "<integer minutes>",
    #         "num_weekly_sessions": "<integer>",
    #         "num_monthly_sessions": "<integer>",
    #         "preferred_days": ["Monday", "Tuesday", "etc"],
    #         "preferred_times": ["6:00 to 8:00", "10:00 to  14:00"],
    #         "unavailable_dates": ["YYYY-MM-DD"]
    #     }}
    # """
    
    prompt_template = """
    You are an AI assistant tasked with extracting and structuring client scheduling preferences for an monthly appointment booking system. Your goal is to provide reliable and consistent output that can be used for scheduling optimization.

Here is the input data:

<client_message>{responses}</client_message>
<date>{date}</date>
<weekday_name>{weekday_name}</weekday_name>
<location>{location}</location>
<preferred_days>{preferred_days}</preferred_days>
<preferred_times>{preferred_times}</preferred_times>
<weekly_sessions>{weekly_sessions}</weekly_sessions>
<session_duration>{session_duration}</session_duration>
<monthly_max>{monthly_max}</monthly_max>

Your task is to parse this information and structure it into a JSON format. Follow these steps:

1. Analyze the input data carefully.
2. Extract the relevant information for each field.
3. Validate and process the data according to the specific rules for each field.
4. Structure the processed data into the required JSON format.

Use the following guidelines for processing each field:

- Location: Must be either "Lab" or "Remote". If invalid, default to Lab.
- Session Duration: Convert to integer minutes.
- Weekly Sessions: Convert to integer.
- Monthly Max Sessions: Convert to integer.
- Preferred Days: List of day names (Monday, Tuesday, etc.).
- Preferred Times: 
  - If client says "anytime" or "flexible", leave blank.
  - Use these ranges:
    - Early Morning: 6:00 AM to 9:00 AM
    - Morning: 9:00 AM to 12:00 PM
    - Afternoon: 12:00 PM to 3:00 PM
    - Evening: 3:00 PM to 6:00 PM
    - Night: 6:00 PM to 9:00 PM
 - For other specific times, format as "6:00 to 9:00", "10:00 to 14:00", etc.
- Unavailable Dates: Extract any mentioned dates and format as YYYY-MM-DD.

The final output should be a JSON object with the following structure:

{{
  "location": "Lab|Remote",
  "session_duration": "<integer minutes>",
  "num_weekly_sessions": "<integer>",
  "num_monthly_sessions": "<integer>",
  "preferred_days": ["Monday", "Tuesday", "etc"],
  "preferred_times": ["6:00 to 9:00", "10:00 to 14:00"],
  "unavailable_dates": ["YYYY-MM-DD"]
}}

Ensure that all integer values are properly parsed and validated. If any required information is missing or cannot be reliably extracted, use null or an empty array as appropriate.

Now, please process the input data and provide the structured JSON output.
"""

    return create_prompt(
        dedent(prompt_template),
        date=kwargs.get("date", ""),
        weekday_name=kwargs.get("weekday_name", ""),
        location=getattr(row, 'location', ''),
        preferred_days=getattr(row, 'preferred_days', ''),
        preferred_times=getattr(row, 'preferred_times', ''),
        weekly_sessions=getattr(row, 'weekly_sessions', ''),
        session_duration=getattr(row, 'session_duration', ''),
        monthly_max=getattr(row, 'monthly_max_sessions', ''),
        responses=getattr(row, 'responses', '')
    )

def parse_llm_response(response: str) -> Optional[Dict]:
    """Parse the LLM JSON response into a dictionary"""
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        print(f"Failed to parse LLM response: {response}")
        return None

def process_client_data(df, start_date=datetime.now()) -> List[ClientPreferences]:
    """Main function to process client data and return structured preferences"""
    # Clean the raw data
    df_cleaned = clean_raw_data(df)
    
    # If more than 30 rows, break with a msg to avoid processing large files
    if len(df_cleaned) > 30:
        print("Detected more than 30 rows in the input file. Please process the data in smaller chunks.")
        raise ValueError("Too many rows in the input file.")
    
    client_preferences = []
    
    for row in df_cleaned.itertuples():
        # Create client object (keeping private info separate)
        client = Client(name=row.client_name, email=row.client_email)
        
        # Extract preferences using LLM
        prompt = create_extraction_prompt(row, date=start_date, weekday_name=start_date.strftime("%A"))
        llm_response = ask_llm(model=MODEL, prompt=prompt, json_mode=True)
        preferences = parse_llm_response(llm_response)
        
        if preferences:
            client_pref = ClientPreferences(
                client=client,
                **preferences
            )
            client_preferences.append(client_pref)
    
    return client_preferences

def create_client_dataframe(client_preferences: List[ClientPreferences]) -> pd.DataFrame:
    """Convert list of ClientPreferences to a pandas DataFrame"""
    client_data = []
    for pref in client_preferences:
        client_dict = {
            'name': pref.client.name,
            'email': pref.client.email,
            'location': pref.location,
            'session_duration': pref.session_duration,
            'num_weekly_sessions': pref.num_weekly_sessions,
            'num_monthly_sessions': pref.num_monthly_sessions,
            'preferred_days': ', '.join(pref.preferred_days),
            'preferred_times': ', '.join(pref.preferred_times),
            'unavailable_dates': ', '.join(pref.unavailable_dates)
        }
        client_data.append(client_dict)
    
    return pd.DataFrame(client_data)

if __name__ == "__main__":
    file_path = '../data/Bret - Client Management - Sheet1.csv'
    df = pd.read_csv(file_path)
    client_preferences = process_client_data(file_path)
    print(f"Processed {len(client_preferences)} client preferences")
    
    # Create and display the client DataFrame
    client_df = create_client_dataframe(client_preferences)
    print("\nClient Preferences DataFrame:")
    print(client_df)
    
    # Optionally save to CSV
    output_path = '../data/processed_client_preferences.csv'
    client_df.to_csv(output_path, index=False)
    print(f"\nSaved processed data to: {output_path}")

