from django.shortcuts import render

from .models import Token


def index(request):
    tokens = Token.objects.all()
    return render(request, 'api/index.html', {'tokens': tokens})

def create_token(request):
    
    if request.method == 'POST':
        name = request.POST.get('name')
        token_value = request.POST.get('token')

        # Create a new Token instance and save it to the database
        token = Token(name=name, token=token_value)
        token.save()

    return render(request, 'api/index.html', {'tokens': Token.objects.all()})

def delete_token(request, token_id):
    if request.method == 'POST':
        token = Token.objects.get(id=token_id) 
        token.delete()
        return render(request, 'api/index.html', {'tokens': Token.objects.all()})
