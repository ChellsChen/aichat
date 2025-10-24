from django.http import HttpResponse

def hello(request):
    return HttpResponse("Hello world ! ")


def oauth_callback(request):
    return HttpResponse("Hello world ! ")