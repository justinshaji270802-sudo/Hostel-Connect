from functools import wraps
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count, Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import (
    HostelBlock,
    Room,
    StudentProfile,
    LeaveRequest,
    Complaint,
    Payment,
    RentCharge,
    FeeCharge,
    HostelNotice,
    MaintenanceRequest,
)

from .forms import (
    StudentRegistrationForm,
    RoomAllocationForm,
    RoomForm,
    HostelBlockForm,
    LeaveRequestForm,
    ComplaintForm,
    PaymentForm,
    HostelNoticeForm,
)


def staff_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff and not request.user.is_superuser:
            messages.error(
                request,
                "You do not have permission to access this page.",
            )
            return redirect("dashboard")

        return view_func(request, *args, **kwargs)

    return wrapper


@staff_required
def send_rent_reminder(request):
    if request.method != "POST":
        return redirect("admin_dashboard")

    due_date = request.POST.get("due_date", "").strip()
    amount = request.POST.get("amount", "").strip()

    if not due_date or not amount:
        messages.error(
            request,
            "Please enter both the rent amount and due date.",
        )
        return redirect("admin_dashboard")

    try:
        due_date_obj = date.fromisoformat(due_date)
        rent_amount = Decimal(amount)
    except (ValueError, InvalidOperation):
        messages.error(
            request,
            "Please enter a valid rent amount and due date.",
        )
        return redirect("admin_dashboard")

    if due_date_obj < date.today():
        messages.error(
            request,
            "The due date cannot be in the past.",
        )
        return redirect("admin_dashboard")

    if not rent_amount.is_finite() or rent_amount <= 0:
        messages.error(
            request,
            "Rent amount must be greater than zero.",
        )
        return redirect("admin_dashboard")

    RentCharge.objects.create(
        amount=rent_amount,
        due_date=due_date_obj,
        created_by=request.user,
    )

    StudentProfile.objects.update(total_fees=rent_amount)

    HostelNotice.objects.create(
        title="Hostel Rent Payment Reminder",
        content=(
            f"Dear Students, your hostel rent payment of "
            f"₹{rent_amount:.2f} is due on "
            f"{due_date_obj.strftime('%d %B %Y')}. "
            "Please complete your payment before the due date."
        ),
        created_by=request.user,
        is_active=True,
    )

    messages.success(
        request,
        f"Rent of ₹{rent_amount:.2f} has been issued successfully.",
    )

    return redirect("admin_dashboard")


def get_student_profile(user):
    try:
        return user.studentprofile
    except StudentProfile.DoesNotExist:
        return None


def home(request):
    return render(request, "home.html")


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = StudentRegistrationForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(
                request,
                "Registration successful. You can now log in.",
            )
            return redirect("login")
    else:
        form = StudentRegistrationForm()

    return render(request, "register.html", {"form": form})


def user_login(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")

        user = authenticate(
            request,
            username=username,
            password=password,
        )

        if user is not None:
            login(request, user)
            return redirect("dashboard")

        messages.error(request, "Invalid username or password.")

    return render(request, "login.html")


@login_required
def user_logout(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("login")


@login_required
def dashboard(request):
    if request.user.is_staff or request.user.is_superuser:
        return redirect("admin_dashboard")

    return redirect("student_dashboard")


@staff_required
def admin_dashboard(request):
    total_students = StudentProfile.objects.count()

    available_rooms = Room.objects.filter(
        is_available=True
    ).count()

    pending_leaves = LeaveRequest.objects.filter(
        status="pending"
    ).count()

    pending_complaints = Complaint.objects.filter(
        status="pending"
    ).count()

    pending_leave_requests = (
        LeaveRequest.objects.filter(status="pending")
        .select_related("student__user")
        .order_by("-created_at")
    )

    pending_complaint_list = (
        Complaint.objects.filter(status="pending")
        .select_related("student__user")
        .order_by("-created_at")
    )

    recent_students = (
        StudentProfile.objects.select_related("user", "room")
        .order_by("-created_at")[:5]
    )

    recent_payments = (
        Payment.objects.select_related("student__user")
        .order_by("-payment_date")[:5]
    )

    recent_notices = (
        HostelNotice.objects.filter(is_active=True)
        .order_by("-created_at")[:5]
    )

    context = {
        "total_students": total_students,
        "available_rooms": available_rooms,
        "pending_leaves": pending_leaves,
        "pending_complaints": pending_complaints,
        "pending_leave_requests": pending_leave_requests,
        "pending_complaint_list": pending_complaint_list,
        "recent_students": recent_students,
        "recent_payments": recent_payments,
        "recent_notices": recent_notices,
        "total_blocks": HostelBlock.objects.count(),
        "total_rooms": Room.objects.count(),
        "total_payments": (
            Payment.objects.aggregate(total=Sum("amount"))["total"] or 0
        ),
        "maintenance_requests": MaintenanceRequest.objects.filter(
            status="pending"
        ).select_related("student__user", "room"),
    }

    return render(request, "dashboard_admin.html", context)


@login_required
def student_dashboard(request):
    student = get_student_profile(request.user)

    if student is None:
        messages.error(
            request,
            "Your student profile was not found. Please contact the administrator.",
        )
        return redirect("home")

    room = student.room if student.room_id is not None else None
    complaints = student.complaints.order_by("-created_at")

    context = {
        "student": student,
        "room": room,
        "pending_leave": student.leave_requests.filter(
            status="pending"
        ).count(),
        "pending_complaint": complaints.filter(
            status="pending"
        ).count(),
        "leave_requests": student.leave_requests.order_by(
            "-created_at"
        )[:5],
        "complaints": complaints[:5],
        "payments": student.payments.order_by("-payment_date")[:5],
        "notices": HostelNotice.objects.filter(
            is_active=True
        ).order_by("-created_at")[:5],
        "available_rooms": Room.objects.filter(
            is_available=True
        ).count(),
    }

    return render(request, "dashboard_student.html", context)


@login_required
def profile(request):
    student = get_student_profile(request.user)

    if student is None:
        messages.error(request, "Student profile not found.")
        return redirect("dashboard")

    if request.method == "POST":
        user = request.user
        user.first_name = request.POST.get("first_name", "").strip()
        user.last_name = request.POST.get("last_name", "").strip()
        user.email = request.POST.get("email", "").strip()
        user.save()

        student.phone = request.POST.get(
            "phone", student.phone
        ).strip()

        student.parent_phone = request.POST.get(
            "parent_phone", student.parent_phone
        ).strip()

        student.address = request.POST.get(
            "address", student.address
        ).strip()

        student.save()

        messages.success(request, "Profile updated successfully.")
        return redirect("profile")

    return render(request, "profile.html", {"student": student})


@staff_required
def hostel_rooms_blocks(request):
    blocks = HostelBlock.objects.annotate(
        room_count=Count("rooms")
    ).order_by("name")

    rooms = Room.objects.select_related("block").annotate(
        student_count=Count("students")
    ).order_by("block__name", "floor_number", "room_number")

    context = {
        "blocks": blocks,
        "rooms": rooms,
        "total_blocks": blocks.count(),
        "total_rooms": Room.objects.count(),
        "available_rooms": Room.objects.filter(is_available=True).count(),
    }

    return render(request, "hostel_rooms_blocks.html", context)


@staff_required
def add_block(request):
    if request.method == "POST":
        form = HostelBlockForm(request.POST)

        if form.is_valid():
            block = form.save()

            messages.success(
                request,
                f"Hostel block '{block.name}' created successfully "
                f"with {block.floors} floor(s).",
            )

            return redirect("hostel_rooms_blocks")
    else:
        form = HostelBlockForm()

    return render(request, "add_block.html", {"form": form})


@staff_required
def add_room(request):
    if request.method == "POST":
        form = RoomForm(request.POST)

        if form.is_valid():
            room = form.save()
            room.update_availability()

            messages.success(request, "Room added successfully.")
            return redirect("room_list")
    else:
        form = RoomForm()

    blocks = HostelBlock.objects.all().order_by("name")

    block_floor_counts = {
        str(block.pk): block.floors
        for block in blocks
    }

    return render(
        request,
        "add_room.html",
        {
            "form": form,
            "blocks": blocks,
            "block_floor_counts": block_floor_counts,
        },
    )


@staff_required
def room_list(request):
    rooms = Room.objects.select_related("block").annotate(
        student_count=Count("students")
    ).order_by("block__name", "floor_number", "room_number")

    return render(request, "room_list.html", {"rooms": rooms})


@staff_required
def room_allocation(request):
    if request.method == "POST":
        form = RoomAllocationForm(request.POST)

        if form.is_valid():
            student = form.cleaned_data["student"]
            room = form.cleaned_data["room"]

            if student.room_id is not None:
                messages.error(
                    request,
                    "This student already has an allocated room.",
                )
                return redirect("room_allocation")

            room = get_object_or_404(
                Room.objects.select_related("block"),
                pk=room.pk,
            )

            if room.available_beds <= 0:
                messages.error(
                    request,
                    "The selected room is full. Please choose another room.",
                )
                return redirect("room_allocation")

            student.room = room
            student.save(update_fields=["room"])
            room.update_availability()

            messages.success(
                request,
                f"Room {room.room_number} allocated successfully.",
            )

            return redirect("room_list")
    else:
        form = RoomAllocationForm()

    return render(request, "room_allocation.html", {"form": form})


@login_required
def leave_management(request):
    student = get_student_profile(request.user)

    if student is None:
        messages.error(request, "Student profile not found.")
        return redirect("dashboard")

    if request.method == "POST":
        form = LeaveRequestForm(request.POST)

        if form.is_valid():
            leave = form.save(commit=False)
            leave.student = student
            leave.save()

            messages.success(
                request,
                "Your leave request has been submitted.",
            )

            return redirect("leave_management")
    else:
        form = LeaveRequestForm()

    leave_requests = student.leave_requests.order_by("-created_at")

    context = {
        "form": form,
        "leave_requests": leave_requests,
        "leaves": leave_requests,
    }

    return render(request, "student_leave_management.html", context)


@staff_required
def admin_leave_management(request):
    if request.method == "POST":
        leave_id = request.POST.get("leave_id")
        action = request.POST.get("action")

        leave = get_object_or_404(LeaveRequest, pk=leave_id)

        if action == "approve":
            if leave.status != "pending":
                messages.warning(
                    request,
                    "This leave request has already been processed.",
                )
            else:
                leave.status = "approved"
                leave.approved_by = request.user
                leave.approved_date = timezone.localdate()
                leave.returned_at = None

                leave.save(
                    update_fields=[
                        "status",
                        "approved_by",
                        "approved_date",
                        "returned_at",
                    ]
                )

                messages.success(
                    request,
                    "Leave request approved successfully.",
                )

        elif action == "reject":
            if leave.status != "pending":
                messages.warning(
                    request,
                    "This leave request has already been processed.",
                )
            else:
                leave.status = "rejected"
                leave.approved_by = request.user
                leave.approved_date = timezone.localdate()

                leave.save(
                    update_fields=[
                        "status",
                        "approved_by",
                        "approved_date",
                    ]
                )

                messages.success(
                    request,
                    "Leave request rejected successfully.",
                )

        elif action == "mark_returned":
            if leave.status != "approved":
                messages.error(
                    request,
                    "Only approved leave requests can be marked as returned.",
                )
            elif leave.returned_at is not None:
                messages.info(
                    request,
                    "This student has already been marked as returned.",
                )
            else:
                leave.returned_at = timezone.now()
                leave.save(update_fields=["returned_at"])

                messages.success(
                    request,
                    "Student marked as returned successfully.",
                )

        else:
            messages.error(
                request,
                "Invalid leave management action.",
            )

        return redirect("admin_leave_management")

    today = timezone.localdate()

    leave_requests = (
        LeaveRequest.objects.select_related("student__user", "approved_by")
        .order_by("-created_at")
    )

    overdue_leaves = leave_requests.filter(
        status="approved",
        returned_at__isnull=True,
        end_date__lt=today,
    )

    context = {
        "leave_requests": leave_requests,
        "leaves": leave_requests,
        "pending_leave_requests": leave_requests.filter(status="pending"),
        "pending_count": leave_requests.filter(status="pending").count(),
        "approved_count": leave_requests.filter(status="approved").count(),
        "rejected_count": leave_requests.filter(status="rejected").count(),
        "overdue_leaves": overdue_leaves,
        "overdue_count": overdue_leaves.count(),
    }

    return render(request, "admin_leave_management.html", context)


@login_required
def complaint_tracking(request):
    student = get_student_profile(request.user)

    if student is None:
        messages.error(request, "Student profile not found.")
        return redirect("dashboard")

    if request.method == "POST":
        form = ComplaintForm(request.POST)

        if form.is_valid():
            complaint = form.save(commit=False)
            complaint.student = student
            complaint.save()

            messages.success(
                request,
                "Your complaint has been submitted.",
            )

            return redirect("complaint_tracking")
    else:
        form = ComplaintForm()

    complaints = student.complaints.order_by("-created_at")

    context = {
        "form": form,
        "complaints": complaints,
        "complaint_list": complaints,
    }

    return render(request, "complaint_tracking.html", context)


@staff_required
def admin_complaint_management(request):
    if request.method == "POST":
        complaint_id = request.POST.get("complaint_id")
        complaint = get_object_or_404(Complaint, pk=complaint_id)

        status = request.POST.get("status", complaint.status)
        resolution = request.POST.get(
            "resolution",
            complaint.resolution or "",
        ).strip()

        valid_statuses = dict(Complaint.STATUS_CHOICES)

        if status not in valid_statuses:
            messages.error(request, "Invalid complaint status.")
            return redirect("admin_complaint_management")

        complaint.status = status
        complaint.resolution = resolution or None

        if status == "resolved":
            complaint.resolved_date = timezone.localdate()
        else:
            complaint.resolved_date = None

        complaint.save(
            update_fields=[
                "status",
                "resolution",
                "resolved_date",
            ]
        )

        messages.success(request, "Complaint updated successfully.")
        return redirect("admin_complaint_management")

    complaints = (
        Complaint.objects.select_related("student__user")
        .order_by("-created_at")
    )

    context = {
        "complaints": complaints,
        "complaint_list": complaints,
        "pending_complaints": complaints.filter(status="pending").count(),
    }

    return render(request, "admin_complaint_management.html", context)


@staff_required
def payment_management(request):
    students = list(
        StudentProfile.objects.select_related("user").order_by(
            "user__first_name",
            "user__last_name",
        )
    )

    if request.method == "POST":
        action = request.POST.get("action", "assign_fee")

        if action == "assign_fee":
            title = request.POST.get("title", "").strip()
            fee_type = request.POST.get("fee_type", "other").strip()
            amount_text = request.POST.get("amount", "").strip()
            due_date_text = request.POST.get("due_date", "").strip()
            student_scope = request.POST.get("student_scope", "all")
            selected_students = request.POST.getlist("students")

            try:
                if not title:
                    raise ValueError("Please enter a fee name.")

                amount = Decimal(amount_text)

                if not amount.is_finite() or amount <= 0:
                    raise ValueError("Enter a valid fee amount.")

                due_date = date.fromisoformat(due_date_text)

                if due_date < timezone.localdate():
                    raise ValueError("Due date cannot be in the past.")

                if fee_type not in dict(FeeCharge.FEE_TYPES):
                    raise ValueError("Please select a valid fee category.")

                if student_scope == "all":
                    target_students = students

                elif student_scope == "selected":
                    if not selected_students:
                        raise ValueError("Please select at least one student.")

                    target_students = list(
                        StudentProfile.objects.filter(
                            pk__in=selected_students
                        ).select_related("user")
                    )

                    if not target_students:
                        raise ValueError("No valid students were selected.")

                else:
                    raise ValueError("Invalid student selection.")

                fee_records = [
                    FeeCharge(
                        student=student,
                        title=title,
                        fee_type=fee_type,
                        amount=amount,
                        due_date=due_date,
                        created_by=request.user,
                    )
                    for student in target_students
                ]

                with transaction.atomic():
                    FeeCharge.objects.bulk_create(fee_records)

                messages.success(
                    request,
                    f"{title} assigned successfully to "
                    f"{len(target_students)} student(s).",
                )

                return redirect("payment_management")

            except (ValueError, InvalidOperation):
                messages.error(
                    request,
                    "Please check the fee name, category, amount, due date "
                    "and student selection.",
                )

        elif action == "record_payment":
            fee_charge_id = request.POST.get("fee_charge_id")
            payment_amount_text = request.POST.get(
                "payment_amount", ""
            ).strip()
            payment_method = request.POST.get(
                "payment_method", ""
            ).strip()
            description = request.POST.get("description", "").strip()

            valid_methods = dict(Payment.PAYMENT_METHODS)

            try:
                payment_amount = Decimal(payment_amount_text)

                if not payment_amount.is_finite() or payment_amount <= 0:
                    raise ValueError("Enter a valid payment amount.")

                if payment_method not in valid_methods:
                    raise ValueError("Select a valid payment method.")

                with transaction.atomic():
                    charge = get_object_or_404(
                        FeeCharge.objects.select_for_update(),
                        pk=fee_charge_id,
                    )

                    already_paid = (
                        Payment.objects.filter(fee_charge=charge)
                        .aggregate(total=Sum("amount"))["total"]
                        or Decimal("0.00")
                    )

                    balance = max(
                        charge.amount - already_paid,
                        Decimal("0.00"),
                    )

                    if balance <= 0:
                        raise ValueError("This fee has already been fully paid.")

                    if payment_amount > balance:
                        raise ValueError(
                            "Payment cannot be greater than the outstanding balance."
                        )

                    Payment.objects.create(
                        student=charge.student,
                        fee_charge=charge,
                        amount=payment_amount,
                        payment_method=payment_method,
                        description=description or charge.title,
                    )

                messages.success(
                    request,
                    f"Payment of ₹{payment_amount:.2f} recorded successfully.",
                )

                return redirect("payment_management")

            except (ValueError, InvalidOperation):
                messages.error(
                    request,
                    "Payment could not be recorded. Check the amount, method "
                    "and outstanding balance.",
                )

        else:
            messages.error(request, "Invalid payment action.")

    fee_charges = list(
        FeeCharge.objects.select_related(
            "student",
            "student__user",
        ).annotate(
            paid_total=Sum("payments__amount")
        ).order_by("-created_at")
    )

    fee_summary_by_student = {}

    total_assigned = Decimal("0.00")
    total_fee_received = Decimal("0.00")
    total_outstanding = Decimal("0.00")

    for charge in fee_charges:
        paid_amount = charge.paid_total or Decimal("0.00")

        balance = max(
            charge.amount - paid_amount,
            Decimal("0.00"),
        )

        charge.assigned_paid_amount = paid_amount
        charge.assigned_balance = balance

        if balance <= 0:
            charge.payment_status = "paid"
        elif paid_amount > 0:
            charge.payment_status = "partial"
        else:
            charge.payment_status = "pending"

        total_assigned += charge.amount
        total_fee_received += paid_amount
        total_outstanding += balance

        student_id = charge.student_id

        if student_id not in fee_summary_by_student:
            fee_summary_by_student[student_id] = {
                "student": charge.student,
                "assigned": Decimal("0.00"),
                "paid": Decimal("0.00"),
                "balance": Decimal("0.00"),
                "has_fees": True,
            }

        summary = fee_summary_by_student[student_id]

        summary["assigned"] += charge.amount
        summary["paid"] += paid_amount
        summary["balance"] += balance

    students_summary = []
    paid_students = []
    unpaid_students = []
    unassigned_students = []

    for student in students:
        summary = fee_summary_by_student.get(student.pk)

        if summary is None:
            summary = {
                "student": student,
                "assigned": Decimal("0.00"),
                "paid": Decimal("0.00"),
                "balance": Decimal("0.00"),
                "has_fees": False,
            }

            unassigned_students.append(summary)

        else:
            if summary["balance"] <= 0:
                paid_students.append(summary)
            else:
                unpaid_students.append(summary)

        students_summary.append(summary)

    payment_history = (
        Payment.objects.select_related(
            "student",
            "student__user",
            "fee_charge",
            "rent_charge",
        )
        .order_by("-payment_date")
    )

    payment_history_count = payment_history.count()

    total_transactions = payment_history_count

    total_received = (
        payment_history.aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")
    )

    paid_count = len(paid_students)
    unpaid_count = len(unpaid_students)
    unassigned_count = len(unassigned_students)

    context = {
        "students": students,
        "fee_charges": fee_charges,
        "students_summary": students_summary,
        "paid_students": paid_students,
        "unpaid_students": unpaid_students,
        "unassigned_students": unassigned_students,
        "total_received": total_received,
        "total_fee_received": total_fee_received,
        "total_transactions": total_transactions,
        "total_assigned": total_assigned,
        "total_outstanding": total_outstanding,
        "total_fee_charges": len(fee_charges),
        "paid_count": paid_count,
        "unpaid_count": unpaid_count,
        "unassigned_count": unassigned_count,
        "total_students": len(students),
        "payment_history": payment_history,
        "payment_history_count": payment_history_count,
    }

    return render(request, "payment_management.html", context)


@login_required
def fee_management(request):
    if request.user.is_staff or request.user.is_superuser:
        payments = Payment.objects.select_related(
            "student__user",
            "rent_charge",
        ).order_by("-payment_date")

        total_transactions = payments.count()

        total_paid = payments.aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

        context = {
            "payments": payments,
            "students": StudentProfile.objects.select_related("user"),
            "total_transactions": total_transactions,
            "total_paid": total_paid,
            "pending_due": Decimal("0.00"),
            "total_fees": Decimal("0.00"),
            "balance": Decimal("0.00"),
        }

        return render(request, "fee_management.html", context)

    student = get_student_profile(request.user)

    if student is None:
        messages.error(request, "Student profile not found.")
        return redirect("dashboard")

    current_rent_charge = RentCharge.objects.order_by(
        "-created_at"
    ).first()

    if request.method == "POST":
        form = PaymentForm(request.POST)

        if form.is_valid():
            if current_rent_charge is None:
                messages.error(
                    request,
                    "The administrator has not issued a rent charge yet.",
                )
                return redirect("fee_management")

            payment = form.save(commit=False)
            payment.student = student
            payment.rent_charge = current_rent_charge
            payment.save()

            messages.success(
                request,
                "Payment record added successfully.",
            )

            return redirect("fee_management")
    else:
        form = PaymentForm()

    payments = student.payments.order_by("-payment_date")
    total_transactions = payments.count()

    total_paid = payments.aggregate(
        total=Sum("amount")
    )["total"] or Decimal("0.00")

    if current_rent_charge is not None:
        current_rent_payments = student.payments.filter(
            rent_charge=current_rent_charge
        )

        current_rent_paid = current_rent_payments.aggregate(
            total=Sum("amount")
        )["total"] or Decimal("0.00")

        total_fees = current_rent_charge.amount

        pending_due = max(
            total_fees - current_rent_paid,
            Decimal("0.00"),
        )
    else:
        total_fees = Decimal("0.00")
        pending_due = Decimal("0.00")

    context = {
        "form": form,
        "payments": payments,
        "total_transactions": total_transactions,
        "total_paid": total_paid,
        "pending_due": pending_due,
        "total_fees": total_fees,
        "balance": pending_due,
        "student": student,
        "current_rent_charge": current_rent_charge,
    }

    return render(request, "fee_management.html", context)


@staff_required
def student_list(request):
    students = StudentProfile.objects.select_related(
        "user",
        "room__block",
    ).order_by("user__first_name", "user__last_name")

    return render(
        request,
        "student_list.html",
        {"students": students},
    )


@login_required
def notice_board(request):
    if request.method == "POST":
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(
                request,
                "You do not have permission to publish notices.",
            )
            return redirect("notice_board")

        form = HostelNoticeForm(request.POST)

        if form.is_valid():
            notice = form.save(commit=False)
            notice.created_by = request.user
            notice.save()

            messages.success(
                request,
                "Notice published successfully.",
            )

            return redirect("notice_board")

    else:
        form = HostelNoticeForm()

    if request.user.is_staff or request.user.is_superuser:
        notices = HostelNotice.objects.order_by("-created_at")
    else:
        notices = HostelNotice.objects.filter(
            is_active=True
        ).order_by("-created_at")

    context = {
        "form": form,
        "notices": notices,
        "is_staff_user": (
            request.user.is_staff or request.user.is_superuser
        ),
    }

    return render(request, "notice_board.html", context)


@staff_required
def reports(request):
    context = {
        "total_students": StudentProfile.objects.count(),
        "total_blocks": HostelBlock.objects.count(),
        "total_rooms": Room.objects.count(),
        "available_rooms": Room.objects.filter(is_available=True).count(),
        "occupied_rooms": Room.objects.filter(
            students__isnull=False
        ).distinct().count(),
        "pending_leaves": LeaveRequest.objects.filter(
            status="pending"
        ).count(),
        "approved_leaves": LeaveRequest.objects.filter(
            status="approved"
        ).count(),
        "pending_complaints": Complaint.objects.filter(
            status="pending"
        ).count(),
        "resolved_complaints": Complaint.objects.filter(
            status="resolved"
        ).count(),
        "total_payments": (
            Payment.objects.aggregate(total=Sum("amount"))["total"] or 0
        ),
        "total_maintenance_requests": MaintenanceRequest.objects.count(),
    }

    return render(request, "reports.html", context)


def about(request):
    return render(request, "about.html")


def contact(request):
    return render(request, "contact.html")