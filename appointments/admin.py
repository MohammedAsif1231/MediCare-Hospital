
from django.contrib import admin
from .models import Appointment


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):

    list_display = (
        'patient_name',
        'mobile_number',
        'doctor',
        'appointment_date',
        'appointment_time',
        'status',
    )

    search_fields = (
        'patient_name',
        'mobile_number',
        'email',
    )

    list_filter = (
        'doctor',
        'appointment_date',
        'status',
    )
