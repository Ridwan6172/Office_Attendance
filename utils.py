from datetime import datetime
import pytz

bd_tz = pytz.timezone("Asia/Dhaka")

def get_bd_time():
    return datetime.now(bd_tz)

def calculate_status(signin_time):
    ref_time = signin_time.replace(hour=9, minute=10, second=0)
    late_limit = signin_time.replace(hour=12, minute=30, second=0)

    if signin_time <= ref_time:
        return "Present"
    elif signin_time <= late_limit:
        return "Late"
    else:
        return "Absent"
