from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .models import (
    StudentProfile,
    Room,
    HostelBlock,
    LeaveRequest,
    Complaint,
    Payment,
    HostelNotice,
)


class StudentRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=True)
    student_id = forms.CharField(max_length=20, required=True)
    phone = forms.CharField(max_length=15, required=True)
    parent_phone = forms.CharField(max_length=15, required=True)
    address = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}))

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
        ]

    def clean_student_id(self):
        student_id = self.cleaned_data["student_id"]
        if StudentProfile.objects.filter(student_id=student_id).exists():
            raise ValidationError("This Student ID is already registered.")
        return student_id

    def save(self, commit=True):
        user = super().save(commit=commit)

        if commit:
            StudentProfile.objects.create(
                user=user,
                student_id=self.cleaned_data["student_id"],
                phone=self.cleaned_data["phone"],
                parent_phone=self.cleaned_data["parent_phone"],
                address=self.cleaned_data["address"],
            )

        return user


class RoomAllocationForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=StudentProfile.objects.none(),
        empty_label="Select Student",
    )
    room = forms.ModelChoiceField(
        queryset=Room.objects.none(),
        empty_label="Select Room",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["student"].queryset = (
            StudentProfile.objects.filter(room__isnull=True)
            .select_related("user")
            .order_by("user__first_name", "user__last_name")
        )

        self.fields["room"].queryset = (
            Room.objects.filter(is_available=True)
            .select_related("block")
            .order_by("block__name", "floor_number", "room_number")
        )

        self.fields["student"].label_from_instance = (
            lambda student: (
                f"{student.user.get_full_name() or student.user.username} "
                f"({student.student_id})"
            )
        )

        self.fields["room"].label_from_instance = (
            lambda room: (
                f"{room.block.name} - Floor {room.floor_number} - "
                f"Room {room.room_number} ({room.get_room_type_display()}, "
                f"{room.available_beds} beds available)"
            )
        )

    def clean(self):
        cleaned_data = super().clean()
        room = cleaned_data.get("room")

        if room and room.available_beds <= 0:
            self.add_error("room", "This room has no available beds.")

        return cleaned_data






class HostelBlockForm(forms.ModelForm):
    class Meta:
        model = HostelBlock
        fields = [
            "name",
            "location",
            "floors",
            "warden_name",
            "warden_number",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter block name",
            }),
            "location": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter block location",
            }),
            "floors": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "1",
                "step": "1",
            }),
            "warden_name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter warden name",
            }),
            "warden_number": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter warden phone number",
                "type": "tel",
            }),
        }

    def clean_floors(self):
        floors = self.cleaned_data["floors"]

        if floors < 1:
            raise ValidationError("A block must have at least one floor.")

        return floors

    def clean_warden_number(self):
        number = self.cleaned_data["warden_number"].strip()

        if not number:
            raise ValidationError("Please enter the warden's phone number.")

        return number


class RoomForm(forms.ModelForm):
    floor_number = forms.TypedChoiceField(
        choices=[("", "Select a block first")],
        coerce=int,
        required=True,
        label="Floor Number",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Room
        fields = [
            "block",
            "department",
            "floor_number",
            "room_number",
            "room_type",
            "capacity",
            "rent",
        ]
        widgets = {
            "block": forms.Select(attrs={
                "class": "form-select",
                "id": "id_block",
            }),
            "department": forms.Select(attrs={
                "class": "form-select",
            }),
            "room_number": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter room number",
            }),
            "room_type": forms.Select(attrs={
                "class": "form-select",
            }),
            "capacity": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "1",
            }),
            "rent": forms.NumberInput(attrs={
                "class": "form-control",
                "min": "0",
                "step": "0.01",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["block"].queryset = (
            HostelBlock.objects.all().order_by("name")
        )

        block_id = None

        if self.is_bound:
            block_id = self.data.get(self.add_prefix("block"))
        elif self.instance.pk:
            block_id = self.instance.block_id
        elif self.initial.get("block"):
            block_id = self.initial["block"]

        selected_block = None

        if block_id:
            try:
                selected_block = HostelBlock.objects.filter(
                    pk=block_id
                ).first()
            except (TypeError, ValueError):
                selected_block = None

        if selected_block:
            self.fields["floor_number"].choices = [
                ("", "Select floor"),
            ] + [
                (floor, f"Floor {floor}")
                for floor in range(1, selected_block.floors + 1)
            ]
        else:
            self.fields["floor_number"].choices = [
                ("", "Select a block first"),
            ]

    def clean(self):
        cleaned_data = super().clean()

        block = cleaned_data.get("block")
        floor_number = cleaned_data.get("floor_number")
        room_number = cleaned_data.get("room_number")

        if block and floor_number is not None:
            if not 1 <= floor_number <= block.floors:
                self.add_error(
                    "floor_number",
                    f"This block has {block.floors} floor(s).",
                )

        if block and room_number:
            rooms = Room.objects.filter(
                block=block,
                room_number=room_number,
            )

            if self.instance.pk:
                rooms = rooms.exclude(pk=self.instance.pk)

            if rooms.exists():
                self.add_error(
                    "room_number",
                    "This room number already exists in the selected block.",
                )

        capacity = cleaned_data.get("capacity")
        if capacity is not None and capacity < 1:
            self.add_error("capacity", "Capacity must be at least 1.")

        rent = cleaned_data.get("rent")
        if rent is not None and rent < 0:
            self.add_error("rent", "Rent cannot be negative.")

        return cleaned_data

class LeaveRequestForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ["start_date", "end_date", "reason"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "reason": forms.Textarea(attrs={"rows": 4}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date and end_date < start_date:
            self.add_error(
                "end_date",
                "End date cannot be before the start date.",
            )

        return cleaned_data


class ComplaintForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = [
            "category",
            "priority",
            "subject",
            "description",
        ]

        widgets = {
            "category": forms.Select(
                attrs={"class": "form-control"}
            ),
            "priority": forms.Select(
                attrs={"class": "form-control"}
            ),
            "subject": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter complaint subject",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Describe your complaint",
                }
            ),
        }

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["amount", "payment_method", "description"]
        widgets = {
            "amount": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "description": forms.TextInput(
                attrs={"placeholder": "Payment description"}
            ),
        }

    def clean_amount(self):
        amount = self.cleaned_data["amount"]

        if amount <= 0:
            raise ValidationError("Payment amount must be greater than zero.")

        return amount


class HostelNoticeForm(forms.ModelForm):
    class Meta:
        model = HostelNotice
        fields = ["title", "content", "is_active"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Notice title"}),
            "content": forms.Textarea(attrs={"rows": 5}),
        }