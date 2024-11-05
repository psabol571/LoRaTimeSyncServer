import json
import grpc
from chirpstack_api import api
from django.conf import settings

import logging
logger = logging.getLogger('django')


def send_downlink(dev_eui, data):
    # data = json.dumps(data)
    logger.info('data_downlink')
    logger.info(data)

    channel = grpc.insecure_channel(settings.CHIRPSTACK_HOST)

    client = api.DeviceServiceStub(channel)

    auth_token = [("authorization", "Bearer %s" % settings.CHIRPSTACK_API_KEY)]

    req = api.EnqueueDeviceQueueItemRequest()
    req.queue_item.confirmed = False
    req.queue_item.data = bytes(data, encoding='utf-8')
    req.queue_item.dev_eui = dev_eui
    req.queue_item.f_port = 10

    logger.info(req.queue_item.data)

    client.Enqueue(req, metadata=auth_token)
