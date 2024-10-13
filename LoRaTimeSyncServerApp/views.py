import json
import time

from chirpstack_api import integration
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from google.protobuf.json_format import Parse
# Create your views here.
from LoRaTimeSyncServerApp.ChirpStackUtils.downlink import send_downlink
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
    saveTimeCollection('test_dev_eui')
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

