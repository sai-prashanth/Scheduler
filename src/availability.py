from typing import List, Dict, Tuple, Any
import pandas as pd
from datetime import datetime, timedelta, date, time
import tzlocal
from dataclasses import dataclass

# Constants
SLOT_INTERVAL = 15  # minutes
TIME_SLOT_FREQ = f"{SLOT_INTERVAL}T"
LOCAL_TZ = tzlocal.get_localzone()

@dataclass
class TimeSlot:
    date: datetime
    weekday: str
    start_time: datetime
    end_time: datetime

def round_time_to_nearest_slot(dt: datetime) -> datetime:
    """Round a datetime to the nearest 15-minute slot."""
    minutes = dt.minute
    rounded_minutes = (minutes // SLOT_INTERVAL) * SLOT_INTERVAL
    return dt.replace(minute=rounded_minutes, second=0, microsecond=0)

def create_daily_time_slots(date: datetime, start_time: time, end_time: time) -> List[TimeSlot]:
    """Create 15-minute time slots for a specific date between start and end times."""
    slots = []
    
    # Create base datetime for start and end
    day_start = datetime.combine(date.date(), start_time)
    day_end = datetime.combine(date.date(), end_time)
    
    # Round to nearest 15-min intervals
    current = round_time_to_nearest_slot(day_start)
    end = round_time_to_nearest_slot(day_end)
    
    while current <= end:
        slots.append(TimeSlot(
            date=current.date(),
            weekday=current.strftime('%A'),
            start_time=current,
            end_time=current + timedelta(minutes=SLOT_INTERVAL)
        ))
        current += timedelta(minutes=SLOT_INTERVAL)
    
    return slots

def create_time_slots(
    start_date: datetime,
    end_date: datetime,
    working_hours: Tuple[time, time],
    working_days: List[str]
) -> pd.DataFrame:
    """
    Create available time slots for the given date range and working hours.
    
    Args:
        start_date: Start datetime
        end_date: End datetime
        working_hours: Tuple of (start_time, end_time)
        working_days: List of working days (e.g., ["Monday", "Tuesday"])
    
    Returns:
        DataFrame with columns: date, weekday, slot_start, slot_end
    """
    all_slots = []
    current_date = start_date
    
    while current_date <= end_date:
        if current_date.strftime('%A') in working_days:
            daily_slots = create_daily_time_slots(
                current_date,
                working_hours[0],
                working_hours[1]
            )
            all_slots.extend(daily_slots)
        current_date += timedelta(days=1)
    
    # Convert to DataFrame
    slots_df = pd.DataFrame([
        {
            'date': slot.date,
            'weekday': slot.weekday,
            'slot_start': slot.start_time,
            'slot_end': slot.end_time
        }
        for slot in all_slots
    ])
    
    return slots_df

def get_available_slots(
    time_slots_df: pd.DataFrame,
    busy_slots: List[Dict[str, Any]]
) -> pd.DataFrame:
    """
    Find available time slots by removing busy periods.
    
    Args:
        time_slots_df: DataFrame of all possible time slots
        busy_slots: List of busy period dictionaries with 'start' and 'end' keys
    
    Returns:
        DataFrame of available time slots
    """
    # Convert busy slots to DataFrame with datetime objects
    busy_df = pd.DataFrame(busy_slots)
    busy_df['start'] = pd.to_datetime(busy_df['start'])
    busy_df['end'] = pd.to_datetime(busy_df['end'])
    
    # Create mask for available slots
    def is_slot_available(row):
        slot_start = row['slot_start']
        slot_end = row['slot_end']
        
        for _, busy in busy_df.iterrows():
            if (slot_start >= busy['start'] and slot_start < busy['end']) or \
               (slot_end > busy['start'] and slot_end <= busy['end']) or \
               (slot_start <= busy['start'] and slot_end >= busy['end']):
                return False
        return True
    
    # Apply filter and return available slots
    available_slots = time_slots_df[time_slots_df.apply(is_slot_available, axis=1)].copy()
    return available_slots

if __name__ == "__main__":
    # Example parameters
    start_date = datetime.now()
    end_date = start_date + timedelta(days=30)
    working_hours = (time(9, 0), time(17, 0))
    working_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    
    # Create all possible time slots
    slots = create_time_slots(start_date, end_date, working_hours, working_days)
    
    # Example busy slots
    busy_slots = [
        {
            'start': '2025-01-27T10:00:00',
            'end': '2025-01-27T10:00:00'
        }
    ]
        
    # Get available slots
    available = get_available_slots(slots, busy_slots)
    print(f"Found {len(available)} available slots")
    
    # Save to CSV
    available.to_csv('../data/available_slots.csv', index=False)