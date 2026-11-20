
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User


class Appointment(models.Model):

    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]

    DOCTOR_CHOICES = [
        ('Dr. Sharma', 'Dr. Sharma - General Physician'),
        ('Dr. Khan', 'Dr. Khan - Cardiologist'),
        ('Dr. Reddy', 'Dr. Reddy - Dermatologist'),
    ]

    patient_name = models.CharField(max_length=100)
    mobile_number = models.CharField(max_length=15)
    email = models.EmailField()

    doctor = models.CharField(
        max_length=100,
        choices=DOCTOR_CHOICES
    )

    appointment_date = models.DateField()
    appointment_time = models.TimeField()
    reason = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Pending'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['doctor', 'appointment_date', 'appointment_time'],
                condition=Q(status__in=['Pending', 'Confirmed', 'Completed']),
                name='unique_active_doctor_slot'
            )
        ]

    def __str__(self):
        return self.patient_name


class PatientProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='patient_profile'
    )

    mobile_number = models.CharField(max_length=15)

    def __str__(self):
        return self.user.username
