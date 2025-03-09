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
from datetime import timedelta
# Create your views here.
from LoRaTimeSyncServerApp.ChirpStackUtils.downlink import send_downlink
from LoRaTimeSyncServerApp.models import TimeCollection, TimeSyncInit, TimeSyncModels
from LoRaTimeSyncServerApp.timesync import initTimeSync, saveTimeCollection, perform_sync, createModel
from LoRaTimeSyncServerApp.testing_utils import create_time_difference_plot, get_time_range_params, get_sync_data

import logging
logger = logging.getLogger('django')


def unmarshal(body, pl):
    return Parse(body, pl)


def uplink_data_to_json(hex_bytes):
    try:
        hex_string = hex_bytes.decode('utf-8')
        return json.loads(hex_string)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
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

        # time when gateway received the message
        time_received = up.time.seconds * (1000**3) + up.time.nanos

        if data is not None and data['p'] is not None: 
            first_uplink_expected = initTimeSync(dev_eui, data['p'], time_received)
            downlink_data = f'i,{time.time_ns()},{first_uplink_expected}'
            send_downlink(dev_eui, downlink_data)
        else:
            saveTimeCollection(dev_eui, now, time_received)
            downlink_data = perform_sync(dev_eui)
            
            # if model is created, send synchronization downlink
            if downlink_data is not None:
                send_downlink(dev_eui, downlink_data)


    return HttpResponse('uplink')


@csrf_exempt
def test_existing_model(request):
    dev_eui, time_from, time_to, unix_from, unix_to = get_time_range_params(request)

    existing_model = TimeSyncModels.objects.filter(dev_eui=dev_eui, created_at__gte=time_from, created_at__lte=time_to).last()

    if existing_model is None:
        return HttpResponse(json.dumps({
            'error': 'No model found for the specified device and time range'
        }), status=404)

    return HttpResponse(json.dumps({
        'a': existing_model.a,
        'b': existing_model.b,
        'new_period_ns': existing_model.new_period_ns,
        'new_period_ms': existing_model.new_period_ms,
    }))


@csrf_exempt
def time_difference_graph(request):
    dev_eui, time_from, time_to, unix_from, unix_to = get_time_range_params(request)
    sync_init, collections = get_sync_data(dev_eui, time_to, unix_from, unix_to)

    if collections and sync_init:
        # x_values represents minutes now
        x_values = [(c.time_expected - sync_init.first_uplink_expected) / (60 * 1e9) for c in collections]
        time_diffs = [(c.time_expected - c.time_received) / 1e9 for c in collections]

        plot_data = create_time_difference_plot(x_values, time_diffs, time_from, time_to)
        return HttpResponse(plot_data, content_type='image/png')
    
    return HttpResponse("No data available", content_type='text/plain')


@csrf_exempt
def time_difference_graph_v2(request):
    dev_eui, time_from, time_to, unix_from, unix_to = get_time_range_params(request)
    sync_init, collections = get_sync_data(dev_eui, time_to, unix_from, unix_to)

    if collections and sync_init:
        filtered_data = [(c.time_expected - sync_init.first_uplink_expected, c.time_expected - c.time_received) 
                     for c in collections 
                     if (c.time_expected - c.time_received) > -1 * 1e9]

        # x_values represents minutes now
        x_values = [(x[0]) / (60 * 1e9) for x in filtered_data]
        time_diffs = [x[1] / 1e9 for x in filtered_data]

        plot_data = create_time_difference_plot(x_values, time_diffs, time_from, time_to)
        return HttpResponse(plot_data, content_type='image/png')
    
    return HttpResponse("No data available", content_type='text/plain')


@csrf_exempt
def test_model(request):
    dev_eui, time_from, time_to, unix_from, unix_to = get_time_range_params(request)
    sync_init, collections = get_sync_data(dev_eui, time_to, unix_from, unix_to)

    if not collections or len(collections) == 0:
        return HttpResponse(json.dumps({
            'error': 'No data available for the specified time range'
        }), status=404)

    first_received = collections[0].time_received
    model2 = createModel(collections, first_received)

    timeSync2 = {
        'a': model2.coef_[0],
        'b': model2.intercept_,
        'a-1': (model2.coef_[0] - 1) * sync_init.period,
        'P': sync_init.period * 1e9 * model2.coef_[0],
        'p_micro': int(sync_init.period * 1e9 * model2.coef_[0] / 1e3),
    }

    return HttpResponse(json.dumps({
        'model': timeSync2,
        'count': len(collections),
    }))



