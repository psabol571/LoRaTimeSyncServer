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


def saveTimeCollection(dev_eui, device_time=time.time_ns(), time_received=time.time_ns()):
    device = TimeSyncInit.objects.filter(dev_eui=dev_eui).last()

    time_diff = time_received - device.first_uplink_expected
    periods_passed = round(time_diff / device.period / (1000**3))
    time_expected = device.first_uplink_expected + periods_passed * device.period * (1000**3)
    
    # Create and save the TimeCollection instance
    time_collection = TimeCollection.objects.create(
        dev_eui=dev_eui,
        time_received=time_received,
        time_expected=time_expected,
        device_time=device_time
    )
    
    return time_collection

