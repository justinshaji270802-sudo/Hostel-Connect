
from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone


class HostelBlock(models.Model):
    name = models.CharField(max_length=50, unique=True)
    location = models.CharField(max_length=200, blank=True, default="")
    floors = models.PositiveIntegerField(default=1)
    warden_name = models.CharField(max_length=100, blank=True, default="")
    warden_number = models.CharField(max_length=15, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Hostel Block"
        verbose_name_plural = "Hostel Blocks"


class Room(models.Model):
    ROOM_TYPES = (
        ("single", "Single"),
        ("double", "Double"),
        ("triple", "Triple"),
        ("dormitory", "Dormitory"),
    )

    DEPARTMENT_CHOICES = (
        ("MCA", "MCA"),
        ("MBA", "MBA"),
        ("ENGINEERING", "Engineering"),
    )

    block = models.ForeignKey(
        HostelBlock,
        on_delete=models.CASCADE,
        related_name="rooms",
    )
    department = models.CharField(
        max_length=20,
        choices=DEPARTMENT_CHOICES,
        default="MCA",
    )
    floor_number = models.PositiveIntegerField(default=1)
    room_number = models.CharField(max_length=10)
    room_type = models.CharField(
        max_length=20,
        choices=ROOM_TYPES,
        default="double",
    )
    capacity = models.IntegerField(default=2)
    rent = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.block.name} - Room {self.room_number}"

    @property
    def occupied(self):
        return self.students.count()

    @property
    def available_beds(self):
        return max(0, self.capacity - self.occupied)

    def update_availability(self):
        self.is_available = self.occupied < self.capacity
        self.save(update_fields=["is_available"])

    class Meta:
        unique_together = ["block", "room_number"]


class StudentProfile(models.Model):
    GENDER_CHOICES = (
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
        ("prefer_not_to_say", "Prefer not to say"),
    )

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="studentprofile",
    )
    student_id = models.CharField(max_length=20, unique=True)
    phone = models.CharField(max_length=15)
    address = models.TextField()
    parent_phone = models.CharField(max_length=15)

    emergency_contact_name = models.CharField(
        max_length=100,
        blank=True,
        default="",
    )
    date_of_birth = models.DateField(
        null=True,
        blank=True,
    )
    gender = models.CharField(
        max_length=20,
        choices=GENDER_CHOICES,
        blank=True,
        default="",
    )
    profile_picture = models.FileField(
        upload_to="profile_pictures/",
        null=True,
        blank=True,
    )

    room = models.ForeignKey(
        Room,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="students",
    )
    total_fees = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.student_id})"

    def get_full_name(self):
        return self.user.get_full_name()


class LeaveRequest(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="leave_requests",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    approved_date = models.DateField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_overdue(self):
        return (
            self.status == "approved"
            and self.returned_at is None
            and self.end_date < timezone.localdate()
        )

    def __str__(self):
        return (
            f"{self.student.user.get_full_name()} - "
            f"{self.start_date} to {self.end_date}"
        )


class Complaint(models.Model):
    CATEGORY_CHOICES = (
        ("infrastructure", "Infrastructure"),
        ("food", "Food"),
        ("sanitation", "Sanitation"),
        ("security", "Security"),
        ("internet", "Internet"),
        ("other", "Other"),
    )

    PRIORITY_CHOICES = (
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    )

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("resolved", "Resolved"),
        ("rejected", "Rejected"),
    )

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="complaints",
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    subject = models.CharField(max_length=200)
    description = models.TextField()
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default="medium",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    resolution = models.TextField(blank=True, null=True)
    resolved_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.subject} - "
            f"{self.student.user.get_full_name()}"
        )


class RentCharge(models.Model):
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Rent ₹{self.amount} - Due {self.due_date}"


class FeeCharge(models.Model):
    FEE_TYPES = (
        ("hostel_rent", "Hostel Rent"),
        ("tuition", "Tuition Fee"),
        ("admission", "Admission Fee"),
        ("mess", "Mess Fee"),
        ("maintenance", "Maintenance Fee"),
        ("other", "Other"),
    )

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="fee_charges",
    )
    title = models.CharField(max_length=200)
    fee_type = models.CharField(
        max_length=30,
        choices=FEE_TYPES,
        default="other",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} - {self.student}"

    @property
    def paid_amount(self):
        return self.payments.aggregate(
            total=models.Sum("amount")
        )["total"] or 0

    @property
    def balance(self):
        return max(self.amount - self.paid_amount, 0)

    @property
    def is_paid(self):
        return self.balance <= 0


class Payment(models.Model):
    PAYMENT_METHODS = (
        ("cash", "Cash"),
        ("card", "Card"),
        ("online", "Online Transfer"),
        ("other", "Other"),
    )

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    rent_charge = models.ForeignKey(
        RentCharge,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    fee_charge = models.ForeignKey(
        FeeCharge,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHODS,
    )
    description = models.CharField(
        max_length=200,
        blank=True,
        null=True,
    )
    payment_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"₹{self.amount} - "
            f"{self.student.user.get_full_name()}"
        )


class HostelNotice(models.Model):
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class MaintenanceRequest(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    )

    student = models.ForeignKey(
        StudentProfile,
        on_delete=models.CASCADE,
        related_name="maintenance_requests",
    )
    room = models.ForeignKey(Room, on_delete=models.CASCADE)
    issue = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Maintenance - {self.room.room_number}"
