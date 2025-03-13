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
    error_greater_than_seconds = request.GET.get('e', None)
    remove_outliers = request.GET.get('o', False)
    show_lines = request.GET.get('l', False)
    sync_init, collections = get_sync_data(dev_eui, time_to, unix_from, unix_to, error_greater_than_seconds, remove_outliers)

    if collections and sync_init:
        # x_values represents minutes now
        x_values = [(c.time_expected - sync_init.first_uplink_expected) / (60 * 1e9) for c in collections]
        time_diffs = [(c.time_expected - c.time_received) / 1e9 for c in collections]

        plot_data = create_time_difference_plot(x_values, time_diffs, time_from, time_to, show_lines)
        return HttpResponse(plot_data, content_type='image/png')
    
    return HttpResponse("No data available", content_type='text/plain')


@csrf_exempt
def time_difference_graph_v2(request):
    dev_eui, time_from, time_to, unix_from, unix_to = get_time_range_params(request)
    error_greater_than_seconds = request.GET.get('e', -1)
    remove_outliers = request.GET.get('o', False)
    sync_init, collections = get_sync_data(dev_eui, time_to, unix_from, unix_to, error_greater_than_seconds, remove_outliers)

    if collections and sync_init:
        x_values = [(c.time_expected - sync_init.first_uplink_expected) / (60 * 1e9) for c in collections]
        time_diffs = [(c.time_expected - c.time_received) / 1e9 for c in collections]

        plot_data = create_time_difference_plot(x_values, time_diffs, time_from, time_to)
        return HttpResponse(plot_data, content_type='image/png')
    
    return HttpResponse("No data available", content_type='text/plain')


@csrf_exempt
def test_model(request):
    dev_eui, time_from, time_to, unix_from, unix_to = get_time_range_params(request)
    error_greater_than_seconds = request.GET.get('e', None)
    remove_outliers = request.GET.get('o', False)
    sync_init, collections = get_sync_data(dev_eui, time_to, unix_from, unix_to, error_greater_than_seconds, remove_outliers)

    if not collections or len(collections) == 0:
        return HttpResponse(json.dumps({
            'error': 'No data available for the specified time range'
        }), status=404)

    first_received = collections[0].time_received
    model = createModel(collections, first_received)

    existing_model = TimeSyncModels.objects.filter(dev_eui=dev_eui, created_at__gte=sync_init.created_at, created_at__lte=time_to).last()

    old_period_ns = existing_model.new_period_ns if existing_model else sync_init.period * 1e9

    new_period_ns = int(old_period_ns * model.coef_[0])
    new_period_ms = int((new_period_ns + 500) / 1e3)
    
    # offset can be calculated as accumulated error over the period passed + model.b

    # calculate accumulated error over the period passed
    time_diff_ns = collections[len(collections) - 1].time_expected - collections[0].time_expected
    accumulated_error = time_diff_ns * (model.coef_[0] - 1)
    offset = accumulated_error + model.intercept_

    old_model = {
        'a': existing_model.a,
        'b': existing_model.b,
        'new_period_ns': existing_model.new_period_ns,
        'new_period_ms': existing_model.new_period_ms,
    } if existing_model else None
    
    new_model = {
        'a': model.coef_[0],
        'b': model.intercept_,
        'new_period_ns': new_period_ns,
        'new_period_ms': new_period_ms,
        'offset': offset,
    }

    return HttpResponse(json.dumps({
        'old_model': old_model,
        'new_model': new_model,
        'count': len(collections),
    }))



