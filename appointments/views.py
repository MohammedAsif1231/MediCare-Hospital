
from datetime import date, time

from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
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
        appointment_date = request.POST.get('appointment_date')
        appointment_time = request.POST.get('appointment_time')

        try:
            selected_date = date.fromisoformat(appointment_date)
            selected_time = time.fromisoformat(appointment_time)
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

        if request.user.is_authenticated and hasattr(request.user, 'patient_profile'):
            profile = request.user.patient_profile
            patient_name = request.user.username
            mobile_number = profile.mobile_number
            email = request.user.email
        else:
            patient_name = request.POST.get('patient_name')
            mobile_number = request.POST.get('mobile_number')
            email = request.POST.get('email')

        doctor = request.POST.get('doctor')

        if doctor not in dict(Appointment.DOCTOR_CHOICES):
            context['error'] = 'Please select a valid doctor.'
            return render(request, 'appointments/booking.html', context)

        already_booked = Appointment.objects.filter(
            doctor=doctor,
            appointment_date=selected_date,
            appointment_time=selected_time,
            status__in=['Pending', 'Confirmed', 'Completed']
        ).exists()

        if already_booked:
            context['error'] = 'This time slot is already booked.'
            return render(request, 'appointments/booking.html', context)

        Appointment.objects.create(
            patient_name=patient_name,
            mobile_number=mobile_number,
            email=email,
            doctor=doctor,
            appointment_date=selected_date,
            appointment_time=selected_time,
            reason=request.POST.get('reason')
        )

        context['success'] = True
        return render(request, 'appointments/booking.html', context)

    return render(request, 'appointments/booking.html', context)


# Available Appointment Slots
def available_slots(request):
    doctor = request.GET.get('doctor')
    appointment_date = request.GET.get('date')

    if doctor not in dict(Appointment.DOCTOR_CHOICES) or not appointment_date:
        return JsonResponse({'booked_slots': []})

    try:
        selected_date = date.fromisoformat(appointment_date)
    except (ValueError, TypeError):
        return JsonResponse({'booked_slots': []})

    booked_slots = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=selected_date,
        status__in=['Pending', 'Confirmed', 'Completed']
    ).values_list('appointment_time', flat=True)

    booked_times = [slot.strftime('%H:%M') for slot in booked_slots]

    return JsonResponse({'booked_slots': booked_times})


# Receptionist Dashboard
@login_required
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


@login_required
def update_appointment_status(request, appointment_id):
    if request.method == 'POST':
        appointment = get_object_or_404(Appointment, id=appointment_id)
        new_status = request.POST.get('status')

        if new_status in dict(Appointment.STATUS_CHOICES):
            appointment.status = new_status
            appointment.save()

    return redirect('receptionist')


@login_required
def delete_appointment(request, appointment_id):
    if request.method == 'POST':
        appointment = get_object_or_404(Appointment, id=appointment_id)
        appointment.delete()

    return redirect('receptionist')


@login_required
def appointment_details(request, appointment_id):
    appointment = get_object_or_404(Appointment, id=appointment_id)

    return render(request, 'appointments/details.html', {
        'appointment': appointment
    })


@login_required
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


@login_required
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
        return redirect('login')

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


# Doctor Accounts
DOCTOR_ACCOUNTS = {
    'dr_sharma': 'Dr. Sharma',
    'dr_khan': 'Dr. Khan',
    'dr_reddy': 'Dr. Reddy',
}

# Doctor Security
def doctor_required(view_func):
    return user_passes_test(
        lambda user: user.is_authenticated and user.username in DOCTOR_ACCOUNTS,
        login_url='doctor_login'
    )(view_func)    

# Doctor Login
def doctor_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()

            if user.username in DOCTOR_ACCOUNTS:
                login(request, user)
                return redirect('doctor_dashboard')

            form.add_error(None, 'Doctor account not found.')
    else:
        form = AuthenticationForm()

    return render(request, 'appointments/doctor_login.html', {
        'form': form
    })


# Doctor Dashboard
@login_required
def doctor_dashboard(request):
    doctor_name = DOCTOR_ACCOUNTS.get(request.user.username)

    if not doctor_name:
        logout(request)
        return redirect('doctor_login')

    if request.method == 'POST':
        appointment_id = request.POST.get('appointment_id')
        new_status = request.POST.get('status')

        if new_status in ['Confirmed', 'Completed']:
            appointment = get_object_or_404(
                Appointment,
                id=appointment_id,
                doctor=doctor_name
            )

            appointment.status = new_status
            appointment.save()

        return redirect('doctor_dashboard')

    appointments = Appointment.objects.filter(
        doctor=doctor_name
    ).order_by('-appointment_date', '-appointment_time')

    return render(request, 'appointments/doctor_dashboard.html', {
        'doctor_name': doctor_name,
        'appointments': appointments
    })


# Doctor Logout
@login_required
def doctor_logout(request):
    if request.user.username not in DOCTOR_ACCOUNTS:
        return redirect('home')

    logout(request)
    return redirect('doctor_login')
