import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional, Any
import numpy as np

def parse_time_range(time_str: str) -> List[Tuple[int, int]]:
    """
    Parse time ranges from string format into list of (start_hour, end_hour) tuples
    Example: "6:00 to 9:00, 14:00 to 17:00" -> [(6, 9), (14, 17)]
    """
    if not isinstance(time_str, str) or not time_str:
        return []
    
    time_ranges = []
    try:
        ranges = [r.strip() for r in time_str.split(',')]
        for r in ranges:
            start, end = r.split(' to ')
            start_hour = int(start.split(':')[0])
            end_hour = int(end.split(':')[0])
            time_ranges.append((start_hour, end_hour))
        return time_ranges
    except:
        return []

def parse_days(days_str: str) -> List[int]:
    """Convert day names to weekday numbers (0-6)"""
    if not isinstance(days_str, str) or not days_str:
        return []
    
    day_map = {
        'monday': 0, 'tuesday': 1, 'wednesday': 2,
        'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6
    }
    
    try:
        return [day_map[day.lower().strip()] 
                for day in days_str.split(',')]
    except:
        return []

def parse_unavailable_dates(dates_str: str) -> List[datetime]:
    """Convert date strings to datetime objects"""
    if not isinstance(dates_str, str) or not dates_str:
        return []
    
    try:
        return [datetime.strptime(date.strip(), '%Y-%m-%d') 
                for date in dates_str.split(',')]
    except:
        return []

def create_availability_blocks(availability_df: pd.DataFrame) -> Dict[datetime, List[Dict]]:
    """
    Convert availability DataFrame to Dict format for scheduling
    
    Args:
        availability_df: DataFrame with columns: date, weekday, slot_start, slot_end
    
    Returns:
        Dict[datetime, List[Dict]]: {date: [{'start': datetime, 'end': datetime, 'booked': False}, ...]}
    """
    availability = {}
    
    # Convert dates to datetime if they're not already
    availability_df['date'] = pd.to_datetime(availability_df['date']).dt.date
    availability_df['slot_start'] = pd.to_datetime(availability_df['slot_start'])
    availability_df['slot_end'] = pd.to_datetime(availability_df['slot_end'])
    
    # Group by date
    for date, group in availability_df.groupby('date'):
        blocks = []
        for _, row in group.iterrows():
            blocks.append({
                'start': row['slot_start'],
                'end': row['slot_end'],
                'booked': False
            })
        availability[date] = blocks
    
    return availability

def is_slot_available(blocks: List[Dict], start_idx: int, 
                     num_blocks: int, time_ranges: List[Tuple[int, int]]) -> bool:
    """Check if consecutive blocks are available and within preferred times"""
    if not blocks or start_idx + num_blocks > len(blocks):
        return False
        
    start_hour = blocks[start_idx]['start'].hour
    end_hour = blocks[start_idx + num_blocks - 1]['end'].hour
    
    # Check if time is within any preferred range
    in_preferred_time = False
    for start_range, end_range in time_ranges:
        if start_hour >= start_range and end_hour <= end_range:
            in_preferred_time = True
            break
    
    if not in_preferred_time:
        return False
    
    # Check if all blocks are available
    return all(not blocks[i]['booked'] 
              for i in range(start_idx, start_idx + num_blocks))

def find_available_slot(availability: Dict, date: datetime, 
                       duration: int, preferred_times: List[Tuple[int, int]], 
                       block_size: int = 15) -> Optional[Tuple[datetime, datetime]]:
    """Find first available slot on given date matching preferences"""
    date_key = date.date() if isinstance(date, datetime) else date
    
    if date_key not in availability:
        print(f"No availability found for date: {date_key}")
        return None
    
    blocks = availability[date_key]
    if not blocks:
        print(f"Empty blocks for date: {date_key}")
        return None

    num_blocks = duration // block_size
    # print(f"Looking for {num_blocks} consecutive blocks on {date_key}")
    
    for i in range(len(blocks) - num_blocks + 1):
        if is_slot_available(blocks, i, num_blocks, preferred_times):
            return (blocks[i]['start'], blocks[i + num_blocks - 1]['end'])
    
    return None

def schedule_sessions(clients_df: pd.DataFrame, 
                      availability_df: pd.DataFrame,
                      start_date: datetime, 
                      end_date: datetime,
                      block_size: int = 15) -> Dict[str, List[Dict]]:
    """
    Schedule sessions for all clients
    Returns: {client_name: [{'start': datetime, 'end': datetime}, ...]}
    """
    # Input validation
    if clients_df.empty or availability_df.empty:
        print("Warning: Empty input dataframes")
        return {}

    print(f"Processing {len(clients_df)} clients")
    print(f"Available slots: {len(availability_df)} time slots")
    
    # Initialize availability calendar
    availability = create_availability_blocks(availability_df)
    print(f"Created availability blocks for {len(availability)} dates")
    
    # Calculate weeks (handle partial first week)
    days_to_monday = (7 - start_date.weekday()) % 7
    first_monday = start_date + timedelta(days=days_to_monday)
    num_full_weeks = (end_date - first_monday).days // 7
    
    # Sort clients by priority
    clients_df = clients_df.assign(
        priority=lambda x: x['session_duration'] * x['num_weekly_sessions']
    ).sort_values('priority', ascending=False)
    
    schedule = {}
    
    for _, client in clients_df.iterrows():
        print(f"\nProcessing client: {client['name']}")
        schedule[client['name']] = []
        preferred_times = parse_time_range(client['preferred_times'])
        preferred_days = parse_days(client['preferred_days'])
        blocked_dates = parse_unavailable_dates(client['unavailable_dates'])
        
        print(f"Preferred times: {preferred_times}")
        print(f"Preferred days: {preferred_days}")
        print(f"Blocked dates: {blocked_dates}")

        # Track sessions per week for each client
        weekly_sessions = {}
        
        # Schedule partial first week
        if days_to_monday > 0 and first_monday <= end_date:
            _schedule_partial_week(
                client, schedule, availability, 
                start_date, first_monday - timedelta(days=1), 
                preferred_days, preferred_times, blocked_dates,
                block_size, weekly_sessions, start_date
            )
        
        # Schedule full weeks
        current_monday = first_monday
        for week in range(num_full_weeks):
            _schedule_week(
                client, schedule, availability,
                current_monday, 
                preferred_times, preferred_days, blocked_dates,
                block_size, weekly_sessions, start_date
            )
            current_monday += timedelta(days=7)
        
        # Schedule remaining days (partial last week)
        if current_monday <= end_date:
            _schedule_partial_week(
                client, schedule, availability,
                current_monday, end_date,
                preferred_days, preferred_times, blocked_dates,
                block_size, weekly_sessions, start_date
            )
    
    return schedule

def get_week_number(date: datetime, start_date: datetime) -> int:
    """Return the week number relative to start_date"""
    return (date - start_date).days // 7

def _schedule_partial_week(client: pd.Series, 
                          schedule: Dict, 
                          availability: Dict,
                          start: datetime,
                          end: datetime,
                          preferred_days: List[int],
                          preferred_times: List[Tuple[int, int]],
                          blocked_dates: List[datetime],
                          block_size: int,
                          weekly_sessions: Dict[int, int],
                          start_date: datetime):
    """Helper function to schedule sessions in a partial week"""
    used_dates = set()
    week_num = get_week_number(start, start_date)
    sessions_left = client['num_weekly_sessions'] - weekly_sessions.get(week_num, 0)
    
    if sessions_left <= 0:
        return

    # Generate all dates in the range and sort them by preference
    date_range = []
    current = start
    while current <= end:
        date_range.append(current)
        current += timedelta(days=1)
    
    # Sort dates putting preferred days first
    date_range.sort(key=lambda d: (d.weekday() not in preferred_days, d))

    # First try preferred days and times
    for current in date_range:
        if sessions_left <= 0:
            break
            
        if (current not in blocked_dates and 
            current.date() not in used_dates):
            # Try preferred times first for all days
            slot = find_available_slot(
                availability, current,
                client['session_duration'],
                preferred_times,
                block_size
            )
            if slot:
                schedule[client['name']].append({
                    'start': slot[0],
                    'end': slot[1]
                })
                _mark_slot_booked(availability, slot[0], slot[1])
                used_dates.add(current.date())
                weekly_sessions[week_num] = weekly_sessions.get(week_num, 0) + 1
                sessions_left -= 1
    
    # If sessions remain, try any available time slot
    if sessions_left > 0:
        all_times = [(0, 24)]
        for current in date_range:
            if sessions_left <= 0:
                break
                
            if (current not in blocked_dates and 
                current.date() not in used_dates):
                slot = find_available_slot(
                    availability, current,
                    client['session_duration'],
                    all_times,
                    block_size
                )
                if slot:
                    schedule[client['name']].append({
                        'start': slot[0],
                        'end': slot[1]
                    })
                    _mark_slot_booked(availability, slot[0], slot[1])
                    used_dates.add(current.date())
                    weekly_sessions[week_num] = weekly_sessions.get(week_num, 0) + 1
                    sessions_left -= 1

def _schedule_week(client: pd.Series, 
                  schedule: Dict,
                  availability: Dict,
                  week_start: datetime,
                  preferred_times: List[Tuple[int, int]],
                  preferred_days: List[int],
                  blocked_dates: List[datetime],
                  block_size: int,
                  weekly_sessions: Dict[int, int],
                  start_date: datetime):
    """Helper function to schedule sessions in a full week"""
    week_num = get_week_number(week_start, start_date)
    sessions_left = client['num_weekly_sessions'] - weekly_sessions.get(week_num, 0)
    used_dates = set()
    
    if sessions_left <= 0:
        return

    # Generate all dates in the week and sort them by preference
    date_range = []
    current = week_start
    while current < week_start + timedelta(days=7):
        date_range.append(current)
        current += timedelta(days=1)
    
    # Sort dates putting preferred days first
    date_range.sort(key=lambda d: (d.weekday() not in preferred_days, d))

    # Try scheduling with preferred times
    for current in date_range:
        if sessions_left <= 0:
            break
            
        if (current not in blocked_dates and 
            current.date() not in used_dates):
            slot = find_available_slot(
                availability, current,
                client['session_duration'],
                preferred_times,
                block_size
            )
            if slot:
                schedule[client['name']].append({
                    'start': slot[0],
                    'end': slot[1]
                })
                _mark_slot_booked(availability, slot[0], slot[1])
                weekly_sessions[week_num] = weekly_sessions.get(week_num, 0) + 1
                sessions_left -= 1
                used_dates.add(current.date())
    
    # If sessions remain, try any available time slot
    if sessions_left > 0:
        all_times = [(0, 24)]
        for current in date_range:
            if sessions_left <= 0:
                break
                
            if (current not in blocked_dates and 
                current.date() not in used_dates):
                slot = find_available_slot(
                    availability, current,
                    client['session_duration'],
                    all_times,
                    block_size
                )
                if slot:
                    schedule[client['name']].append({
                        'start': slot[0],
                        'end': slot[1]
                    })
                    _mark_slot_booked(availability, slot[0], slot[1])
                    weekly_sessions[week_num] = weekly_sessions.get(week_num, 0) + 1
                    sessions_left -= 1
                    used_dates.add(current.date())

def _mark_slot_booked(availability: Dict, 
                      start: datetime, 
                      end: datetime):
    """Mark time slots as booked in availability"""
    date = start.date()
    for block in availability[date]:
        if start <= block['start'] < end:
            block['booked'] = True

def print_schedule(schedule):
    """Print the schedule in a readable format"""
    for client, sessions in schedule.items():
        print(f"\nSchedule for {client}:")
        for session in sorted(sessions, key=lambda x: x['start']):
            print(f"  {session['start'].strftime('%Y-%m-%d %H:%M')} - "
                  f"{session['end'].strftime('%H:%M')}")

# Example usage
if __name__ == "__main__":
    # Sample data loading
    try:
        clients_df = pd.read_csv('../data/processed_client_preferences.csv')
        # print("\nClient data:")
        # print(clients_df.head())
        
        availability_df = pd.read_csv('../data/available_slots.csv')
        # Convert datetime columns
        availability_df['slot_start'] = pd.to_datetime(availability_df['slot_start'])
        availability_df['slot_end'] = pd.to_datetime(availability_df['slot_end'])
        # print("\nAvailability data:")
        # print(availability_df.head())
        
        start_date = datetime(2025, 2, 2)
        end_date = datetime(2025, 2, 2)
        
        print(f"\nScheduling from {start_date} to {end_date}")
        schedule = schedule_sessions(clients_df, availability_df, start_date, end_date)
        print("\nFinal Schedule:")
        print_schedule(schedule)
        
    except Exception as e:
        print(f"Error occurred: {str(e)}")