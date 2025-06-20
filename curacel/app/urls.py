from django.urls import path
from . import views

urlpatterns = [
    path('claimgpt/', views.claimgpt, name='claimgpt'),
    path('policymatch/', views.policymatchgpt, name='policy'),
        path('claims_assistant/', views.claims_assistant, name='claims_assistant'),
                path('bot/', views.insurance_chatbot, name='bot'),
                path('home/', views.index, name="home" )




]