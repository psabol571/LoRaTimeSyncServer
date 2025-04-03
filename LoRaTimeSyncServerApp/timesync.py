import time

from django.utils import timezone
from django.db.models import F
from datetime import timedelta
from .models import TimeSyncInit, TimeCollection, TimeSyncModels
from sklearn.linear_model import LinearRegression
import numpy as np
from .testing_utils import filter_time_diff_outliers
import logging
logger = logging.getLogger('django')


def initTimeSync(dev_eui, period, now):
    reserve = 3
    first_uplink_expected = (
        (now + (period + reserve) * (1000**3))  # add period and reserve as nanoseconds
        // (1000**3) 
    ) * (1000**3)  # and cut it to nearest second
    
    time_sync_device = TimeSyncInit.objects.create(
        dev_eui=dev_eui,
        period=period,
        first_uplink_expected=first_uplink_expected,
    )

    return first_uplink_expected


def saveTimeCollection(dev_eui, device_time, time_received):
    device = TimeSyncInit.objects.filter(dev_eui=dev_eui).last()

    if device is None:
        return None

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



def createModel(collections, first_received):
    # Prepare data for linear regression
    X = np.array([c.time_received - first_received for c in collections]).reshape(-1, 1)
    y = np.array([c.time_expected - first_received for c in collections])

    # Perform linear regression
    model = LinearRegression()
    model.fit(X, y)

    return model


def createModelWithOffset(collections, dev_eui, old_period_ns):
    model = createModel(collections, collections[0].time_received)

    new_period_ns = int(old_period_ns * model.coef_[0])
    new_period_ms = int((new_period_ns + 500) / 1e3)

    time_diff_ns = collections[len(collections) - 1].time_expected - collections[0].time_expected
    # periods_passed = round(time_diff_ns / old_period_ns)
    # accumulated_error = (new_period_ns - old_period_ns) * periods_passed
    # accumulated_error = (old_period_ns * model.coef_[0] - old_period_ns) * periods_passed
    # accumulated_error = old_period_ns * (model.coef_[0] - 1) * periods_passed
    # accumulated_error = old_period_ns * (model.coef_[0] - 1) * time_diff_ns / old_period_ns
    accumulated_error = time_diff_ns * (model.coef_[0] - 1)
    offset = int(accumulated_error + model.intercept_)

    return {
        'a': model.coef_[0],
        'b': model.intercept_,
        'new_period_ns': new_period_ns,
        'new_period_ms': new_period_ms,
        'offset': offset,
        'dev_eui': dev_eui,
        'last_collection_time_received': collections[len(collections) - 1].time_received,
    }
    

def saveModelWithOffset(model_data):
    return TimeSyncModels.objects.create(
        dev_eui=model_data['dev_eui'],
        a=model_data['a'],
        b=model_data['b'],
        last_collection_time_received=model_data['last_collection_time_received'],
        new_period_ns=model_data['new_period_ns'],
        new_period_ms=model_data['new_period_ms'],
        offset=model_data['offset'],
    )


def createModelFromCollections(collections, dev_eui, old_period_ns):
    # create linear regression model
    model = createModelWithOffset(collections, dev_eui, old_period_ns)

    saveModelWithOffset(model)

    return f's,{model["offset"]},{model["new_period_ns"]}'


def syncAfterFirstUplink(collections):
    # Calculate the offset for the first uplink
    first_collection = collections[0]
    offset = first_collection.time_expected - first_collection.time_received

    # send offset after first uplink
    return f's,{int(offset)}'


def nonExistingModelSync(sync_init, MIN_N):
    # Get collections after the first uplink
    collections = TimeCollection.objects.filter(
        dev_eui=sync_init.dev_eui, 
        time_expected__gte=sync_init.first_uplink_expected
    ).order_by('time_received')

    # immediately sync propagation delay after first uplink
    if len(collections) == 1:
        return syncAfterFirstUplink(collections)

    # perform sync on clockdrift only when you have at least MIN_N records of data
    if len(collections) < MIN_N:
        return

    # remove first 2 unsynced outlier uplinks
    return createModelFromCollections(collections[2:], sync_init.dev_eui, sync_init.period * 1e9)


def existingModelSync(existing_model, MIN_N, MIN_HOURS_FOR_NEW_MODEL):
    # Check if MIN_HOURS_FOR_NEW_MODEL hours have passed since last model creation
    time_since_last_model = timezone.now() - existing_model.created_at
    if time_since_last_model < timedelta(hours=MIN_HOURS_FOR_NEW_MODEL):
        return

    # Get collections 
    collections = TimeCollection.objects.filter(
        dev_eui=existing_model.dev_eui,
        time_received__gt=existing_model.last_collection_time_received, # after the last model creation
    ).order_by('time_received')

    collections = filter_time_diff_outliers(collections)

    logger.info(f"existingModelSync - collections lenght: {len(collections)}")
        
    # first, create a model without saving it
    model = createModelWithOffset(collections, existing_model.dev_eui, existing_model.new_period_ms * 1e3)

    treshold_offset_nanoseconds = 0.04 * 1e9 ## try to keep it in +- 40 miliseconds

    # if offset is in the precision threshold, do not save a new model, we dont need a resync yet
    if -treshold_offset_nanoseconds < model['offset'] < treshold_offset_nanoseconds:
        return

    saveModelWithOffset(model)

    return f's,{model["offset"]},{model["new_period_ns"]}'


def perform_sync(dev_eui):
    # adjust parameters as needed
    MIN_N = 150
    MIN_HOURS_FOR_NEW_MODEL = 24

    # Get the last TimeSyncInit record 
    sync_init = TimeSyncInit.objects.filter(
        dev_eui=dev_eui,
    ).last()

    if sync_init is None:
        return

    # Get the last TimeSyncModels record created after first TimeSyncInit
    existing_model = TimeSyncModels.objects.filter(
        dev_eui=dev_eui, created_at__gt=sync_init.created_at
    ).last()

    if existing_model is None:
        return nonExistingModelSync(sync_init, MIN_N)
    else:
        return existingModelSync(existing_model, MIN_N, MIN_HOURS_FOR_NEW_MODEL)




