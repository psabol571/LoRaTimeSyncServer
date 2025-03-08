import time

from django.utils import timezone
from django.db.models import F
from datetime import timedelta
from .models import TimeSyncInit, TimeCollection, TimeSyncModels
from sklearn.linear_model import LinearRegression
import numpy as np

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


def createModelFromCollections(collections, dev_eui, old_period_ns):
    # create linear regression model
    model = createModel(collections, collections[0].time_received)

    new_period_ns = int(old_period_ns * model.coef_[0])
    new_period_ms = int((new_period_ns + 500) / 1e3)
    
    # offset can be calculated as accumulated error over the period passed + model.b

    # calculate accumulated error over the period passed
    time_diff_ns = collections[len(collections) - 1].time_expected - collections[0].time_expected
    # periods_passed = round(time_diff_ns / old_period_ns)
    # accumulated_error = (new_period_ns - old_period_ns) * periods_passed
    # accumulated_error = (old_period_ns - old_period_ns * model.coef_[0]) * periods_passed
    # accumulated_error = olr_period_ns * (1 - model.a) * periods_passed
    # accumulated_error = old_period_ns * (1 - model.a) * time_diff_ns / old_period_ns
    accumulated_error = time_diff_ns * (1 - model.coef_[0])
    offset = accumulated_error + model.intercept_

    # Save the model parameters
    model = TimeSyncModels.objects.create(
        dev_eui=dev_eui,
        a=model.coef_[0],
        b=model.intercept_,
        last_collection_time_received=collections[len(collections) - 1].time_received,
        new_period_ms=int(offset),
        new_period_ns=new_period_ns,
    )

    return f's,{int(offset)},{model.new_period_ns}'


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
    
    
    # # immediately sync propagation delay after first uplink
    # if len(collections) == 1:
    #     return syncAfterFirstUplink(collections)

    # Check if MIN_HOURS_FOR_NEW_MODEL hours have passed since last model creation
    time_since_last_model = timezone.now() - existing_model.created_at
    if time_since_last_model < timedelta(hours=MIN_HOURS_FOR_NEW_MODEL):
        return

    # Get collections 
    collections = TimeCollection.objects.filter(
        dev_eui=existing_model.dev_eui,
        time_received__gt=existing_model.last_collection_time_received, # after the last model creation
        time_expected__lt=F('time_received') + 1000000000 # error (received - expected) > - 1 second (filters out deep sleep outliers)
    ).order_by('time_received')

    logger.info(f"existingModelSync - collections lenght: {len(collections)}")
        
    # perform sync on clockdrift only when you have at least MIN_N records of data
    if len(collections) < MIN_N:
        return

    return createModelFromCollections(collections, existing_model.dev_eui, existing_model.new_period_ms * 1e3)


def perform_sync(dev_eui):
    # adjust parameters as needed
    MIN_N = 300
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




