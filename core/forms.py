# core/forms.py (crie o arquivo)
from django import forms
from .models import Movimento, Acerto
from django.core.validators import RegexValidator

class MovimentoForm(forms.ModelForm):
    class Meta:
        model = Movimento
        fields = ['nome', 'responsavel', 'telefone']
        widgets = {
            'telefone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '(99) 99999-9999',
                'data-mask': '(00) 00000-0000'  # Para plugins de máscara
            }),
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'responsavel': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def clean_telefone(self):
        telefone = self.cleaned_data['telefone']
        # Remove caracteres não numéricos
        return ''.join(filter(str.isdigit, telefone))

class AcertoForm(forms.ModelForm):
    # Campos "virtuais" que usamos para a tela de edição
    numeros_vendidas = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        required=False,
        label="Números das Cartelas Vendidas"
    )
    numeros_devolvidas = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        required=False,
        label="Números das Cartelas Devolvidas"
    )
    numeros_cortesia = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        required=False,
        label="Números das Cartelas Cortesia"
    )

    class Meta:
        model = Acerto
        # Note que os campos ManyToMany NÃO ESTÃO AQUI
        fields = [
            'movimento', 
            'membro_pastoral', 
            'valor_recebido',
            'tipo_pagamento',
            'observacoes'
        ]
        widgets = {
            'movimento': forms.Select(attrs={'class': 'form-select'}),
            'membro_pastoral': forms.TextInput(attrs={'class': 'form-control'}),
            'valor_recebido': forms.NumberInput(attrs={'class': 'form-control'}),
            'tipo_pagamento': forms.Select(attrs={'class': 'form-select'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class CancelamentoForm(forms.Form):
    numero_cartela = forms.CharField(label="Número da Cartela", max_length=4)
    motivo = forms.CharField(label="Motivo do Cancelamento", widget=forms.Textarea)

class CancelamentoLoteForm(forms.Form):
    numeros_cartelas = forms.CharField(
        label='Números das Cartelas',
        widget=forms.Textarea(attrs={'rows': 6, 'placeholder': 'Cole ou digite os números aqui, separados por espaço, vírgula ou um por linha.'}),
        help_text='Insira todos os números das cartelas que deseja cancelar.'
    )
    motivo = forms.CharField(
        label='Motivo do Cancelamento',
        max_length=200,
        widget=forms.TextInput(attrs={'placeholder': 'Ex: Perdida, danificada, etc.'})
    )