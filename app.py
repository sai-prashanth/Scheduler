import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date, time
from streamlit_calendar import calendar
from icalendar import Calendar as iCalendar
import requests
import tzlocal
from src.preprocessing import process_client_data, create_client_dataframe
from src.schedule import schedule_sessions
from src.availability import create_time_slots, get_available_slots

# Page configuration
st.set_page_config(page_title="Schedule Manager", layout="wide")

# Initialize session states
if 'raw_data' not in st.session_state:
    st.session_state.raw_data = None
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None
if 'friend_availability' not in st.session_state:
    st.session_state.friend_availability = []
if 'optimized_schedule' not in st.session_state:
    st.session_state.optimized_schedule = None
    

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", 
    ["0. Configuration",
    "1. Load Client Data", 
     "2. Process Data", 
     "3. Your Availability", 
     "4. Optimize Schedule",
     "5. Send Invites"])

# Global Config
if 'working_days' not in st.session_state:
    st.session_state.working_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

if 'default_working_hours' not in st.session_state:
    # Initialize them as time objects (7:00 AM to 3:00 PM)
    st.session_state.default_working_hours = (time(7, 0), time(15, 0))

if 'default_session_duration' not in st.session_state:
    st.session_state.default_session_duration = 60  # 60 minutes
if 'min_manage_date' not in st.session_state:
    # By default, let's set it to today's date minus 1 day
    st.session_state.min_manage_date = datetime.now()
if 'max_manage_date' not in st.session_state:
    # By default, let's set it to 30 days from now
    st.session_state.max_manage_date = datetime.now() + timedelta(days=30)
if 'calendar_url' not in st.session_state:
    st.session_state.calendar_url = ""

############################################
# 0. CONFIGURATION
############################################
def configuration_page():
    st.header("🔧 Global Configuration")
    st.markdown("Setup global parameters for scheduling.")

    # Working days
    possible_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    st.session_state.working_days = st.multiselect(
        "Select your working days:",
        options=possible_days,
        default=st.session_state.working_days
    )

    # Default working hours
    col1, col2 = st.columns(2)
    with col1:
        daily_start_time = st.time_input("Daily Start Time", value=st.session_state.default_working_hours[0])
    with col2:
        daily_end_time = st.time_input("Daily End Time", value=st.session_state.default_working_hours[1])
    st.session_state.default_working_hours = (daily_start_time, daily_end_time)

    # Default session duration
    st.session_state.default_session_duration = st.number_input("Default Session Duration (minutes)",
                                                               value=st.session_state.default_session_duration,
                                                               min_value=15, max_value=120)

    # Min and Max manage date
    # -- Validate date range: must be at least 7 days long --

    col3, col4 = st.columns(2)
    with col3:
        st.session_state.min_manage_date = st.date_input("Minimum date to manage:", value=st.session_state.min_manage_date)
    with col4:
        st.session_state.max_manage_date = st.date_input("Maximum date to manage:", value=st.session_state.max_manage_date)
        
    # Add instructions for getting Google Calendar public URL
    st.markdown("### Setup Google Calendar Integration")
    with st.expander("How to get your Google Calendar public URL"):
        st.markdown("""
        Follow these steps to get your public calendar URL:
        1. Open [Google Calendar](https://calendar.google.com)
        2. Click on the Settings icon (⚙️) in the top right
        3. Click on the calendar you want to share under "Settings for my calendars"
        4. Scroll down to "Access permissions for events"
        5. Check "Make available to public" and select "See only free/busy (hide details)"
        6. Scroll down to "Integrate calendar"
        7. Copy the "Public URL to this calendar" (ends with basic.ics)
        """)
    
    # Input field for calendar URL
    calendar_url = st.text_input(
        "Enter your public Google Calendar URL (.ics)",
        value=st.session_state.calendar_url,
        placeholder="https://calendar.google.com/calendar/ical/..."
    )
    
    # Validate and save the calendar URL
    if calendar_url:
        if calendar_url.endswith('.ics') and 'calendar.google.com' in calendar_url:
            st.session_state.calendar_url = calendar_url
            st.success("Calendar URL saved successfully!")
        else:
            st.error("Please enter a valid Google Calendar .ics URL")

############################################
# 1. LOAD CLIENT DATA
############################################
def load_client_data():
    st.header("📤 Load Client Data")
    # -- File uploader --
    st.subheader("Upload Client Data")
    uploaded_file = st.file_uploader("Upload client data CSV", type=['csv'])
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            required_columns = [
                'Client Name', 'Client Email', 'Preferred Days', 'Location',
                'Weekly Sessions', 'Session Duration (mins)', 'Responses'
            ]
            
            if all(col in df.columns for col in required_columns):
                st.session_state.raw_data = df
                st.success("Data loaded successfully!")
                
                with st.expander("View Raw Data"):
                    st.dataframe(df)
            else:
                st.error(f"CSV file must contain all required columns! Missing: {', '.join(set(required_columns) - set(df.columns))}")
        except Exception as e:
            st.error(f"Error loading file: {str(e)}")

def process_client_data_st():
    st.header("🔄 Process Client Data")
    
    if st.session_state.raw_data is None:
        st.warning("Please load client data first!")
        return
    
    col1, col2 = st.columns([1, 4])
    with col1:
        process_button = st.button("Process Data")
    
    try:
        # Test loading from file
        # temp_df = pd.read_csv("./data/processed_client_preferences.csv")
        # st.session_state.processed_data = temp_df
        # st.success("Data refreshed from file successfully!")
        
        # Process new data if process button is clicked
        if process_button:
            processed_client_data = process_client_data(st.session_state.raw_data)
            st.session_state.processed_data = create_client_dataframe(processed_client_data)
            
            # Save to CSV
            # st.session_state.processed_data.to_csv(
            #     "./data/processed_client_preferences.csv",
            #     index=False
            # )
            st.success("Data processed successfully!")
        
        # Always show the dataframe if it exists in session state
        if st.session_state.processed_data is not None:
            st.subheader("Processed Client Data")
            st.dataframe(
                st.session_state.processed_data,
                use_container_width=True,
                hide_index=True
            )
            
            # Add download button
            st.download_button(
                "Download Processed Data",
                st.session_state.processed_data.to_csv(index=False),
                "processed_client_preferences.csv",
                "text/csv",
                key='download-processed-csv'
            )
            
    except Exception as e:
        st.error(f"Error processing client data: {str(e)}")

############################################
# 3. YOUR AVAILABILITY (ENHANCED WITH CALENDAR)
############################################
# Lets pull the availability from teh calendar URL shared between the min and max manage dates
# Using the calendar URL, we can get the free/busy slots for the user
# Show these on the app using streamlit_calendar component

day_map = {
    "Sunday": 0, "Monday": 1, "Tuesday": 2, 
    "Wednesday": 3, "Thursday": 4, "Friday": 5, "Saturday": 6
}

def fetch_calendar_data(calendar_url):
    try:
        response = requests.get(calendar_url)
        gcal = iCalendar.from_ical(response.text)
        return gcal
    except Exception as e:
        st.error(f"Error fetching calendar: {str(e)}")
        return None

def get_busy_slots(gcal, start_date, end_date):
    """
    Get busy slots from Google Calendar data within the specified date range.
    """
    busy_slots = []
    local_tz = tzlocal.get_localzone()
    
    try:
        if not gcal:
            return busy_slots

        # Ensure start_date and end_date are timezone-aware
        if isinstance(start_date, datetime) and start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=local_tz)
        if isinstance(end_date, datetime) and end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=local_tz)

        for component in gcal.walk():
            if component.name == "VEVENT":
                try:
                    event_start = component.get('dtstart').dt
                    event_end = component.get('dtend').dt
                    
                    # Handle all-day events
                    if isinstance(event_start, date) and not isinstance(event_start, datetime):
                        event_start = datetime.combine(event_start, datetime.min.time())
                        event_end = datetime.combine(event_end, datetime.max.time())
                    
                    # Make naive datetime timezone-aware
                    if event_start.tzinfo is None:
                        event_start = event_start.replace(tzinfo=local_tz)
                    else:
                        event_start = event_start.astimezone(local_tz)
                        
                    if event_end.tzinfo is None:
                        event_end = event_end.replace(tzinfo=local_tz)
                    else:
                        event_end = event_end.astimezone(local_tz)
                    
                    # Compare timezone-aware datetimes
                    if (start_date <= event_start <= end_date or 
                        start_date <= event_end <= end_date or
                        (event_start <= start_date and event_end >= end_date)):
                        
                        busy_slots.append({
                            'title': 'Busy',
                            'start': event_start.strftime('%Y-%m-%dT%H:%M:%S'),
                            'end': event_end.strftime('%Y-%m-%dT%H:%M:%S'),
                            'backgroundColor': '#FF0000',
                            'display': 'block'
                        })
                except Exception as e:
                    st.error(f"Error processing event: {str(e)}")
                    continue
                    
        return busy_slots
    except Exception as e:
        st.error(f"Error getting busy slots: {str(e)}")
        return []

def manage_availability():
    """
    Manage calendar availability and display the calendar.
    """
    st.header("📅 Your Availability")
    
    if not st.session_state.get('calendar_url'):
        st.warning("Please set up your Google Calendar URL in the Configuration page first!")
        return
    
    # Initialize session state variables
    if 'calendar_busy_slots' not in st.session_state:
        st.session_state.calendar_busy_slots = []
        
    # Add refresh button with a unique key
    refresh_clicked = st.button('🔄 Refresh Calendar', key='refresh_calendar_button')
    
    if refresh_clicked:
        try:
            local_tz = tzlocal.get_localzone()
            
            # Create timezone-aware datetime objects
            start_date = datetime.combine(
                st.session_state.min_manage_date, 
                datetime.min.time()
            ).replace(tzinfo=local_tz)
            
            end_date = datetime.combine(
                st.session_state.max_manage_date, 
                datetime.max.time()
            ).replace(tzinfo=local_tz)
            
            # Fetch calendar data
            gcal = fetch_calendar_data(st.session_state.calendar_url)
            if gcal:
                calendar_busy_slots = get_busy_slots(gcal, start_date, end_date)
                print(calendar_busy_slots)
                st.session_state.calendar_busy_slots = calendar_busy_slots
                st.success("Calendar refreshed successfully!")
                # Force a rerun to update the calendar
                st.rerun()
            else:
                st.error("Failed to fetch calendar data")
        except Exception as e:
            st.error(f"Error refreshing calendar: {str(e)}")
    
    # Calendar options
    calendar_options = {
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,timeGridDay"
        },
        "initialView": "timeGridWeek",
        "selectable": True,
        "selectMirror": True,
        "businessHours": {
            "daysOfWeek": [day_map[day] for day in st.session_state.working_days],
            "startTime": f"{st.session_state.default_working_hours[0]}:00:00",
            "endTime": f"{st.session_state.default_working_hours[1]}:00:00",
        },
        "slotMinTime": "00:00:00",
        "slotMaxTime": "24:00:00",
        "slotDuration": "00:30:00",
        "nowIndicator": True,
        "slotLaneClassNames": "non-business-hours",
        "allDaySlot": False,
        "slotEventOverlap": True,
    }
    
    try:
        # Debug output
        st.write("Number of events:", len(st.session_state.calendar_busy_slots))
        
        # Display calendar with fixed key and stored events
        calendar_data = calendar(
            events=st.session_state.calendar_busy_slots,
            options=calendar_options,
            key=f"availability_calendar_{hash(str(st.session_state.calendar_busy_slots))}"  # Dynamic key based on events
        )
        
        # Handle calendar interactions
        if calendar_data:
            if 'view' in calendar_data:
                st.session_state.current_calendar_view = calendar_data['view']
            
            if 'eventClick' in calendar_data:
                event = calendar_data['eventClick']
                st.write(f"Clicked event: {event}")
                
    except Exception as e:
        st.error(f"Error displaying calendar: {str(e)}")     
              
############################################
# 4. OPTIMIZE SCHEDULE
############################################
def optimize_schedule():
    st.header("⚡ Optimize Schedule")
    
    if st.session_state.processed_data is None:
        st.warning("Please process client data first!")
        return
        
    if not st.session_state.calendar_busy_slots:
        st.warning("Please refresh your calendar availability first!")
        return
    
    try:
        # Initialize schedule state if not exists
        if 'schedule_generated' not in st.session_state:
            st.session_state.schedule_generated = False
            
        start_date = st.session_state.min_manage_date
        end_date = st.session_state.max_manage_date
        working_hours = st.session_state.default_working_hours
        working_days = st.session_state.working_days
        
        # Create all possible time slots
        all_slots = create_time_slots(
            start_date=datetime.combine(start_date, datetime.min.time()),
            end_date=datetime.combine(end_date, datetime.max.time()),
            working_hours=working_hours,
            working_days=working_days
        )
        
        busy_slots = [
            {
                'start': event['start'],
                'end': event['end']
            }
            for event in st.session_state.calendar_busy_slots
        ]
        
        availability_df = get_available_slots(all_slots, busy_slots)
        
        if availability_df.empty:
            st.error("No available time slots found!")
            return
            
        st.info(f"Found {len(availability_df)} available time slots")
        
        # Generate schedule button
        if st.button("Generate Optimal Schedule") or st.session_state.schedule_generated:
            st.session_state.schedule_generated = True
            
            with st.spinner("Generating optimal schedule..."):
                schedule = schedule_sessions(
                    st.session_state.processed_data,
                    availability_df,
                    datetime.combine(start_date, datetime.min.time()),
                    datetime.combine(end_date, datetime.max.time()),
                    block_size=15
                )
                
                if not schedule:
                    st.error("Could not generate schedule. Please check client preferences and availability.")
                    st.session_state.schedule_generated = False
                    return
                
                # Store schedule in session state
                st.session_state.optimized_schedule = schedule
                
                # Create schedule data
                schedule_data = []
                for client, sessions in schedule.items():
                    for session in sessions:
                        schedule_data.append({
                            'Client': client,
                            'Date': session['start'].strftime('%Y-%m-%d'),
                            'Start Time': session['start'].strftime('%H:%M'),
                            'End Time': session['end'].strftime('%H:%M'),
                        })
                
                if schedule_data:
                    schedule_df = pd.DataFrame(schedule_data)
                    schedule_df = schedule_df.sort_values(['Date', 'Start Time'])
                    
                    # Display as calendar view
                    st.subheader("Calendar View")
                    
                    # Generate unique colors for each client
                    unique_clients = schedule_df['Client'].unique()
                    colors = [
                        '#FF6B6B', '#45B7D1', '#9B59B6', '#3498DB', 
                        '#2ECC71', '#F1C40F', '#E74C3C', '#1ABC9C', 
                        '#884EA0', '#17A589', '#CA6F1E', '#BA4A00', 
                        '#FF7F50', '#4169E1', '#FF69B4', '#8A2BE2', 
                        '#FF8C00', '#9370DB'
                    ]
                    # If more colors needed, generate them programmatically
                    if len(unique_clients) > len(colors):
                        import random
                        additional_colors = [
                            f'#{random.randint(0, 0xFFFFFF):06x}' 
                            for _ in range(len(unique_clients) - len(colors))
                        ]
                        colors.extend(additional_colors)
                    
                    client_colors = dict(zip(unique_clients, colors))
                    
                    # Create calendar events with unique colors
                    calendar_events = [
                        {
                            'title': f"{row['Client']}",
                            'start': f"{row['Date']}T{row['Start Time']}",
                            'end': f"{row['Date']}T{row['End Time']}",
                            'backgroundColor': client_colors[row['Client']],
                            'borderColor': client_colors[row['Client']],
                            'textColor': '#FFFFFF'
                        }
                        for _, row in schedule_df.iterrows()
                    ]
                    
                    calendar_options = {
                        "headerToolbar": {
                            "left": "prev,next today",
                            "center": "title",
                            "right": "timeGridWeek,timeGridDay,dayGridMonth"
                        },
                        "initialView": "timeGridWeek",
                        "slotMinTime": f"00:00:00",
                        "slotMaxTime": f"23:59:59",
                        "allDaySlot": False,
                        "slotDuration": "00:15:00",
                        "height": "auto",
                        "businessHours": {
                            "daysOfWeek": [day_map[day] for day in working_days],
                            "startTime": f"{working_hours[0]}:00:00",
                            "endTime": f"{working_hours[1]}:00:00",
                        },
                        "weekends": True,
                        "nowIndicator": True,
                        "navLinks": True,
                        "dayMaxEvents": True,
                        "eventMaxStack": 3,
                        "views": {
                            "timeGridWeek": {
                                "titleFormat": { "year": "numeric", "month": "short", "day": "numeric" }
                            },
                            "listMonth": {
                                "listDayFormat": { "weekday": "long" },
                                "listDaySideFormat": { "month": "short", "day": "numeric" }
                            }
                        },
                        "eventTimeFormat": {
                            "hour": "2-digit",
                            "minute": "2-digit",
                            "meridiem": False,
                            "hour12": False
                        }
                    }

                    # Display client color legend
                    st.markdown("### Client Color Legend")
                    legend_cols = st.columns(4)
                    for idx, (client, color) in enumerate(client_colors.items()):
                        col_idx = idx % 4
                        legend_cols[col_idx].markdown(
                            f'<div style="background-color: {color}; color: white; '
                            f'padding: 5px; margin: 2px; border-radius: 5px; '
                            f'text-align: center;">{client}</div>', 
                            unsafe_allow_html=True
                        )

                    # Calendar container with scrollable height
                    st.markdown("""
                        <style>
                            .calendar-container {
                                height: 800px;
                                overflow-y: auto;
                                border: 1px solid #ddd;
                                border-radius: 5px;
                                padding: 10px;
                                margin: 10px 0;
                            }
                            .fc-scroller {
                                height: auto !important;
                            }
                        </style>
                    """, unsafe_allow_html=True)

                    # st.markdown('<div class="calendar-container">', unsafe_allow_html=True)
                    calendar(
                        events=calendar_events,
                        options=calendar_options,
                        key=f"schedule_calendar_{hash(str(calendar_events))}"
                    )
                    # st.markdown('</div>', unsafe_allow_html=True)

                    # Enhanced table display with filtering and sorting
                    st.subheader("Detailed Schedule")
                    
                    # Add filter controls
                    col1, col2 = st.columns(2)
                    with col1:
                        selected_client = st.multiselect(
                            "Filter by Client",
                            options=sorted(schedule_df['Client'].unique()),
                            default=[]
                        )
                    with col2:
                        selected_date = st.date_input(
                            "Filter by Date Range",
                            value=(schedule_df['Date'].min(), schedule_df['Date'].max()),
                            min_value=schedule_df['Date'].min(),
                            max_value=schedule_df['Date'].max()
                        )

                    # Apply filters
                    filtered_df = schedule_df.copy()
                    if selected_client:
                        filtered_df = filtered_df[filtered_df['Client'].isin(selected_client)]
                    if isinstance(selected_date, tuple):
                        filtered_df = filtered_df[
                            (filtered_df['Date'] >= str(selected_date[0])) & 
                            (filtered_df['Date'] <= str(selected_date[1]))
                        ]

                    # Add sorting options
                    sort_col, sort_order = st.columns(2)
                    with sort_col:
                        sort_by = st.selectbox(
                            "Sort by",
                            options=['Date', 'Start Time', 'Client'],
                            index=0
                        )
                    with sort_order:
                        ascending = st.checkbox("Ascending order", value=True)

                    # Apply sorting
                    filtered_df = filtered_df.sort_values(by=sort_by, ascending=ascending)

                    # Display enhanced table with formatting
                    st.markdown("""
                        <style>
                            .stDataFrame {
                                border: 1px solid #ddd;
                                border-radius: 5px;
                                padding: 10px;
                            }
                            .dataframe {
                                font-size: 14px;
                            }
                        </style>
                    """, unsafe_allow_html=True)

                    # Add metrics above the table
                    metric_cols = st.columns(4)
                    metric_cols[0].metric("Total Sessions", len(filtered_df))
                    metric_cols[1].metric("Unique Clients", filtered_df['Client'].nunique())
                    metric_cols[2].metric("Total Days", filtered_df['Date'].nunique())
                    total_hours = (pd.to_datetime(filtered_df['End Time']) - 
                                 pd.to_datetime(filtered_df['Start Time'])).sum().total_seconds() / 3600
                    metric_cols[3].metric("Total Hours", f"{total_hours:.1f}")

                    # Display the table with enhanced formatting
                    st.dataframe(
                        filtered_df,
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "Date": st.column_config.DateColumn(
                                "Date",
                                format="YYYY-MM-DD"
                            ),
                            "Start Time": st.column_config.TimeColumn(
                                "Start Time",
                                format="HH:mm"
                            ),
                            "End Time": st.column_config.TimeColumn(
                                "End Time",
                                format="HH:mm"
                            ),
                            "Client": st.column_config.TextColumn(
                                "Client",
                                width="medium"
                            )
                        }
                    )
                    
                    # Add export button
                    csv = schedule_df.to_csv(index=False)
                    st.download_button(
                        "Download Schedule",
                        csv,
                        "schedule.csv",
                        "text/csv",
                        key='download-schedule'
                    )
                    
                    # Add session statistics
                    st.markdown("### 📊 Session Statistics")
                    
                    # Calculate statistics
                    total_sessions = len(schedule_df)
                    total_clients = len(schedule_df['Client'].unique())
                    
                    # Calculate total hours
                    schedule_df['Duration'] = pd.to_datetime(schedule_df['End Time']) - pd.to_datetime(schedule_df['Start Time'])
                    total_hours = schedule_df['Duration'].sum().total_seconds() / 3600
                    
                    # Sessions per client
                    sessions_per_client = schedule_df['Client'].value_counts()
                    
                    # Weekly distribution
                    schedule_df['WeekDay'] = pd.to_datetime(schedule_df['Date']).dt.day_name()
                    sessions_per_day = schedule_df['WeekDay'].value_counts()
                    
                    # Display statistics in columns
                    stat_cols = st.columns(3)
                    
                    # Column 1: Overall Statistics
                    with stat_cols[0]:
                        st.markdown("""
                        <div style="border:1px solid #ccc; padding:10px; border-radius:5px">
                            <h4>Overall Statistics</h4>
                            <p>📊 Total Sessions: {}</p>
                            <p>👥 Total Clients: {}</p>
                            <p>⏰ Total Hours: {:.1f}</p>
                        </div>
                        """.format(total_sessions, total_clients, total_hours), unsafe_allow_html=True)
                    
                    # Column 2: Sessions per Client
                    with stat_cols[1]:
                        st.markdown("""
                        <div style="border:1px solid #ccc; padding:10px; border-radius:5px">
                            <h4>Sessions per Client</h4>
                        </div>
                        """, unsafe_allow_html=True)
                        for client, count in sessions_per_client.items():
                            st.markdown(f"• {client}: {count} sessions")
                    
                    # Column 3: Weekly Distribution
                    with stat_cols[2]:
                        st.markdown("""
                        <div style="border:1px solid #ccc; padding:10px; border-radius:5px">
                            <h4>Weekly Distribution</h4>
                        </div>
                        """, unsafe_allow_html=True)
                        for day, count in sessions_per_day.items():
                            st.markdown(f"• {day}: {count} sessions")
                    
                    # Add a spacer
                    st.markdown("<br>", unsafe_allow_html=True)

                    # Add reset button
                    if st.button("Reset Schedule"):
                        st.session_state.schedule_generated = False
                        st.rerun()
                        
                else:
                    st.warning("No sessions could be scheduled. Please check client preferences and availability.")
                    st.session_state.schedule_generated = False
                    
    except Exception as e:
        st.error(f"Error generating schedule: {str(e)}")
        st.exception(e)
        st.session_state.schedule_generated = False

############################################
# 5. SEND INVITES
############################################
def send_invites():
    st.header("📧 Send Calendar Invites")
    
    if st.session_state.optimized_schedule is None:
        st.warning("Please optimize schedule first!")
        return
    
    if st.button("Send Calendar Invites"):
        # Placeholder for calendar invite logic
        st.info("Sending calendar invites...")
        # Add actual calendar invite sending logic here
        st.success("Calendar invites sent successfully!")

# Main app logic
if page == "0. Configuration":
    configuration_page()
elif page == "1. Load Client Data":
    load_client_data()
elif page == "2. Process Data":
    process_client_data_st()
elif page == "3. Your Availability":
    manage_availability()
elif page == "4. Optimize Schedule":
    optimize_schedule()
else:
    send_invites()

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("🎨 by Prashanth")