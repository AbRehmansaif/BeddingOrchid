from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Page, ContactMessage

def page_detail(request, slug):
    page = get_object_or_404(Page, slug=slug)
    return render(request, 'pages/page_detail.html', {'page': page})


def contact_us(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message_text = request.POST.get('message', '').strip()

        if not name or not phone or not message_text:
            messages.error(request, "Please enter your name, phone number, and message.")
        else:
            ContactMessage.objects.create(
                name=name,
                phone=phone,
                email=email,
                subject=subject or 'General Inquiry',
                message=message_text
            )
            messages.success(request, "Thank you! Your message has been received. Our team will contact you shortly.")
            return redirect('pages:contact')

    return render(request, 'pages/contact.html')


def faq_page(request):
    return render(request, 'pages/faq.html')
