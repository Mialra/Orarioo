from django.shortcuts import render


def frontend_playground(request):
    return render(request, "main/frontend_playground.html")

