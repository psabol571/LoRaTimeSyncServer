import io
import json
import time
from django.conf import settings
from chirpstack_api import integration
import matplotlib.pyplot as plt
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from google.protobuf.json_format import Parse
# Create your views here.
from LoRaTimeSyncServerApp.ChirpStackUtils.downlink import send_downlink
from LoRaTimeSyncServerApp.models import TimeCollection
from LoRaTimeSyncServerApp.timesync import initTimeSync, saveTimeCollection, perform_sync

import logging
logger = logging.getLogger('django')


def unmarshal(body, pl):
    return Parse(body, pl)


def uplink_data_to_json(hex_bytes):
    hex_string = hex_bytes.decode('utf-8')
    logger.info('hex_string')
    logger.info(hex_string)
    try:
        return json.loads(hex_string)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode JSON")
        return None


@csrf_exempt
def receive_uplink(request):
    now = time.time_ns()
    event = request.GET.get('event', None)
    body = request.body

    if event == "up":
        up = unmarshal(body, integration.UplinkEvent())

        dev_eui = up.device_info.dev_eui
        data = uplink_data_to_json(up.data)
        logger.info('data')
        logger.info(data)
        logger.info('dev-eui')
        logger.info(dev_eui)

        if data is not None and data['p'] is not None: 
            first_uplink_expected = initTimeSync(dev_eui, data['p'], now)
            downlink_data = f'i,{time.time_ns()},{first_uplink_expected}'
            send_downlink(dev_eui, downlink_data)
        else:
            saveTimeCollection(dev_eui, now, now)


    return HttpResponse('uplink')



@csrf_exempt
def test_receive(request: WSGIRequest):
    now = time.time_ns()
    saveTimeCollection('test_dev_eui', now, now)
    return HttpResponse(json.dumps(request.POST))



@csrf_exempt
def test_init(request: WSGIRequest):
    now = time.time_ns()
    now = initTimeSync('test_dev_eui', 120, now)

    resp = json.dumps({
        'a': str(now),
    #     'b': now.second,
    #    'ms': now.microsecond,
        'ns': time.time_ns(),
    })
    return HttpResponse(resp)


@csrf_exempt
def test_sync(request: WSGIRequest):
    perform_sync('test_dev_eui')

    return HttpResponse('hi')

@csrf_exempt
def test_host(request: WSGIRequest):
    return HttpResponse(settings.HOST)


# example usage: localhost:8000/graph-time-diff?time_from=2023-01-01T00:00:00&time_to=2023-12-31T23:59:59&dev_eui=test_dev_eui
@csrf_exempt
def time_difference_graph(request):
    dev_eui = request.GET.get('dev_eui', '')
    time_from = request.GET.get('time_from', '')
    time_to = request.GET.get('time_to', '')


    #  Convert time strings to datetime objects
    time_from = timezone.datetime.fromisoformat(time_from) if time_from else timezone.now() - timedelta(days=7)
    time_to = timezone.datetime.fromisoformat(time_to) if time_to else timezone.now()

    #  Convert datetime to Unix timestamp in nanoseconds
    unix_from = time_from.timestamp() * 1e9
    unix_to = time_to.timestamp() * 1e9

    # Fetch TimeCollection data
    collections = TimeCollection.objects.filter(
        dev_eui=dev_eui,
        time_received__range=(unix_from, unix_to)
    ).order_by('time_received')

    # Prepare data for plotting
    x_values = range(1, len(collections) + 1)
    time_diffs = [(c.time_expected - c.time_received) for c in collections]

    plt.figure(figsize=(10, 6))
    plt.plot(x_values, time_diffs, 'bo-')
    plt.xlabel('Time slot id')
    plt.ylabel('Time Difference (nanoseconds)')
    plt.title(f'Time Difference for Device \'{dev_eui}\' from {time_from} to {time_to}')
    plt.grid(True)
    plt.xticks(x_values)

    # Save the plot to a buffer
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    plt.close()

    # Return the image as an HTTP response
    return HttpResponse(buffer.getvalue(), content_type='image/png')

