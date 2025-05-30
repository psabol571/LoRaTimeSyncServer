"""
URL configuration for LoRaTimeSyncServer project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from LoRaTimeSyncServerApp import views

urlpatterns = [
    path('uplink', views.receive_uplink),
    path('graph-time-diff', views.time_difference_graph),
    path('test_model', views.test_model),
    path('test_existing_model', views.test_existing_model),
    path('test_progressive_models', views.test_progressive_models),
]
