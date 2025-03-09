import io
import matplotlib.pyplot as plt
from django.utils import timezone
from datetime import timedelta
from LoRaTimeSyncServerApp.models import TimeCollection, TimeSyncInit

def create_time_difference_plot(x_values, time_diffs, time_from, time_to):
    plt.figure(figsize=(10, 6))
    plt.plot(x_values, time_diffs, 'bo-')
    plt.xlabel('Čas (minúty)')
    plt.ylabel('Časový rozdiel T0-t0 (sekundy)')
    plt.title(f'{time_from} - {time_to}')        
    plt.grid(True)

    # Save the plot to a buffer
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    plt.close()
    
    return buffer.getvalue()

def get_time_range_params(request, default_days=7):
    dev_eui = request.GET.get('dev_eui', '')
    time_from = request.GET.get('time_from', '')
    time_to = request.GET.get('time_to', '')

    # Convert time strings to datetime objects
    time_from = timezone.datetime.fromisoformat(time_from) if time_from else timezone.now() - timedelta(days=default_days)
    time_to = timezone.datetime.fromisoformat(time_to) if time_to else timezone.now()

    # Convert datetime to Unix timestamp in nanoseconds
    unix_from = time_from.timestamp() * 1e9
    unix_to = time_to.timestamp() * 1e9
    
    return dev_eui, time_from, time_to, unix_from, unix_to

def get_sync_data(dev_eui, time_to, unix_from, unix_to, error_greater_than_seconds=None):
    # Get the last TimeSyncInit record for this experiment
    sync_init = TimeSyncInit.objects.filter(
        dev_eui=dev_eui,
        created_at__lte=time_to
    ).order_by('-created_at').first()

    # Fetch TimeCollection data
    collections = TimeCollection.objects.filter(
        dev_eui=dev_eui,
        time_received__range=(unix_from, unix_to)
    ).order_by('time_received')

    if error_greater_than_seconds is not None:
        collections = [c for c in collections if (c.time_expected - c.time_received) > int(float(error_greater_than_seconds) * 1e9)]
    
    return sync_init, collections
