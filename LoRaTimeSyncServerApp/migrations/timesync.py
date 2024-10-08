
from django.utils import timezone
from datetime import timedelta
from .models import TimeSyncInit, TimeCollection

def initTimeSync(dev_eui, period):
    now = timezone.now()
    first_uplink_expected = now + timedelta(seconds=period)
    
    # Round up to the nearest minute
    first_uplink_expected = first_uplink_expected.replace(second=0, microsecond=0) + timedelta(minutes=1)
    
    time_sync_device = TimeSyncInit.objects.create(
        dev_eui=dev_eui,
        period=period,
        first_uplink_expected=first_uplink_expected
    )
    
    return time_sync_device



