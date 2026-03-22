from django.shortcuts import render


def frontend_playground(request):
    return render(request, "main/frontend_playground.html")


def schedule_generator(request):
    return render(request, "main/schedule_generator.html")


def manual_change(request):
    return render(request, "main/manual_change.html")
