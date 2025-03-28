import io
import matplotlib.pyplot as plt
from django.utils import timezone
from datetime import timedelta
import numpy as np
from scipy import stats
from LoRaTimeSyncServerApp.models import TimeCollection, TimeSyncInit

def create_time_difference_plot(x_values, time_diffs, time_from, time_to, show_lines=False, lang='sk', time_unit='m',err_limit=0.05):
    # Calculate statistics
    avg_error = sum(time_diffs) / len(time_diffs)
    max_error = max(time_diffs)
    min_error = min(time_diffs)

    in_limit_count = sum(1 for x in time_diffs if abs(x) <= float(err_limit))
    in_limit_percentage = in_limit_count / len(time_diffs) * 100
    
    # Calculate standard deviation
    variance = sum((x - avg_error) ** 2 for x in time_diffs) / len(time_diffs)
    std_dev = variance ** 0.5

    x_vals = [x if time_unit == 'm' else x / 60 if time_unit == 'h' else x / (60 * 24) for x in x_values]

    plot_style = 'bo-' if show_lines else 'b.'
    plt.figure(figsize=(12, 6))
    plt.plot(x_vals, time_diffs, plot_style)
    plt.grid(True)

    x_label_min = 'Čas (minúty)' if lang == 'sk' else 'Time (minutes)'
    x_label_hour = 'Čas (hodiny)' if lang == 'sk' else 'Time (hours)'
    x_label_day = 'Čas (dni)' if lang == 'sk' else 'Time (days)'
    x_label = x_label_min if time_unit == 'm' else x_label_hour if time_unit == 'h' else x_label_day

    plt.xlabel(x_label)
    plt.ylabel('Časový rozdiel Tn-tn (sekundy)' if lang == 'sk' else 'Time difference Tn-tn (seconds)')

    messages_interval_title = "Spravy s chybou v intervale" if lang == 'sk' else "Messages with error in interval"
    
    # Format the date range and statistics for the title
    title = f"{time_from.strftime('%Y-%m-%d %H:%M:%S')} - {time_to.strftime('%Y-%m-%d %H:%M:%S')}\n"
    title += f"Avg: {avg_error:.3f}s, Max: {max_error:.3f}s, Min: {min_error:.3f}s, StdDev: {std_dev:.3f}s"
    title += f"\nMessages with error in interval (-{err_limit}s,{err_limit}s): {in_limit_count}/{len(time_diffs)} ({in_limit_percentage:.2f}%)"
    plt.title(title)

    # Save the plot to a buffer
    buffer = io.BytesIO()
    if show_lines:
        plt.savefig(buffer, format='png')
    else:
        plt.savefig(buffer, format='png', bbox_inches='tight', dpi=100)
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

def filter_time_diff_outliers(collections, method='iqr'):
    if not collections:
        return collections
        
    # Calculate time differences in nanoseconds
    time_diffs = np.array([c.time_expected - c.time_received for c in collections])
    
    # Calculate IQR bounds
    q1 = np.percentile(time_diffs, 25)
    q3 = np.percentile(time_diffs, 75)
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    
    # Filter collections based on bounds
    filtered_collections = [c for c in collections 
                          if lower_bound <= (c.time_expected - c.time_received) <= upper_bound]
    
    return filtered_collections

def get_sync_data(dev_eui, time_to, unix_from, unix_to, error_greater_than_seconds=None, remove_outliers=False):
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
    
    # Remove outliers if requested
    if remove_outliers:
        collections = filter_time_diff_outliers(collections)
    
    return sync_init, collections
