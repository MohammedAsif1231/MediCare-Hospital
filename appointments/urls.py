
from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),

    # Appointment Booking
    path('booking/', views.booking, name='booking'),
    path('available-slots/', views.available_slots, name='available_slots'),

    # Receptionist
    path('receptionist/', views.receptionist_dashboard, name='receptionist'),
    path(
        'receptionist/cancel/<int:appointment_id>/',
        views.cancel_receptionist_appointment,
        name='receptionist_cancel'
    ),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),

    # Patient
    path('patient/register/', views.patient_register, name='patient_register'),
    path('patient/login/', views.patient_login, name='patient_login'),
    path('patient/dashboard/', views.patient_dashboard, name='patient_dashboard'),
    path('patient/logout/', views.patient_logout, name='patient_logout'),
    path(
        'patient/cancel/<int:appointment_id>/',
        views.cancel_patient_appointment,
        name='cancel_patient_appointment'
    ),

    # Appointment Details
    path(
        'appointment-details/<int:appointment_id>/',
        views.appointment_details,
        name='appointment_details'
    ),

    # Patient History
    path('patient-history/', views.patient_history, name='patient_history'),
]
