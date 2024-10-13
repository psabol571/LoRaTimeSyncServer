import time

from django.utils import timezone
from datetime import timedelta
from .models import TimeSyncInit, TimeCollection

def initTimeSync(dev_eui, period):
    now = time.time_ns()
    reserve = 10
    first_uplink_expected = now + (period + reserve) * (1000**3)  # add period and reserver as nanoseconds
    
    time_sync_device = TimeSyncInit.objects.create(
        dev_eui=dev_eui,
        period=period,
        first_uplink_expected=first_uplink_expected,
    )

    return now


def saveTimeCollection(dev_eui, device_time=timezone.now(), time_received=timezone.now()):
    device = TimeSyncInit.objects.get(dev_eui=dev_eui)
    
    latest_collection = TimeCollection.objects.filter(dev_eui=dev_eui).order_by('-time_received').first()
    
    # calculate nearest period
    if latest_collection:
        time_diff = time_received - latest_collection.time_expected
        periods_passed = round(time_diff.total_seconds() / device.period)
        time_expected = latest_collection.time_expected + timedelta(seconds=periods_passed * device.period)
    else:
        time_diff = time_received - device.first_uplink_expected
        periods_passed = round(time_diff.total_seconds() / device.period)
        time_expected = device.first_uplink_expected + timedelta(seconds=periods_passed * device.period)
    
    
    # Create and save the TimeCollection instance
    time_collection = TimeCollection.objects.create(
        dev_eui=dev_eui,
        time_received=time_received,
        time_expected=time_expected,
        device_time=device_time
    )
    
    return time_collection

