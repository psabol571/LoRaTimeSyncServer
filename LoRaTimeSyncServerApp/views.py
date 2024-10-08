import json

from chirpstack_api import integration
from django.views.decorators.csrf import csrf_exempt
from google.protobuf.json_format import Parse
# Create your views here.
from LoRaTimeSyncServerApp.ChirpStackUtils.downlink import send_downlink


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

