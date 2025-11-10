from django.contrib import admin
from .models import Movimento, Cartela, Distribuicao, Acerto

@admin.register(Movimento)
class MovimentoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'responsavel', 'telefone')
    search_fields = ('nome', 'responsavel')

@admin.register(Cartela)
class CartelaAdmin(admin.ModelAdmin):
    list_display = ('numero', 'status', 'movimento')
    list_filter = ('status', 'movimento')
    search_fields = ('numero',)

@admin.register(Distribuicao)
class DistribuicaoAdmin(admin.ModelAdmin):
    list_display = ('movimento', 'quantidade', 'data_distribuicao')
    list_filter = ('movimento',)

# Esta é a versão correta e única para o AcertoAdmin
@admin.register(Acerto)
class AcertoAdmin(admin.ModelAdmin):
    list_display = ('id', 'movimento', 'membro_pastoral', 'data', 'valor_total', 'valor_recebido')
    list_filter = ('movimento', 'data', 'tipo_pagamento')
    search_fields = ('movimento__nome', 'membro_pastoral')
    date_hierarchy = 'data'