from django.db import models
from datetime import timedelta
from django.utils import timezone

class FeeStructure(models.Model):
    grade = models.IntegerField(null=True) 
    academic_year = models.CharField(max_length=20)  
    base_fee = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    fine_per_day = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = ('grade', 'academic_year')

    def __str__(self):
        return f"Class {self.grade} - {self.academic_year}"

class StudentFee(models.Model):
    student_id = models.IntegerField()  
    fee_structure = models.ForeignKey('FeeStructure', on_delete=models.CASCADE)  
    total_amount = models.DecimalField(max_digits=10, decimal_places=2) 
    due_date = models.DateField()
    lock = models.IntegerField(default=0,)  
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ("uploaded", "Uploaded"), 
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(default=timezone.now)

    def update_status(self):
        today = timezone.now().date()
        if today > self.due_date:
            self.status = "overdue"
        else:
            self.status = "pending"
        self.save()

    def __str__(self):
        return f"{self.student} - {self.fee_structure.academic_year} - {self.status}"        

class Payment(models.Model):
    student_fee = models.ForeignKey('StudentFee', on_delete=models.CASCADE)
    
    GATEWAY_CHOICES = [
        ('razorpay', 'Razorpay'),
        ('offline', 'Offline'),
    ]
    gateway = models.CharField(max_length=20, choices=GATEWAY_CHOICES)
    
    transaction_id = models.CharField(max_length=100, unique=True, null=True, blank=True)  # from gateway
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    STATUS_CHOICES = [
        ('initiated', 'Initiated'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='initiated')
    payment_date = models.DateTimeField(default=timezone.now)
    remarks = models.TextField(null=True, blank=True)
   
    def __str__(self):
        return f"Payment {self.id} - {self.status} - {self.amount}"

class Fine(models.Model):
    student_fee = models.ForeignKey('StudentFee', on_delete=models.CASCADE)
    student_id = models.IntegerField()
    days_overdue = models.IntegerField()
    fine_amount = models.DecimalField(max_digits=10, decimal_places=2)
    calculated_on = models.DateField()

    def __str__(self):
        return f"Fine {self.fine_amount} for {self.student_fee}"

class Receipt(models.Model):
    payment = models.ForeignKey('Payment', on_delete=models.CASCADE)
    receipt_number = models.CharField(max_length=50, unique=True)  
    student_id = models.IntegerField()
    fee_structure = models.ForeignKey('FeeStructure', on_delete=models.CASCADE)  
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)  
    fine_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)  
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)  
    receipt_file = models.CharField(max_length=255, null=True, blank=True)  
    issued_date = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Receipt {self.receipt_number} - {self.student}"
