from django.db import models
from django.utils import timezone

class Movimento(models.Model):
    nome = models.CharField(max_length=100)  # Ex: "Pastoral Familiar"
    responsavel = models.CharField(max_length=100)
    telefone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.nome

class Cartela(models.Model):
    STATUS_CHOICES = [
        ('DISPONIVEL', 'Disponível'),      # No estoque geral
        ('DISTRIBUIDA', 'Distribuída'),     # Com um movimento
        ('ACERTADA', 'Acertada'),           # Pagamento confirmado
        ('DEVOLVIDA', 'Devolvida'),         # Retornou ao estoque
        ('CORTESIA', 'Cortesia'),           # Entregue como cortesia
        ('CANCELADA', 'Cancelada'),
                  
    ]
    numero = models.CharField(max_length=6, unique=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='DISPONIVEL')
    movimento = models.ForeignKey(Movimento, on_delete=models.SET_NULL, null=True, blank=True, related_name='cartelas')
    data_distribuicao = models.DateField(null=True, blank=True)
    data_acerto = models.DateField(null=True, blank=True)
    # REMOVIDO: cortesia = models.BooleanField(default=False)
    # REMOVIDO: devolvida = models.BooleanField(default=False)


    def __str__(self):
        return f"Cartela {self.numero} ({self.get_status_display()})"
    
class Acerto(models.Model):
    TIPO_PAGAMENTO = [
        ('DINHEIRO', 'Dinheiro'),
        ('PIX', 'PIX'),
        ('CARTAO_CREDITO', 'Cartão de Crédito'),
        ('CARTAO_DEBITO', 'Cartão de Débito'),
        ('PREFEITURA', 'Prefeitura'),
        ('DESCONTO_SERVICO', 'Desconto em Serviços'),
    ]
    
    movimento = models.ForeignKey(Movimento, on_delete=models.PROTECT, related_name='acertos')
    data = models.DateTimeField(auto_now_add=True)
    
    # Campo para o nome do membro
    membro_pastoral = models.CharField(max_length=100, blank=True, null=True, verbose_name="Acertado por")
    
    valor_total = models.DecimalField(max_digits=10, decimal_places=2)
    valor_recebido = models.DecimalField(max_digits=10, decimal_places=2)
    tipo_pagamento = models.CharField(max_length=20, choices=TIPO_PAGAMENTO)
    
    # Campo de observações
    observacoes = models.TextField(blank=True, null=True)

    # Relações com as cartelas
    cartelas_vendidas = models.ManyToManyField('Cartela', related_name='acerto_venda', blank=True)
    cartelas_devolvidas = models.ManyToManyField('Cartela', related_name='acerto_devolucao', blank=True)
    cartelas_cortesia = models.ManyToManyField('Cartela', related_name='acerto_cortesia', blank=True)

    def __str__(self):
        return f"Acerto de {self.movimento.nome} em {self.data.strftime('%d/%m/%Y')}"

class Distribuicao(models.Model):
    movimento = models.ForeignKey(Movimento, on_delete=models.PROTECT, related_name='distribuicoes')
    data_distribuicao = models.DateTimeField(auto_now_add=True)
    quantidade = models.PositiveIntegerField()
    # Este campo é a chave: ele armazena quais cartelas saíram neste lote.
    cartelas = models.ManyToManyField(Cartela, related_name='distribuicoes')
    membro_responsavel = models.CharField(max_length=100, blank=True, null=True, verbose_name="Membro Responsável")
    
    def __str__(self):
        return f"Distribuição de {self.quantidade} cartelas para {self.movimento.nome} em {self.data_distribuicao.strftime('%d/%m/%Y')}"
    
class LogCancelamento(models.Model):
    cartela = models.OneToOneField(Cartela, on_delete=models.CASCADE, related_name='log_cancelamento')
    motivo = models.TextField(verbose_name="Motivo do Cancelamento")
    data_cancelamento = models.DateTimeField(auto_now_add=True)
    status_anterior = models.CharField(max_length=20, null=True, blank=True)
    movimento_anterior = models.ForeignKey('Movimento', on_delete=models.SET_NULL, null=True, blank=True)
    #usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True) # Para auditar quem cancelou

    def __str__(self):
        return f"Cancelamento da cartela {self.cartela.numero}"