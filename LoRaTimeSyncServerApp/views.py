import io
import json
import time

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


def unmarshal(body, pl):
    return Parse(body, pl)


def uplink_to_json(body):
    message = body['payload']
    hex_bytes = bytes.fromhex(message)
    hex_string = hex_bytes.decode('utf-8')
    return json.loads(hex_string)


@csrf_exempt
def receive_uplink(request):
    event = request.GET.get('event', None)
    body = request.body
    body_json = json.loads(body if body else '{}')

    if event == "up":
        up = unmarshal(body, integration.UplinkEvent())

        uplink_json = uplink_to_json(up.body.hex())
        dev_eui = up.device_info.dev_eui
        print(dev_eui)
        print(uplink_json)



@csrf_exempt
def test_receive(request: WSGIRequest):
    now = time.time_ns()
    saveTimeCollection('test_dev_eui', now, now)
    return HttpResponse(json.dumps(request.POST))



@csrf_exempt
def test_init(request: WSGIRequest):
    now = initTimeSync('test_dev_eui', 120)

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



# example usage: localhost:8000/graph-time-diff?time_to=1728886139242509027&time_from=0&dev_eui=test_dev_eui
def time_difference_graph(request):
    dev_eui = request.GET.get('dev_eui', '')
    time_from = request.GET.get('time_from', '')
    time_to = request.GET.get('time_to', '')

    # Fetch TimeCollection data
    collections = TimeCollection.objects.filter(
        dev_eui=dev_eui,
        time_received__range=(time_from, time_to)
    ).order_by('time_received')

    # Prepare data for plotting
    x_values = range(1, len(collections) + 1)
    time_diffs = [(c.time_expected - c.time_received) for c in collections]

    from_date = timezone.datetime.fromtimestamp(int(time_from)/1e9)
    to_date = timezone.datetime.fromtimestamp(int(time_to)/1e9)
    # Create the plot
    plt.figure(figsize=(10, 6))
    plt.plot(x_values, time_diffs, 'bo-')
    plt.xlabel('Time slot id')
    plt.ylabel('Time Difference (nanoseconds)')
    plt.title(f'Time Difference for Device \'{dev_eui}\' from {from_date} to {to_date}')
    plt.grid(True)
    plt.xticks(x_values)

    # Save the plot to a buffer
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    plt.close()

    # Return the image as an HTTP response
    return HttpResponse(buffer.getvalue(), content_type='image/png')

