
from datetime import date, time

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.db import IntegrityError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.urls import reverse

from .forms import LoginForm, PatientRegistrationForm
from .models import Appointment, PatientProfile


# Receptionist Security
def receptionist_required(view_func):
    return user_passes_test(
        lambda user: user.is_authenticated and (user.is_staff or user.is_superuser),
        login_url='login'
    )(view_func)


# Home Page
def home(request):
    context = {
        'total_appointments': Appointment.objects.count(),
        'pending_appointments': Appointment.objects.filter(status='Pending').count(),
        'confirmed_appointments': Appointment.objects.filter(status='Confirmed').count(),
        'completed_appointments': Appointment.objects.filter(status='Completed').count(),
    }
    return render(request, 'appointments/index.html', context)


# Appointment Booking
def booking(request):
    if not request.user.is_authenticated:
        return redirect(f"{reverse('patient_login')}?next={reverse('booking')}")

    if not hasattr(request.user, 'patient_profile'):
        return redirect('home')

    today = timezone.localdate()

    appointment_slots = [
        time(9, 0), time(10, 0), time(11, 0),
        time(12, 0), time(13, 0),
        time(15, 0), time(16, 0), time(17, 0),
        time(18, 0), time(19, 0), time(20, 0),
        time(21, 0),
    ]

    context = {
        'today': today.isoformat(),
        'appointment_slots': appointment_slots,
    }

    if request.method == 'POST':
        try:
            selected_date = date.fromisoformat(
                request.POST.get('appointment_date')
            )
            selected_time = time.fromisoformat(
                request.POST.get('appointment_time')
            )
        except (ValueError, TypeError):
            context['error'] = 'Please enter a valid date and time.'
            return render(request, 'appointments/booking.html', context)

        if selected_date < today:
            context['error'] = 'Past dates are not allowed.'
            return render(request, 'appointments/booking.html', context)

        if selected_time not in appointment_slots:
            context['error'] = 'Please select a valid appointment time.'
            return render(request, 'appointments/booking.html', context)

        current_time = timezone.localtime().time().replace(tzinfo=None)

        if selected_date == today and selected_time <= current_time:
            context['error'] = 'Please select a future appointment time.'
            return render(request, 'appointments/booking.html', context)

        doctor = request.POST.get('doctor')

        if doctor not in dict(Appointment.DOCTOR_CHOICES):
            context['error'] = 'Please select a valid doctor.'
            return render(request, 'appointments/booking.html', context)

        profile = request.user.patient_profile

        try:
            Appointment.objects.create(
                patient_name=request.user.username,
                mobile_number=profile.mobile_number,
                email=request.user.email,
                doctor=doctor,
                appointment_date=selected_date,
                appointment_time=selected_time,
                reason=request.POST.get('reason'),
                 status='Confirmed'
            )
        except IntegrityError:
            context['error'] = 'This time slot is already booked.'
            return render(request, 'appointments/booking.html', context)

        context['success'] = True

    return render(request, 'appointments/booking.html', context)



# Available Appointment Slots and Dates
def available_slots(request):
    from calendar import monthrange

    doctor = request.GET.get('doctor', '')
    appointment_date = request.GET.get('date')
    selected_month = request.GET.get('month')

    doctors = [choice[0] for choice in Appointment.DOCTOR_CHOICES]

    if doctor and doctor not in doctors:
        return JsonResponse({
            'booked_slots': [],
            'available_slots': [],
            'fully_booked_dates': []
        })

    all_slots = [
        time(9, 0), time(10, 0), time(11, 0),
        time(12, 0), time(13, 0),
        time(15, 0), time(16, 0),
        time(17, 0), time(18, 0),
        time(19, 0), time(20, 0), time(21, 0)
    ]

    active_appointments = Appointment.objects.filter(
        status__in=['Pending', 'Confirmed', 'Completed']
    )

    selected_doctors = [doctor] if doctor else doctors

    fully_booked_dates = []

    if selected_month:
        try:
            year, month = map(int, selected_month.split('-'))
            days_in_month = monthrange(year, month)[1]

            for day in range(1, days_in_month + 1):
                current_date = date(year, month, day)
                all_doctors_full = True

                for doc in selected_doctors:
                    booked = set(
                        active_appointments.filter(
                            doctor=doc,
                            appointment_date=current_date
                        ).values_list('appointment_time', flat=True)
                    )

                    if not all(slot in booked for slot in all_slots):
                        all_doctors_full = False
                        break

                if all_doctors_full:
                    fully_booked_dates.append(current_date.isoformat())

        except (ValueError, TypeError):
            pass

    booked_slots = []
    available_slots = []

    if appointment_date:
        try:
            selected_date = date.fromisoformat(appointment_date)

            for slot in all_slots:
                booked_for_all = True

                for doc in selected_doctors:
                    exists = active_appointments.filter(
                        doctor=doc,
                        appointment_date=selected_date,
                        appointment_time=slot
                    ).exists()

                    if not exists:
                        booked_for_all = False
                        break

                if booked_for_all:
                    booked_slots.append(slot.strftime('%H:%M'))
                else:
                    available_slots.append(slot.strftime('%H:%M'))

        except (ValueError, TypeError):
            pass

    return JsonResponse({
        'booked_slots': booked_slots,
        'available_slots': available_slots,
        'fully_booked_dates': fully_booked_dates
    })


# Receptionist Dashboard
@receptionist_required
def receptionist_dashboard(request):
    search_query = request.GET.get('q', '')
    doctor_filter = request.GET.get('doctor', '')

    appointments = Appointment.objects.all()

    if search_query:
        appointments = appointments.filter(
            Q(patient_name__icontains=search_query) |
            Q(mobile_number__icontains=search_query)
        )

    if doctor_filter:
        appointments = appointments.filter(doctor=doctor_filter)

    appointments = appointments.order_by('-created_at')

    return render(request, 'appointments/receptionist.html', {
        'appointments': appointments,
        'status_choices': Appointment.STATUS_CHOICES,
        'search_query': search_query,
        'doctor_choices': Appointment.DOCTOR_CHOICES,
        'doctor_filter': doctor_filter,
    })


# Update Appointment Status
@receptionist_required
def update_appointment_status(request, appointment_id):
    if request.method == 'POST':
        appointment = get_object_or_404(Appointment, id=appointment_id)
        new_status = request.POST.get('status')

        if new_status in dict(Appointment.STATUS_CHOICES):
            appointment.status = new_status
            appointment.save()

    return redirect('receptionist')


# Delete Appointment
@receptionist_required
def delete_appointment(request, appointment_id):
    if request.method == 'POST':
        appointment = get_object_or_404(Appointment, id=appointment_id)
        appointment.delete()

    return redirect('receptionist')


# Appointment Details
@receptionist_required
def appointment_details(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)

    return render(request, 'appointments/details.html', {
        'appointment': appointment
    })


# Patient History
@receptionist_required
def patient_history(request):
    mobile_number = request.GET.get('mobile', '')
    appointments = Appointment.objects.none()

    if mobile_number:
        appointments = Appointment.objects.filter(
            mobile_number=mobile_number
        ).order_by('-appointment_date', '-appointment_time')

    return render(request, 'appointments/history.html', {
        'appointments': appointments,
        'mobile_number': mobile_number,
    })


# Receptionist Login
def user_login(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()

            if user.is_staff or user.is_superuser:
                login(request, user)
                return redirect('receptionist')

            form.add_error(None, 'Receptionist account not found.')
    else:
        form = LoginForm()

    return render(request, 'appointments/login.html', {'form': form})


# Receptionist Logout
@receptionist_required
def user_logout(request):
    logout(request)
    return redirect('home')


# Patient Registration
def patient_register(request):
    next_url = request.POST.get('next') or request.GET.get('next')

    if request.method == 'POST':
        form = PatientRegistrationForm(request.POST)
        mobile_number = request.POST.get('mobile_number', '').strip()

        if not mobile_number:
            form.add_error(None, 'Mobile number is required.')

        elif form.is_valid():
            user = form.save()

            PatientProfile.objects.create(
                user=user,
                mobile_number=mobile_number
            )

            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()}
            ):
                return redirect(f"{reverse('patient_login')}?next={next_url}")

            return redirect('patient_login')
    else:
        form = PatientRegistrationForm()

    return render(request, 'appointments/patient_register.html', {
        'form': form
    })


# Patient Login
def patient_login(request):
    next_url = request.POST.get('next') or request.GET.get('next')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()

            if hasattr(user, 'patient_profile'):
                login(request, user)

                if next_url and url_has_allowed_host_and_scheme(
                    next_url,
                    allowed_hosts={request.get_host()}
                ):
                    return redirect(next_url)

                return redirect('patient_dashboard')

            form.add_error(None, 'Patient account not found.')
    else:
        form = AuthenticationForm()

    return render(request, 'appointments/patient_login.html', {
        'form': form
    })


# Patient Dashboard
@login_required(login_url='patient_login')
def patient_dashboard(request):
    patient_profile = get_object_or_404(
        PatientProfile,
        user=request.user
    )

    appointments = Appointment.objects.filter(
        mobile_number=patient_profile.mobile_number
    ).order_by('-created_at')

    return render(request, 'appointments/patient_dashboard.html', {
        'patient': patient_profile,
        'appointments': appointments
    })


# Patient Logout
@login_required(login_url='patient_login')
def patient_logout(request):
    if not hasattr(request.user, 'patient_profile'):
        return redirect('home')

    logout(request)
    return redirect('home')


# Patient Appointment Cancellation
@login_required(login_url='patient_login')
def cancel_patient_appointment(request, appointment_id):
    if request.method == 'POST':
        patient_profile = get_object_or_404(
            PatientProfile,
            user=request.user
        )

        appointment = get_object_or_404(
            Appointment,
            id=appointment_id,
            mobile_number=patient_profile.mobile_number
        )

        if appointment.status in ['Pending', 'Confirmed']:
            appointment.status = 'Cancelled'
            appointment.save()

    return redirect('patient_dashboard')


@receptionist_required
def cancel_receptionist_appointment(request, appointment_id):
    if request.method == 'POST':
        appointment = get_object_or_404(
            Appointment,
            id=appointment_id
        )

        if appointment.status in ['Pending', 'Confirmed']:
            appointment.status = 'Cancelled'
            appointment.save()

    return redirect('receptionist')
